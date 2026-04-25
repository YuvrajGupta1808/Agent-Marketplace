from __future__ import annotations

import operator
from typing import Annotated

from typing_extensions import TypedDict

from shared.types import BuyerWorkflowRecord, PaymentRecord, ResearchResult, TaskSpec


class OrchestratorState(TypedDict, total=False):
    user_goal: str
    thread_id: str
    buyer_agent_id: str
    seller_agent_id: str | None
    results: Annotated[list[ResearchResult], operator.add]
    buyer_workflows: Annotated[list[BuyerWorkflowRecord], operator.add]
    failed_tasks: Annotated[list[str], operator.add]
    transaction_hashes: Annotated[list[str], operator.add]
    payments: Annotated[list[PaymentRecord], operator.add]
    final_answer: str | None
    error: str | None
    pending_question: str | None
    clarification_answer: str | None
