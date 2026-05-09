from typing import Annotated

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)


async def get_current_actor(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> str:
    """Return the bearer token as actor ID. Any non-empty token is accepted."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=403, detail="Missing or invalid bearer token")
    return credentials.credentials


ActorDepend = Annotated[str, Depends(get_current_actor)]
