"""eBay Marketplace Account Deletion notifications."""

import hashlib
import logging
import os
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from services.ebay_account_deletion import handle_ebay_account_deletion

router = APIRouter()
logger = logging.getLogger(__name__)


def _is_enabled() -> bool:
    return os.getenv("EBAY_MAD_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _get_verification_token() -> str:
    return os.getenv("EBAY_MAD_VERIFICATION_TOKEN", "").strip()


def _endpoint_url(request: Request) -> str:
    configured = os.getenv("EBAY_MAD_ENDPOINT_URL", "").strip()
    if configured:
        return configured
    return str(request.url).split("?", 1)[0]


@router.get("/ebay/account-deletion")
async def ebay_account_deletion_challenge(request: Request, challenge_code: str | None = None):
    """Handle eBay endpoint verification challenge."""
    if not _is_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    if not challenge_code:
        raise HTTPException(status_code=400, detail="Missing challenge_code")

    token = _get_verification_token()
    if not token:
        logger.error("EBAY_MAD_VERIFICATION_TOKEN is not set")
        raise HTTPException(status_code=500, detail="Server not configured")

    endpoint = _endpoint_url(request)
    digest = hashlib.sha256(f"{challenge_code}{token}{endpoint}".encode("utf-8")).hexdigest()
    return JSONResponse({"challengeResponse": digest})


@router.post("/ebay/account-deletion")
async def ebay_account_deletion_notification(request: Request, background_tasks: BackgroundTasks):
    """Receive account deletion notifications and schedule cleanup."""
    if not _is_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        payload = {}

    background_tasks.add_task(handle_ebay_account_deletion, payload)
    return Response(status_code=200)
