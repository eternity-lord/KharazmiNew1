"""Financial Audit Trail — ردگیری کامل تغییرات مالی (Transaction / Installment).

## چرا این‌طور پیاده شد
- **لاگ‌گیری خودکار**: listener روی `Session.before_flush` + `Session.after_flush_postexec`.
  هیچ اندپوینتی لاگ نمی‌زند؛ هر مسیری که از ORM بنویسد (finance, classes, automation, admin, ...)
  خودکار لاگ می‌شود و هیچ‌کدام از روترهای موجود دست نمی‌خورند.
- **before_flush** = مقادیر «قبلی»: در این لحظه هنوز UPDATE/DELETE اجرا نشده، پس اسنپ‌شات
  از ردیف دیتابیس (`SELECT`) دقیقاً مقدار قبلی است. (reading از state آبجکت غلط است: بعد از
  commit، آبجکت‌ها expire‌اند و مقدار قبلی در حافظه وجود ندارد.)
- **after_flush_postexec** = مقادیر «جدید» + `entity_id`: در create، PK تازه بعد از INSERT تعیین
  می‌شود (در before_flush هنوز None است) و defaultهای ستون‌ها هم فقط بعد از INSERT اعمال شده‌اند.
- **درج لاگ با Core-insert روی `session.connection()`**: در همان تراکنشِ نوشتن ⇒ rollback
  ⇒ لاگ هم برمی‌گردد (هیچ تغییر commit‌نشده‌ای لاگ نمی‌شود). درج از مسیر ORM انجام نمی‌شود تا
  خودِ ردیف لاگ دوباره باعث flush/recursion نشود.
- **UPDATE بی‌اثر لاگ نمی‌شود**: اگر کسی بعد از commit دوباره همان مقدار را set کند، SQLAlchemy
  یک UPDATE می‌فرستد؛ با مقایسه‌ی اسنپ‌شات قبلی/جدید این نویز حذف می‌شود.
- **مقاوم‌بودن**: هیچ استثنایی از listener بیرون نمی‌زند؛ خطای لاگ ⇒ هشدار در لاگ سرور و
  نوشتن بیزینس سالم می‌ماند.
- **محدودیت آگاهانه**: bulk update/delete سبک Core (`query.update()`, `query.delete()`) رویداد
  ORM تولید نمی‌کند ⇒ لاگ نمی‌شود. مسیرهای مالی این پروژه از ORM استفاده می‌کنند.
- **زمان**: `timestamp` به UTC ذخیره می‌شود (استاندارد پروژه) و اندپوینت آن را به وقت محلی سرور
  برمی‌گرداند؛ فیلترهای تاریخ هم به‌صورت تاریخ محلی/جلالی گرفته و به UTC تبدیل می‌شوند.
"""
import contextvars
import datetime
import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import event, func, inspect, or_, select, tuple_
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

import models
from dependencies import check_admin_access, display_name, get_db, get_session_from_token
# FIX (گروه۲/آیتم۸): برای join نام‌ها به‌جای شناسهٔ خام و جست‌وجوی نام
from models import (ActivityLog, Branch, Course, Enrollment, FinancialAuditLog, Installment,
                    Student, Teacher, Transaction, User)

router = APIRouter()

# مدل‌های تحت نظر + مقادیر مجاز فیلترها
AUDITED_MODELS = (Transaction, Installment)
ENTITY_TYPES = ("transaction", "installment")
ACTIONS = ("create", "update", "delete")

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
_MAX_CELL_CHARS = 1000          # سقف طول هر مقدار در JSON (محافظت از سلول‌های غول)
_PENDING_KEY = "_kharazmi_audit_pending"


# ==========================================
# 1) زمینه‌ی درخواست (کاربر/IP) برای listener ها
# ==========================================
# چرا ContextVar و نه request.state: listener های SQLAlchemy به درخواست دسترسی ندارند و
# میدل‌ور/اندپوینت در تسک‌های متفاوت اجرا می‌شوند؛ ContextVar در async و به‌صورت خودکار در
# threadpool (اندپوینت‌های sync) کپی می‌شود ⇒ امن و بی‌نیاز از global mutable.
_audit_context: "contextvars.ContextVar[Optional[Dict[str, Any]]]" = contextvars.ContextVar(
    "kharazmi_audit_context", default=None
)


def set_audit_context(user_id: Optional[int], username: Optional[str], ip_address: Optional[str]):
    return _audit_context.set({"user_id": user_id, "username": username, "ip_address": ip_address})


def reset_audit_context(token) -> None:
    try:
        _audit_context.reset(token)
    except (ValueError, LookupError):
        # token متعلق به context دیگری است (تسک‌های فرزند) — بی‌خطر
        pass


def current_audit_context() -> Dict[str, Any]:
    return _audit_context.get() or {}


def _client_ip(request) -> Optional[str]:
    """IP کاربر: اولین مقدار X-Forwarded-For (پشت ریورس‌پروکسی) وگرنه هاست اتصال."""
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded[:45]
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client is not None else None
    return host[:45] if host else None


class AuditContextMiddleware(BaseHTTPMiddleware):
    """برای درخواست‌های تغییردهنده، کاربر توکن را در ContextVar می‌گذارد تا listener ها
    بتوانند «چه کسی» را ثبت کنند.

    - فقط متدهای POST/PUT/PATCH/DELETE ⇒ روی خواندن‌ها (GET) صفر سربار/صفر کوئری.
    - کش کوتاه ۳۰ ثانیه‌ای توکن→کاربر: درخواست‌های نوشتنِ پشت‌سرهم یک کاربر، یک کوئری اضافه ندارند.
    - این میدل‌ور فقط «برچسب» لاگ را می‌سازد؛ احراز هویت واقعی همان Depends(check_admin_access)/get_db است.
    """

    _MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
    _TTL_SECONDS = 30
    _MAX_CACHE = 256
    _cache: Dict[str, Tuple[float, Optional[int], Optional[str]]] = {}

    async def dispatch(self, request, call_next):
        token = self._bearer_token(request) if request.method in self._MUTATING else None
        context_token = None
        if token:
            identity = self._resolve_identity(token)
            if identity is not None:
                context_token = set_audit_context(identity[0], identity[1], _client_ip(request))
        try:
            return await call_next(request)
        finally:
            # پاک‌سازی لازم است: در غیر این‌صورت کاربرِ درخواست قبلی به درخواست بعدی «نشت» می‌کرد.
            if context_token is not None:
                reset_audit_context(context_token)

    @staticmethod
    def _bearer_token(request) -> Optional[str]:
        parts = (request.headers.get("authorization") or "").split()
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1]:
            return parts[1]
        return None

    @classmethod
    def _resolve_identity(cls, token: str) -> Optional[Tuple[Optional[int], Optional[str]]]:
        now = time.monotonic()
        cached = cls._cache.get(token)
        if cached is not None and cached[0] > now:
            return cached[1], cached[2]

        db = models.SessionLocal()
        try:
            session, _ = get_session_from_token(db, token)
            if not session:
                return None
            user = db.query(User).filter(User.id == session.user_id).first()
            if not user:
                return None
            if len(cls._cache) >= cls._MAX_CACHE:
                cls._cache.clear()
            cls._cache[token] = (now + cls._TTL_SECONDS, user.id, user.username)
            return user.id, user.username
        except Exception as exc:  # توکن خراب/دیتابیس در دسترس نباشد ⇒ لاگ بی‌کاربر، نه 500
            print(f"⚠️ Audit Trail: resolve user failed: {exc}")
            return None
        finally:
            db.close()


# ==========================================
# 2) اسنپ‌شات‌گیری و listener های SQLAlchemy
# ==========================================
def _column_keys(obj) -> List[str]:
    try:
        return [attr.key for attr in inspect(obj).mapper.column_attrs]
    except Exception:
        return []


def _db_snapshot(session: Session, obj) -> Optional[Dict[str, Any]]:
    """اسنپ‌شات ردیف فعلی دیتابیس (در before_flush = مقادیر قبلی) با یک SELECT."""
    pk = getattr(obj, "id", None)
    if pk is None:
        return None
    table = obj.__table__
    keys = [key for key in _column_keys(obj) if key in table.c]
    if not keys:
        return None
    try:
        row = session.connection().execute(
            select(*[table.c[key] for key in keys]).where(table.c.id == pk)
        ).mappings().first()
    except Exception as exc:
        print(f"⚠️ Audit Trail: old snapshot failed: {exc}")
        return None
    return dict(row) if row is not None else None


def _state_snapshot(obj) -> Dict[str, Any]:
    """اسنپ‌شات state آبجکت (در after_flush_postexec = مقادیر نهایی، شامل defaultهای ستون)."""
    snapshot: Dict[str, Any] = {}
    for key in _column_keys(obj):
        try:
            snapshot[key] = getattr(obj, key)
        except Exception:
            # آبجکت حذف‌شده/expire‌شده — مقدار در دسترس نیست (نمی‌خواهیم اینجا خطا بدهیم)
            snapshot[key] = None
    return snapshot


def _comparable(payload: Optional[Dict[str, Any]]) -> Any:
    """نرمال‌سازی برای مقایسه (DateTime/Decimal → رشته) تا مقایسه‌ی قبلی/جدید معتبر باشد."""
    if payload is None:
        return None
    try:
        return json.loads(json.dumps(payload, default=str, ensure_ascii=False, sort_keys=True))
    except Exception:
        return str(payload)


def _dump(payload: Optional[Dict[str, Any]]) -> Optional[str]:
    if payload is None:
        return None
    safe: Dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str) and len(value) > _MAX_CELL_CHARS:
            value = value[:_MAX_CELL_CHARS] + "…"
        safe[key] = value
    try:
        return json.dumps(safe, ensure_ascii=False, default=str)
    except Exception:
        try:
            return json.dumps({key: str(value) for key, value in payload.items()}, ensure_ascii=False)
        except Exception as exc:
            print(f"⚠️ Audit Trail: dump failed: {exc}")
            return None


def _entity_type(obj) -> str:
    return "transaction" if isinstance(obj, Transaction) else "installment"


def _capture_financial_changes(session: Session, flush_context, instances) -> None:
    """before_flush: مقادیر قبلی را از DB می‌خواند و رکوردها را در session.info نگه می‌دارد."""
    try:
        records = session.info.setdefault(_PENDING_KEY, [])
        for obj in list(session.new):
            if isinstance(obj, AUDITED_MODELS):
                records.append({"obj": obj, "action": "create", "old": None})
        for obj in list(session.dirty):
            if not isinstance(obj, AUDITED_MODELS) or obj in session.deleted:
                continue
            old = _db_snapshot(session, obj)
            if old is not None and _comparable(old) == _comparable(_state_snapshot(obj)):
                # UPDATE بی‌اثر (مقدار هم‌مقدار ست‌شده بعد از expire) ⇒ نویز لاگ نمی‌شود
                continue
            records.append({"obj": obj, "action": "update", "old": old})
        for obj in list(session.deleted):
            if isinstance(obj, AUDITED_MODELS):
                old = _db_snapshot(session, obj)
                records.append({
                    "obj": obj,
                    "action": "delete",
                    "old": old if old is not None else _state_snapshot(obj),
                })
    except Exception as exc:
        print(f"⚠️ Audit Trail: capture failed (نوشتن بیزینس ادامه می‌یابد): {exc}")


def _persist_financial_logs(session: Session, flush_context) -> None:
    """after_flush_postexec: PK/مقادیر نهایی مشخص است ⇒ درج لاگ در همان تراکنش."""
    records = session.info.pop(_PENDING_KEY, None)
    if not records:
        return
    context = current_audit_context()
    now = datetime.datetime.utcnow()
    rows = []
    for record in records:
        obj = record["obj"]
        action = record["action"]
        new_values = None if action == "delete" else _state_snapshot(obj)
        rows.append({
            "timestamp": now,
            "user_id": context.get("user_id"),
            "username": context.get("username"),
            "action": action,
            "entity_type": _entity_type(obj),
            "entity_id": getattr(obj, "id", None),
            "old_values": _dump(record["old"]),
            "new_values": _dump(new_values),
            "ip_address": context.get("ip_address"),
        })
    try:
        session.connection().execute(FinancialAuditLog.__table__.insert(), rows)
    except Exception as exc:
        # تصمیم آگاهانه: «در‌دسترس‌بودن» مهم‌تر از «کامل‌بودن» است — یک خطای لاگ نباید
        # ثبت پرداخت/قسط را ۵۰۰ کند. با هشدار در لاگ سرور کاملاً قابل رصد است.
        print(f"⚠️ Audit Trail: insert failed, {len(rows)} record(s) skipped: {exc}")


def _drop_pending_records(session: Session, *args) -> None:
    """rollback (کامل یا savepoint) ⇒ رکوردهای معلق دور ریخته می‌شوند."""
    session.info.pop(_PENDING_KEY, None)


_LISTENERS_INSTALLED = False


def setup_audit_listeners(engine=None) -> bool:
    """ثبت listener ها (idempotent) + اطمینان از وجود جدول `financial_audit_logs`.

    برمی‌گرداند True اگر همین حالا نصب شد (برای تست/گزارش).
    """
    global _LISTENERS_INSTALLED
    if _LISTENERS_INSTALLED:
        return False
    event.listen(Session, "before_flush", _capture_financial_changes)
    event.listen(Session, "after_flush_postexec", _persist_financial_logs)
    event.listen(Session, "after_rollback", _drop_pending_records)
    event.listen(Session, "after_soft_rollback", _drop_pending_records)
    _LISTENERS_INSTALLED = True
    # مایگریشن: فقط همین جدول جدید (idempotent، بدون دست‌زدن به جداول موجود).
    try:
        FinancialAuditLog.__table__.create(bind=engine or models.engine, checkfirst=True)
    except Exception as exc:
        print(f"⚠️ Audit Trail: create table failed: {exc}")
    return True


# ==========================================
# 3) اندپوینت کوئری — GET /audit-trail/logs (admin only)
# ==========================================
# ---------------------------------------------------------------------------
# FIX (گروه۲/آیتم ۸): غنی‌سازی نمایش تاریخچه — «چه چیزی عوض شد» به زبان آدم،
# نام‌ها به‌جای شناسهٔ خام، کاربر تغییردهنده، لینک صورت‌حساب، جست‌وجوی نام و رنگ.
# همه‌ی اینها فقط در **لایهٔ خواندن** اضافه شده‌اند: جدول `financial_audit_logs`،
# listener ها و کلیدهای قبلی پاسخ دست‌نخورده‌اند (کلاینت منتشرشده نمی‌شکند و
# سند خام old/new_values برای ممیزی دقیق سر جایش می‌ماند).
# ---------------------------------------------------------------------------
ACTION_LABELS = {"create": "ایجاد", "update": "ویرایش", "delete": "حذف"}
ACTION_COLORS = {"create": "#4CAF50", "update": "#FB8C00", "delete": "#E53935"}
CHANGE_TYPE_COLORS = {
    "new_payment": "#4CAF50",   # سبز — ثبت جدید
    "edited": "#FB8C00",        # نارنجی — ویرایش
    "reversed": "#E53935",      # قرمز — برگشت‌خورده
    "voided": "#9E9E9E",        # خاکستری — باطل/حذف نرم
    "deleted": "#E53935",       # قرمز — حذف
}

# action های ActivityLog → برچسب فارسی (برای `actor_action`؛ مقدار خام در `actor_action_key`)
ACTIVITY_ACTION_LABELS = {
    "transaction_refund": "استرداد تراکنش",
    "transaction_edit": "ویرایش تراکنش",
    "transaction_delete": "حذف تراکنش",
    "transaction_reversed": "برگشت تراکنش",
    "submit_payment": "ثبت پرداخت",
    "online_payment_success": "پرداخت آنلاین موفق",
    "create_installment": "ایجاد قسط",
    "update_installment_amount": "ویرایش مبلغ قسط",
    "delete_installment": "حذف قسط",
    "pay_installment_manual": "وصول دستی قسط",
    "debtors_reminder": "یادآوری بدهی",
}
FIELD_LABELS = {
    # مشترک
    "amount": "مبلغ", "date": "تاریخ", "is_deleted": "حذف‌شده", "description": "شرح",
    "id": "شناسه",
    # Transaction
    "remittance_number": "شمارهٔ حواله", "branch_id": "شعبه", "session_id": "جلسه",
    "student_id": "دانش‌آموز", "enrollment_id": "ثبت‌نام", "course_id": "کلاس",
    "payment_method": "روش پرداخت", "tracking_code": "کد رهگیری", "receiver": "گیرنده",
    "type": "نوع تراکنش", "share_teacher": "سهم معلم", "share_institute": "سهم آموزشگاه",
    "target_wallet": "کیف پول مقصد", "idempotency_key": "کلید یکتایی",
    "is_reversed": "برگشت‌خورده",
    # Installment
    "due_date": "سررسید", "is_paid": "پرداخت‌شده", "paid_at": "زمان پرداخت",
    "paid_amount": "مبلغ پرداخت‌شده",
}
ID_LABEL_KEYS = {"branch_id", "session_id", "student_id", "enrollment_id", "course_id"}
MONEY_FIELDS = {"amount", "share_teacher", "share_institute", "paid_amount"}
BOOL_FIELDS = {"is_deleted", "is_reversed", "is_paid"}
_MAX_SUMMARY_ITEMS = 4          # سقف بندهای جملهٔ خلاصه (بقیه: «و N تغییر دیگر»)
_SEARCH_ID_LIMIT = 2000         # سقف شناسه‌های تزریق‌شده به IN (محافظ SQLite variable limit)
_ACTOR_WINDOW_MINUTES = 30      # پنجرهٔ زمانی fallback روی ActivityLog


def _field_label(key: str) -> str:
    return FIELD_LABELS.get(key, key)


def _display_value(key: str, value: Any) -> str:
    """مقدار خام → متن خوانا (هزارگان برای پول، بله/خیر برای بول، «خالی» برای None)."""
    if value is None or value == "":
        return "خالی"
    if key in BOOL_FIELDS:
        return "بله" if value in (True, 1, "1", "true", "True") else "خیر"
    if key in MONEY_FIELDS:
        try:
            return f"{int(value):,}"
        except Exception:
            return str(value)
    return str(value)


def _change_summary(action: str, changed: List[str], old: Optional[Dict[str, Any]],
                    new: Optional[Dict[str, Any]]) -> str:
    """جملهٔ فارسی «چه چیزی عوض شد» — به‌جای لیست خام نام ستون‌ها."""
    verb = {"create": "ثبت شد", "update": "تغییر کرد", "delete": "حذف شد"}.get(action, action)
    if action == "create":
        items = [f"{_field_label(key)} {_display_value(key, (new or {}).get(key))}"
                 for key in changed[:_MAX_SUMMARY_ITEMS]]
    elif action == "delete":
        items = [f"{_field_label(key)} {_display_value(key, (old or {}).get(key))}"
                 for key in changed[:_MAX_SUMMARY_ITEMS]]
    else:
        items = [f"{_field_label(key)}: {_display_value(key, (old or {}).get(key))} ← "
                 f"{_display_value(key, (new or {}).get(key))}"
                 for key in changed[:_MAX_SUMMARY_ITEMS]]
    summary = "؛ ".join(item for item in items if item)
    rest = len(changed) - len(items)
    if rest > 0:
        summary = f"{summary}؛ و {rest} تغییر دیگر" if summary else f"{rest} تغییر"
    return f"{verb}: {summary}" if summary else verb


def _change_type_meta(action: str, old: Optional[Dict[str, Any]],
                      new: Optional[Dict[str, Any]]) -> Tuple[str, str, str]:
    """(نوع تغییر به زبان ساده, کلید نوع, رنگ) — کلاینت Android رنگ را مستقیم مصرف می‌کند
    (بدون نیاز به drawable جدید)؛ `icon_color` هم برای آیکون رنگی هر نوع تغییر است."""
    # `action_label` همیشه ترجمهٔ سادهٔ خود action است (ایجاد/ویرایش/حذف)؛
    # ظرافت‌ها (برگشت‌خورده/باطل‌شده) در `change_type` + `icon_color` منعکس می‌شود.
    if action == "create":
        key = "new_payment"
    elif action == "delete":
        key = "deleted"
    elif (new or {}).get("is_reversed") and not (old or {}).get("is_reversed"):
        key = "reversed"
    elif (new or {}).get("is_deleted") and not (old or {}).get("is_deleted"):
        key = "voided"
    else:
        key = "edited"
    return ACTION_LABELS.get(action, action), key, CHANGE_TYPE_COLORS.get(key, "#607D8B")


def _collect_ref_ids(entity_type: str, old: Optional[Dict[str, Any]], new: Optional[Dict[str, Any]],
                     wanted: Dict[str, set]) -> None:
    """شناسه‌های موردنیاز join یک ردیف لاگ را در `wanted` جمع می‌کند.

    کلیدها: student_id / course_id / branch_id / enrollment_id (هرکدام یک set با حداکثر یک عضو؛
    مقدار جدید اولویت دارد و در نبودش مقدار قبلی — مثلاً در delete فقط old_values هست).
    `enrollments`/`installment_enrollments` در سطح صفحه برای کوئری دسته‌ای جمع می‌شوند.
    """
    def as_int(value: Any) -> Optional[int]:
        try:
            return int(value) if value is not None else None
        except Exception:
            return None

    for source in (new, old):
        if not source:
            continue
        for key in ("student_id", "course_id", "branch_id", "enrollment_id"):
            value = as_int(source.get(key))
            if value is None:
                continue
            bucket = wanted.setdefault(key, set())
            if not bucket:
                bucket.add(value)


def _entity_refs_batch(db: Session, collected: List[Tuple[int, str, Dict[str, set]]],
                       page_ids: Dict[str, set]) -> Tuple[Dict[int, Dict[str, Any]], Dict[int, Optional[int]]]:
    """join دسته‌ای نام‌ها (یک کوئری به‌ازای هر نوع موجودیت برای کل صفحه ⇒ بدون N+1).

    برمی‌گرداند: (`refs_by_log`, `student_id_by_log`) — دومی برای «لینک صورت‌حساب» لازم است
    و از همان joinهای دسته‌ای می‌آید (کوئری اضافی به‌ازای هر ردیف زده نمی‌شود).
    سیاست نام تهی: شناسه‌ای که موجودیتش پیدا نشود (رکورد یتیم/حذف فیزیکی) در خروجی
    **نمی‌آید** تا کلاینت «None» نشان ندهد.
    """
    students: Dict[int, Any] = {}
    courses: Dict[int, Any] = {}
    branches: Dict[int, str] = {}
    enrollments: Dict[int, Any] = {}
    enrollment_ids = set(page_ids.get("enrollment_ids") or ()) | set(
        page_ids.get("installment_enrollment_ids") or ())
    if enrollment_ids:
        enrollments = {row.id: row for row in db.query(Enrollment).filter(
            Enrollment.id.in_(enrollment_ids)).all()}
    # دانش‌آموزِ خودِ ردیف + دانش‌آموزِ ثبت‌نامِ linked (قسط student_id ندارد)
    student_ids = set(page_ids.get("student_ids") or ())
    student_ids |= {enrollment.student_id for enrollment in enrollments.values()
                    if enrollment.student_id}
    if student_ids:
        students = {row.id: row for row in db.query(Student).filter(
            Student.id.in_(student_ids)).all()}
    if page_ids.get("course_ids"):
        courses = {row.id: row for row in db.query(Course).filter(
            Course.id.in_(page_ids["course_ids"])).all()}
    # branch_id در برخی تراکنش‌های legacy خالی است؛ از کلاس/ثبت‌نام به‌عنوان
    # fallback نمایشی استفاده می‌کنیم، بدون تغییر سند خام ممیزی.
    derived_branch_ids = set(page_ids.get("branch_ids") or ())
    derived_branch_ids |= {course.branch_id for course in courses.values() if course.branch_id}
    derived_branch_ids |= {enrollment.branch_id for enrollment in enrollments.values() if enrollment.branch_id}
    if derived_branch_ids:
        branches = {row.id: (row.name or "") for row in db.query(Branch).filter(
            Branch.id.in_(derived_branch_ids)).all()}

    teacher_ids = {course.teacher_id for course in courses.values() if course.teacher_id}
    # معلمِ کلاسِ ثبت‌نام هم لازم است (قسط خودش course_id ندارد)
    extra_course_ids = {enrollment.course_id for enrollment in enrollments.values()
                        if enrollment.course_id and enrollment.course_id not in courses}
    if extra_course_ids:
        for row in db.query(Course).filter(Course.id.in_(extra_course_ids)).all():
            courses[row.id] = row
            if row.teacher_id:
                teacher_ids.add(row.teacher_id)
    teacher_ids.discard(None)
    teachers: Dict[int, Any] = {}
    if teacher_ids:
        teachers = {row.id: row for row in db.query(Teacher).filter(
            Teacher.id.in_(teacher_ids)).all()}

    refs_by_log: Dict[int, Dict[str, Any]] = {}
    student_by_log: Dict[int, Optional[int]] = {}
    for log_id, entity_type, wanted in collected:
        refs: Dict[str, Any] = {}
        student_id = next(iter(wanted.get("student_id") or ()), None)
        course_id = next(iter(wanted.get("course_id") or ()), None)
        branch_id = next(iter(wanted.get("branch_id") or ()), None)
        enrollment_id = next(iter(wanted.get("enrollment_id") or ()), None)
        enrollment = enrollments.get(enrollment_id) if enrollment_id is not None else None
        if enrollment is not None:
            student_id = student_id if student_id is not None else enrollment.student_id
            course_id = course_id if course_id is not None else enrollment.course_id
            branch_id = branch_id if branch_id is not None else enrollment.branch_id
        student_by_log[log_id] = student_id
        student = students.get(student_id) if student_id is not None else None
        course = courses.get(course_id) if course_id is not None else None
        branch_id = branch_id if branch_id is not None else (course.branch_id if course is not None else None)
        teacher = None
        if course is not None and course.teacher_id:
            teacher = teachers.get(course.teacher_id)
        refs["student"] = display_name(student, "نامشخص") if student is not None else ""
        refs["teacher"] = display_name(teacher, "نامشخص") if teacher is not None else ""
        if course is not None:
            refs["course"] = course.title or "کلاس بدون نام"
        if branch_id is not None and branches.get(branch_id):
            refs["branch"] = branches[branch_id]
        if entity_type == "installment" and enrollment is not None:
            parts = [part for part in (refs["student"], refs.get("course", "")) if part]
            if parts:
                refs["enrollment"] = " — ".join(parts)
        # کلیدهای تهی حذف می‌شوند (تا کلاینت «None» نبیند) اما student/teacher همیشه
        # می‌مانند — چون UI برای آن‌ها placeholder ثابت دارد («بدون معلم»/«—»).
        kept = {key: value for key, value in refs.items() if value}
        kept.setdefault("student", "")
        kept.setdefault("teacher", "")
        refs_by_log[log_id] = kept
    return refs_by_log, student_by_log


def _activity_actor(db: Session, entity_type: str, entity_id: Optional[int],
                    candidates: Tuple[Optional[datetime.datetime], ...]) -> Tuple[str, Optional[str]]:
    """کاربر تغییردهنده از `ActivityLog` موجود — فقط وقتی لاگ ممیزی کاربر ندارد.

    نوشتن‌های سیستمی/ورکری (پایان خودکار جلسه، تسویهٔ خودکار، …) در `FinancialAuditLog`
    بی‌`username` می‌مانند؛ همان عملیات در `ActivityLog` (که در مسیرهای مالی نوشته می‌شود)
    کاربر را دارد ⇒ به‌جای موتور لاگ جدید، از همان منبع موجود fallback می‌گیریم.

    تطبیق: `target_id` = شناسهٔ همان موجودیت + action هم‌خانواده + پنجرهٔ زمانی.
    `candidates` عمداً چندتایی است: `FinancialAuditLog.timestamp` را listener با
    `utcnow()` می‌نویسد ولی بخشی از مسیرهای قدیمی/تست‌ها زمان محلی می‌گذارند و
    `ActivityLog.timestamp` هم `utcnow()` است ⇒ پنجره از min تا max هر دو تفسیر
    (به‌علاوهٔ ±۳۰ دقیقه) گرفته می‌شود تا تفاوت ساعت‌منطقه باعث از دست رفتن کاربر نشود.
    """
    if entity_id is None:
        return "", None
    family = {
        "installment": ("create_installment", "update_installment_amount", "delete_installment",
                        "pay_installment_manual"),
        "transaction": ("transaction_refund", "transaction_edit", "transaction_delete",
                        "transaction_reversed", "submit_payment", "online_payment_success"),
    }.get(entity_type)
    if not family:
        return "", None
    stamps = [stamp for stamp in candidates if stamp is not None] or [datetime.datetime.utcnow()]
    window = datetime.timedelta(minutes=_ACTOR_WINDOW_MINUTES)
    # نکتهٔ داده‌ای (بدون حدس، از روی کد): مسیرهای مختلف `ActivityLog.target_id` را جور
    # دیگری پر می‌کنند — استرداد تراکنش در finance.py شناسهٔ **دانش‌آموز** را می‌گذارد و
    # «#<شناسهٔ تراکنش>» را در details می‌نویسد، ولی مسیرهای قسط شناسهٔ خود قسط را
    # می‌گذارند. پس هر دو شکل تطبیق داده می‌شود تا نام کاربر گم نشود.
    try:
        row = (db.query(ActivityLog)
               .filter(ActivityLog.action.in_(family),
                       or_(ActivityLog.target_id == entity_id,
                           ActivityLog.details.like(f"%#{entity_id}%")),
                       ActivityLog.timestamp >= min(stamps) - window,
                       ActivityLog.timestamp <= max(stamps) + window)
               .order_by(ActivityLog.id.desc())
               .first())
    except Exception:
        row = None
    if row is None or not row.admin_username:
        return "", None
    return row.admin_username, row.action


def _resolve_search(db: Session, term: str) -> Tuple[set, set]:
    """جست‌وجوی نام ⇒ (شناسهٔ تراکنش‌ها, شناسهٔ قسط‌ها) — «پیشنهاد من» آیتم ۸.

    منابع تطبیق: نام دانش‌آموز · نام معلم (از کلاسِ تراکنش/قسط) · عنوان کلاس · نام شعبه ·
    گیرندهٔ رسید · کد ملی/موبایل. همه با یک ILIKE/LIKE روی هر جدول (بدون حلقه روی ردیف‌ها).
    """
    like = f"%{term}%"
    # نام کامل هم تطبیق داده می‌شود («مریم احمدی» نه در first_name است نه در last_name)
    student_full = func.coalesce(Student.first_name, "") + " " + func.coalesce(Student.last_name, "")
    teacher_full = func.coalesce(Teacher.first_name, "") + " " + func.coalesce(Teacher.last_name, "")
    student_ids = {row[0] for row in db.query(Student.id).filter(
        or_(Student.first_name.like(like), Student.last_name.like(like), student_full.like(like),
            Student.national_code.like(like), Student.student_mobile.like(like),
            Student.parent_mobile.like(like))).limit(_SEARCH_ID_LIMIT).all()}
    teacher_ids = {row[0] for row in db.query(Teacher.id).filter(
        or_(Teacher.first_name.like(like), Teacher.last_name.like(like), teacher_full.like(like),
            Teacher.mobile.like(like))).limit(_SEARCH_ID_LIMIT).all()}
    teacher_courses = {row[0] for row in db.query(Course.id).filter(
        Course.teacher_id.in_(teacher_ids)).limit(_SEARCH_ID_LIMIT).all()} if teacher_ids else set()
    title_courses = {row[0] for row in db.query(Course.id).filter(
        Course.title.like(like)).limit(_SEARCH_ID_LIMIT).all()}
    course_ids = teacher_courses | title_courses
    branch_ids = {row[0] for row in db.query(Branch.id).filter(
        Branch.name.like(like)).limit(_SEARCH_ID_LIMIT).all()}

    tx_query = db.query(Transaction.id).filter(or_(
        Transaction.student_id.in_(student_ids),
        Transaction.course_id.in_(course_ids),
        Transaction.branch_id.in_(branch_ids),
        Transaction.receiver.like(like),
        Transaction.description.like(like),
    ))
    tx_ids = {row[0] for row in tx_query.limit(_SEARCH_ID_LIMIT).all()}

    enrollment_ids = {row[0] for row in db.query(Enrollment.id).filter(or_(
        Enrollment.student_id.in_(student_ids),
        Enrollment.course_id.in_(course_ids),
        Enrollment.branch_id.in_(branch_ids),
    )).limit(_SEARCH_ID_LIMIT).all()}
    inst_ids = {row[0] for row in db.query(Installment.id).filter(
        Installment.enrollment_id.in_(enrollment_ids)).limit(_SEARCH_ID_LIMIT).all()
    } if enrollment_ids else set()
    return tx_ids, inst_ids


class AuditLogEntry(BaseModel):
    id: int
    timestamp: str
    username: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    changed_fields: List[str] = []
    # FIX (گروه۲/آیتم ۸): فیلدهای نمایشی جدید — همه افزودنی‌اند (کلیدهای بالا دست‌نخورده)
    labels: Dict[str, str] = {}                 # نام ستون → برچسب فارسی
    changed_labels: List[str] = []              # برچسب فارسی ستون‌های تغییریافته
    change_summary: str = ""                    # جملهٔ خوانا: «مبلغ: 100,000 ← 250,000»
    action_label: str = ""                      # ایجاد/ویرایش/حذف/باطل‌شده/برگشت‌خورده
    change_type: str = ""                       # کلید ماشین‌خوان نوع تغییر
    action_color: str = ""                      # رنگ پیشنهادی ردیف (Material)
    icon_color: str = ""                        # رنگ آیکون همان نوع تغییر
    entity_refs: Dict[str, Any] = {}            # نام‌ها به‌جای شناسهٔ خام (کلاس/شعبه/دانش‌آموز/معلم)
    student_id: Optional[int] = None
    student_name: str = ""
    student_statement_path: str = ""            # لینک مستقیم به صورت‌حساب دانش‌آموز
    actor_username: str = ""                    # کاربر تغییردهنده (با fallback روی ActivityLog)
    actor_source: str = ""                      # audit_context | activity_log | none
    actor_action: Optional[str] = None          # برچسب فارسیِ عملیاتِ ActivityLog (در حالت fallback)
    actor_action_key: Optional[str] = None      # همان action خام (برای فیلتر/دیباگ)


class AuditTrailResponse(BaseModel):
    logs: List[AuditLogEntry]
    total: int
    page: int
    limit: int
    pages: int


def _load_json(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """JSON خراب ⇒ هرگز ۵۰۰ نمی‌دهد."""
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except Exception:
        return {"raw": raw[:_MAX_CELL_CHARS]}
    return value if isinstance(value, dict) else {"value": value}


def _changed_fields(action: str, old: Optional[Dict[str, Any]], new: Optional[Dict[str, Any]]) -> List[str]:
    # کلید مصنوعی «raw» (JSON خراب که قابل تفسیر نبود) ستون واقعی نیست ⇒ نویز گزارش نشود.
    old = {key: value for key, value in (old or {}).items() if key != "raw"}
    new = {key: value for key, value in (new or {}).items() if key != "raw"}
    if action == "create":
        return sorted(key for key, value in new.items() if value is not None)
    if action == "delete":
        return sorted(key for key, value in old.items() if value is not None)
    keys = set(old) | set(new)
    return sorted(key for key in keys if old.get(key) != new.get(key))


def _to_local_naive(value: datetime.datetime) -> datetime.datetime:
    """UTC ذخیره‌شده → وقت محلی سرور (برای نمایش درست در اپ)."""
    try:
        return value.replace(tzinfo=datetime.timezone.utc).astimezone().replace(tzinfo=None)
    except Exception:
        return value


def _to_utc_naive(value: datetime.datetime) -> datetime.datetime:
    """تاریخ/ساعت محلی سرور → UTC (برای فیلتر روی ستون UTC)."""
    try:
        return value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    except Exception:
        return value


_JALALI_DATE_RE = re.compile(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$")


def _parse_bound(value: Optional[str], *, is_end: bool) -> Tuple[Optional[datetime.datetime], bool]:
    """پارامتر تاریخ/ساعت را به UTC تبدیل می‌کند.

    پذیرش: ISO (`2026-09-16` یا `2026-09-16T14:30[:00]`)، Jalali (`1405/06/25` — سال < 1700).
    برمی‌گرداند (datetime_utc, inclusive)؛ برای تاریخ خالصِ end، «کل آن روز» پوشش داده می‌شود.
    """
    if value is None:
        return None, True
    text = value.strip().replace("T", " ")
    if not text:
        return None, True

    match = _JALALI_DATE_RE.match(text)
    if match:
        year, month, day = (int(part) for part in match.groups())
        try:
            if year < 1700:  # جلالی (هم‌راستا با today_summary.parse_project_date)
                from today_summary import jalali_to_gregorian
                date_value = jalali_to_gregorian(year, month, day)
            else:
                date_value = datetime.date(year, month, day)
        except Exception:
            raise HTTPException(status_code=400, detail=f"تاریخ نامعتبر است: {value}")
        start = datetime.datetime.combine(date_value, datetime.time.min)
        if is_end:
            return _to_utc_naive(start + datetime.timedelta(days=1)), False  # کل روز پایان
        return _to_utc_naive(start), True

    try:
        parsed = datetime.datetime.fromisoformat(text)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="قالب تاریخ نامعتبر است (نمونه‌ی درست: 2026-09-16 یا 1405/06/25)",
        )
    return _to_utc_naive(parsed), True


@router.get("/audit-trail/logs", response_model=AuditTrailResponse)
def list_audit_logs(
    entity_type: Optional[str] = Query(None, description="transaction | installment"),
    entity_id: Optional[int] = Query(None, ge=1, description="شناسه‌ی رکورد مالی"),
    action: Optional[str] = Query(None, description="create | update | delete"),
    user_id: Optional[int] = Query(None, ge=1, description="فیلتر بر اساس کاربر"),
    start_date: Optional[str] = Query(None, description="از تاریخ (ISO یا جلالی)"),
    end_date: Optional[str] = Query(None, description="تا تاریخ (ISO یا جلالی، شامل کل روز)"),
    search: Optional[str] = Query(None, description="جست‌وجوی نام دانش‌آموز/معلم/کلاس/شعبه/گیرنده"),
    page: int = Query(1, ge=1),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    _: str = Depends(check_admin_access),
    db: Session = Depends(get_db),
):
    """تاریخچه‌ی تغییرات مالی، صفحه‌بندی‌شده و فیلترپذیر (فقط ادمین)."""
    if entity_type is not None and entity_type not in ENTITY_TYPES:
        raise HTTPException(status_code=400, detail="entity_type باید transaction یا installment باشد")
    if action is not None and action not in ACTIONS:
        raise HTTPException(status_code=400, detail="action باید create یا update یا delete باشد")

    start_dt, start_inclusive = _parse_bound(start_date, is_end=False)
    end_dt, end_inclusive = _parse_bound(end_date, is_end=True)
    if start_dt and end_dt and (
        start_dt > end_dt or (start_dt == end_dt and not end_inclusive)
    ):
        # Date-only end bounds are exclusive midnight of the following day; equality
        # therefore means a reversed/empty range (e.g. 29th through the 28th).
        raise HTTPException(status_code=400, detail="start_date بعد از end_date است")

    query = db.query(FinancialAuditLog)
    # FIX (گروه۲/آیتم ۸ — «پیشنهاد من»): جست‌وجو بر اساس نام (نه فقط شناسه).
    # اسم‌ها در جدول لاگ ذخیره نمی‌شوند (سند خام باید دست‌نخورده بماند) ⇒ نام به شناسه
    # ترجمه و روی `entity_id` فیلتر می‌شود؛ `total`/`pages` هم درست می‌مانند.
    search_term = (search or "").strip()
    if search_term:
        tx_ids, inst_ids = _resolve_search(db, search_term)
        if entity_type == "transaction":
            inst_ids = set()
        elif entity_type == "installment":
            tx_ids = set()
        pairs = ([("transaction", tx_id) for tx_id in tx_ids]
                 + [("installment", inst_id) for inst_id in inst_ids])
        if not pairs:
            return AuditTrailResponse(logs=[], total=0, page=page, limit=limit, pages=0)
        pairs = pairs[:_SEARCH_ID_LIMIT]
        query = query.filter(tuple_(FinancialAuditLog.entity_type, FinancialAuditLog.entity_id)
                             .in_(pairs))
    if entity_type is not None:
        query = query.filter(FinancialAuditLog.entity_type == entity_type)
    if entity_id is not None:
        query = query.filter(FinancialAuditLog.entity_id == entity_id)
    if action is not None:
        query = query.filter(FinancialAuditLog.action == action)
    if user_id is not None:
        query = query.filter(FinancialAuditLog.user_id == user_id)
    if start_dt is not None:
        query = query.filter(FinancialAuditLog.timestamp >= start_dt if start_inclusive
                             else FinancialAuditLog.timestamp > start_dt)
    if end_dt is not None:
        query = query.filter(FinancialAuditLog.timestamp <= end_dt if end_inclusive
                             else FinancialAuditLog.timestamp < end_dt)

    total = query.count()
    rows = (
        query.order_by(FinancialAuditLog.timestamp.desc(), FinancialAuditLog.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    # FIX (گروه۲/آیتم ۸): دو پاس روی همان ردیف‌های صفحه — پاس اول فقط شناسه‌ها را جمع
    # می‌کند تا join نام‌ها **دسته‌ای** انجام شود (بدون N+1؛ limit صفحه حداکثر 200 است).
    parsed: List[Tuple[Any, Optional[Dict[str, Any]], Optional[Dict[str, Any]], List[str], Dict[str, set]]] = []
    page_ids: Dict[str, set] = {"student_ids": set(), "course_ids": set(), "branch_ids": set(),
                                "enrollment_ids": set(), "installment_enrollment_ids": set()}
    for row in rows:
        old_values = _load_json(row.old_values)
        new_values = _load_json(row.new_values)
        wanted: Dict[str, set] = {}
        _collect_ref_ids(row.entity_type, old_values, new_values, wanted)
        for key in ("student_id", "course_id", "branch_id", "enrollment_id"):
            page_ids[f"{key}s"] |= wanted.get(key, set())
        if row.entity_type == "installment":
            # قسط فقط `enrollment_id` دارد ⇒ زنجیرهٔ قسط→ثبت‌نام→(دانش‌آموز/کلاس/معلم)
            page_ids["installment_enrollment_ids"] |= wanted.get("enrollment_id", set())
        parsed.append((row, old_values, new_values,
                       _changed_fields(row.action, old_values, new_values), wanted))

    refs_by_log, student_id_by_log = _entity_refs_batch(
        db, [(row.id, row.entity_type, wanted) for row, _o, _n, _c, wanted in parsed], page_ids)

    logs: List[AuditLogEntry] = []
    for row, old_values, new_values, changed, wanted in parsed:
        action_label, change_type, icon_color = _change_type_meta(row.action, old_values, new_values)
        refs = refs_by_log.get(row.id, {})
        student_id = student_id_by_log.get(row.id)
        student_name = refs.get("student", "")
        # «لینک مستقیم به صورت‌حساب دانش‌آموز»: مسیرِ همان اندپوینت موجود
        # (GET /reports/student_statement) تا کلاینت فقط باز کند — اندپوینت جدید لازم نیست.
        statement_path = f"/reports/student_statement?student_id={student_id}" if student_id else ""

        # timestamp خام (UTC طبق listener) + تفسیر محلی — هر دو به fallback کاربر داده می‌شود
        when_utc = _to_utc_naive(row.timestamp) if row.timestamp else None
        actor_action_key = None
        if row.username:
            actor_username, actor_source, actor_action = row.username, "audit_context", None
        else:
            # نوشتن سیستمی/ورکری ⇒ نام کاربر از ActivityLog موجود (موتور لاگ جدید نساختیم)
            activity_username, activity_action = _activity_actor(
                db, row.entity_type, row.entity_id, (row.timestamp, when_utc))
            if activity_username:
                actor_username, actor_source = activity_username, "activity_log"
                actor_action = ACTIVITY_ACTION_LABELS.get(activity_action, activity_action)
                actor_action_key = activity_action
            else:
                actor_username, actor_source, actor_action = "", "none", None

        logs.append(AuditLogEntry(
            id=row.id,
            timestamp=_to_local_naive(row.timestamp).isoformat(sep=" ") if row.timestamp else "",
            username=row.username,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=row.ip_address,
            changed_fields=changed,
            labels={key: _field_label(key) for key in changed},
            changed_labels=[_field_label(key) for key in changed],
            change_summary=_change_summary(row.action, changed, old_values, new_values),
            action_label=action_label,
            change_type=change_type,
            # رنگ ردیف = رنگ «نوع تغییر» (برگشت‌خورده قرمز، باطل‌شده خاکستری، …) نه رنگ action خام؛
            # در غیر این صورت یک استرداد همیشه نارنجیِ «ویرایش» دیده می‌شد.
            action_color=CHANGE_TYPE_COLORS.get(change_type, ACTION_COLORS.get(row.action, "#607D8B")),
            icon_color=icon_color,
            entity_refs=refs,
            student_id=student_id,
            student_name=student_name,
            student_statement_path=statement_path,
            actor_username=actor_username,
            actor_source=actor_source,
            actor_action=actor_action,
            actor_action_key=actor_action_key,
        ))

    pages = (total + limit - 1) // limit if limit else 0
    return AuditTrailResponse(logs=logs, total=total, page=page, limit=limit, pages=pages)
