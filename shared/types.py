from __future__ import annotations

from typing import Any
from typing import Literal

from pydantic import BaseModel, Field


class TaskSpec(BaseModel):
    task_id: str
    query: str
    objective: str = "Research and return a concise, cited answer."


class ResearchCitation(BaseModel):
    title: str
    url: str
    snippet: str


class ResearchResult(BaseModel):
    task_id: str
    title: str
    summary: str
    bullets: list[str] = Field(default_factory=list)
    citations: list[ResearchCitation] = Field(default_factory=list)
    tx_hash: str | None = None
    circle_transaction_id: str | None = None
    amount_usdc: str | None = None
    seller_name: str = "seller-agent"
    seller_endpoint: str | None = None
    is_ambiguous: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class UserRecord(BaseModel):
    id: str
    external_id: str | None = None
    display_name: str
    created_at: str


class WalletRecord(BaseModel):
    id: str
    owner_type: str
    owner_id: str
    circle_wallet_id: str
    wallet_set_id: str
    blockchain: str
    account_type: str
    address: str
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentRecord(BaseModel):
    id: str
    user_id: str
    role: Literal["buyer", "seller"]
    name: str
    endpoint_url: str | None = None
    created_at: str
    wallet: WalletRecord
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateUserRequest(BaseModel):
    display_name: str
    external_id: str | None = None


class CreateAgentRequest(BaseModel):
    user_id: str
    role: Literal["buyer", "seller"]
    name: str
    endpoint_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchRequest(BaseModel):
    task_id: str
    query: str
    buyer_agent_id: str
    seller_agent_id: str


class RunRequest(BaseModel):
    user_goal: str
    buyer_agent_id: str
    seller_agent_id: str
    thread_id: str = "demo-thread"


class ResumeRequest(BaseModel):
    thread_id: str
    answer: str


class PaymentRecord(BaseModel):
    task_id: str
    circle_transaction_id: str
    amount_usdc: str
    tx_hash: str | None = None
    state: str = "INITIATED"
    created_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphNodeOutput(BaseModel):
    node_name: str
    title: str
    phase: str = "execute"
    status: str = "done"
    duration_ms: int | None = None
    reasoning: str = ""
    input_state: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    state_after: dict[str, Any] = Field(default_factory=dict)


class BuyerWorkflowRecord(BaseModel):
    task_id: str
    execution_plan: list[str] = Field(default_factory=list)
    node_outputs: list[GraphNodeOutput] = Field(default_factory=list)


class RunResponse(BaseModel):
    thread_id: str
    final_answer: str | None = None
    running_answer: str | None = None
    query_intent: str = "research"
    is_conversational: bool = False
    task_specs: list[TaskSpec] = Field(default_factory=list)
    results: list[ResearchResult] = Field(default_factory=list)
    buyer_workflows: list[BuyerWorkflowRecord] = Field(default_factory=list)
    transaction_hashes: list[str] = Field(default_factory=list)
    payments: list[PaymentRecord] = Field(default_factory=list)
    failed_tasks: list[str] = Field(default_factory=list)
    pending_question: str | None = None


class CreateUserResponse(BaseModel):
    user: UserRecord


class CreateAgentResponse(BaseModel):
    agent: AgentRecord
