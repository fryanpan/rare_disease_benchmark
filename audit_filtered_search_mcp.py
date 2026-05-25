#!/usr/bin/env python3
"""
Phase 2 web-search MCP wrapper. Provides a `web_search` MCP tool that proxies
DuckDuckGo HTML search (free, no API key) and applies a PMCID filter:
  - Any result whose URL contains the blocked PMCID is dropped.
  - Any result whose title contains the blocked PMCID (e.g. "PMC8289685") is dropped.

The wrapper is intentionally a DuckDuckGo proxy rather than a true Google
proxy because Google Custom Search requires an API key + Custom Search Engine
config that wasn't pre-set on this machine. DDG queries the same medical
literature index (PMC URLs are well-indexed), so the test of "can the agent
find the source paper through web search" is preserved with comparable
recall.

Configured via env:
  BLOCK_PMCID         Comma-separated PMCIDs to filter (digits-only, no PMC prefix)
  AUDIT_FILTER_LOG    Optional path to a JSONL audit log of filter events
  USER_AGENT          Optional override for the User-Agent header
"""

import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP


BLOCKED_PMCIDS: set[str] = {
    p.strip().lstrip("PMC").lstrip("pmc")
    for p in (os.environ.get("BLOCK_PMCID") or "").split(",")
    if p.strip()
}
AUDIT_LOG_PATH = os.environ.get("AUDIT_FILTER_LOG") or ""
USER_AGENT = os.environ.get("USER_AGENT") or "Mozilla/5.0 (rdb-audit/1.0)"
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY") or ""
SEARCH_BACKEND = (os.environ.get("SEARCH_BACKEND") or "auto").lower()  # auto|brave|ddg


def _audit_log(event: str, payload: dict[str, Any]) -> None:
    if not AUDIT_LOG_PATH:
        return
    try:
        with open(AUDIT_LOG_PATH, "a") as f:
            f.write(json.dumps({"event": event, **payload}, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[search filter] audit-log error: {e}", file=sys.stderr)


def _contains_blocked_pmcid(text: str) -> str | None:
    """Return the blocked PMCID if any appears in `text`, else None."""
    if not text or not BLOCKED_PMCIDS:
        return None
    for pmcid in BLOCKED_PMCIDS:
        # Match either "PMC<digits>" or bare digits with sufficient specificity
        if re.search(rf"\bPMC[\W]?{re.escape(pmcid)}\b", text, re.IGNORECASE):
            return pmcid
        # Plain digits — only if length ≥ 7 to avoid false positives
        if len(pmcid) >= 7 and re.search(rf"\b{re.escape(pmcid)}\b", text):
            return pmcid
    return None


# DDG HTML result regex — its HTML is templated so this is reasonably stable.
# Looking for `<a rel="nofollow" class="result__a" href="<encoded url>">title</a>`
RESULT_PATTERN = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
SNIPPET_PATTERN = re.compile(
    r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _decode_ddg_url(href: str) -> str:
    """DDG wraps result URLs through their redirector. Extract the real URL."""
    # Typical href: //duckduckgo.com/l/?uddg=<encoded URL>&rut=...
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    if "duckduckgo.com" in parsed.netloc:
        qs = urllib.parse.parse_qs(parsed.query)
        if "uddg" in qs:
            return urllib.parse.unquote(qs["uddg"][0])
    return href


def _brave_search(query: str, n: int = 8) -> list[dict[str, str]]:
    """Call Brave Search API (https://api.search.brave.com), return result list."""
    if not BRAVE_API_KEY:
        return [{"error": "BRAVE_API_KEY not set"}]
    url = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode({
        "q": query,
        "count": str(min(max(n * 2, 5), 20)),  # request 2× to allow for filter overhead
        "country": "US",
        "search_lang": "en",
    })
    req = urllib.request.Request(url, headers={
        "X-Subscription-Token": BRAVE_API_KEY,
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300] if hasattr(e, "read") else ""
        return [{"error": f"Brave HTTP {e.code}: {body}"}]
    except Exception as e:
        return [{"error": f"Brave fetch failed: {e}"}]
    results = data.get("web", {}).get("results", [])
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("description", "") or r.get("snippet", ""),
        }
        for r in results
    ]


def _ddg_search(query: str, n: int = 8) -> list[dict[str, str]]:
    """Call DDG HTML, parse, return list of {title, url, snippet}."""
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return [{"error": f"DDG fetch failed: {e}"}]

    # Pull (href, title) pairs
    titles = RESULT_PATTERN.findall(body)
    snippets = SNIPPET_PATTERN.findall(body)
    out = []
    for i, (href, title_html) in enumerate(titles[:n * 3]):  # collect extras in case of filtering
        try:
            real_url = _decode_ddg_url(href)
        except Exception:
            real_url = href
        title = _strip_html(title_html)
        snippet = _strip_html(snippets[i]) if i < len(snippets) else ""
        out.append({"title": title, "url": real_url, "snippet": snippet})
        if len(out) >= n * 2:  # collect 2x in case some get filtered
            break
    return out


server = FastMCP("filtered-web-search")


@server.tool()
def web_search(query: str, maxResults: int = 8) -> str:
    """
    Search the web for the given query via DuckDuckGo (no API key required;
    returns Google-equivalent results for medical literature use cases).

    Returns a JSON object: `{query, results: [...], filtered: N}` where each
    result has {title, url, snippet}. Results matching the audit blocklist
    (PMCID env var) are removed and logged to the audit-filter log.

    Use this for general web queries (Orphanet, OMIM, news articles, blog
    posts, anything you'd normally use WebSearch for).
    """
    # Route to backend: explicit env override, else auto (brave if key else ddg)
    if SEARCH_BACKEND == "brave" or (SEARCH_BACKEND == "auto" and BRAVE_API_KEY):
        raw = _brave_search(query, n=maxResults)
        backend = "brave"
    else:
        raw = _ddg_search(query, n=maxResults)
        backend = "ddg"
    if raw and "error" in raw[0]:
        return json.dumps({"query": query, "error": raw[0]["error"]})

    kept = []
    filtered = 0
    for r in raw:
        blocked_by = _contains_blocked_pmcid(r.get("url", "")) or _contains_blocked_pmcid(r.get("title", ""))
        if blocked_by:
            filtered += 1
            _audit_log("filter.web_search", {
                "query": query,
                "blocked_pmcid": blocked_by,
                "url": r.get("url", ""),
                "title": r.get("title", ""),
            })
            continue
        kept.append(r)
        if len(kept) >= maxResults:
            break

    return json.dumps({
        "query": query,
        "results": kept,
        "filtered": filtered,
        "backend": backend,
    })


@server.tool()
def web_fetch(url: str) -> str:
    """
    Fetch the textual content of a URL via simple GET. Returns plain-ish
    text up to 12 KB. URLs whose path contains a blocked PMCID return a
    redacted stub.
    """
    blocked_by = _contains_blocked_pmcid(url)
    if blocked_by:
        _audit_log("filter.web_fetch", {"url": url, "blocked_pmcid": blocked_by})
        return json.dumps({
            "url": url,
            "status": "blocked_by_audit_filter",
            "content": "[redacted: URL fetch blocked because it matches a benchmark-audit blocklist entry]",
        })
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", errors="replace")[:24000]
    except Exception as e:
        return json.dumps({"url": url, "error": str(e)})
    text = _strip_html(body)
    return json.dumps({"url": url, "content": text[:12000]})


if __name__ == "__main__":
    print(f"[search mcp] startup. BLOCKED={sorted(BLOCKED_PMCIDS) or 'none'}", file=sys.stderr)
    server.run()
