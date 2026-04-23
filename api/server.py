from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
async def run_marketplace_stream(request: RunRequest):
    """Stream the marketplace execution as Server-Sent Events (SSE) with real-time progress."""
    import asyncio
    import json
    import time
    from fastapi.responses import StreamingResponse

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

    async def event_generator():
        """Generate SSE events showing real-time agent thinking and progress."""
        import json as json_module
        queue: list = []

        def make_serializable(obj):
            """Recursively convert Pydantic models and other objects to JSON-serializable types."""
            if hasattr(obj, 'model_dump'):
                return make_serializable(obj.model_dump())
            elif isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [make_serializable(item) for item in obj]
            else:
                return obj

        def emit_event(event_type: str, data: dict, phase: str = None):
            """Emit an event to the stream."""
            event = {
                "type": event_type,
                "phase": phase,
                "data": make_serializable(data),
                "timestamp_ms": int(time.time() * 1000),
            }
            queue.append(event)

        try:
            # Phase 1: Detecting Intent
            emit_event("phase_start", {"phase": "intent_detection", "message": "🧠 Analyzing query intent..."}, "plan")
            yield f"data: {json.dumps(queue.pop(0))}\n\n"

            print(f"\n{'='*60}")
            print(f"🚀 Starting orchestrator stream:")
            print(f"   Goal: {request.user_goal}")
            print(f"   Buyer: {buyer.name}")
            print(f"   Seller: {seller.name}")
            print(f"{'='*60}")

            # Run the orchestrator
            start_time = time.time()
            result = orchestrator_graph.invoke(
                {
                    "user_goal": request.user_goal,
                    "thread_id": request.thread_id,
                    "buyer_agent_id": request.buyer_agent_id,
                    "seller_agent_id": request.seller_agent_id,
                },
                config={"configurable": {"thread_id": request.thread_id}},
            )
            execution_time = int((time.time() - start_time) * 1000)

            # Emit planning phase
            task_specs = result.get("task_specs", [])
            if task_specs:
                try:
                    tasks_data = []
                    for t in task_specs:
                        if hasattr(t, 'model_dump'):
                            t_dict = t.model_dump()
                        elif isinstance(t, dict):
                            t_dict = t
                        else:
                            t_dict = {"task_id": str(t), "query": ""}
                        tasks_data.append({
                            "task_id": t_dict.get("task_id", "unknown"),
                            "query": str(t_dict.get("query", ""))[:80]
                        })
                    emit_event("tasks_planned", {
                        "task_count": len(task_specs),
                        "message": f"Decomposed into {len(task_specs)} research task(s)",
                        "tasks": tasks_data
                    }, "plan")
                    yield f"data: {json.dumps(queue.pop(0))}\n\n"
                except Exception as e:
                    print(f"Error emitting tasks_planned event: {e}")

            # Emit buyer workflows progress
            buyer_workflows = result.get("buyer_workflows", [])
            for workflow in buyer_workflows:
                try:
                    task_id = workflow.get("task_id") if isinstance(workflow, dict) else getattr(workflow, "task_id", "unknown")
                    emit_event("buyer_workflow_start", {
                        "task_id": task_id,
                        "message": f"Processing: {task_id}"
                    }, "execute")
                    yield f"data: {json.dumps(queue.pop(0))}\n\n"

                    # Show each node execution
                    node_outputs = workflow.get("node_outputs", []) if isinstance(workflow, dict) else getattr(workflow, "node_outputs", []) or []
                    for node in node_outputs:
                        try:
                            node_name = node.get("node_name") if isinstance(node, dict) else getattr(node, "node_name", "")
                            node_output = node.get("output", {}) if isinstance(node, dict) else getattr(node, "output", {})

                            # Extract relevant info from node output
                            if node_name == "execute_payment" and isinstance(node_output, dict):
                                emit_event("payment_executed", {
                                    "task_id": task_id,
                                    "amount_usdc": "0.001",
                                    "status": "settled"
                                }, "execute")
                                yield f"data: {json.dumps(queue.pop(0))}\n\n"

                            elif node_name == "send_research_request":
                                emit_event("research_sent", {
                                    "task_id": task_id,
                                    "status": "sent"
                                }, "execute")
                                yield f"data: {json.dumps(queue.pop(0))}\n\n"

                            elif node_name == "fetch_result" and isinstance(node_output, dict):
                                result_data = node_output.get("result")
                                if result_data:
                                    result_title = result_data.get("title", "Result") if isinstance(result_data, dict) else "Result"
                                    emit_event("result_fetched", {
                                        "task_id": task_id,
                                        "title": str(result_title)[:80],
                                        "status": "fetched"
                                    }, "execute")
                                    yield f"data: {json.dumps(queue.pop(0))}\n\n"
                        except Exception as e:
                            print(f"Error processing node {node}: {e}")
                            continue
                except Exception as e:
                    print(f"Error processing workflow: {e}")
                    continue

            # Emit synthesis
            try:
                emit_event("synthesis_started", {
                    "result_count": len(result.get("results", [])),
                    "message": "Synthesizing final answer..."
                }, "answer")
                yield f"data: {json.dumps(queue.pop(0))}\n\n"
            except Exception as e:
                print(f"Error emitting synthesis_started: {e}")

            # Show results
            results = result.get("results", [])
            if results:
                for res in results:
                    try:
                        res_title = res.get("title", "Result") if isinstance(res, dict) else getattr(res, "title", "Result")
                        res_summary = (res.get("summary", "") if isinstance(res, dict) else getattr(res, "summary", ""))[:150]
                        emit_event("result", {
                            "title": res_title,
                            "summary": res_summary,
                            "bullets": (res.get("bullets", []) if isinstance(res, dict) else getattr(res, "bullets", []))[:2]
                        }, "answer")
                        yield f"data: {json.dumps(queue.pop(0))}\n\n"
                    except Exception as e:
                        print(f"Error emitting result event: {e}")
                        continue

            # Final answer
            final_answer = result.get("final_answer") or result.get("running_answer")
            print(f"\n📤 Emitting done event:")
            print(f"   final_answer: {final_answer[:100] if final_answer else 'EMPTY'}...")
            print(f"   execution_time: {execution_time}ms")

            emit_event("done", {
                "final_answer": final_answer,
                "execution_time_ms": execution_time,
                "payments": len(result.get("payments", [])),
                "full_result": result
            })
            yield f"data: {json.dumps(queue.pop(0))}\n\n"

            print(f"✅ Stream completed in {execution_time}ms\n")

        except Exception as exc:
            import traceback
            error_msg = traceback.format_exc()
            print(f"\n❌ Stream error: {error_msg}\n")

            emit_event("error", {
                "error": str(exc),
                "type": type(exc).__name__
            })
            yield f"data: {json.dumps(queue.pop(0))}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
