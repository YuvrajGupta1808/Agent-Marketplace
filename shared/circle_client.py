from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Any

from shared.config import get_settings
from shared.ssl import configure_ssl_cert_file


@dataclass(slots=True)
class CircleProvisionedWallet:
    circle_wallet_id: str
    address: str
    wallet_set_id: str
    blockchain: str
    account_type: str
    metadata: dict[str, Any]


@dataclass(slots=True)
class CircleSignedPayload:
    signature: str
    typed_data: dict[str, Any]
    memo: str


@dataclass(slots=True)
class CircleTransferResult:
    transaction_id: str
    state: str
    tx_hash: str | None = None
    raw: dict[str, Any] | None = None


class CircleClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.circle_enabled:
            raise RuntimeError("CIRCLE_API_KEY and CIRCLE_ENTITY_SECRET must be configured.")
        configure_ssl_cert_file()
        try:
            from circle.web3 import utils
        except ImportError as exc:
            raise RuntimeError(
                "Circle SDK is not installed. Install `circle-developer-controlled-wallets`."
            ) from exc

        self.client = utils.init_developer_controlled_wallets_client(
            api_key=self.settings.circle_api_key.get_secret_value(),
            entity_secret=self.settings.circle_entity_secret.get_secret_value(),
        )

    def create_wallet_set(self, name: str) -> str:
        from circle.web3.developer_controlled_wallets import WalletSetsApi, CreateWalletSetRequest
        api = WalletSetsApi(self.client)
        request = CreateWalletSetRequest.from_dict({"name": name})
        response = api.create_wallet_set(create_wallet_set_request=request)
        payload = response.to_dict().get("data", {})
        wallet_set = payload.get("walletSet") or payload.get("wallet_set") or {}
        wallet_set_id = wallet_set.get("id")
        if not wallet_set_id:
            raise RuntimeError(f"Wallet set creation succeeded but no wallet set id was returned: {payload}")
        return wallet_set_id

    def create_agent_wallet(self, wallet_set_id: str, ref_id: str, name: str) -> CircleProvisionedWallet:
        from circle.web3.developer_controlled_wallets import WalletsApi, CreateWalletRequest
        api = WalletsApi(self.client)
        request = CreateWalletRequest.from_dict(
            {
                "idempotencyKey": str(uuid.uuid4()),
                "accountType": self.settings.circle_account_type,
                "blockchains": [self.settings.arc_blockchain],
                "count": 1,
                "walletSetId": wallet_set_id,
                "metadata": [{"name": name, "refId": ref_id}],
            }
        )
        response = api.create_wallet(create_wallet_request=request)
        payload = response.to_dict().get("data", {})
        wallets = payload.get("wallets") or []
        if not wallets:
            raise RuntimeError(f"Wallet creation succeeded but no wallet payload was returned: {payload}")
        wallet = wallets[0]
        return CircleProvisionedWallet(
            circle_wallet_id=wallet["id"],
            address=wallet["address"],
            wallet_set_id=wallet.get("walletSetId") or wallet.get("wallet_set_id") or wallet_set_id,
            blockchain=wallet["blockchain"],
            account_type=wallet.get("accountType") or wallet.get("account_type") or self.settings.circle_account_type,
            metadata={"name": wallet.get("name", "") or name, "ref_id": wallet.get("refId") or wallet.get("ref_id") or ref_id},
        )

    def sign_typed_data(self, wallet_id: str, typed_data: dict[str, Any], memo: str) -> CircleSignedPayload:
        from circle.web3.developer_controlled_wallets import SigningApi, SignTypedDataRequest
        api = SigningApi(self.client)
        request = SignTypedDataRequest.from_dict(
            {
                "walletId": wallet_id,
                "data": json.dumps(typed_data),
                "memo": memo,
            }
        )
        response = api.sign_typed_data(sign_typed_data_request=request)
        return CircleSignedPayload(signature=response.data.signature, typed_data=typed_data, memo=memo)

    def create_transfer(
        self,
        wallet_id: str,
        destination_address: str,
        amount_usdc: str,
        ref_id: str,
    ) -> CircleTransferResult:
        from circle.web3.developer_controlled_wallets import TransactionsApi, CreateTransferTransactionForDeveloperRequest
        api = TransactionsApi(self.client)
        request = CreateTransferTransactionForDeveloperRequest.from_dict(
            {
                "amounts": [amount_usdc],
                "destinationAddress": destination_address,
                "feeLevel": self.settings.circle_fee_level,
                "tokenAddress": self.settings.arc_usdc_contract,
                "blockchain": self.settings.arc_blockchain,
                "walletId": wallet_id,
                "refId": ref_id,
                "idempotencyKey": str(uuid.uuid4()),
            }
        )
        response = api.create_developer_transaction_transfer(
            create_transfer_transaction_for_developer_request=request
        )
        payload = response.to_dict()["data"]
        return CircleTransferResult(
            transaction_id=payload["id"],
            state=payload["state"],
            tx_hash=payload.get("tx_hash"),
            raw=payload,
        )

    def get_transaction(self, transaction_id: str) -> dict[str, Any]:
        from circle.web3.developer_controlled_wallets import TransactionsApi
        api = TransactionsApi(self.client)
        response = api.get_transaction(id=transaction_id)
        return response.to_dict()["data"]["transaction"]


def format_usdc_amount(amount: float | str) -> str:
    quantized = Decimal(str(amount)).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
    return format(quantized, "f")


def get_circle_client() -> CircleClient:
    return CircleClient()
