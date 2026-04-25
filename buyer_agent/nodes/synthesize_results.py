from __future__ import annotations

import re

from openai import OpenAI

from buyer_agent.state import BuyerState
from shared.config import get_settings


def _strip_synthesized_answer_prefix(answer: str) -> str:
    cleaned = re.sub(
        r"^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*synthesi[sz]ed answer\s*:?\s*(?:\*\*)?\s*:?\s*",
        "",
        answer,
        count=1,
        flags=re.IGNORECASE,
    ).lstrip()
    return cleaned or answer.strip()


def synthesize_results(state: BuyerState) -> dict:
    """Synthesize task results into a final answer using buyer agent's voice."""
    task_results = state.get("task_results", [])
    agent_name = state.get("buyer_agent_name", "Buyer Agent")
    agent_description = state.get("buyer_agent_description", "")
    agent_system_prompt = state.get("buyer_agent_system_prompt", "")
    user_goal = state.get("user_goal", "").strip()

    print(f"  🔗 synthesize_results: {len(task_results)} result(s)")

    if not task_results:
        return {
            "final_answer": "No results were available to synthesize. All tasks may have failed.",
            "thinking": "No task results to synthesize",
        }

    # Build result summary from all task results
    result_text = ""
    for i, result in enumerate(task_results, 1):
        if isinstance(result, dict):
            title = result.get("title", f"Task {i} Result")
            summary = result.get("summary", "")
            result_text += f"\n\n**{i}. {title}**\n{summary}"

    settings = get_settings()
    if not settings.live_llm_enabled or not task_results:
        # Fallback: just concatenate results
        return {
            "final_answer": result_text.strip() if result_text else "No synthesis available.",
            "thinking": "LLM not available or no results, returning concatenated results",
        }

    # Build system message from agent identity
    system_message = f"You are {agent_name}"
    if agent_description:
        system_message += f": {agent_description}"
    system_message += ".\n\n"
    if agent_system_prompt:
        system_message += f"Your instructions: {agent_system_prompt}\n\n"

    system_message += """Synthesize the following research results into a single comprehensive answer to the user's goal.
Integrate findings, highlight key insights, and respond in your voice.
Do not begin with a meta label such as "Synthesized Answer:". Start with the answer content itself.
"""

    client = OpenAI(
        api_key=settings.featherless_api_key.get_secret_value(),
        base_url=settings.featherless_base_url,
    )

    try:
        completion = client.chat.completions.create(
            model=settings.orchestrator_model,
            messages=[
                {"role": "system", "content": system_message},
                {
                    "role": "user",
                    "content": f"Original goal: {user_goal}\n\n Research results:\n{result_text}\n\nProvide a synthesized answer.",
                },
            ],
            max_tokens=2048,
            temperature=0.3,
        )

        final_answer = _strip_synthesized_answer_prefix(completion.choices[0].message.content or "")
        if final_answer:
            print(f"    ✓ Synthesized answer ({len(final_answer)} chars)")
            return {"final_answer": final_answer, "thinking": ""}
        else:
            # Fallback: return concatenated results
            return {
                "final_answer": result_text.strip() if result_text else "Synthesis failed.",
                "thinking": "LLM returned empty response",
            }

    except Exception as e:
        print(f"    ⚠️ Synthesis error: {e}")
        # Fallback: return concatenated results
        return {
            "final_answer": result_text.strip() if result_text else f"Synthesis error: {str(e)}",
            "thinking": f"Synthesis error: {str(e)}",
        }
