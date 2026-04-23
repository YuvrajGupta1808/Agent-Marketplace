from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langgraph.types import Command

try:
    from circle.web3.configurations.exceptions import ApiException as CircleConfigApiException
    from circle.web3.developer_controlled_wallets.exceptions import (
        ApiException as CircleWalletApiException,
    )
    from circle.web3.developer_controlled_wallets.exceptions import BadRequestException as CircleWalletBadRequestException
except ImportError:
    # Circle SDK not installed - use fallback
    CircleConfigApiException = Exception  # type: ignore
    CircleWalletApiException = Exception  # type: ignore
    CircleWalletBadRequestException = Exception  # type: ignore

from orchestrator.graph import orchestrator_graph
from shared.circle_client import get_circle_client
from shared.config import get_settings
from shared.provisioning import ensure_circle_wallet_set_id
from shared.repository import repository
from shared.ssl import configure_ssl_cert_file
from shared.types import (
    CreateAgentRequest,
    CreateAgentResponse,
    CreateUserRequest,
    CreateUserResponse,
    PaymentRecord,
    ResumeRequest,
    RunRequest,
    RunResponse,
)

configure_ssl_cert_file()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    repository  # initialize DB on startup
    yield


app = FastAPI(title="Agent Marketplace API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/users", response_model=CreateUserResponse)
def create_user(request: CreateUserRequest) -> CreateUserResponse:
    user = repository.create_user(request)
    return CreateUserResponse(user=user)


@app.get("/users")
def list_users() -> list[dict]:
    return [user.model_dump() for user in repository.list_users()]


@app.get("/users/{user_id}")
def get_user(user_id: str) -> dict:
    try:
        return repository.get_user(user_id).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/agents", response_model=CreateAgentResponse)
def create_agent(request: CreateAgentRequest) -> CreateAgentResponse:
    try:
        repository.get_user(request.user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    settings = get_settings()
    endpoint_url = request.endpoint_url
    if request.role == "seller" and not endpoint_url:
        endpoint_url = f"{settings.seller_base_url}{settings.seller_research_path}"

    if not settings.circle_enabled:
        raise HTTPException(
            status_code=400,
            detail="Circle credentials not configured. Real Circle wallets are required.",
        )

    try:
        wallet_set_id = ensure_circle_wallet_set_id()
        wallet = get_circle_client().create_agent_wallet(
            wallet_set_id=wallet_set_id,
            ref_id=f"{request.role}:{request.user_id}",
            name=request.name,
        )
    except (CircleWalletBadRequestException, CircleWalletApiException, CircleConfigApiException) as exc:
        raise HTTPException(status_code=400, detail=f"Circle wallet creation failed: {exc}") from exc
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Wallet provisioning failed: {type(exc).__name__}: {str(exc)}") from exc

    agent = repository.create_agent(request.model_copy(update={"endpoint_url": endpoint_url}), wallet)
    return CreateAgentResponse(agent=agent)


@app.get("/agents")
def list_agents(
    user_id: str | None = None,
    role: str | None = None,
) -> list[dict]:
    return [
        agent.model_dump()
        for agent in repository.list_agents(user_id=user_id, role=role)
    ]


@app.get("/agents/{agent_id}")
def get_agent(agent_id: str) -> dict:
    try:
        return repository.get_agent(agent_id).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/users/{user_id}/agents")
def list_user_agents(
    user_id: str,
    role: str | None = None,
) -> list[dict]:
    try:
        repository.get_user(user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [
        agent.model_dump()
        for agent in repository.list_agents(user_id=user_id, role=role)
    ]


def _poll_payment_status(circle_tx_id: str, max_retries: int = 3, retry_delay: float = 0.5) -> tuple[str | None, str]:
    import time
    state = "INITIATED"
    tx_hash = None
    for attempt in range(max_retries):
        try:
            tx = get_circle_client().get_transaction(circle_tx_id)
            state = tx.get("state", "INITIATED")
            tx_hash = tx.get("txHash") or tx.get("tx_hash")
            if state in ("CONFIRMED", "FAILED", "DENIED"):
                break
        except Exception:
            pass
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
    return tx_hash, state


@app.get("/health")
def health_check() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "circle_enabled": settings.circle_enabled,
        "research_mode": settings.research_mode,
        "seller_price_usdc": settings.seller_price_usdc,
    }


@app.post("/run", response_model=RunResponse)
def run_marketplace(request: RunRequest) -> RunResponse:
    # Validate agents exist
    try:
        buyer = repository.get_agent(request.buyer_agent_id)
        seller = repository.get_agent(request.seller_agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Agent not found: {exc}") from exc

    if buyer.role != "buyer":
        raise HTTPException(status_code=400, detail="buyer_agent_id must reference a buyer agent.")
    if seller.role != "seller":
        raise HTTPException(status_code=400, detail="seller_agent_id must reference a seller agent.")

    try:
        print(f"\n🚀 Starting orchestrator with:")
        print(f"   Goal: {request.user_goal}")
        print(f"   Buyer: {request.buyer_agent_id}")
        print(f"   Seller: {request.seller_agent_id}")
        print(f"   Thread: {request.thread_id}\n")

        result = orchestrator_graph.invoke(
            {
                "user_goal": request.user_goal,
                "thread_id": request.thread_id,
                "buyer_agent_id": request.buyer_agent_id,
                "seller_agent_id": request.seller_agent_id,
            },
            config={"configurable": {"thread_id": request.thread_id}},
        )
        print(f"✅ Orchestrator completed successfully\n")

    except (CircleWalletBadRequestException, CircleWalletApiException, CircleConfigApiException) as exc:
        import traceback
        error_msg = traceback.format_exc()
        print(f"\n❌ CIRCLE ERROR:\n{error_msg}\n")
        raise HTTPException(status_code=400, detail=f"Marketplace run failed: {exc}") from exc

    except Exception as exc:
        import traceback
        error_msg = traceback.format_exc()
        print(f"\n❌ ORCHESTRATOR ERROR:\n{error_msg}\n")
        print(f"Exception type: {type(exc).__name__}")
        print(f"Exception args: {exc.args}")
        print(f"Full exception: {str(exc)}\n")
        raise HTTPException(status_code=500, detail=f"Orchestrator error: {type(exc).__name__}: {str(exc)}") from exc

    # Poll Circle for payment confirmations if Circle is enabled
    payments = result.get("payments", [])
    tx_hashes = result.get("transaction_hashes", [])
    settings = get_settings()

    # Convert PaymentRecord objects to dicts if needed, then poll for updates
    if payments and settings.circle_enabled:
        payment_dicts = []
        for pmt in payments:
            # Convert Pydantic model to dict if needed
            pmt_dict = pmt.model_dump() if hasattr(pmt, 'model_dump') else dict(pmt)

            # Poll for transaction status
            if pmt_dict.get("circle_transaction_id") and not pmt_dict.get("tx_hash"):
                tx_hash, state = _poll_payment_status(pmt_dict["circle_transaction_id"])
                if tx_hash:
                    pmt_dict["tx_hash"] = tx_hash
                    if tx_hash not in tx_hashes:
                        tx_hashes.append(tx_hash)
                pmt_dict["state"] = state

            payment_dicts.append(pmt_dict)
        payments = payment_dicts

    # Save transactions to database
    for payment in payments:
        for task_spec in result.get("task_specs", []):
            repository.save_transaction(
                thread_id=request.thread_id,
                task_id=task_spec.get("task_id") if isinstance(task_spec, dict) else task_spec.task_id,
                buyer_agent_id=request.buyer_agent_id,
                seller_agent_id=request.seller_agent_id,
                payment=payment if isinstance(payment, dict) else payment.model_dump(),
            )

    return RunResponse(
        thread_id=request.thread_id,
        final_answer=result.get("final_answer"),
        running_answer=result.get("running_answer"),
        query_intent=result.get("query_intent", "research"),
        is_conversational=result.get("is_conversational", False),
        task_specs=result.get("task_specs", []),
        results=result.get("results", []),
        buyer_workflows=result.get("buyer_workflows", []),
        transaction_hashes=tx_hashes,
        payments=payments,
        failed_tasks=result.get("failed_tasks", []),
        pending_question=result.get("pending_question"),
    )


@app.post("/run/stream")
def run_marketplace_stream(request: RunRequest) -> StreamingResponse:
    """Stream execution updates in real-time using Server-Sent Events."""
    try:
        buyer = repository.get_agent(request.buyer_agent_id)
        seller = repository.get_agent(request.seller_agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Agent not found: {exc}") from exc

    if buyer.role != "buyer":
        raise HTTPException(status_code=400, detail="buyer_agent_id must reference a buyer agent.")
    if seller.role != "seller":
        raise HTTPException(status_code=400, detail="seller_agent_id must reference a seller agent.")

    def _make_serializable(obj):
        """Convert non-serializable objects to JSON-safe format."""
        if hasattr(obj, 'model_dump'):
            return obj.model_dump()
        elif isinstance(obj, dict):
            return {k: _make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [_make_serializable(item) for item in obj]
        else:
            try:
                json.dumps(obj)
                return obj
            except (TypeError, ValueError):
                return str(obj)

    def event_generator():
        final_result = None
        try:
            print(f"\n🚀 Starting streaming orchestrator with:")
            print(f"   Goal: {request.user_goal}")
            print(f"   Buyer: {request.buyer_agent_id}")
            print(f"   Seller: {request.seller_agent_id}")
            print(f"   Thread: {request.thread_id}\n")

            for chunk in orchestrator_graph.stream(
                {
                    "user_goal": request.user_goal,
                    "thread_id": request.thread_id,
                    "buyer_agent_id": request.buyer_agent_id,
                    "seller_agent_id": request.seller_agent_id,
                },
                config={"configurable": {"thread_id": request.thread_id}},
                stream_mode=["updates", "custom"],
                version="v2",
            ):
                if chunk["type"] == "updates":
                    for node_name, state in chunk["data"].items():
                        # Capture final result from synthesize_answer node
                        if node_name == "synthesize_answer":
                            final_result = state

                        event_data = {
                            "type": "node_update",
                            "node": node_name,
                            "data": _make_serializable(state),
                        }
                        try:
                            yield f"data: {json.dumps(event_data)}\n\n"
                        except Exception as e:
                            print(f"  ⚠️ Failed to serialize update: {e}")

                elif chunk["type"] == "custom":
                    event_data = {
                        "type": "custom_event",
                        "data": _make_serializable(chunk["data"]),
                    }
                    try:
                        yield f"data: {json.dumps(event_data)}\n\n"
                    except Exception as e:
                        print(f"  ⚠️ Failed to serialize custom event: {e}")

            print(f"✅ Orchestrator completed successfully\n")

            # Save transactions to database (same as /run endpoint)
            if final_result:
                payments = final_result.get("payments", [])
                task_specs = final_result.get("task_specs", [])

                if payments and task_specs:
                    # Convert PaymentRecord objects to dicts if needed
                    payment_dicts = []
                    for pmt in payments:
                        pmt_dict = pmt.model_dump() if hasattr(pmt, 'model_dump') else dict(pmt)
                        payment_dicts.append(pmt_dict)

                    # Save each payment-task combination to database
                    for payment in payment_dicts:
                        for task_spec in task_specs:
                            task_id = task_spec.get("task_id") if isinstance(task_spec, dict) else task_spec.task_id
                            try:
                                repository.save_transaction(
                                    thread_id=request.thread_id,
                                    task_id=task_id,
                                    buyer_agent_id=request.buyer_agent_id,
                                    seller_agent_id=request.seller_agent_id,
                                    payment=payment if isinstance(payment, dict) else payment.model_dump(),
                                )
                                print(f"  ✓ Saved transaction for task {task_id}")
                            except Exception as e:
                                print(f"  ⚠️ Failed to save transaction: {e}")

            # Emit final result with the answer
            if final_result:
                final_answer = final_result.get("final_answer") or final_result.get("running_answer")
                if final_answer:
                    yield f"data: {json.dumps({'type': 'final_answer', 'answer': final_answer})}\n\n"

            yield f"data: {json.dumps({'type': 'stream_complete'})}\n\n"

        except (CircleWalletBadRequestException, CircleWalletApiException, CircleConfigApiException) as exc:
            import traceback
            error_msg = traceback.format_exc()
            print(f"\n❌ CIRCLE ERROR:\n{error_msg}\n")
            yield f"data: {json.dumps({'type': 'error', 'error': f'Circle error: {exc}'})}\n\n"

        except Exception as exc:
            import traceback
            error_msg = traceback.format_exc()
            print(f"\n❌ ORCHESTRATOR ERROR:\n{error_msg}\n")
            yield f"data: {json.dumps({'type': 'error', 'error': f'Orchestrator error: {type(exc).__name__}: {str(exc)}'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/transactions")
def get_transactions(thread_id: str | None = None, buyer_agent_id: str | None = None) -> dict:
    """Fetch transactions, optionally filtered by thread or buyer agent."""
    transactions = repository.list_transactions(thread_id=thread_id, buyer_agent_id=buyer_agent_id)
    return {
        "total": len(transactions),
        "transactions": transactions,
    }


@app.post("/resume", response_model=RunResponse)
def resume_marketplace(request: ResumeRequest) -> RunResponse:
    result = orchestrator_graph.invoke(
        Command(resume=request.answer),
        config={"configurable": {"thread_id": request.thread_id}},
    )
    return RunResponse(
        thread_id=request.thread_id,
        final_answer=result.get("final_answer"),
        running_answer=result.get("running_answer"),
        query_intent=result.get("query_intent", "research"),
        is_conversational=result.get("is_conversational", False),
        task_specs=result.get("task_specs", []),
        results=result.get("results", []),
        buyer_workflows=result.get("buyer_workflows", []),
        transaction_hashes=result.get("transaction_hashes", []),
        payments=result.get("payments", []),
        failed_tasks=result.get("failed_tasks", []),
        pending_question=result.get("pending_question"),
    )


@app.get("/payments")
def list_all_payments() -> list[dict]:
    """Get all historical payments - stored in memory during session."""
    # Payments are accumulated during orchestrator runs
    # This endpoint returns what was captured in the last run
    # Full history is maintained in localStorage on the frontend
    return []


@app.get("/payments/{circle_transaction_id}")
def check_payment(circle_transaction_id: str) -> dict:
    if not get_settings().circle_enabled:
        return {
            "transaction_id": circle_transaction_id,
            "state": "STUB_MODE",
            "tx_hash": None,
            "amounts": [],
            "destination": None,
            "blockchain": None,
            "raw": {},
        }
    try:
        tx = get_circle_client().get_transaction(circle_transaction_id)
        return {
            "transaction_id": circle_transaction_id,
            "state": tx.get("state", "UNKNOWN"),
            "tx_hash": tx.get("txHash") or tx.get("tx_hash"),
            "amounts": tx.get("amounts", []),
            "destination": tx.get("destinationAddress") or tx.get("destination_address"),
            "blockchain": tx.get("blockchain"),
            "raw": tx,
        }
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
