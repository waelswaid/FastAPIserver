from datetime import datetime, timezone
from typing import Any, Dict

from app.repositories.token_blacklist_repository import add_to_blacklist


async def blacklist_jwt(payload: Dict[str, Any]) -> None:
    """Blacklist a token by its decoded payload.

    Assumes `jti` and `exp` are present — PyJWT verifies these on decode for
    every token type used here. Callers that need to handle missing fields
    (e.g. logout's strict access-token check) do so themselves before calling
    this helper.
    """
    jti = payload["jti"]
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    await add_to_blacklist(jti, expires_at)
