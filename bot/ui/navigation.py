"""Carry the originating subscription in callback data, including after restarts."""


def subscription_tier(data):
    value = (data or "").rsplit(":", 1)[-1]
    return value if value in ("basic", "mobile") else None


def scoped_action(action, tier):
    return f"{action}:{tier}" if tier in ("basic", "mobile") else action


def subscription_back(tier):
    return scoped_action("subscription_tier", tier) if tier else "subscription"
