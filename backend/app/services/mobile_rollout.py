from app.core.config import settings
from app.services.rollout_access import rollout_allowed


def mobile_pilot_allowed(user_id: int) -> bool:
    """Keep the historical name; * explicitly opens Mobile purchases to all."""
    return rollout_allowed(settings.mobile_pilot_user_ids, user_id)
