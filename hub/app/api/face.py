# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Server-rendered htmx face for solo play.

The face is intentionally not an API: every HTML route is excluded from
OpenAPI. It talks to the same ``CampaignRepository`` and ``SoloLoop`` the
Android spoke uses. htmx handles navigation, campaign creation, and dashboard
refreshes; the turn itself is an SSE response parsed by ``face.js`` so the
browser sees dice/HP/narration as they resolve instead of waiting for a
buffered JSON body.

Auth is a browser-friendly wrapper over the existing API key: the login form
verifies ``PFGOD_API_KEY`` against the configured SHA-256, then stores only a
random in-process session token in an HttpOnly cookie. Header auth still works
for tests and CLI clients. Keyless local installs are allowed, matching the
hub's existing local-only mode.
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from contextlib import suppress
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from fastapi.templating import Jinja2Templates

from app.api.campaign import build_solo_loop
from app.api.deps import get_repo
from app.api.security import (
    API_KEY_HEADER_NAME,
    AUTHORIZATION_HEADER,
    verify_api_key,
)
from app.config import get_settings
from app.db.repository import CampaignRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["face"])

APP_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

FACE_COOKIE = "pfgod_face"
FACE_SESSION_TTL_S = 12 * 60 * 60
_FACE_SESSIONS: dict[str, float] = {}
_TURN_DONE = object()


# ── auth ────────────────────────────────────────────────────────────────


def _expected_key() -> str:
    return (get_settings().api_key_sha256 or "").strip()


def _prune_sessions() -> None:
    now = time.monotonic()
    for token, expires_at in list(_FACE_SESSIONS.items()):
        if expires_at <= now:
            _FACE_SESSIONS.pop(token, None)


def _header_key(request: Request) -> str:
    key = request.headers.get(API_KEY_HEADER_NAME) or ""
    if key:
        return key
    auth = request.headers.get(AUTHORIZATION_HEADER) or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def face_authorized(request: Request) -> bool:
    """True for keyless local mode, a valid API-key header, or a face cookie."""
    expected = _expected_key()
    if not expected:
        return True

    _prune_sessions()
    token = request.cookies.get(FACE_COOKIE) or ""
    expires_at = _FACE_SESSIONS.get(token)
    if expires_at is not None and expires_at > time.monotonic():
        return True

    key = _header_key(request)
    return bool(key) and verify_api_key(key, expected)


def _login_redirect(request: Request) -> RedirectResponse | None:
    if face_authorized(request):
        return None
    return RedirectResponse("/play/login", status_code=303)


# ── context ─────────────────────────────────────────────────────────────


def _campaign_context(repo: CampaignRepository, campaign_id: int) -> dict[str, Any]:
    campaign = repo.get_or_create_campaign(campaign_id)
    state = repo.ensure_solo_state(campaign_id)
    party = repo.get_party(campaign_id)
    combatants = repo.get_combatants(campaign_id)
    combatant_by_name = {c.name: asdict(c) for c in combatants}
    active = repo.get_active_encounter(campaign_id)
    location = (
        repo.get_location(campaign_id, state.current_location_id)
        if state.current_location_id is not None
        else None
    )
    items = repo.get_items(campaign_id)
    quests = [asdict(q) for q in repo.get_active_quests(campaign_id)]
    events = [asdict(e) for e in repo.list_events(campaign_id, limit=12)]
    events.reverse()
    turns = [asdict(t) for t in repo.get_recent_turns(campaign_id, limit=6)]

    scene = None
    if active is not None:
        scene = active.state.get("scene") or (active.state.get("map") or {}).get("scene")
    scene_json = json.dumps(scene, separators=(",", ":")) if scene else ""

    return {
        "campaigns": repo.list_campaigns(),
        "campaign": asdict(campaign),
        "state": asdict(state),
        "party": party,
        "combatants": [asdict(c) for c in combatants],
        "combatant_by_name": combatant_by_name,
        "active_encounter": asdict(active) if active is not None else None,
        "location": asdict(location) if location is not None else None,
        "items": items,
        "quests": quests,
        "events": events,
        "turns": turns,
        "scene_json": scene_json,
        "actor": "player",
    }


def _dashboard_context(
    repo: CampaignRepository, campaign_id: int
) -> dict[str, Any]:
    return _campaign_context(repo, campaign_id)


# ── static assets ───────────────────────────────────────────────────────


@router.get("/play/static/htmx.min.js", include_in_schema=False)
async def face_htmx() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "vendor" / "htmx.min.js",
        media_type="text/javascript",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/play/static/face.js", include_in_schema=False)
async def face_js() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "face.js",
        media_type="text/javascript",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/play/static/face.css", include_in_schema=False)
async def face_css() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "face.css",
        media_type="text/css",
        headers={"Cache-Control": "no-cache"},
    )


# ── pages ───────────────────────────────────────────────────────────────


@router.get("/", include_in_schema=False)
async def root_redirect() -> RedirectResponse:
    return RedirectResponse("/play", status_code=303)


@router.get("/play/login", include_in_schema=False, response_class=HTMLResponse)
async def login_page(request: Request) -> Response:
    if face_authorized(request):
        return RedirectResponse("/play", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="face/login.html",
        context={"error": None},
    )


@router.post("/play/login", include_in_schema=False, response_class=HTMLResponse)
async def login_submit(
    request: Request,
    api_key: str = Form(""),
    next_path: str = Form("/play"),
) -> Response:
    expected = _expected_key()
    if not expected:
        return RedirectResponse("/play", status_code=303)
    if not verify_api_key(api_key.strip(), expected):
        return templates.TemplateResponse(
            request=request,
            name="face/login.html",
            context={"error": "Invalid API key."},
            status_code=401,
        )

    token = secrets.token_urlsafe(32)
    _FACE_SESSIONS[token] = time.monotonic() + FACE_SESSION_TTL_S
    safe_next = next_path if next_path.startswith("/play") else "/play"
    response = RedirectResponse(safe_next, status_code=303)
    response.set_cookie(
        FACE_COOKIE,
        token,
        max_age=FACE_SESSION_TTL_S,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/play/logout", include_in_schema=False)
async def logout(request: Request) -> RedirectResponse:
    token = request.cookies.get(FACE_COOKIE) or ""
    _FACE_SESSIONS.pop(token, None)
    response = RedirectResponse("/play/login", status_code=303)
    response.delete_cookie(FACE_COOKIE, path="/")
    return response


@router.get("/play", include_in_schema=False, response_class=HTMLResponse)
async def face_home(
    request: Request,
    campaign_id: int | None = Query(None, ge=1, le=2147483647),
    repo: CampaignRepository = Depends(get_repo),
) -> Response:
    redirect = _login_redirect(request)
    if redirect is not None:
        return redirect

    campaigns = repo.list_campaigns()
    if not campaigns:
        repo.get_or_create_campaign(1, "Pathfinder God")
        campaigns = repo.list_campaigns()
    selected = campaign_id or campaigns[0]["id"]
    if not repo.campaign_exists(selected):
        raise HTTPException(status_code=404, detail="Campaign not found")

    context = _campaign_context(repo, selected)
    return templates.TemplateResponse(
        request=request,
        name="face/index.html",
        context=context,
    )


@router.get(
    "/play/campaign/{campaign_id}",
    include_in_schema=False,
)
async def face_campaign(campaign_id: int) -> RedirectResponse:
    return RedirectResponse(f"/play?campaign_id={campaign_id}", status_code=303)


@router.get(
    "/play/campaign/{campaign_id}/dashboard",
    include_in_schema=False,
    response_class=HTMLResponse,
)
async def face_dashboard(
    request: Request,
    campaign_id: int,
    repo: CampaignRepository = Depends(get_repo),
) -> Response:
    redirect = _login_redirect(request)
    if redirect is not None:
        return redirect
    if not repo.campaign_exists(campaign_id):
        raise HTTPException(status_code=404, detail="Campaign not found")
    context = _dashboard_context(repo, campaign_id)
    return templates.TemplateResponse(
        request=request,
        name="face/_dashboard.html",
        context=context,
    )


@router.post("/play/campaigns", include_in_schema=False)
async def create_campaign_face(
    request: Request,
    name: str = Form(...),
    edition: str = Form("2e"),
    repo: CampaignRepository = Depends(get_repo),
) -> Response:
    redirect = _login_redirect(request)
    if redirect is not None:
        return redirect
    clean_name = " ".join(name.split())[:80]
    if not clean_name:
        return HTMLResponse("Campaign name is required.", status_code=400)
    clean_edition = edition if edition in ("1e", "2e") else "2e"
    campaign = repo.create_campaign(clean_name, clean_edition)
    target = f"/play?campaign_id={campaign.id}"
    if request.headers.get("HX-Request") == "true":
        return Response(status_code=200, headers={"HX-Redirect": target})
    return RedirectResponse(target, status_code=303)


# ── turn SSE ────────────────────────────────────────────────────────────


def _sse(event: dict[str, Any]) -> str:
    event_type = str(event.get("type") or "message")
    payload = json.dumps(event, default=str, separators=(",", ":"))
    return f"event: {event_type}\ndata: {payload}\n\n"


async def _run_turn(
    queue: asyncio.Queue[Any],
    repo: CampaignRepository,
    campaign_id: int,
    action: str,
    actor: str,
    seed: int | None,
) -> None:
    loop = None
    try:
        loop = build_solo_loop(repo)
        await loop.take_turn(
            campaign_id,
            action,
            actor=actor,
            seed=seed,
            emit=queue.put,
        )
    except ValueError as exc:
        await queue.put({"type": "error", "message": str(exc)})
    except Exception:
        logger.exception("face turn failed")
        await queue.put(
            {
                "type": "error",
                "message": "The turn failed. Check the hub log for details.",
            }
        )
    finally:
        if loop is not None:
            with suppress(Exception):
                await loop.close()
        await queue.put(_TURN_DONE)


@router.get("/play/turn/stream", include_in_schema=False)
async def face_turn_stream(
    request: Request,
    campaign_id: int = Query(..., ge=1, le=2147483647),
    action: str = Query(..., min_length=1, max_length=4000),
    actor: str = Query("player", min_length=1, max_length=80),
    seed: int | None = Query(None),
    repo: CampaignRepository = Depends(get_repo),
) -> Response:
    if not face_authorized(request):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    if not repo.campaign_exists(campaign_id):
        raise HTTPException(status_code=404, detail="Campaign not found")

    queue: asyncio.Queue[Any] = asyncio.Queue()

    async def stream():
        task = asyncio.create_task(
            _run_turn(queue, repo, campaign_id, action, actor, seed)
        )
        try:
            while True:
                item = await queue.get()
                if item is _TURN_DONE:
                    break
                yield _sse(item)
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
