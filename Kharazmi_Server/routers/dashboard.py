"""
Admin Command Center - Dashboard KPIs (Read-Only, Lightweight, Optimized)
Isolated router - no modifications to finance/timeline.
Security: Admin only (check_admin_access)
Performance: SQL-level filtering via Jalali string comparison, COUNT/SUM only, 60s TTL cache, lightweight count helpers.
"""

import datetime
import time
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import DeviceToken, Installment, Student
from dependencies import get_db, check_admin_access
from today_summary import jalali_date_string
# FIX O-08: تعریف واحد «وصولی نقدی» از لایهٔ محاسبات مالی — همان تابعی که گزارش‌ها می‌خوانند.
# FIX (گروه۲/آیتم۴): تعریف یگانهٔ «وصولی نقدی آموزشگاه» — همان تابعی که
# `/admin/today_summary` («پرداخت امروز») استفاده می‌کند، تا دو عددِ یک روز در دو صفحهٔ اپ
# یکی باشد. `calculate_institute_collected_revenue` (O-07/O-08) برای گزارش‌های ماه/سال و
# نمودار درآمد دست‌نخورده باقی می‌ماند.
from financial_calculations import calculate_institute_cash_collected

router = APIRouter()

# Simple TTL cache — 60s to prevent repeated heavy queries
_dashboard_cache = {}
CACHE_TTL = 60  # seconds


def _clear_dashboard_cache():
    """For tests: clear in-memory TTL cache."""
    _dashboard_cache.clear()



class PushStatus(BaseModel):
    """وضعیت لایهٔ Push — O-15. فقط «تنظیم است یا نه»؛ هرگز خودِ کلید."""

    fcm_configured: bool
    device_token_count: int


class DashboardKPIs(BaseModel):
    today_revenue: int
    total_overdue_amount: int
    overdue_installments_count: int
    active_students_count: int
    suspicious_alerts_count: int
    dunning_pending_count: int


@router.get("/kpis", response_model=DashboardKPIs)
def get_dashboard_kpis(
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access),
):
    """
    Lightweight KPIs for Admin Command Center.
    Optimized: SQL COUNT/SUM via Jalali string comparison, <5 queries, 60s cache.
    """
    # TTL cache check (in-memory, per-process)
    cache_key = "dashboard_kpis"
    now_ts = time.time()
    if cache_key in _dashboard_cache:
        cached_data, cached_time = _dashboard_cache[cache_key]
        if now_ts - cached_time < CACHE_TTL:
            return cached_data

    today = datetime.date.today()
    today_jalali = jalali_date_string(today)  # e.g., "1405/06/16"

    # 1. Today's Revenue — FIX O-08: پیش‌تر SUM با LIKE روی تاریخ شمسی بود ⇒ شارژ جلسه
    #    (عدد منفی) از وصولی کم می‌شد، واریزی با تاریخ میلادی/بی‌تاریخ دیده نمی‌شد و عدد با
    #    گزارش‌های مالی نمی‌خواند. اکنون همان تعریف گزارش‌ها: وصولی نقدی امروز به کیف آموزشگاه.
    #    FIX (گروه۲/آیتم۴): تابع مشترک با «پرداخت امروز» در `/admin/today_summary`
    #    (`calculate_institute_cash_collected`) تا KPI و خلاصهٔ امروز هیچ‌وقت از هم واگرا نشوند؛
    #    این تعریف علاوه بر `deposit`/کیف آموزشگاه، پیش‌پرداخت ثبت‌نام (`enrollment_payment`)،
    #    پرداخت CRM (`tuition`) و ردیف‌های legacy (بدون type/کیف) را هم می‌بیند و واریزی به
    #    کیف معلم و شارژ جلسه را نمی‌شمارد.
    try:
        today_revenue = int(calculate_institute_cash_collected(db, today_jalali, today_jalali) or 0)
    except Exception as e:
        print(f"[Dashboard] today_revenue failed: {e}")
        today_revenue = 0

    # 2 & 3. Overdue installments — SQL string comparison (YYYY/MM/DD) — single query for COUNT+SUM
    # Since due_date is stored as Jalali "YYYY/MM/DD", string comparison works.
    try:
        overdue_row = (
            db.query(func.count(Installment.id), func.coalesce(func.sum(Installment.amount), 0))
            .filter(
                Installment.is_deleted == False,
                Installment.is_paid == False,
                Installment.due_date < today_jalali,
                Installment.due_date.isnot(None),
            )
            .first()
        )
        if overdue_row:
            overdue_installments_count = int(overdue_row[0] or 0)
            total_overdue_amount = int(overdue_row[1] or 0)
        else:
            overdue_installments_count = 0
            total_overdue_amount = 0
    except Exception as e:
        print(f"[Dashboard] overdue SQL failed: {e}")
        overdue_installments_count = 0
        total_overdue_amount = 0

    # 4. Active Students Count — single COUNT
    try:
        active_students_count = db.query(func.count(Student.id)).filter(Student.is_deleted == False).scalar() or 0
        active_students_count = int(active_students_count)
    except Exception as e:
        print(f"[Dashboard] active_students count failed: {e}")
        active_students_count = 0

    # 5. Suspicious Alerts Count — lightweight COUNT helper (no full Alert objects)
    suspicious_alerts_count = 0
    try:
        from routers.audit import count_suspicious_patterns  # type: ignore

        suspicious_alerts_count = int(count_suspicious_patterns(db) or 0)
    except Exception as e:
        print(f"[Dashboard] audit count failed: {e}")
        suspicious_alerts_count = 0

    # 6. Dunning Pending Count — lightweight COUNT helper (no draft building)
    dunning_pending_count = 0
    try:
        from routers.dunning import count_dunning_pending  # type: ignore

        dunning_pending_count = int(count_dunning_pending(db) or 0)
    except Exception as e:
        print(f"[Dashboard] dunning count failed: {e}")
        # Fallback to overdue count if dunning helper fails
        dunning_pending_count = int(overdue_installments_count or 0)

    kpis = DashboardKPIs(
        today_revenue=int(today_revenue),
        total_overdue_amount=int(total_overdue_amount),
        overdue_installments_count=int(overdue_installments_count),
        active_students_count=int(active_students_count),
        suspicious_alerts_count=int(suspicious_alerts_count),
        dunning_pending_count=int(dunning_pending_count),
    )

    # Cache result
    _dashboard_cache[cache_key] = (kpis, now_ts)
    return kpis


@router.get("/push_status", response_model=PushStatus)
def get_push_status(db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    """وضعیت Push برای مدیر (FIX O-15) — عیب‌یابی «چرا هیچ اعلانی به گوشی نمی‌رسد».

    دو پرسشِ واقعیِ مدیر را پاسخ می‌دهد، بدون افشای هیچ رازی:
      1. آیا اعتبارنامهٔ FCM روی سرور تنظیم شده؟ (`fcm_configured` از گارد محیطی `push_service`)
      2. چند توکن دستگاه در `device_tokens` ثبت شده؟ (`device_token_count`)

    فقط‌خواندنی و بدون کش: این مقادیر باید «همین حالا» را نشان دهند؛ ضمناً هیچ کلیدی
    خوانده/نوشته نمی‌شود و مقدار کلید در پاسخ برنمی‌گردد.
    """
    from push_service import fcm_configured  # import محلی: جلوگیری از وابستگی حلقه‌ای

    return PushStatus(
        fcm_configured=bool(fcm_configured()),
        device_token_count=int(db.query(func.count(DeviceToken.id)).scalar() or 0),
    )
