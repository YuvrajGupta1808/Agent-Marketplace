from __future__ import annotations

from pathlib import Path


def upsert_env_values(path: str | Path, values: dict[str, str]) -> None:
    env_path = Path(path)
    existing_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    pending = dict(values)
    updated: list[str] = []

    for line in existing_lines:
        if "=" not in line or line.lstrip().startswith("#"):
            updated.append(line)
            continue

        key, _, _ = line.partition("=")
        if key in pending:
            updated.append(f"{key}={pending.pop(key)}")
        else:
            updated.append(line)

    for key, value in pending.items():
        updated.append(f"{key}={value}")

    env_path.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")

