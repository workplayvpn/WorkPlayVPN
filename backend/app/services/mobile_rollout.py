from app.core.config import settings


def mobile_pilot_allowed(user_id: int) -> bool:
    """Mobile purchases stay closed unless the database user is listed."""
    return str(user_id) in {
        item.strip()
        for item in settings.mobile_pilot_user_ids.split(",")
        if item.strip().isdigit()
    }
