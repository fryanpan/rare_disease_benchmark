#!/usr/bin/env python3
"""
Phase 2 of audit: a minimal PubMed MCP server that mirrors @cyanheads/pubmed-mcp-server's
interface for the two tools the agent uses (search + fetch), with optional filtering
of a single blocked PMCID set via the BLOCK_PMCID env var.

Exposes:
  pubmed_search_articles(query, maxResults, summaryCount) -> articles list (with PMCID filter)
  pubmed_fetch_articles(pmids) -> per-article details (with PMCID filter)

The blocked PMCID is the digits part of the RareArena case _id (the case _id format is
"{pmcid}-{n}" — we filter out any returned record whose PMCID matches that digits part).

Configured via env:
  BLOCK_PMCID         Comma-separated list of PMCIDs to block (digits only, no "PMC" prefix)
  NCBI_API_KEY        Optional NCBI E-utilities API key for higher rate limits

Run as an MCP server over stdio: `uv run --no-project python audit_filtered_pubmed_mcp.py`
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP


BLOCKED_PMCIDS: set[str] = {
    p.strip().lstrip("PMC").lstrip("pmc")
    for p in (os.environ.get("BLOCK_PMCID") or "").split(",")
    if p.strip()
}
NCBI_API_KEY = os.environ.get("NCBI_API_KEY", "")
EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Audit log for what got filtered (so we have ground-truth on filter activity)
AUDIT_LOG_PATH = os.environ.get("AUDIT_FILTER_LOG") or ""


def _audit_log(event: str, payload: dict[str, Any]) -> None:
    if not AUDIT_LOG_PATH:
        return
    try:
        with open(AUDIT_LOG_PATH, "a") as f:
            f.write(json.dumps({"event": event, **payload}, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[filter mcp] audit-log error: {e}", file=sys.stderr)


def _fetch(path: str, params: dict[str, str]) -> bytes:
    p = dict(params)
    if NCBI_API_KEY:
        p["api_key"] = NCBI_API_KEY
    p["tool"] = "rare-disease-benchmark-audit"
    p["email"] = "fryanpan@gmail.com"
    url = f"{EUTILS_BASE}/{path}?{urllib.parse.urlencode(p)}"
    req = urllib.request.Request(url, headers={"User-Agent": "rdb-audit/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


server = FastMCP("filtered-pubmed")


def _pmcid_blocked(pmcid: str | None) -> bool:
    if not pmcid:
        return False
    return pmcid.lstrip("PMC").lstrip("pmc") in BLOCKED_PMCIDS


@server.tool()
def pubmed_search_articles(query: str, maxResults: int = 10, summaryCount: int = 10) -> str:
    """
    Search PubMed for articles matching the query. Returns a JSON object with
    `{query, effectiveQuery, count, articles: [...]}`. The articles list contains
    title, abstract, authors, journal, pubDate, pmid, pmcid, and doi for each hit.

    BLOCKED PMCIDs (set via env var) are removed from the results before return
    and logged to the audit-filter log.
    """
    # esearch
    try:
        es = _fetch("esearch.fcgi", {
            "db": "pubmed",
            "term": query,
            "retmax": str(max(1, min(maxResults, 50))),
            "retmode": "json",
        })
        es_data = json.loads(es)
        pmids = es_data.get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        return json.dumps({"query": query, "error": f"esearch failed: {e}"})

    if not pmids:
        return json.dumps({
            "query": query,
            "effectiveQuery": query,
            "count": 0,
            "articles": [],
        })

    # esummary on first summaryCount
    pmids_for_summary = pmids[: max(1, summaryCount)]
    try:
        sm = _fetch("esummary.fcgi", {
            "db": "pubmed",
            "id": ",".join(pmids_for_summary),
            "retmode": "json",
        })
        sm_data = json.loads(sm)
    except Exception as e:
        return json.dumps({"query": query, "error": f"esummary failed: {e}", "pmids": pmids})

    result_objs = sm_data.get("result", {})
    uids = result_objs.get("uids", pmids_for_summary)

    articles_out = []
    filtered_count = 0
    for pmid in uids:
        d = result_objs.get(pmid, {})
        if not d:
            continue
        # Find PMCID from articleids
        pmcid_val = None
        for aid in d.get("articleids", []):
            if aid.get("idtype") == "pmc":
                pmcid_val = aid.get("value", "").lstrip("PMC").lstrip("pmc")
                break
        if _pmcid_blocked(pmcid_val):
            filtered_count += 1
            _audit_log("filter.search", {
                "query": query,
                "blocked_pmcid": pmcid_val,
                "title": d.get("title", ""),
                "pmid": pmid,
            })
            continue
        articles_out.append({
            "pmid": pmid,
            "pmcid": pmcid_val,
            "title": d.get("title", ""),
            "authors": "; ".join([a.get("name", "") for a in d.get("authors", [])[:5]]),
            "journal": d.get("source", ""),
            "pubDate": d.get("pubdate", ""),
            "doi": next(
                (aid.get("value", "") for aid in d.get("articleids", []) if aid.get("idtype") == "doi"),
                "",
            ),
        })

    return json.dumps({
        "query": query,
        "effectiveQuery": query,
        "count": len(articles_out),
        "filtered_due_to_block": filtered_count,
        "articles": articles_out,
    })


@server.tool()
def pubmed_fetch_articles(pmids: list[str] | str) -> str:
    """
    Fetch full abstract + metadata for one or more PMIDs (or PMCIDs).
    BLOCKED PMCIDs return a "blocked" stub instead of content.
    """
    if isinstance(pmids, str):
        pmids_list = [p.strip() for p in pmids.replace(",", " ").split() if p.strip()]
    else:
        pmids_list = [str(p).strip() for p in pmids if p]

    if not pmids_list:
        return json.dumps({"articles": []})

    # Map any pmid to its pmcid via esummary first so we can filter
    try:
        sm = _fetch("esummary.fcgi", {
            "db": "pubmed",
            "id": ",".join(pmids_list),
            "retmode": "json",
        })
        sm_data = json.loads(sm).get("result", {})
    except Exception as e:
        return json.dumps({"error": f"esummary failed: {e}"})

    out_articles = []
    fetch_pmids = []
    for pmid in pmids_list:
        d = sm_data.get(pmid, {})
        pmcid_val = None
        for aid in d.get("articleids", []):
            if aid.get("idtype") == "pmc":
                pmcid_val = aid.get("value", "").lstrip("PMC").lstrip("pmc")
                break
        if _pmcid_blocked(pmcid_val):
            _audit_log("filter.fetch", {
                "pmid": pmid,
                "blocked_pmcid": pmcid_val,
                "title": d.get("title", ""),
            })
            out_articles.append({
                "pmid": pmid,
                "pmcid": pmcid_val,
                "status": "blocked_by_audit_filter",
                "title": "[redacted: paper retrieval blocked by benchmark audit filter]",
            })
            continue
        fetch_pmids.append(pmid)

    if fetch_pmids:
        try:
            efetch = _fetch("efetch.fcgi", {
                "db": "pubmed",
                "id": ",".join(fetch_pmids),
                "rettype": "abstract",
                "retmode": "text",
            }).decode("utf-8", errors="replace")
        except Exception as e:
            efetch = f"[efetch failed: {e}]"
        # We won't try to parse out individual abstracts — return one combined text
        # alongside the summary metadata.
        for pmid in fetch_pmids:
            d = sm_data.get(pmid, {})
            pmcid_val = None
            for aid in d.get("articleids", []):
                if aid.get("idtype") == "pmc":
                    pmcid_val = aid.get("value", "").lstrip("PMC").lstrip("pmc")
                    break
            out_articles.append({
                "pmid": pmid,
                "pmcid": pmcid_val,
                "title": d.get("title", ""),
                "journal": d.get("source", ""),
                "pubDate": d.get("pubdate", ""),
                "abstract_or_text": efetch[:8000],  # combined; agent gets shared text
            })

    return json.dumps({"articles": out_articles})


if __name__ == "__main__":
    # MCP stdio server
    print(f"[filter mcp] startup. BLOCKED={sorted(BLOCKED_PMCIDS) or 'none'}", file=sys.stderr)
    server.run()
