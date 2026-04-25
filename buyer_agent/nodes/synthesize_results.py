from __future__ import annotations

import re

from buyer_agent.state import BuyerState
from shared.llm_client import BuyerLlmNotConfigured, get_buyer_openai_client


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
    task_errors = state.get("task_errors", [])
    agent_name = state.get("buyer_agent_name", "Buyer Agent")
    agent_description = state.get("buyer_agent_description", "")
    agent_system_prompt = state.get("buyer_agent_system_prompt", "")
    user_goal = state.get("user_goal", "").strip()

    print(f"  🔗 synthesize_results: {len(task_results)} result(s)")

    if not task_results:
        if task_errors:
            first_error = task_errors[0].get("message", "Task failed before synthesis")
            return {
                "error": first_error,
                "thinking": "No task results to synthesize because task execution failed",
            }
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

    try:
        client, llm_config = get_buyer_openai_client(state.get("buyer_agent_llm_config"))
    except BuyerLlmNotConfigured as exc:
        # Fallback: just concatenate results
        if task_errors:
            error_lines = "\n".join(f"- {error.get('message', 'Unknown task error')}" for error in task_errors)
            result_text = f"{result_text.strip()}\n\n**Errors**\n{error_lines}"
        return {
            "final_answer": result_text.strip() if result_text else "No synthesis available.",
            "thinking": f"{exc} Returning concatenated results.",
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

    try:
        completion = client.chat.completions.create(
            model=llm_config["model"],
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
            if task_errors:
                error_lines = "\n".join(f"- {error.get('message', 'Unknown task error')}" for error in task_errors)
                final_answer = f"{final_answer.strip()}\n\n**Errors**\n{error_lines}"
            print(f"    ✓ Synthesized answer ({len(final_answer)} chars)")
            return {"final_answer": final_answer, "thinking": ""}
        else:
            # Fallback: return concatenated results
            if task_errors:
                error_lines = "\n".join(f"- {error.get('message', 'Unknown task error')}" for error in task_errors)
                result_text = f"{result_text.strip()}\n\n**Errors**\n{error_lines}"
            return {
                "final_answer": result_text.strip() if result_text else "Synthesis failed.",
                "thinking": "LLM returned empty response",
            }

    except Exception as e:
        print(f"    ⚠️ Synthesis error: {e}")
        # Fallback: return concatenated results
        if task_errors:
            error_lines = "\n".join(f"- {error.get('message', 'Unknown task error')}" for error in task_errors)
            result_text = f"{result_text.strip()}\n\n**Errors**\n{error_lines}"
        return {
            "final_answer": result_text.strip() if result_text else f"Synthesis error: {str(e)}",
            "thinking": f"Synthesis error: {str(e)}",
        }
