from __future__ import annotations

import ast
import csv
import io
import ipaddress
import json
import math
import re
import socket
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.util import find_spec
from typing import Any
from urllib.parse import quote, urlparse

import httpx
from pydantic import BaseModel

from shared.config import get_settings

HTTP_HEADERS = {
    "User-Agent": "Agent-Marketplace/0.1 research-tool",
}
URL_RE = re.compile(r"https?://[^\s<>'\"]+", re.IGNORECASE)


class BuiltInTool(BaseModel):
    id: str
    name: str
    description: str
    enabled: bool = True
    requires_platform_key: bool = False


@dataclass(slots=True)
class ToolRunResult:
    context: str
    citations: list[dict[str, str]]
    tool_outputs: list[dict[str, Any]]


def list_builtin_tools() -> list[BuiltInTool]:
    settings = get_settings()
    return [
        BuiltInTool(
            id="web_search",
            name="Web Search",
            description="Fast privacy-focused web lookup via DuckDuckGo instant answers.",
            enabled=True,
        ),
        BuiltInTool(
            id="tavily_search",
            name="Tavily Search",
            description="Deep web search with ranked sources and synthesized answer.",
            enabled=bool(settings.tavily_api_key),
            requires_platform_key=True,
        ),
        BuiltInTool(
            id="yutori_research",
            name="Yutori Research",
            description="Uses the platform Yutori key to run a managed web research task.",
            enabled=bool(settings.yutori_api_key),
            requires_platform_key=True,
        ),
        BuiltInTool(
            id="wikipedia_summary",
            name="Wikipedia Summary",
            description="Fetches concise summaries from Wikipedia pages.",
            enabled=True,
        ),
        BuiltInTool(
            id="arxiv_search",
            name="arXiv Search",
            description="Searches arXiv for relevant academic papers.",
            enabled=True,
        ),
        BuiltInTool(
            id="crossref_lookup",
            name="Crossref Lookup",
            description="Looks up DOI-indexed scholarly publications.",
            enabled=True,
        ),
        BuiltInTool(
            id="semantic_scholar_search",
            name="Semantic Scholar Search",
            description="Finds academic papers with citation metadata.",
            enabled=True,
        ),
        BuiltInTool(
            id="openalex_search",
            name="OpenAlex Search",
            description="Searches OpenAlex corpus for research outputs.",
            enabled=True,
        ),
        BuiltInTool(
            id="sec_edgar_filings",
            name="SEC Edgar Filings",
            description="Retrieves recent SEC filings for matched companies.",
            enabled=True,
        ),
        BuiltInTool(
            id="company_ticker_lookup",
            name="Company Ticker Lookup",
            description="Maps company names/tickers to SEC CIK records.",
            enabled=True,
        ),
        BuiltInTool(
            id="world_bank_indicators",
            name="World Bank Indicators",
            description="Gets country-level macroeconomic indicator series.",
            enabled=True,
        ),
        BuiltInTool(
            id="open_meteo_weather",
            name="Open-Meteo Weather",
            description="Live weather and short-range forecast context.",
            enabled=True,
        ),
        BuiltInTool(
            id="nominatim_geocode",
            name="Nominatim Geocode",
            description="Geocodes place names into coordinates and location metadata.",
            enabled=True,
        ),
        BuiltInTool(
            id="timezone_lookup",
            name="Timezone Lookup",
            description="Resolves current time and timezone context for locations.",
            enabled=True,
        ),
        BuiltInTool(
            id="github_repo_inspector",
            name="GitHub Repo Inspector",
            description="Inspects repository metadata, health, and activity.",
            enabled=True,
        ),
        BuiltInTool(
            id="hacker_news_search",
            name="Hacker News Search",
            description="Searches stories from Hacker News via Algolia index.",
            enabled=True,
        ),
        BuiltInTool(
            id="rss_reader",
            name="RSS Reader",
            description="Reads and summarizes RSS/Atom feeds from public URLs.",
            enabled=True,
        ),
        BuiltInTool(
            id="changelog_reader",
            name="Changelog Reader",
            description="Reads GitHub releases or changelog feeds.",
            enabled=True,
        ),
        BuiltInTool(
            id="gdelt_news_search",
            name="GDELT News Search",
            description="Monitors recent global news coverage from GDELT.",
            enabled=True,
        ),
        BuiltInTool(
            id="mediastack_news",
            name="Mediastack News",
            description="Searches news coverage via Mediastack API.",
            enabled=bool(settings.mediastack_api_key),
            requires_platform_key=True,
        ),
        BuiltInTool(
            id="newsapi_dev",
            name="NewsAPI",
            description="Searches recent news with NewsAPI.",
            enabled=bool(settings.newsapi_api_key),
            requires_platform_key=True,
        ),
        BuiltInTool(
            id="page_reader",
            name="Page Reader",
            description="Fetches and extracts readable text from public web pages.",
            enabled=True,
        ),
        BuiltInTool(
            id="pdf_reader",
            name="PDF Reader",
            description="Downloads and extracts text from public PDFs.",
            enabled=find_spec("pypdf") is not None,
        ),
        BuiltInTool(
            id="csv_analyzer",
            name="CSV Analyzer",
            description="Analyzes CSV data from URL or inline content.",
            enabled=True,
        ),
        BuiltInTool(
            id="json_api_fetcher",
            name="JSON API Fetcher",
            description="Fetches public JSON APIs and returns structured previews.",
            enabled=True,
        ),
        BuiltInTool(
            id="calculator",
            name="Calculator",
            description="Evaluates arithmetic expressions safely.",
            enabled=True,
        ),
        BuiltInTool(
            id="date_time_tool",
            name="Date Time Tool",
            description="Returns current UTC date and time context.",
            enabled=True,
        ),
    ]


def enabled_tool_ids() -> set[str]:
    return {tool.id for tool in list_builtin_tools() if tool.enabled}


def _truncate(value: str, limit: int = 1200) -> str:
    return value if len(value) <= limit else f"{value[:limit].rstrip()}..."


def _clean_query(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


def _extract_url(query: str) -> str | None:
    match = URL_RE.search(query)
    if not match:
        return None
    return match.group(0).rstrip(".,);]")


def _is_private_host(host: str) -> bool:
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        pass
    try:
        addresses = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False
    for address in addresses:
        ip_text = address[4][0]
        try:
            ip = ipaddress.ip_address(ip_text)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False


def _safe_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only public http/https URLs are supported.")
    if _is_private_host(parsed.hostname):
        raise ValueError("Private or local URLs are not allowed.")
    return url


def _citation(title: str, url: str, snippet: str) -> dict[str, str]:
    return {
        "title": _truncate(title, 160),
        "url": url,
        "snippet": _truncate(snippet, 300),
    }


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    return re.sub(r"\s+", " ", text).strip()


def _run_web_search(query: str) -> dict[str, Any]:
    response = httpx.get(
        "https://api.duckduckgo.com/",
        params={
            "q": query,
            "format": "json",
            "no_redirect": 1,
            "no_html": 1,
        },
        headers=HTTP_HEADERS,
        timeout=8,
    )
    response.raise_for_status()
    data = response.json()

    lines: list[str] = []
    citations: list[dict[str, str]] = []

    abstract = data.get("AbstractText")
    abstract_url = data.get("AbstractURL")
    if abstract:
        title = data.get("AbstractTitle") or query
        lines.append(f"{title}: {abstract}")
        if abstract_url:
            citations.append(_citation(str(title), str(abstract_url), str(abstract)))

    related_topics = data.get("RelatedTopics") or []
    for item in related_topics[:5]:
        if not isinstance(item, dict):
            continue
        text = item.get("Text")
        if not text:
            continue
        lines.append(str(text))
        first_url = item.get("FirstURL")
        if first_url:
            citations.append(_citation(str(text).split(" - ")[0], str(first_url), str(text)))

    return {
        "tool": "web_search",
        "context": "\n".join(lines) if lines else f"No web search results found for: {query}",
        "citations": citations,
        "raw": {"source": "duckduckgo_instant_answer"},
    }


def _run_tavily_search(query: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured.")

    response = httpx.post(
        "https://api.tavily.com/search",
        headers={
            "Authorization": f"Bearer {settings.tavily_api_key.get_secret_value()}",
            "Content-Type": "application/json",
            **HTTP_HEADERS,
        },
        json={
            "query": query,
            "search_depth": "advanced",
            "include_answer": True,
            "include_raw_content": False,
            "max_results": 5,
        },
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()

    lines: list[str] = []
    citations: list[dict[str, str]] = []
    answer = data.get("answer")
    if answer:
        lines.append(f"Tavily answer: {answer}")

    for result in data.get("results") or []:
        if not isinstance(result, dict):
            continue
        title = str(result.get("title") or result.get("url") or "Tavily result")
        url = str(result.get("url") or "")
        content = str(result.get("content") or "")
        if content:
            lines.append(f"{title}: {content}")
        if url:
            citations.append(_citation(title, url, content))

    return {
        "tool": "tavily_search",
        "context": "\n".join(lines) if lines else f"No Tavily results found for: {query}",
        "citations": citations,
        "raw": {"query": data.get("query"), "result_count": len(data.get("results") or [])},
    }


def _run_yutori_research(query: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.yutori_api_key:
        raise RuntimeError("YUTORI_API_KEY is not configured.")

    headers = {
        "X-API-Key": settings.yutori_api_key.get_secret_value(),
        "Content-Type": "application/json",
        **HTTP_HEADERS,
    }
    create_response = httpx.post(
        "https://api.yutori.com/v1/research/tasks",
        headers=headers,
        json={
            "query": query,
            "mode": "fast",
            "skip_email": True,
        },
        timeout=20,
    )
    create_response.raise_for_status()
    created = create_response.json()
    task_id = created.get("task_id")
    if not task_id:
        raise RuntimeError("Yutori did not return a task_id.")

    deadline = time.monotonic() + settings.yutori_poll_timeout_seconds
    latest: dict[str, Any] = dict(created)
    while time.monotonic() < deadline:
        status_response = httpx.get(
            f"https://api.yutori.com/v1/research/tasks/{task_id}",
            headers={"X-API-Key": settings.yutori_api_key.get_secret_value(), **HTTP_HEADERS},
            timeout=20,
        )
        status_response.raise_for_status()
        latest = status_response.json()
        if latest.get("status") in {"succeeded", "failed"}:
            break
        time.sleep(settings.yutori_poll_interval_seconds)

    result = latest.get("result")
    updates = latest.get("updates") or []
    citations: list[dict[str, str]] = []
    for update in updates:
        if not isinstance(update, dict):
            continue
        for citation in update.get("citations") or []:
            if not isinstance(citation, dict):
                continue
            url = citation.get("url")
            if url:
                citations.append(_citation(str(citation.get("id") or "Yutori citation"), str(url), str(update.get("content") or "")))

    context = str(result or "")
    if not context:
        status = latest.get("status") or created.get("status") or "unknown"
        view_url = latest.get("view_url") or created.get("view_url") or ""
        context = f"Yutori task {task_id} is {status}."
        if view_url:
            context += f" View: {view_url}"

    return {
        "tool": "yutori_research",
        "context": context,
        "citations": citations,
        "raw": {
            "task_id": task_id,
            "status": latest.get("status") or created.get("status"),
            "view_url": latest.get("view_url") or created.get("view_url"),
        },
    }


def _run_wikipedia_summary(query: str) -> dict[str, Any]:
    search = httpx.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": 1,
            "format": "json",
            "utf8": 1,
        },
        headers=HTTP_HEADERS,
        timeout=10,
    )
    search.raise_for_status()
    result = (search.json().get("query", {}).get("search") or [{}])[0]
    title = result.get("title")
    if not title:
        return {"tool": "wikipedia_summary", "context": f"No Wikipedia page found for: {query}", "citations": [], "raw": {}}

    summary = httpx.get(
        f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(str(title), safe='')}",
        headers=HTTP_HEADERS,
        timeout=10,
    )
    summary.raise_for_status()
    data = summary.json()
    extract = str(data.get("extract") or "")
    url = data.get("content_urls", {}).get("desktop", {}).get("page") or f"https://en.wikipedia.org/wiki/{quote(str(title).replace(' ', '_'))}"
    return {
        "tool": "wikipedia_summary",
        "context": f"{title}: {extract}" if extract else f"Wikipedia page found: {title}",
        "citations": [_citation(str(title), str(url), extract)] if url else [],
        "raw": {"title": title},
    }


def _run_arxiv_search(query: str) -> dict[str, Any]:
    response = httpx.get(
        "https://export.arxiv.org/api/query",
        params={
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": 5,
            "sortBy": "relevance",
        },
        headers=HTTP_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    root = ET.fromstring(response.text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    lines: list[str] = []
    citations: list[dict[str, str]] = []
    for entry in root.findall("atom:entry", ns):
        title = re.sub(r"\s+", " ", (entry.findtext("atom:title", default="", namespaces=ns))).strip()
        summary = re.sub(r"\s+", " ", (entry.findtext("atom:summary", default="", namespaces=ns))).strip()
        url = entry.findtext("atom:id", default="", namespaces=ns)
        authors = [author.findtext("atom:name", default="", namespaces=ns) for author in entry.findall("atom:author", ns)]
        published = entry.findtext("atom:published", default="", namespaces=ns)[:10]
        lines.append(f"{title} ({published}) by {', '.join([a for a in authors if a][:4])}: {summary}")
        if url:
            citations.append(_citation(title, url, summary))
    return {
        "tool": "arxiv_search",
        "context": "\n".join(lines) if lines else f"No arXiv papers found for: {query}",
        "citations": citations,
        "raw": {"result_count": len(lines)},
    }


def _run_crossref_lookup(query: str) -> dict[str, Any]:
    response = httpx.get(
        "https://api.crossref.org/works",
        params={"query": query, "rows": 5},
        headers=HTTP_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    items = response.json().get("message", {}).get("items") or []
    lines: list[str] = []
    citations: list[dict[str, str]] = []
    for item in items:
        title = " ".join(item.get("title") or []) or item.get("DOI") or "Crossref work"
        doi = item.get("DOI")
        url = item.get("URL") or (f"https://doi.org/{doi}" if doi else "")
        published = item.get("published-print") or item.get("published-online") or item.get("created") or {}
        year = ((published.get("date-parts") or [[None]])[0] or [None])[0]
        container = " ".join(item.get("container-title") or [])
        snippet = f"{container} {year or ''} DOI: {doi or 'n/a'}".strip()
        lines.append(f"{title}: {snippet}")
        if url:
            citations.append(_citation(str(title), str(url), snippet))
    return {
        "tool": "crossref_lookup",
        "context": "\n".join(lines) if lines else f"No Crossref works found for: {query}",
        "citations": citations,
        "raw": {"result_count": len(items)},
    }


def _run_semantic_scholar_search(query: str) -> dict[str, Any]:
    response = httpx.get(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        params={
            "query": query,
            "limit": 5,
            "fields": "title,year,authors,abstract,url,citationCount",
        },
        headers=HTTP_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    papers = response.json().get("data") or []
    lines: list[str] = []
    citations: list[dict[str, str]] = []
    for paper in papers:
        title = str(paper.get("title") or "Semantic Scholar paper")
        authors = ", ".join(str(author.get("name")) for author in (paper.get("authors") or [])[:4] if author.get("name"))
        abstract = str(paper.get("abstract") or "")
        url = str(paper.get("url") or "")
        snippet = f"{paper.get('year') or 'n.d.'}; citations: {paper.get('citationCount', 0)}; {authors}. {abstract}"
        lines.append(f"{title}: {snippet}")
        if url:
            citations.append(_citation(title, url, snippet))
    return {
        "tool": "semantic_scholar_search",
        "context": "\n".join(lines) if lines else f"No Semantic Scholar papers found for: {query}",
        "citations": citations,
        "raw": {"result_count": len(papers)},
    }


def _run_openalex_search(query: str) -> dict[str, Any]:
    response = httpx.get(
        "https://api.openalex.org/works",
        params={"search": query, "per-page": 5},
        headers=HTTP_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    works = response.json().get("results") or []
    lines: list[str] = []
    citations: list[dict[str, str]] = []
    for work in works:
        title = str(work.get("display_name") or "OpenAlex work")
        url = str(work.get("doi") or work.get("id") or "")
        authorships = work.get("authorships") or []
        authors = ", ".join(str(a.get("author", {}).get("display_name")) for a in authorships[:4] if a.get("author", {}).get("display_name"))
        snippet = f"{work.get('publication_year') or 'n.d.'}; cited by {work.get('cited_by_count', 0)}; {authors}"
        lines.append(f"{title}: {snippet}")
        if url:
            citations.append(_citation(title, url, snippet))
    return {
        "tool": "openalex_search",
        "context": "\n".join(lines) if lines else f"No OpenAlex works found for: {query}",
        "citations": citations,
        "raw": {"result_count": len(works)},
    }


def _sec_company_matches(query: str) -> list[dict[str, Any]]:
    response = httpx.get("https://www.sec.gov/files/company_tickers.json", headers=HTTP_HEADERS, timeout=15)
    response.raise_for_status()
    query_lower = query.lower()
    tokens = {token for token in re.findall(r"[a-zA-Z0-9]+", query_lower) if len(token) > 1}
    matches: list[dict[str, Any]] = []
    for item in response.json().values():
        ticker = str(item.get("ticker") or "").lower()
        title = str(item.get("title") or "").lower()
        if ticker in tokens or any(token in title for token in tokens):
            matches.append(item)
        if len(matches) >= 5:
            break
    return matches


def _run_company_ticker_lookup(query: str) -> dict[str, Any]:
    matches = _sec_company_matches(query)
    lines = [
        f"{item.get('title')} ({item.get('ticker')}): CIK {str(item.get('cik_str')).zfill(10)}"
        for item in matches
    ]
    citations = [
        _citation(
            str(item.get("title") or item.get("ticker")),
            f"https://www.sec.gov/edgar/browse/?CIK={str(item.get('cik_str')).zfill(10)}",
            f"Ticker {item.get('ticker')}; CIK {str(item.get('cik_str')).zfill(10)}",
        )
        for item in matches
    ]
    return {
        "tool": "company_ticker_lookup",
        "context": "\n".join(lines) if lines else f"No SEC ticker match found for: {query}",
        "citations": citations,
        "raw": {"result_count": len(matches)},
    }


def _run_sec_edgar_filings(query: str) -> dict[str, Any]:
    matches = _sec_company_matches(query)
    if not matches:
        return {"tool": "sec_edgar_filings", "context": f"No SEC company match found for: {query}", "citations": [], "raw": {}}
    company = matches[0]
    cik = str(company.get("cik_str")).zfill(10)
    response = httpx.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=HTTP_HEADERS, timeout=15)
    response.raise_for_status()
    data = response.json()
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form") or []
    dates = recent.get("filingDate") or []
    accession_numbers = recent.get("accessionNumber") or []
    descriptions = recent.get("primaryDocDescription") or []
    lines: list[str] = []
    citations: list[dict[str, str]] = []
    for idx, form in enumerate(forms[:8]):
        accession = str(accession_numbers[idx] if idx < len(accession_numbers) else "")
        accession_path = accession.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_path}/"
        snippet = f"{dates[idx] if idx < len(dates) else ''} {form}: {descriptions[idx] if idx < len(descriptions) else ''}".strip()
        lines.append(snippet)
        citations.append(_citation(f"{data.get('name', company.get('title'))} {form}", url, snippet))
    return {
        "tool": "sec_edgar_filings",
        "context": f"{data.get('name', company.get('title'))} ({company.get('ticker')}) recent filings:\n" + "\n".join(lines),
        "citations": citations,
        "raw": {"cik": cik, "ticker": company.get("ticker")},
    }


COUNTRY_CODES = {
    "united states": "US",
    "usa": "US",
    "us": "US",
    "india": "IN",
    "china": "CN",
    "united kingdom": "GB",
    "uk": "GB",
    "germany": "DE",
    "france": "FR",
    "japan": "JP",
    "canada": "CA",
    "brazil": "BR",
    "australia": "AU",
    "mexico": "MX",
}
INDICATORS = {
    "population": "SP.POP.TOTL",
    "gdp": "NY.GDP.MKTP.CD",
    "inflation": "FP.CPI.TOTL.ZG",
    "unemployment": "SL.UEM.TOTL.ZS",
    "life expectancy": "SP.DYN.LE00.IN",
    "co2": "EN.ATM.CO2E.PC",
}


def _run_world_bank_indicators(query: str) -> dict[str, Any]:
    lower = query.lower()
    country = next((code for name, code in COUNTRY_CODES.items() if name in lower), "US")
    indicator = next((code for name, code in INDICATORS.items() if name in lower), "NY.GDP.MKTP.CD")
    response = httpx.get(
        f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}",
        params={"format": "json", "per_page": 8, "mrv": 8},
        headers=HTTP_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
    lines = [
        f"{row.get('country', {}).get('value')} {row.get('date')}: {row.get('value')}"
        for row in rows
        if row.get("value") is not None
    ]
    return {
        "tool": "world_bank_indicators",
        "context": "\n".join(lines) if lines else f"No World Bank indicator values found for: {query}",
        "citations": [_citation("World Bank Indicators API", "https://api.worldbank.org/v2/", f"{country} {indicator}")],
        "raw": {"country": country, "indicator": indicator},
    }


def _geocode_place(query: str) -> dict[str, Any] | None:
    response = httpx.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": query, "format": "jsonv2", "limit": 1},
        headers=HTTP_HEADERS,
        timeout=12,
    )
    response.raise_for_status()
    results = response.json()
    return results[0] if results else None


def _run_nominatim_geocode(query: str) -> dict[str, Any]:
    result = _geocode_place(query)
    if not result:
        return {"tool": "nominatim_geocode", "context": f"No geocode result found for: {query}", "citations": [], "raw": {}}
    display_name = str(result.get("display_name") or query)
    context = f"{display_name}: latitude {result.get('lat')}, longitude {result.get('lon')}, type {result.get('type')}"
    return {
        "tool": "nominatim_geocode",
        "context": context,
        "citations": [_citation(display_name, "https://www.openstreetmap.org/", context)],
        "raw": {"lat": result.get("lat"), "lon": result.get("lon")},
    }


def _run_open_meteo_weather(query: str) -> dict[str, Any]:
    place = _geocode_place(query)
    if not place:
        return {"tool": "open_meteo_weather", "context": f"No place found for weather query: {query}", "citations": [], "raw": {}}
    response = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": place.get("lat"),
            "longitude": place.get("lon"),
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "forecast_days": 3,
            "timezone": "auto",
        },
        headers=HTTP_HEADERS,
        timeout=12,
    )
    response.raise_for_status()
    data = response.json()
    current = data.get("current", {})
    daily = data.get("daily", {})
    context = (
        f"Weather for {place.get('display_name')}: current temperature {current.get('temperature_2m')} C, "
        f"humidity {current.get('relative_humidity_2m')}%, wind {current.get('wind_speed_10m')} km/h. "
        f"Daily max temperatures: {daily.get('temperature_2m_max')}; min temperatures: {daily.get('temperature_2m_min')}; "
        f"precipitation probabilities: {daily.get('precipitation_probability_max')}."
    )
    return {
        "tool": "open_meteo_weather",
        "context": context,
        "citations": [_citation("Open-Meteo forecast", "https://open-meteo.com/", context)],
        "raw": {"timezone": data.get("timezone")},
    }


def _run_timezone_lookup(query: str) -> dict[str, Any]:
    iana_match = re.search(r"\b[A-Z][A-Za-z_]+/[A-Z][A-Za-z_]+(?:/[A-Z][A-Za-z_]+)?\b", query)
    if iana_match:
        from zoneinfo import ZoneInfo

        zone = iana_match.group(0)
        now = datetime.now(ZoneInfo(zone))
        context = f"Current time in {zone}: {now.isoformat()}"
        return {"tool": "timezone_lookup", "context": context, "citations": [], "raw": {"timezone": zone}}
    weather = _run_open_meteo_weather(query)
    timezone = weather.get("raw", {}).get("timezone")
    context = f"{weather['context']} Timezone: {timezone or 'unknown'}"
    return {"tool": "timezone_lookup", "context": context, "citations": weather.get("citations", []), "raw": {"timezone": timezone}}


def _extract_github_repo(query: str) -> tuple[str, str] | None:
    match = re.search(r"github\.com/([^/\s]+)/([^/\s#?]+)", query, re.IGNORECASE)
    if match:
        return match.group(1), match.group(2).removesuffix(".git")
    match = re.search(r"\b([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)\b", query)
    if match:
        return match.group(1), match.group(2)
    return None


def _run_github_repo_inspector(query: str) -> dict[str, Any]:
    repo = _extract_github_repo(query)
    if repo:
        owner, name = repo
        response = httpx.get(f"https://api.github.com/repos/{owner}/{name}", headers=HTTP_HEADERS, timeout=12)
    else:
        response = httpx.get("https://api.github.com/search/repositories", params={"q": query, "per_page": 1}, headers=HTTP_HEADERS, timeout=12)
    response.raise_for_status()
    data = response.json()
    if not repo:
        items = data.get("items") or []
        if not items:
            return {"tool": "github_repo_inspector", "context": f"No GitHub repo found for: {query}", "citations": [], "raw": {}}
        data = items[0]
    full_name = str(data.get("full_name") or "")
    url = str(data.get("html_url") or "")
    context = (
        f"{full_name}: {data.get('description') or 'No description'}; "
        f"stars {data.get('stargazers_count')}, forks {data.get('forks_count')}, "
        f"open issues {data.get('open_issues_count')}, language {data.get('language')}, "
        f"updated {data.get('updated_at')}."
    )
    return {
        "tool": "github_repo_inspector",
        "context": context,
        "citations": [_citation(full_name, url, context)] if url else [],
        "raw": {"full_name": full_name},
    }


def _run_hacker_news_search(query: str) -> dict[str, Any]:
    response = httpx.get(
        "https://hn.algolia.com/api/v1/search",
        params={"query": query, "tags": "story", "hitsPerPage": 5},
        headers=HTTP_HEADERS,
        timeout=12,
    )
    response.raise_for_status()
    hits = response.json().get("hits") or []
    lines: list[str] = []
    citations: list[dict[str, str]] = []
    for hit in hits:
        title = str(hit.get("title") or "Hacker News story")
        url = str(hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}")
        snippet = f"points {hit.get('points')}; comments {hit.get('num_comments')}; created {hit.get('created_at')}"
        lines.append(f"{title}: {snippet}")
        citations.append(_citation(title, url, snippet))
    return {
        "tool": "hacker_news_search",
        "context": "\n".join(lines) if lines else f"No Hacker News stories found for: {query}",
        "citations": citations,
        "raw": {"result_count": len(hits)},
    }


def _parse_feed(xml_text: str) -> tuple[list[str], list[dict[str, str]]]:
    root = ET.fromstring(xml_text)
    lines: list[str] = []
    citations: list[dict[str, str]] = []
    if root.tag.endswith("rss"):
        items = root.findall("./channel/item")[:8]
        for item in items:
            title = item.findtext("title", default="RSS item")
            link = item.findtext("link", default="")
            description = _strip_html(item.findtext("description", default=""))
            pub_date = item.findtext("pubDate", default="")
            lines.append(f"{title} ({pub_date}): {description}")
            if link:
                citations.append(_citation(title, link, description))
        return lines, citations
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall("atom:entry", ns)[:8]:
        title = entry.findtext("atom:title", default="Atom entry", namespaces=ns)
        link_node = entry.find("atom:link", ns)
        link = link_node.attrib.get("href", "") if link_node is not None else ""
        summary = _strip_html(entry.findtext("atom:summary", default="", namespaces=ns) or entry.findtext("atom:content", default="", namespaces=ns))
        updated = entry.findtext("atom:updated", default="", namespaces=ns)
        lines.append(f"{title} ({updated}): {summary}")
        if link:
            citations.append(_citation(title, link, summary))
    return lines, citations


def _run_rss_reader(query: str) -> dict[str, Any]:
    url = _extract_url(query)
    if not url:
        return {"tool": "rss_reader", "context": "No RSS/Atom feed URL found in the request.", "citations": [], "raw": {}}
    safe_url = _safe_public_url(url)
    response = httpx.get(safe_url, headers=HTTP_HEADERS, timeout=12, follow_redirects=True)
    response.raise_for_status()
    lines, citations = _parse_feed(response.text)
    return {
        "tool": "rss_reader",
        "context": "\n".join(lines) if lines else f"No feed entries found at {safe_url}",
        "citations": citations,
        "raw": {"url": safe_url, "entry_count": len(lines)},
    }


def _run_changelog_reader(query: str) -> dict[str, Any]:
    repo = _extract_github_repo(query)
    if repo:
        owner, name = repo
        response = httpx.get(f"https://api.github.com/repos/{owner}/{name}/releases", headers=HTTP_HEADERS, timeout=12)
        response.raise_for_status()
        releases = response.json()[:5]
        lines: list[str] = []
        citations: list[dict[str, str]] = []
        for release in releases:
            title = str(release.get("name") or release.get("tag_name") or "Release")
            url = str(release.get("html_url") or "")
            body = _strip_html(str(release.get("body") or ""))
            snippet = f"{release.get('published_at')}: {body}"
            lines.append(f"{title}: {snippet}")
            if url:
                citations.append(_citation(title, url, snippet))
        return {
            "tool": "changelog_reader",
            "context": "\n".join(lines) if lines else f"No GitHub releases found for {owner}/{name}.",
            "citations": citations,
            "raw": {"repo": f"{owner}/{name}"},
        }
    return {**_run_rss_reader(query), "tool": "changelog_reader"}


def _run_gdelt_news_search(query: str) -> dict[str, Any]:
    response = httpx.get(
        "https://api.gdeltproject.org/api/v2/doc/doc",
        params={"query": query, "mode": "artlist", "format": "json", "maxrecords": 5, "sort": "hybridrel"},
        headers=HTTP_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    articles = response.json().get("articles") or []
    lines: list[str] = []
    citations: list[dict[str, str]] = []
    for article in articles:
        title = str(article.get("title") or "GDELT article")
        url = str(article.get("url") or "")
        snippet = f"{article.get('seendate')}: {article.get('domain')} {article.get('language', '')}"
        lines.append(f"{title}: {snippet}")
        if url:
            citations.append(_citation(title, url, snippet))
    return {
        "tool": "gdelt_news_search",
        "context": "\n".join(lines) if lines else f"No GDELT articles found for: {query}",
        "citations": citations,
        "raw": {"result_count": len(articles)},
    }


def _run_mediastack_news(query: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.mediastack_api_key:
        raise RuntimeError("MEDIASTACK_API_KEY is not configured.")
    response = httpx.get(
        "http://api.mediastack.com/v1/news",
        params={"access_key": settings.mediastack_api_key.get_secret_value(), "keywords": query, "limit": 5},
        headers=HTTP_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    articles = response.json().get("data") or []
    lines: list[str] = []
    citations: list[dict[str, str]] = []
    for article in articles:
        title = str(article.get("title") or "Mediastack article")
        url = str(article.get("url") or "")
        snippet = f"{article.get('published_at')}: {article.get('source')} - {article.get('description') or ''}"
        lines.append(f"{title}: {snippet}")
        if url:
            citations.append(_citation(title, url, snippet))
    return {
        "tool": "mediastack_news",
        "context": "\n".join(lines) if lines else f"No Mediastack articles found for: {query}",
        "citations": citations,
        "raw": {"result_count": len(articles)},
    }


def _run_newsapi_dev(query: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.newsapi_api_key:
        raise RuntimeError("NEWSAPI_API_KEY is not configured.")
    response = httpx.get(
        "https://newsapi.org/v2/everything",
        params={"apiKey": settings.newsapi_api_key.get_secret_value(), "q": query, "pageSize": 5, "sortBy": "relevancy"},
        headers=HTTP_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    articles = response.json().get("articles") or []
    lines: list[str] = []
    citations: list[dict[str, str]] = []
    for article in articles:
        title = str(article.get("title") or "NewsAPI article")
        url = str(article.get("url") or "")
        snippet = f"{article.get('publishedAt')}: {article.get('source', {}).get('name')} - {article.get('description') or ''}"
        lines.append(f"{title}: {snippet}")
        if url:
            citations.append(_citation(title, url, snippet))
    return {
        "tool": "newsapi_dev",
        "context": "\n".join(lines) if lines else f"No NewsAPI articles found for: {query}",
        "citations": citations,
        "raw": {"result_count": len(articles)},
    }


def _run_page_reader(query: str) -> dict[str, Any]:
    url = _extract_url(query)
    if not url:
        return {"tool": "page_reader", "context": "No public URL found in the request.", "citations": [], "raw": {}}
    safe_url = _safe_public_url(url)
    response = httpx.get(safe_url, headers=HTTP_HEADERS, timeout=15, follow_redirects=True)
    response.raise_for_status()
    text = _strip_html(response.text)
    title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", response.text)
    title = _strip_html(title_match.group(1)) if title_match else safe_url
    context = _truncate(text, 4000)
    return {
        "tool": "page_reader",
        "context": context if context else f"No readable text found at {safe_url}",
        "citations": [_citation(title, safe_url, context)] if context else [],
        "raw": {"url": safe_url},
    }


def _run_pdf_reader(query: str) -> dict[str, Any]:
    url = _extract_url(query)
    if not url:
        return {"tool": "pdf_reader", "context": "No public PDF URL found in the request.", "citations": [], "raw": {}}
    if find_spec("pypdf") is None:
        raise RuntimeError("pypdf is not installed.")
    safe_url = _safe_public_url(url)
    response = httpx.get(safe_url, headers=HTTP_HEADERS, timeout=20, follow_redirects=True)
    response.raise_for_status()
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(response.content))
    page_texts = [(page.extract_text() or "") for page in reader.pages[:5]]
    text = _truncate("\n".join(page_texts), 5000)
    return {
        "tool": "pdf_reader",
        "context": text if text else f"No extractable PDF text found at {safe_url}",
        "citations": [_citation("PDF document", safe_url, text)] if text else [],
        "raw": {"url": safe_url, "pages_read": min(len(reader.pages), 5)},
    }


def _run_csv_analyzer(query: str) -> dict[str, Any]:
    url = _extract_url(query)
    if url:
        safe_url = _safe_public_url(url)
        response = httpx.get(safe_url, headers=HTTP_HEADERS, timeout=15, follow_redirects=True)
        response.raise_for_status()
        csv_text = response.text
        source = safe_url
    else:
        csv_text = query
        source = "inline"
    rows = list(csv.reader(io.StringIO(csv_text)))
    if not rows:
        return {"tool": "csv_analyzer", "context": "No CSV rows found.", "citations": [], "raw": {}}
    header = rows[0]
    sample = rows[1:6]
    context = f"CSV source {source}: {len(rows) - 1} data rows, {len(header)} columns. Columns: {header}. Sample rows: {sample}"
    return {
        "tool": "csv_analyzer",
        "context": context,
        "citations": [_citation("CSV source", source, context)] if url else [],
        "raw": {"rows": len(rows), "columns": len(header)},
    }


def _run_json_api_fetcher(query: str) -> dict[str, Any]:
    url = _extract_url(query)
    if not url:
        return {"tool": "json_api_fetcher", "context": "No public JSON API URL found in the request.", "citations": [], "raw": {}}
    safe_url = _safe_public_url(url)
    response = httpx.get(safe_url, headers=HTTP_HEADERS, timeout=15, follow_redirects=True)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict):
        context = f"JSON object keys: {list(data.keys())[:30]}. Preview: {_truncate(json.dumps(data, default=str), 3000)}"
    elif isinstance(data, list):
        context = f"JSON array length {len(data)}. Preview: {_truncate(json.dumps(data[:5], default=str), 3000)}"
    else:
        context = f"JSON value: {_truncate(json.dumps(data, default=str), 3000)}"
    return {
        "tool": "json_api_fetcher",
        "context": context,
        "citations": [_citation("JSON API", safe_url, context)],
        "raw": {"url": safe_url},
    }


ALLOWED_AST_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.FloorDiv,
    ast.USub,
    ast.UAdd,
)


def _safe_eval_math(expression: str) -> float | int:
    tree = ast.parse(expression, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_AST_NODES):
            raise ValueError("Unsupported expression.")
    return eval(compile(tree, "<calculator>", "eval"), {"__builtins__": {}}, {})


def _run_calculator(query: str) -> dict[str, Any]:
    expressions = re.findall(r"(?<![A-Za-z])[-+*/().\d\s%]{3,}(?![A-Za-z])", query)
    results: list[str] = []
    for expression in expressions[:5]:
        cleaned = expression.strip()
        if not re.search(r"\d", cleaned):
            continue
        try:
            value = _safe_eval_math(cleaned)
        except Exception:
            continue
        if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
            continue
        results.append(f"{cleaned} = {value}")
    context = "\n".join(results) if results else "No arithmetic expression found."
    return {"tool": "calculator", "context": context, "citations": [], "raw": {"result_count": len(results)}}


def _run_date_time_tool(query: str) -> dict[str, Any]:
    now = datetime.now(UTC)
    context = f"Current UTC time: {now.isoformat()}. Current UTC date: {now.date().isoformat()}."
    return {"tool": "date_time_tool", "context": context, "citations": [], "raw": {"utc": now.isoformat()}}


def run_builtin_tools(tool_ids: list[str], query: str) -> ToolRunResult:
    enabled = enabled_tool_ids()
    outputs: list[dict[str, Any]] = []
    contexts: list[str] = []
    citations: list[dict[str, str]] = []

    runners = {
        "web_search": _run_web_search,
        "tavily_search": _run_tavily_search,
        "yutori_research": _run_yutori_research,
        "wikipedia_summary": _run_wikipedia_summary,
        "arxiv_search": _run_arxiv_search,
        "crossref_lookup": _run_crossref_lookup,
        "semantic_scholar_search": _run_semantic_scholar_search,
        "openalex_search": _run_openalex_search,
        "sec_edgar_filings": _run_sec_edgar_filings,
        "company_ticker_lookup": _run_company_ticker_lookup,
        "world_bank_indicators": _run_world_bank_indicators,
        "open_meteo_weather": _run_open_meteo_weather,
        "nominatim_geocode": _run_nominatim_geocode,
        "timezone_lookup": _run_timezone_lookup,
        "github_repo_inspector": _run_github_repo_inspector,
        "hacker_news_search": _run_hacker_news_search,
        "rss_reader": _run_rss_reader,
        "changelog_reader": _run_changelog_reader,
        "gdelt_news_search": _run_gdelt_news_search,
        "mediastack_news": _run_mediastack_news,
        "newsapi_dev": _run_newsapi_dev,
        "page_reader": _run_page_reader,
        "pdf_reader": _run_pdf_reader,
        "csv_analyzer": _run_csv_analyzer,
        "json_api_fetcher": _run_json_api_fetcher,
        "calculator": _run_calculator,
        "date_time_tool": _run_date_time_tool,
    }

    seen: set[str] = set()
    for tool_id in tool_ids:
        if tool_id in seen:
            continue
        seen.add(tool_id)
        runner = runners.get(tool_id)
        if not runner:
            continue
        if tool_id not in enabled:
            outputs.append(
                {
                    "tool": tool_id,
                    "status": "disabled",
                    "error": "Tool is disabled because required platform configuration is missing.",
                }
            )
            continue
        try:
            result = runner(_clean_query(query))
            context = str(result.get("context") or "")
            outputs.append(
                {
                    "tool": tool_id,
                    "status": "ok",
                    "context": _truncate(context, 2000),
                    "raw": result.get("raw", {}),
                }
            )
            if context:
                contexts.append(f"[{tool_id}]\n{context}")
            citations.extend(result.get("citations") or [])
        except Exception as exc:
            outputs.append(
                {
                    "tool": tool_id,
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    return ToolRunResult(
        context="\n\n".join(contexts),
        citations=citations[:20],
        tool_outputs=outputs,
    )
