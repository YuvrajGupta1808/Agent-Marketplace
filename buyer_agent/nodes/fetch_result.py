from __future__ import annotations

from buyer_agent.state import BuyerState
from shared.types import ResearchResult


def fetch_result(state: BuyerState) -> dict:
    import json

    if state.get("error"):
        print(f"    ❌ fetch_result: error from previous step: {state.get('error')}")
        return {"error": state["error"]}

    print(f"  📥 fetch_result")
    try:
        payload = state["response_body"]

        # Try to get result from payload
        result_data = payload.get("result")
        if not result_data:
            raise ValueError("No result in response_body")

        # If result_data is already a ResearchResult object/dict, use it
        if isinstance(result_data, dict):
            result_dict = result_data
        else:
            # Try to convert Pydantic model to dict
            result_dict = result_data.model_dump() if hasattr(result_data, 'model_dump') else dict(result_data)

        # Ensure required fields exist, extract from summary/bullets if needed
        title = result_dict.get("title")
        if not title:
            # Extract title from query if not in result
            title = f"Research: {state.get('query', 'Query')[:60]}"

        summary = result_dict.get("summary", "")
        if not summary and isinstance(summary, str):
            # If summary is empty, use first bullet or generic text
            bullets = result_dict.get("bullets", [])
            summary = bullets[0] if bullets else "Research completed"

        bullets = result_dict.get("bullets", [])
        if not isinstance(bullets, list):
            bullets = [str(bullets)] if bullets else []

        # Reconstruct the result with all required fields
        structured_result = ResearchResult(
            task_id=result_dict.get("task_id", state.get("task_id", "")),
            title=str(title)[:200],
            summary=str(summary)[:2000],
            bullets=[str(b)[:500] for b in bullets][:10],
            citations=result_dict.get("citations", []),
            seller_name=result_dict.get("seller_name", "Seller Agent"),
            is_ambiguous=result_dict.get("is_ambiguous", False),
            metadata=result_dict.get("metadata", {}),
        )

        # Add payment info from the execute_payment receipt
        receipt = state.get("payment_receipt") or {}
        print(f"    📋 Payment receipt: {bool(receipt)}, has transaction_id: {bool(receipt.get('transaction_id'))}")
        if receipt.get("tx_hash"):
            structured_result.tx_hash = receipt["tx_hash"]
        if receipt.get("transaction_id"):
            structured_result.circle_transaction_id = receipt["transaction_id"]
            print(f"    ✓ Set circle_transaction_id: {receipt.get('transaction_id')[:16]}...")
        if receipt.get("amount_usdc"):
            structured_result.amount_usdc = receipt["amount_usdc"]

        print(f"    ✓ Result fetched: {structured_result.title[:40]}")
        return {"result": structured_result.model_dump()}
    except Exception as e:
        error_msg = f"fetch_result error: {type(e).__name__}: {str(e)[:80]}"
        print(f"    ❌ {error_msg}")
        return {"error": error_msg}

