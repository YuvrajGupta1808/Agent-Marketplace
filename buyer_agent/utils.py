from __future__ import annotations

import json
import re


def extract_json(content: str) -> dict:
    """Robustly extract JSON from LLM response."""
    cleaned = content.strip()
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()

    if "```" in cleaned:
        parts = cleaned.split("```")
        cleaned = next((part for part in parts if "{" in part), cleaned)
        cleaned = cleaned.replace("json", "", 1).strip()

    def try_parse(s: str) -> dict | None:
        try:
            return json.loads(s)
        except (json.JSONDecodeError, ValueError):
            return None

    result = try_parse(cleaned)
    if result:
        return result

    result = try_parse(re.sub(r',(\s*[}\]])', r'\1', cleaned))
    if result:
        return result

    balanced = cleaned.rstrip('}') + '}' * max(0, cleaned.count('{') - cleaned.count('}'))
    result = try_parse(balanced)
    if result:
        return result

    depth = 0
    in_string = False
    escape = False
    start = -1

    for i, char in enumerate(cleaned):
        if escape:
            escape = False
            continue
        if char == '\\' and in_string:
            escape = True
            continue
        if char == '"' and (i == 0 or cleaned[i-1] != '\\'):
            in_string = not in_string
            continue
        if not in_string:
            if char == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0 and start != -1:
                    json_str = cleaned[start:i+1]
                    result = try_parse(json_str)
                    if result:
                        return result

    raise ValueError(f"Failed to parse JSON after all recovery attempts. Original: {content[:300]}...")
