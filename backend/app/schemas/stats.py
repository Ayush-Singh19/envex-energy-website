from pydantic import BaseModel

from app.schemas.admin_enquiry import EnquiryItem


class TodayKpis(BaseModel):
    new_this_week: int
    waiting_for_call: int
    quotes_out: int
    won_this_month: int
    month_label: str


class ClickCounts(BaseModel):
    call: int = 0
    whatsapp: int = 0
    quote: int = 0
    email: int = 0


class TodayOut(BaseModel):
    kpis: TodayKpis
    call_first: list[EnquiryItem]  # status new, longest waiting first
    follow_ups: list[EnquiryItem]  # due today or overdue, most overdue first
    later_this_week: int
    clicks_this_week: ClickCounts
