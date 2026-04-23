from __future__ import annotations

from seller_agent.state import SellerState


def retrieve_context(state: SellerState) -> dict:
    import httpx

    query = state["query"]

    try:
        response = httpx.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_redirect": 1,
                "no_html": 1,
            },
            timeout=5,
        )
        data = response.json()

        citations = []
        # Parse DuckDuckGo results
        if data.get("AbstractText"):
            citations.append({
                "title": data.get("AbstractTitle", query),
                "url": data.get("AbstractURL", ""),
                "snippet": data.get("AbstractText", ""),
            })

        # Add related searches
        if data.get("RelatedTopics"):
            for item in data.get("RelatedTopics", [])[:3]:
                if isinstance(item, dict) and "Text" in item:
                    citations.append({
                        "title": item.get("Text", "").split(" - ")[0],
                        "url": item.get("FirstURL", ""),
                        "snippet": item.get("Text", ""),
                    })

        return {
            "retrieval_context": citations if citations else [],
            "draft_summary": f"Retrieved context for: {query}"
        }
    except Exception:
        # No fallback - return empty if search fails
        return {
            "retrieval_context": [],
            "draft_summary": f"No results found for: {query}"
        }

