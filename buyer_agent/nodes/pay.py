from __future__ import annotations

import httpx

from buyer_agent.state import BuyerState
from shared.config import get_settings
from shared.x402_client import (
    PAYMENT_REQUIRED_HEADER,
    PAYMENT_RESPONSE_HEADER,
    PAYMENT_SIGNATURE_HEADER,
    PAYMENT_TX_ID_HEADER,
    PaymentOffer,
    PaymentReceipt,
    get_x402_client,
)


def execute_payment(state: BuyerState) -> dict:
    settings = get_settings()

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
            return {"error": f"Expected 402 from seller, received {initial.status_code}: {initial.text}"}

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

        paid = client.post(
            state["seller_url"],
            headers={
                PAYMENT_SIGNATURE_HEADER: authorization.model_dump_json(),
                PAYMENT_TX_ID_HEADER: receipt.transaction_id,
            },
            json={
                "task_id": state["task_id"],
                "query": state["query"],
                "buyer_agent_id": state["buyer_agent_id"],
                "seller_agent_id": state["seller_agent_id"],
            },
        )
        if paid.status_code >= 400:
            return {"error": f"Payment retry failed with {paid.status_code}: {paid.text}"}

        seller_receipt = PaymentReceipt.model_validate_json(paid.headers[PAYMENT_RESPONSE_HEADER])
        return {
            "payment_offer": offer.model_dump(),
            "payment_receipt": seller_receipt.model_dump(),
            "response_body": paid.json(),
        }
