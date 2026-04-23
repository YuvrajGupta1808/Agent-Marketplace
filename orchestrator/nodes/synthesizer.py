from __future__ import annotations

from openai import OpenAI

from orchestrator.prompts import SYNTHESIZER_SYSTEM_PROMPT
from orchestrator.state import OrchestratorState
from shared.config import get_settings


def _synthesize_with_llm(goal: str, results: list, user_goal: str) -> str:
    settings = get_settings()
    if not settings.live_llm_enabled:
        return None

    try:
        result_text = "\n".join([
            f"- {result.title if hasattr(result, 'title') else result.get('title', 'Result')}: "
            f"{result.summary if hasattr(result, 'summary') else result.get('summary', '')}"
            for result in results
        ])

        client = OpenAI(
            api_key=settings.featherless_api_key.get_secret_value(),
            base_url=settings.featherless_base_url,
        )
        completion = client.chat.completions.create(
            model=settings.orchestrator_model,
            messages=[
                {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"User goal: {user_goal}\n\nResearch results:\n{result_text}",
                },
            ],
            max_tokens=512,
            temperature=0.3,
        )
        return completion.choices[0].message.content or None
    except Exception:
        return None


def synthesize_answer(state: OrchestratorState) -> dict:
    user_goal = state.get("user_goal", "")
    results = state.get("results", [])
    failed_tasks = state.get("failed_tasks", [])

    if state.get("is_conversational") and state.get("direct_answer"):
        running_answer = state.get("direct_answer")
        final_answer = running_answer
        return {
            "running_answer": running_answer,
            "final_answer": final_answer,
        }

    if not results:
        final_answer = "No research results were found."
        return {
            "running_answer": final_answer,
            "final_answer": final_answer,
        }

    llm_synthesis = _synthesize_with_llm(user_goal, results, user_goal)
    if llm_synthesis:
        running_answer = llm_synthesis
    else:
        lines = []
        if user_goal:
            lines.append(f"**Research Goal:** {user_goal}\n")

        if results:
            for i, result in enumerate(results, 1):
                title = result.title if hasattr(result, "title") else result.get("title", "Result")
                summary = result.summary if hasattr(result, "summary") else result.get("summary", "")
                bullets = result.bullets if hasattr(result, "bullets") else result.get("bullets", [])
                citations = result.citations if hasattr(result, "citations") else result.get("citations", [])

                lines.append(f"### Result {i}: {title}")
                if summary:
                    lines.append(f"\n{summary}\n")

                if bullets:
                    lines.append("**Key Points:**")
                    for bullet in bullets:
                        lines.append(f"- {bullet}")
                    lines.append("")

                if citations:
                    lines.append("**Sources:**")
                    for cite in citations:
                        cite_title = cite.title if hasattr(cite, "title") else cite.get("title", "Source")
                        cite_url = cite.url if hasattr(cite, "url") else cite.get("url", "#")
                        lines.append(f"- [{cite_title}]({cite_url})")
                    lines.append("")

        if failed_tasks:
            lines.append(f"\n⚠️ **Note:** Some research tasks failed: {', '.join(failed_tasks)}")

        running_answer = "\n".join(lines).strip() if lines else "No results available."

    finished = len(results) + len(failed_tasks)
    expected = len(state.get("task_specs", []))
    final_answer = running_answer if expected and finished >= expected else None

    return {
        "running_answer": running_answer,
        "final_answer": final_answer,
    }

