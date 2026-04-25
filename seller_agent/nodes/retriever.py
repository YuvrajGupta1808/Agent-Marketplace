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

        context_text = ""
        # Parse DuckDuckGo results
        if data.get("AbstractText"):
            context_text += f"{data.get('AbstractTitle', query)}: {data.get('AbstractText', '')}\n\n"

        # Add related searches
        if data.get("RelatedTopics"):
            for item in data.get("RelatedTopics", [])[:3]:
                if isinstance(item, dict) and "Text" in item:
                    context_text += f"{item.get('Text', '')}\n"

        return {
            "retrieval_context": context_text if context_text else f"No search results found for: {query}",
        }
    except Exception:
        return {
            "retrieval_context": f"Unable to search for: {query}"
        }

