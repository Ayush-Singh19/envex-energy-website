"""Public endpoints: no authentication. Thin HTTP layer over the services."""

from fastapi import APIRouter, BackgroundTasks, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import text

from app.api.deps import RequestMetaDep, SessionDep, SettingsDep
from app.core.errors import AppError
from app.core.rate_limit import enquiry_limit, events_limit, limiter
from app.schemas.enquiry import EnquiryCreate, EnquiryCreated
from app.schemas.event import ClickEventIn
from app.services import enquiry_service, event_service, notification_service

router = APIRouter(tags=["public"])

MAX_EVENT_BODY_BYTES = 2048


@router.get("/health")
async def health(session: SessionDep) -> JSONResponse:
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "degraded", "db": "unavailable"}, status_code=503)
    return JSONResponse({"status": "ok", "db": "ok"})


@router.post("/enquiries", status_code=201, response_model=EnquiryCreated)
@limiter.limit(enquiry_limit)
async def create_enquiry(
    request: Request,  # required by the rate limiter
    payload: EnquiryCreate,
    background: BackgroundTasks,
    session: SessionDep,
    settings: SettingsDep,
    meta: RequestMetaDep,
) -> EnquiryCreated:
    """Save the enquiry, queue the email alert, and return the WhatsApp link to open."""
    result = await enquiry_service.submit_enquiry(session, payload, meta, settings)
    if result.alert is not None:
        background.add_task(notification_service.send_new_enquiry_alert, result.alert, settings)
    return result.response


@router.post("/events", status_code=204, response_class=Response)
@limiter.limit(events_limit)
async def record_event(request: Request, session: SessionDep) -> Response:
    """Record an anonymous CTA click: JSON body ``{"type", "page"?, "utm_source"?}``.

    The body is parsed manually because ``navigator.sendBeacon`` sends it as
    ``text/plain`` (a JSON content type would need a CORS preflight, which beacons can't do).
    """
    body = await request.body()
    if len(body) > MAX_EVENT_BODY_BYTES:
        raise AppError(413, "payload_too_large", "Event payload is too large.")
    try:
        event = ClickEventIn.model_validate_json(body or b"{}")
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    await event_service.record_click(session, event)
    return Response(status_code=204)
