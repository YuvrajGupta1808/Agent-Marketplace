from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from shared.circle_client import CircleSignedPayload, CircleTransferResult, format_usdc_amount, get_circle_client
from shared.config import get_settings

PAYMENT_REQUIRED_HEADER = "PAYMENT-REQUIRED"
PAYMENT_SIGNATURE_HEADER = "PAYMENT-SIGNATURE"
PAYMENT_RESPONSE_HEADER = "PAYMENT-RESPONSE"
PAYMENT_TX_ID_HEADER = "PAYMENT-TX-ID"


class PaymentOffer(BaseModel):
    amount_usdc: str
    chain_id: int
    pay_to: str
    seller_agent_id: str
    resource: str = "/research"
    quote_id: str = Field(default_factory=lambda: os.urandom(8).hex())
    description: str = "Marketplace research request"


class PaymentAuthorization(BaseModel):
    buyer_agent_id: str
    buyer_wallet_id: str
    buyer_wallet_address: str
    seller_agent_id: str
    seller_wallet_address: str
    amount_usdc: str
    query: str
    valid_after: int
    valid_before: int
    nonce: str
    signature: str
    typed_data: dict[str, Any]


class PaymentReceipt(BaseModel):
    transaction_id: str
    transaction_state: str
    tx_hash: str | None = None
    amount_usdc: str
    pay_to: str
    settled_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


def build_payment_typed_data(
    *,
    buyer_wallet_address: str,
    seller_wallet_address: str,
    amount_usdc: str,
    query: str,
) -> dict[str, Any]:
    settings = get_settings()
    now = int(datetime.now(UTC).timestamp())
    valid_before = int((datetime.now(UTC) + timedelta(days=5)).timestamp())
    nonce = "0x" + os.urandom(32).hex()
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "MarketplacePayment": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "amount", "type": "string"},
                {"name": "query", "type": "string"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ],
        },
        "primaryType": "MarketplacePayment",
        "domain": {
            "name": "AgentMarketplace",
            "version": "1",
            "chainId": settings.arc_chain_id,
            "verifyingContract": settings.arc_usdc_contract,
        },
        "message": {
            "from": buyer_wallet_address,
            "to": seller_wallet_address,
            "amount": amount_usdc,
            "query": query,
            "validAfter": now,
            "validBefore": valid_before,
            "nonce": nonce,
        },
    }


@dataclass(slots=True)
class CirclePaymentClient:
    def create_offer(self, seller_wallet_address: str, seller_agent_id: str, amount_usdc: str | None = None) -> PaymentOffer:
        settings = get_settings()
        return PaymentOffer(
            amount_usdc=amount_usdc or format_usdc_amount(settings.seller_price_usdc),
            chain_id=settings.arc_chain_id,
            pay_to=seller_wallet_address,
            seller_agent_id=seller_agent_id,
        )

    def sign_payment(
        self,
        *,
        buyer_agent_id: str,
        buyer_wallet_id: str,
        buyer_wallet_address: str,
        seller_agent_id: str,
        seller_wallet_address: str,
        amount_usdc: str,
        query: str,
    ) -> PaymentAuthorization:
        settings = get_settings()
        typed_data = build_payment_typed_data(
            buyer_wallet_address=buyer_wallet_address,
            seller_wallet_address=seller_wallet_address,
            amount_usdc=amount_usdc,
            query=query,
        )
        message = typed_data["message"]

        if not settings.circle_enabled:
            raise RuntimeError("Circle credentials are required for payment signing.")

        signed: CircleSignedPayload = get_circle_client().sign_typed_data(
            wallet_id=buyer_wallet_id,
            typed_data=typed_data,
            memo="Marketplace payment authorization",
        )
        signature = signed.signature

        return PaymentAuthorization(
            buyer_agent_id=buyer_agent_id,
            buyer_wallet_id=buyer_wallet_id,
            buyer_wallet_address=buyer_wallet_address,
            seller_agent_id=seller_agent_id,
            seller_wallet_address=seller_wallet_address,
            amount_usdc=amount_usdc,
            query=query,
            valid_after=message["validAfter"],
            valid_before=message["validBefore"],
            nonce=message["nonce"],
            signature=signature,
            typed_data=typed_data,
        )

    def settle_payment(self, buyer_wallet_id: str, seller_wallet_address: str, amount_usdc: str, ref_id: str) -> PaymentReceipt:
        settings = get_settings()
        if not settings.circle_enabled:
            raise RuntimeError("Circle credentials are required for payment settlement.")

        transfer: CircleTransferResult = get_circle_client().create_transfer(
            wallet_id=buyer_wallet_id,
            destination_address=seller_wallet_address,
            amount_usdc=amount_usdc,
            ref_id=ref_id,
        )
        return PaymentReceipt(
            transaction_id=transfer.transaction_id,
            transaction_state=transfer.state,
            tx_hash=transfer.tx_hash,
            amount_usdc=amount_usdc,
            pay_to=seller_wallet_address,
        )

    def verify_authorization(self, authorization_json: str, expected_offer: PaymentOffer, expected_query: str) -> PaymentAuthorization:
        authorization = PaymentAuthorization.model_validate_json(authorization_json)
        if authorization.seller_agent_id != expected_offer.seller_agent_id:
            raise ValueError("Seller agent does not match payment offer.")
        if authorization.seller_wallet_address.lower() != expected_offer.pay_to.lower():
            raise ValueError("Seller wallet does not match payment offer.")
        if authorization.amount_usdc != expected_offer.amount_usdc:
            raise ValueError("Payment amount does not match payment offer.")
        if authorization.query != expected_query:
            raise ValueError("Payment query does not match request.")
        return authorization


def get_x402_client() -> CirclePaymentClient:
    return CirclePaymentClient()
