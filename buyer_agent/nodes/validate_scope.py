from __future__ import annotations

from openai import OpenAI

from buyer_agent.state import BuyerState
from buyer_agent.utils import extract_json
from shared.config import get_settings


def validate_scope(state: BuyerState) -> dict:
    """Validate if the user goal is within the buyer agent's scope/capabilities."""
    user_goal = state.get("user_goal", "").strip()
    query = state.get("query", user_goal).strip()
    agent_name = state.get("buyer_agent_name", "Buyer Agent")
    agent_description = state.get("buyer_agent_description", "")
    agent_system_prompt = state.get("buyer_agent_system_prompt", "")

    print(f"  ✓ validate_scope: '{query[:50]}'")

    settings = get_settings()
    if not settings.live_llm_enabled:
        # If LLM not available, accept the goal (conservative fallback)
        return {
            "within_scope": True,
            "scope_rejection_reason": "",
            "thinking": "LLM not available, accepting goal by default",
        }

    # Build system message from agent identity
    system_message = f"You are {agent_name}.\n"
    if agent_description:
        system_message += f"Your use case: {agent_description}\n"
    if agent_system_prompt:
        system_message += f"Your instructions: {agent_system_prompt}\n"

    system_message += """
Your job is to decide if the following user goal is something you can handle based on your use case and capabilities.

Be STRICT: if the goal is clearly outside your defined use case, say so.
If the goal is ambiguous but plausibly related to your use case, accept it.

Return ONLY valid JSON:
{
    "within_scope": true/false,
    "reason": "brief explanation"
}"""

    client = OpenAI(
        api_key=settings.featherless_api_key.get_secret_value(),
        base_url=settings.featherless_base_url,
    )

    try:
        completion = client.chat.completions.create(
            model=settings.orchestrator_model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": f"User goal: {query}\n\nCan you handle this?"},
            ],
            max_tokens=256,
            temperature=0.3,
        )

        content = completion.choices[0].message.content or ""
        if not content:
            return {
                "within_scope": True,
                "scope_rejection_reason": "",
                "thinking": "LLM returned empty, accepting by default",
            }

        try:
            result = extract_json(content)
        except ValueError:
            return {
                "within_scope": True,
                "scope_rejection_reason": "",
                "thinking": "Failed to parse LLM response, accepting by default",
            }

        within_scope = result.get("within_scope", True)
        reason = result.get("reason", "")

        if within_scope:
            print(f"    ✓ Goal is within scope")
            return {
                "within_scope": True,
                "scope_rejection_reason": "",
                "thinking": reason,
            }
        else:
            print(f"    ✗ Goal is out of scope: {reason}")
            return {
                "within_scope": False,
                "scope_rejection_reason": reason,
                "thinking": reason,
            }

    except Exception as e:
        print(f"    ⚠️ Validation error: {e}, accepting by default")
        return {
            "within_scope": True,
            "scope_rejection_reason": "",
            "thinking": f"Validation error: {str(e)}",
        }
