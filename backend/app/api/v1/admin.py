"""Admin endpoints. Every route requires a valid session cookie."""

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse

from app.api.deps import ClientIpDep, CurrentAdmin, SessionDep, SettingsDep, get_current_admin
from app.core.constants import PROJECT_TYPES, EnquiryStatus
from app.core.errors import AppError
from app.schemas.admin_enquiry import EnquiryDetail, EnquiryPage, EnquiryUpdate
from app.schemas.note import NoteIn
from app.schemas.stats import TodayOut
from app.services import admin_enquiry_service, export_service, stats_service

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


@router.get("/today", response_model=TodayOut)
async def today(session: SessionDep, settings: SettingsDep) -> TodayOut:
    """Numbers and lists for the admin home screen."""
    return await stats_service.today(session, settings)


@router.get("/enquiries", response_model=EnquiryPage)
async def list_enquiries(
    session: SessionDep,
    settings: SettingsDep,
    status: Literal["all"] | EnquiryStatus = "all",
    q: Annotated[str | None, Query(max_length=100)] = None,
    project_type: Annotated[str | None, Query(max_length=60)] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> EnquiryPage:
    """Newest first. ``status=all`` hides "Not relevant" leads, like the All tab."""
    if project_type and project_type not in PROJECT_TYPES:
        raise AppError(
            422, "validation_error", "Unknown project type.", {"project_type": "Unknown"}
        )
    return await admin_enquiry_service.list_enquiries(
        session,
        status=None if status == "all" else status,
        q=q,
        project_type=project_type,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
        settings=settings,
    )


# Declared before /enquiries/{enquiry_id} so "export.csv" isn't parsed as an id.
@router.get("/enquiries/export.csv", response_class=StreamingResponse)
async def export_csv(
    admin: CurrentAdmin, session: SessionDep, settings: SettingsDep, ip: ClientIpDep
) -> StreamingResponse:
    await export_service.record_export(session, admin, ip)
    return StreamingResponse(
        export_service.stream_csv(settings),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{export_service.filename(settings)}"'
        },
    )


@router.get("/enquiries/{enquiry_id}", response_model=EnquiryDetail)
async def get_enquiry(
    enquiry_id: uuid.UUID, session: SessionDep, settings: SettingsDep
) -> EnquiryDetail:
    return await admin_enquiry_service.get_detail(session, enquiry_id, settings)


@router.patch("/enquiries/{enquiry_id}", response_model=EnquiryDetail)
async def update_enquiry(
    enquiry_id: uuid.UUID,
    payload: EnquiryUpdate,
    admin: CurrentAdmin,
    session: SessionDep,
    settings: SettingsDep,
    ip: ClientIpDep,
) -> EnquiryDetail:
    """Change status and/or follow-up date. Old and new values go to the audit log."""
    return await admin_enquiry_service.update_enquiry(
        session, enquiry_id, payload, admin, ip, settings
    )


@router.delete("/enquiries/{enquiry_id}", status_code=204, response_class=Response)
async def delete_enquiry(
    enquiry_id: uuid.UUID, admin: CurrentAdmin, session: SessionDep, ip: ClientIpDep
) -> Response:
    """Erase an enquiry on the customer's request. Audit-logged without the personal data."""
    await admin_enquiry_service.delete_enquiry(session, enquiry_id, admin, ip)
    return Response(status_code=204)


@router.post("/enquiries/{enquiry_id}/notes", response_model=EnquiryDetail, status_code=201)
async def add_note(
    enquiry_id: uuid.UUID,
    payload: NoteIn,
    admin: CurrentAdmin,
    session: SessionDep,
    settings: SettingsDep,
    ip: ClientIpDep,
) -> EnquiryDetail:
    return await admin_enquiry_service.add_note(session, enquiry_id, payload, admin, ip, settings)
