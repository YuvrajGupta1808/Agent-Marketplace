from __future__ import annotations

import httpx

from buyer_agent.state import BuyerState
from shared.config import get_settings
from shared.x402_client import (
    PAYMENT_REQUIRED_HEADER,
    PaymentOffer,
    get_x402_client,
)


def execute_payment(state: BuyerState) -> dict:
    if state.get("error"):
        print(f"    ❌ execute_payment: error from previous step: {state.get('error')}")
        return {"error": state["error"]}

    print(f"  💳 execute_payment: {state['seller_url']}")
    settings = get_settings()

    try:
        with httpx.Client(timeout=settings.request_timeout_seconds) as client:
            initial = client.post(
                state["seller_url"],
                json={
                    "task_id": state["task_id"],
                    "query": state["query"],
                    "buyer_agent_id": state["buyer_agent_id"],
                    "seller_agent_id": state["seller_agent_id"],
                },
            )
            if initial.status_code != 402:
                error_msg = f"Expected 402 from seller, received {initial.status_code}: {initial.text[:100]}"
                print(f"    ❌ {error_msg}")
                return {"error": error_msg}

            print(f"    ✓ Payment request received (402)")
            offer = PaymentOffer.model_validate_json(initial.headers[PAYMENT_REQUIRED_HEADER])
            authorization = get_x402_client().sign_payment(
                buyer_agent_id=state["buyer_agent_id"],
                buyer_wallet_id=state["buyer_wallet_id"],
                buyer_wallet_address=state["buyer_wallet_address"],
                seller_agent_id=state["seller_agent_id"],
                seller_wallet_address=state["seller_wallet_address"] or offer.pay_to,
                amount_usdc=offer.amount_usdc,
                query=state["query"],
            )
            receipt = get_x402_client().settle_payment(
                buyer_wallet_id=state["buyer_wallet_id"],
                seller_wallet_address=state["seller_wallet_address"] or offer.pay_to,
                amount_usdc=offer.amount_usdc,
                ref_id=f"{state['task_id']}:{state['seller_agent_id']}",
            )
            # Add query metadata to receipt for ledger display
            receipt_dict = receipt.model_dump()
            receipt_dict["metadata"] = {
                "query": state.get("query", ""),
                "task_id": state.get("task_id", ""),
            }
            print(f"    ✓ Payment settled: {offer.amount_usdc} USDC")
            return {
                "execution_plan": state.get("execution_plan", []),
                "payment_authorization": authorization.model_dump(),
                "payment_offer": offer.model_dump(),
                "payment_receipt": receipt_dict,
            }
    except (ImportError, Exception) as e:
        error_msg = f"Payment processing failed: {type(e).__name__}: {str(e)[:80]}"
        print(f"    ⚠️ {error_msg}")
        return {
            "error": error_msg,
            "execution_plan": state.get("execution_plan", []),
        }
