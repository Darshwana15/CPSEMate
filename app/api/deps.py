from fastapi import Header, HTTPException
from app.core.config import settings


def get_current_reviewer(x_reviewer_token: str | None = Header(None)) -> str:
    """
    MVP authentication for human review endpoints.
    Requires X-Reviewer-Token header and accepts any configured reviewer token.
    """
    if not x_reviewer_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if x_reviewer_token not in settings.reviewer_tokens:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return "human_reviewer"
