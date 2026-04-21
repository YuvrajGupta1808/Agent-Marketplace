from __future__ import annotations

from orchestrator.state import OrchestratorState


def synthesize_answer(state: OrchestratorState) -> dict:
    results = state.get("results", [])
    failed_tasks = state.get("failed_tasks", [])
    user_goal = state.get("user_goal", "")

    # Build final answer from all research results
    lines = []

    # Add goal context
    if user_goal:
        lines.append(f"**Research Goal:** {user_goal}\n")

    # Add all research results
    if results:
        for i, result in enumerate(results, 1):
            # Handle both ResearchResult objects and dicts
            title = result.title if hasattr(result, "title") else result.get("title", "Result")
            summary = result.summary if hasattr(result, "summary") else result.get("summary", "")
            bullets = result.bullets if hasattr(result, "bullets") else result.get("bullets", [])
            citations = result.citations if hasattr(result, "citations") else result.get("citations", [])

            lines.append(f"### Result {i}: {title}")
            if summary:
                lines.append(f"\n{summary}\n")

            # Add bullets if available
            if bullets:
                lines.append("**Key Points:**")
                for bullet in bullets:
                    lines.append(f"- {bullet}")
                lines.append("")

            # Add citations if available
            if citations:
                lines.append("**Sources:**")
                for cite in citations:
                    cite_title = cite.title if hasattr(cite, "title") else cite.get("title", "Source")
                    cite_url = cite.url if hasattr(cite, "url") else cite.get("url", "#")
                    lines.append(f"- [{cite_title}]({cite_url})")
                lines.append("")

    # Add failure notice if any tasks failed
    if failed_tasks:
        lines.append(f"\n⚠️ **Note:** Some research tasks failed: {', '.join(failed_tasks)}")

    running_answer = "\n".join(lines).strip() if lines else None

    # Only set final_answer when all tasks are complete
    finished = len(results) + len(failed_tasks)
    expected = len(state.get("task_specs", []))
    final_answer = running_answer if expected and finished >= expected else None

    return {
        "running_answer": running_answer,
        "final_answer": final_answer,
    }

