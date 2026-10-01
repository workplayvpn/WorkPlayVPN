"""Explicit rollout controls: empty disables, IDs select users, * enables all."""


def rollout_allowed(configured_ids: str, user_id: int) -> bool:
    values = {part.strip() for part in configured_ids.split(",") if part.strip()}
    return "*" in values or str(user_id) in values
