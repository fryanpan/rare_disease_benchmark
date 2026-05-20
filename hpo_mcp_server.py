#!/usr/bin/env python3
"""
HPO (Human Phenotype Ontology) MCP Server for rare disease diagnosis.

Provides phenotype→Orphanet disease mapping as MCP tools.
pyhpo ships with Orphanet annotations so no external API calls needed.

Setup: uv add pyhpo (one-time; downloads HPO annotation data ~50MB)
Usage: uv run python hpo_mcp_server.py

Tools exposed:
- search_hpo_terms(query): Find HPO terms matching a symptom description
- lookup_diseases_by_phenotypes(hpo_terms): Find Orphanet diseases matching a phenotype set
- get_disease_phenotypes(orpha_id): Get HPO phenotypes for a specific disease
- phenotype_differential_diagnosis(symptoms): Full pipeline: symptoms → top disease candidates
"""

import json
import socket
import sys
from typing import Any

# Force IPv4 — NLM Clinical Tables' IPv6 path is unreachable from some networks
# and urllib does not Happy-Eyeballs fail over, causing multi-minute SYN hangs.
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4_only_getaddrinfo

# MCP server imports
from mcp.server.fastmcp import FastMCP

# HPO library — loads Orphanet annotation data on first import
try:
    import pyhpo
    pyhpo.Ontology()
    _HPO_LOADED = True
except ImportError:
    _HPO_LOADED = False
    print("ERROR: pyhpo not installed. Run: uv add pyhpo", file=sys.stderr)
    sys.exit(1)

# NLM Clinical Tables API (for fuzzy symptom → HPO term lookup)
import urllib.parse
import urllib.request


mcp = FastMCP("hpo-disease-mapper")


# ── HPO term search ───────────────────────────────────────────────────────────

@mcp.tool()
def search_hpo_terms(query: str, max_results: int = 10) -> str:
    """
    Search for HPO (Human Phenotype Ontology) terms matching a symptom or clinical feature.

    Use this to standardize free-text symptoms to HPO codes before disease lookup.
    Example: "muscle weakness" → HP:0001324 (Muscle weakness)

    Args:
        query: Free-text symptom description (e.g., "fatigue", "abnormal EEG", "hepatomegaly")
        max_results: Maximum number of HPO terms to return (default: 10)

    Returns:
        JSON list of matching HPO terms with code and name.
    """
    url = (
        f"https://clinicaltables.nlm.nih.gov/api/hpo/v3/search"
        f"?terms={urllib.parse.quote(query)}&maxList={max_results}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "hpo-mcp-server/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return json.dumps({"error": str(e)})

    # data[1] = list of HP codes; data[3] = list of [code, name] rows
    results = []
    if data[1] and len(data) > 3 and data[3]:
        for row in data[3][:max_results]:
            if len(row) >= 2:
                results.append({"code": row[0], "name": row[1]})

    return json.dumps(results, indent=2)


# ── Disease lookup ────────────────────────────────────────────────────────────

@mcp.tool()
def lookup_diseases_by_phenotypes(
    hpo_codes: list[str],
    top_n: int = 20,
    min_matching: int = 1,
) -> str:
    """
    Find Orphanet rare diseases that share given HPO phenotype codes.

    The more HPO codes you provide, the more specific the results.
    Results are ranked by number of matching phenotypes (most specific diseases first).

    Args:
        hpo_codes: List of HPO codes (e.g., ["HP:0001324", "HP:0003236"]).
                   Use search_hpo_terms() first if you have free-text symptoms.
        top_n: Return top N diseases (default: 20)
        min_matching: Only include diseases with at least this many matching phenotypes (default: 1)

    Returns:
        JSON list of Orphanet diseases ranked by phenotype match count.
        Each entry: {orpha_id, name, matching_phenotypes, total_phenotypes, match_ratio}
    """
    # Resolve HPO codes to pyhpo term objects
    matched_terms = []
    for code in hpo_codes:
        try:
            term = pyhpo.Ontology.get_hpo_object(code)
            matched_terms.append(term)
        except Exception:
            pass

    if not matched_terms:
        return json.dumps({"error": "No valid HPO codes found", "input": hpo_codes})

    # Count disease overlaps
    disease_hit_counts: dict[int, int] = {}
    for term in matched_terms:
        for disease in term.orpha_diseases:
            disease_hit_counts[disease.id] = disease_hit_counts.get(disease.id, 0) + 1

    # Build result set
    id_to_disease = {d.id: d for d in pyhpo.Ontology.orpha_diseases}
    results = []
    for orpha_id, hits in disease_hit_counts.items():
        if hits < min_matching:
            continue
        disease = id_to_disease.get(orpha_id)
        if disease is None:
            continue
        total = len(disease.hpo)
        results.append({
            "orpha_id": f"ORPHA:{orpha_id}",
            "name": disease.name,
            "matching_phenotypes": hits,
            "total_phenotypes": total,
            "match_ratio": round(hits / total, 3) if total else 0,
        })

    # Sort by (hits, match_ratio) descending — prioritize highly specific matches
    results.sort(key=lambda x: (x["matching_phenotypes"], x["match_ratio"]), reverse=True)
    return json.dumps(results[:top_n], indent=2)


@mcp.tool()
def get_disease_phenotypes(orpha_id: str) -> str:
    """
    Get the complete HPO phenotype list for a specific Orphanet disease.

    Useful for comparing a patient's presentation against a candidate disease's
    expected phenotypes.

    Args:
        orpha_id: Orphanet ID as integer or "ORPHA:XXXXX" string (e.g., "ORPHA:50" or "50")

    Returns:
        JSON with disease name and list of associated HPO phenotypes.
    """
    # Normalize ID
    raw = str(orpha_id).replace("ORPHA:", "").replace("Orpha:", "").strip()
    try:
        oid = int(raw)
    except ValueError:
        return json.dumps({"error": f"Invalid Orphanet ID: {orpha_id}"})

    id_to_disease = {d.id: d for d in pyhpo.Ontology.orpha_diseases}
    disease = id_to_disease.get(oid)
    if disease is None:
        return json.dumps({"error": f"Orphanet disease {orpha_id} not found in pyhpo data"})

    phenotypes = []
    for term in disease.hpo:
        try:
            t = pyhpo.Ontology.get_hpo_object(term.id)
            phenotypes.append({"code": str(t.id), "name": t.name})
        except Exception:
            phenotypes.append({"code": str(term.id), "name": str(term)})

    return json.dumps({
        "orpha_id": f"ORPHA:{oid}",
        "name": disease.name,
        "phenotype_count": len(phenotypes),
        "phenotypes": phenotypes,
    }, indent=2)


@mcp.tool()
def phenotype_differential_diagnosis(
    symptom_descriptions: list[str],
    top_n: int = 20,
) -> str:
    """
    Full diagnostic pipeline: free-text symptoms → top Orphanet rare disease candidates.

    This is the primary diagnostic tool. Given a list of clinical features in plain text,
    it:
    1. Maps each symptom to the best matching HPO term (using NLM Clinical Tables API)
    2. Looks up Orphanet diseases associated with those HPO phenotypes
    3. Returns diseases ranked by how many of the patient's phenotypes they explain

    Args:
        symptom_descriptions: List of clinical features from the case report.
            Extract key symptoms, signs, and lab findings.
            Example: ["muscle weakness", "elevated CK", "cardiomyopathy", "ptosis"]
        top_n: Number of top candidate diseases to return (default: 20)

    Returns:
        JSON with:
        - resolved_hpo: Which symptoms were mapped to HPO codes
        - unmapped: Symptoms that couldn't be mapped (try more specific terms)
        - candidates: Top N Orphanet diseases ranked by phenotype overlap
    """
    # Step 1: Map each symptom to best HPO term
    resolved = []
    unmapped = []
    hpo_codes = []

    for symptom in symptom_descriptions:
        url = (
            f"https://clinicaltables.nlm.nih.gov/api/hpo/v3/search"
            f"?terms={urllib.parse.quote(symptom)}&maxList=1"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "hpo-mcp-server/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            if data[1] and len(data) > 3 and data[3]:
                code, name = data[3][0][0], data[3][0][1]
                resolved.append({"symptom": symptom, "hpo_code": code, "hpo_name": name})
                hpo_codes.append(code)
            else:
                unmapped.append(symptom)
        except Exception:
            unmapped.append(symptom)

    if not hpo_codes:
        return json.dumps({
            "error": "No symptoms could be mapped to HPO terms",
            "unmapped": unmapped,
        })

    # Step 2: Find matching diseases
    candidates_json = lookup_diseases_by_phenotypes(hpo_codes, top_n=top_n)
    candidates = json.loads(candidates_json)

    return json.dumps({
        "resolved_hpo": resolved,
        "unmapped": unmapped,
        "hpo_codes_used": hpo_codes,
        "candidates": candidates if isinstance(candidates, list) else [],
    }, indent=2)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
