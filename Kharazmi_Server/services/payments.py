
import datetime
import html
import os

from fastapi import Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
from dependencies import check_admin_access, check_admin_or_secretary_access, display_name, get_db
from models import (
    ActivityLog,
    Course,
    Enrollment,
    Installment,
    SmsLog,
    Student,
    Transaction,
    TransactionInstallmentAllocation,
    User,
)
from payment_gateways import get_payment_gateway
from schemas import FinanceSubmitData
from services.branch_scope import get_user_branch_filter

"""لایهٔ سرویسِ «پرداخت» — بدنهٔ دامنه‌ایِ مسیرهای مالی درگاه و رسید.

شامل: کال‌بک درگاه (`GET /finance/payment/callback`) با صفحه‌های HTMLِ وضعیت،
ثبت پرداخت (`POST /finance/pay`) با کلید idempotency، و بازگشتِ رسید
(`POST /finance/transaction/{id}/refund`)؛ به‌همراه هلپرهای خصوصیِ همین مسیرها
(زمانِ شمسی، بازپخشِ پرداختِ idempotent، صفحه‌های کال‌بک) و فلگِ ویژگیِ درگاه.

قرارداد لایه در `services/__init__.py`: بدون route و بدون APIRouter. سه handlerِ
این ماژول در `routers/finance.py` به‌صورت **پوستهٔ HTTP** باقی مانده‌اند، چون
تست‌ها آن‌ها را مستقیم و گاهی پوزیشنال صدا می‌زنند
(`finance.refund_transaction(original.id, db=..., _="admin")`) و امضایشان
قرارداد OpenAPI است. `routers/finance.py` نام‌های مشترک (`_jalali_now_str`،
`PAYMENT_GATEWAY_ENABLED`) را بازصادرات می‌کند چون بقیهٔ handlerهای همان فایل
هنوز از آن‌ها استفاده می‌کنند.

استثنای مستند: `pay_installment_manually` عمداً در روتر مانده و پوسته نشده —
`test_tuition_installments_audit.py:684` نام `ActivityLog` را روی فضای
`routers.finance` مانکی‌پچ می‌کند تا «خطا در آخرین قدم» را بسازد؛ اگر بدنه به این
لایه می‌آمد آن patch بی‌اثر می‌شد و تست سبزِ کاذب می‌داد.
"""


# --- Feature flag درگاه پرداخت آنلاین ---
# پیش‌فرض false: تا اتصال درگاه واقعی بانکی، کال‌بک و صفحه‌ی شبیه‌ساز 404 می‌دهند.
PAYMENT_GATEWAY_ENABLED = os.getenv("PAYMENT_GATEWAY_ENABLED", "false").lower() in ("1", "true", "yes")


def _jalali_now_str() -> str:
    """FIX L7: paid_at شمسی (هماهنگ با due_date و Transaction.date) + ساعت سرور."""
    from today_summary import jalali_date_string  # lazy، مثل H3-B3 همین فایل
    _now = datetime.datetime.now()
    return jalali_date_string(_now.date()) + _now.strftime(" %H:%M")


def _replay_idempotent_payment(db: Session, key: str, data: FinanceSubmitData):
    """FIX (audit-v2/idempotency-قدم۱): اگر کلیدی قبلاً پردازش شده، همان نتیجه برگردد — فقط-خواندنی، بدون هیچ نوشتن.
    برمی‌گرداند: dict پاسخ، یا None اگر کلید تازه است. 422 اگر کلید با مبلغ/شاگرد متفاوت reuse شده باشد (باگ کلاینت، نه retry)."""
    rows = (
        db.query(Transaction)
        .filter(Transaction.idempotency_key == key, Transaction.is_deleted == False)
        .order_by(Transaction.id.asc())
        .all()
    )
    if not rows:
        return None
    if rows[0].student_id != data.student_id or sum((r.amount or 0) for r in rows) != data.amount:
        raise HTTPException(status_code=422, detail="این کلید پرداخت قبلاً با مبلغ/شاگرد دیگری ثبت شده؛ کلید تازه تولید کنید")
    _st = db.query(Student).filter(Student.id == data.student_id).first()
    return {
        "message": "مبلغ ثبت و حساب بروزرسانی شد." + (" (تقسیم هر دو)" if data.target_wallet == "both" else ""),
        "receipt_id": rows[0].id,
        "receipt_ids": [r.id for r in rows],
        "new_balance_teacher": (_st.wallet_teacher or 0) if _st else 0,
        "new_balance_institute": (_st.wallet_institute or 0) if _st else 0,
        "duplicate": True,
    }


# --- ۲ و ۳. کال‌بک / وب‌هووک درگاه پرداخت آنلاین (با قابلیت Idempotency کامل) ---
# --- FIX F-B1: صفحه‌های کمکی کال‌بک (بدون هیچ نوشتن/وریفای؛ فقط مسیریابی حالت) ---
def _callback_static_page(title: str, message: str, color: str):
    """نتیجه‌ی پایانیِ قبلاً ثبت‌شده (بازپخش) — ایستا، بدون رفرش خودکار."""
    return HTMLResponse(content=f"""
    <html>
    <head><title>{html.escape(title)}</title><meta charset="utf-8"></head>
    <body style="font-family: Tahoma; text-align: center; direction: rtl; padding-top: 50px; background-color: #f7f7f7;">
        <div style="border: 2px solid {color}; display: inline-block; padding: 30px; border-radius: 12px; background: white; width: 450px;">
            <h2 style="color: {color};">{html.escape(title)}</h2>
            <p>{html.escape(message)}</p>
        </div>
    </body>
    </html>
    """)


def _callback_refresh_page(payment_id: int):
    """تعارض گذرا (دیگری جلوتر وضعیت را برد) — رفرش خودکار، حالت تازه را نشان می‌دهد."""
    return HTMLResponse(content=f"""
    <html>
    <head><title>به‌روزرسانی وضعیت پرداخت</title><meta charset="utf-8"><meta http-equiv="refresh" content="3"></head>
    <body style="font-family: Tahoma; text-align: center; direction: rtl; padding-top: 50px; background-color: #f7f7f7;">
        <div style="border: 2px solid #007bff; display: inline-block; padding: 30px; border-radius: 12px; background: white; width: 450px;">
            <h2 style="color: #007bff;">وضعیت پرداخت در حال به‌روزرسانی است</h2>
            <p>پرداخت #{payment_id} هم‌زمان در حال پردازش است؛ چند لحظه دیگر به‌صورت خودکار تازه می‌شود.</p>
            <p><a href="">تلاش مجدد</a></p>
        </div>
    </body>
    </html>
    """)


def _callback_processing_page(payment_id: int):
    """VERIFYING تازه (دارنده‌ی دیگری در حال وریفای است) — صبر + رفرش خودکار، بدون وریفای دوم."""
    return HTMLResponse(content=f"""
    <html>
    <head><title>پرداخت در حال پردازش</title><meta charset="utf-8"><meta http-equiv="refresh" content="5"></head>
    <body style="font-family: Tahoma; text-align: center; direction: rtl; padding-top: 50px; background-color: #f7f7f7;">
        <div style="border: 2px solid #ffc107; display: inline-block; padding: 30px; border-radius: 12px; background: white; width: 450px;">
            <h2 style="color: #d39e00;">پرداخت در حال پردازش است</h2>
            <p>پرداخت #{payment_id} در درگاه در حال تایید نهایی است؛ لطفاً صبر کنید، این صفحه خودکار تازه می‌شود.</p>
            <p><a href="">تلاش مجدد</a></p>
        </div>
    </body>
    </html>
    """)


def payment_callback(
    request: Request,
    payment_id: int,
    status: str,
    gateway_ref: str | None = None,
    db: Session = Depends(get_db)
):
    """بدنهٔ دامنه‌ایِ `payment_callback`؛ توضیحِ HTTP در پوستهٔ روتر است."""
    # TODO(security) (audit-v2/#12 + FIX F-B1): وضعیت بازنویسی کال‌بک:
    #  ۱) DONE: تطابق authority با ردیف PENDING (عدم‌تطابق → ۴۰۰ بدون تغییر وضعیت)؛
    #  ۲) OPEN: وریفای واقعی درگاه (امضا/استعلام) هنوز Mock است — اتصال درگاه واقعی + کلید merchant
    #     لازم دارد؛ تا آن زمان: فلگ پیش‌فرض خاموش + نگهبان ENV=production (fail-loud).
    #     نکته‌ی تک‌مصرف برای بازنویسی آینده: پاسخ «قبلاً وریفای‌شده» درگاه را موفقیت حساب کن، چون
    #     بازیابی تسخیر کهنه (کرش بین وریفای و ثبت نهایی) دوباره وریفای می‌زند و درگاهِ مصرف‌شده خطا می‌دهد!
    #  ۳) DONE: هرگز به status کوئری اعتماد نمی‌شود (فقط راهنمای انصراف؛ تنها منبع حقیقت کردیت = پاسخ وریفای)؛
    #  ۴) DONE: ماشین‌حالت اتمیک PENDING→VERIFYING→SUCCESS/FAILED (+CANCELLED) با UPDATE مشروط و بازیابی
    #     تسخیر کهنه (۱۰ دقیقه)؛ بازپخش روی وضعیت پایانی بدون وریفای مجدد.
    if not PAYMENT_GATEWAY_ENABLED:
        raise HTTPException(status_code=404, detail="درگاه پرداخت آنلاین غیرفعال است")
    # FIX F-B1: نگهبان پروداکشن — ماژول payment_gateways سراسر Mock است؛ حتی با فلگ روشن،
    # در پروداکشن fail-loud (500) نه mint ساکت. (factory هم مستقلاً همین گارد را دارد.)
    if os.getenv("ENV", "development").lower() == "production":
        raise HTTPException(status_code=500, detail="درگاه پرداخت آنلاین در پروداکشن پیکربندی نشده است")
    # FIX F-B1: بدون with_for_update (روی SQLite بی‌اثر است؛ گیت‌های واقعی، UPDATEهای مشروط پایین‌اند —
    # همان الگوی H8-P4). این خواندن فقط مسیریابی اولیه است؛ هر تصمیم با UPDATE مشروط بازتأیید می‌شود.
    payment = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="تراکنش آنلاین یافت نشد")

    # Idempotency: بازپخش روی وضعیت پایانی — همان نتیجه، بدون هیچ وریفای/نوشتن مجدد.
    # (وریفای واقعی تک‌مصرف است؛ FAILED قبلاً دوباره وارد وریفای می‌شد — دیگر نه.)
    # REFUNDED هم همان صفحه‌ی «از قبل ثبت شده» را می‌گیرد (پرداخت واقعاً ثبت شده بود).
    if payment.status in ("SUCCESS", "REFUNDED"):
        return HTMLResponse(content=f"""
        <html>
        <head>
            <title>تراکنش موفق</title>
            <meta charset="utf-8">
        </head>
        <body style="font-family: Tahoma; text-align: center; direction: rtl; padding-top: 50px; background-color: #f4fdf4;">
            <div style="border: 2px solid #28a745; display: inline-block; padding: 30px; border-radius: 12px; background: white; box-shadow: 0px 4px 12px rgba(0,0,0,0.05); width: 450px;">
                <h2 style="color: #28a745; margin-bottom: 20px;">تراکنش از قبل ثبت شده است</h2>
                <hr style="border: 0.5px solid #eee; margin-bottom: 20px;">
                <p>این پرداخت قبلاً با موفقیت پردازش و در سیستم ثبت شده است.</p>
                <p>شناسه رهگیری درگاه: <code>{payment.tracking_code}</code></p>
                <p>مبلغ پرداختی: <strong>{payment.amount:,} تومان</strong></p>
                <p style="color: #666; font-size: 0.9em; margin-top: 20px;">(رعایت قابلیت هم‌راستایی و عدم ثبت مجدد تراکنش تکراری)</p>
            </div>
        </body>
        </html>
        """)

    # FIX F-B1: بازپخش FAILED/CANCELLED دیگر وریفای مجدد نمی‌زند — فقط همان نتیجه‌ی پایانی.
    if payment.status == "FAILED":
        return _callback_static_page("پرداخت ناموفق", "این پرداخت قبلاً ناموفق ثبت شده و دوباره بررسی نمی‌شود.", "#dc3545")
    if payment.status == "CANCELLED":
        return _callback_static_page("پرداخت لغو شد", "این پرداخت قبلاً لغوشده ثبت شده است.", "#d39e00")

    # FIX F-B1: اتصال authority — شناسه‌ی برگشتی باید دقیقاً همان باشد که در initiate روی ردیف
    # PENDING ذخیره شده؛ وگرنه 400 بدون هیچ تغییر وضعیتی (fail-closed؛ جلوی enumeration با payment_id
    # تنها و دستکاری پرداخت دیگران). سطر بدون authority ذخیره‌شده هم بسته می‌ماند (initiate آینده همیشه ست می‌کند).
    if not gateway_ref or not payment.gateway_reference or gateway_ref != payment.gateway_reference:
        raise HTTPException(status_code=400, detail="شناسه‌ی درگاه با این پرداخت مطابقت ندارد")

    # FIX F-B1: ساخت درگاهِ همان‌مسیر (نه هاردکد زرین‌پال) — قبل از هر تسخیر؛ نام ناشناخته → 400.
    try:
        gateway = get_payment_gateway(payment.gateway or "zarinpal")
    except ValueError:
        raise HTTPException(status_code=400, detail="درگاه این پرداخت نامعتبر است")

    # FIX F-B1: status کوئری فقط «راهنما»ست نه «حقیقت» (OK/NOK همان قرارداد زرین‌پال واقعی است؛
    # Mock فعلی SUCCESS/FAILED می‌فرستد). تنها منبع حقیقتِ کردیت، پاسخ وریفای پایین است.
    if status.upper() in ("SUCCESS", "OK"):
        # FIX F-B1: تسخیر اتمیک PENDING→VERIFYING (الگوی H8-P4) — فقط یک کال‌بکِ هم‌زمان وارد وریفای
        # تک‌مصرف می‌شود؛ بازنده‌ها صفحه‌ی پردازش/رفرش می‌گیرند نه وریفای دوم.
        _claimed = (
            db.query(models.Payment)
            .filter(models.Payment.id == payment.id, models.Payment.status == "PENDING")
            .update({models.Payment.status: "VERIFYING", models.Payment.claimed_at: datetime.datetime.utcnow()}, synchronize_session=False)
        )
        db.commit()  # تسخیر قبل از فراخوان خارجی کامیت می‌شود (وریفای نگه‌داشتن تراکنش باز نمی‌خواهد).
        if _claimed != 1:
            # دیگری جلوتر است — یک خوانش تازه و مسیریابی بدون هیچ نوشتن/وریفای:
            payment = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
            if payment is not None and payment.status == "VERIFYING":
                _stale_cutoff = datetime.datetime.utcnow() - datetime.timedelta(minutes=10)
                _stale = payment.claimed_at is not None and payment.claimed_at < _stale_cutoff
                _reclaimed = 0
                if _stale:
                    # بازیابی تسخیر گیرکرده (کرش بین تسخیر و ثبت نهایی) — فقط اگر واقعاً کهنه باشد:
                    _reclaimed = (
                        db.query(models.Payment)
                        .filter(models.Payment.id == payment.id, models.Payment.status == "VERIFYING", models.Payment.claimed_at < _stale_cutoff)
                        .update({models.Payment.claimed_at: datetime.datetime.utcnow()}, synchronize_session=False)
                    )
                    db.commit()
                if _stale and _reclaimed == 1:
                    pass  # حالا ما دارنده‌ایم — ادامه به وریفای پایین.
                else:
                    return _callback_processing_page(payment.id)  # تازه است یا مسابقه را باختیم — صبر + رفرش.
            else:
                return _callback_refresh_page(payment_id)  # پایانی شده — رفرش، همان نتیجه را نشان می‌دهد.
        # تایید رسمی صحت مبلغ تراکنش از درگاه — فقط با مقادیر ذخیره‌شده‌ی سرور (هرگز ورودی کوئری):
        verified_ok, trk_code = gateway.verify_payment(payment.gateway_reference, payment.amount)

        if verified_ok:
            # FIX F-B1: پیش‌شرط‌های فقط-خواندنی قبل از علامت SUCCESS — هر کدام نامعتبر بود، همان سرنوشت
            # M12 (FAILED مشروط + رد حسابرسی + همان صفحه‌ی خطا؛ پول درگاه وریفای شده پس 400 نه).
            _bad_reason = None
            if (payment.amount or 0) <= 0:
                _bad_reason = ("online_payment_invalid_amount", f"مبلغ نامعتبر «{payment.amount}» برای پرداخت وریفای‌شده #{payment.id} — شارژ نشد، مغایرت‌گیری دستی لازم است.")
            elif payment.target_wallet not in ("teacher", "institute"):
                _bad_reason = ("online_payment_invalid_wallet", f"کیف نامعتبر «{payment.target_wallet}» برای پرداخت وریفای‌شده #{payment.id} (مبلغ {payment.amount:,}) — شارژ نشد، مغایرت‌گیری دستی لازم است.")
            elif payment.student_id is None or db.query(Student.id).filter(Student.id == payment.student_id).first() is None:
                _bad_reason = ("online_payment_missing_student", f"شاگرد #{payment.student_id} پرداخت وریفای‌شده #{payment.id} یافت نشد (مبلغ {payment.amount:,}) — شارژ نشد، مغایرت‌گیری دستی لازم است.")
            if _bad_reason is not None:
                _bad_action, _bad_details = _bad_reason
                _brows = (
                    db.query(models.Payment)
                    .filter(models.Payment.id == payment.id, models.Payment.status == "VERIFYING")
                    .update({models.Payment.status: "FAILED"}, synchronize_session=False)
                )
                if _brows != 1:
                    db.rollback()
                    return _callback_refresh_page(payment.id)
                db.add(ActivityLog(
                    admin_username="online_payment_system",
                    action=_bad_action,
                    target_id=payment.id,
                    target_name="online_payment",
                    details=_bad_details,
                ))
                db.commit()
                return HTMLResponse(content=f"""
            <html>
            <head><title>خطای پردازش پرداخت</title><meta charset="utf-8"></head>
            <body style="font-family: Tahoma; text-align: center; direction: rtl; padding-top: 50px; background-color: #fdf4f4;">
                <div style="border: 2px solid #dc3545; display: inline-block; padding: 30px; border-radius: 12px; background: white; width: 450px;">
                    <h2 style="color: #dc3545;">خطای پردازش پرداخت</h2>
                    <p>پرداخت شما در درگاه تایید شد ولی به‌خاطر خطای سیستمی در حساب شما ثبت نشد.</p>
                    <p>لطفاً با پشتیبانی تماس بگیرید (شناسه پرداخت: <code>{payment.id}</code>)؛ مبلغ شما محفوظ است.</p>
                </div>
            </body>
            </html>
            """)
            # ۱. تغییر وضعیت رکورد تراکنش آنلاین به موفق — UPDATE مشروط (فقط دارنده‌ی VERIFYING).
            _srows = (
                db.query(models.Payment)
                .filter(models.Payment.id == payment.id, models.Payment.status == "VERIFYING")
                .update({models.Payment.status: "SUCCESS", models.Payment.tracking_code: trk_code, models.Payment.paid_at: datetime.datetime.utcnow()}, synchronize_session=False)
            )
            if _srows != 1:
                db.rollback()  # چیزی جز علامت (کامیت‌نشده) در تراکنش نیست — VERIFYING دست‌نخورده می‌ماند.
                return _callback_refresh_page(payment.id)
            db.refresh(payment)  # UPDATE خام آبجکت را stale کرد؛ ادامه با مقادیر تازه.

            # ۲. بروزرسانی کیف پول دانش‌آموز — افزایش اتمیک (نه RMW؛ دو پرداخت هم‌زمان یک شاگرد هم گم نمی‌شود).
            student = db.query(Student).filter(Student.id == payment.student_id).first()
            _wrows = 0
            if student is not None:
                _wcol = Student.wallet_teacher if payment.target_wallet == "teacher" else Student.wallet_institute
                _wrows = (
                    db.query(Student)
                    .filter(Student.id == payment.student_id)
                    .update({_wcol: func.coalesce(_wcol, 0) + payment.amount}, synchronize_session=False)
                )
            if student is None or _wrows != 1:
                # شاگرد بین پیش‌شرط و این‌جا حذف شد — پول هنوز هیچ‌جا نرفته: کل تراکنش rollback،
                # سپس FAILED مشروط + رد حسابرسی (همان سرنوشت M12).
                db.rollback()
                db.query(models.Payment).filter(models.Payment.id == payment.id, models.Payment.status == "VERIFYING").update({models.Payment.status: "FAILED"}, synchronize_session=False)
                db.add(ActivityLog(
                    admin_username="online_payment_system",
                    action="online_payment_missing_student",
                    target_id=payment.id,
                    target_name="online_payment",
                    details=f"شاگرد #{payment.student_id} پرداخت وریفای‌شده #{payment.id} حین ثبت حذف شده بود (مبلغ {payment.amount:,}) — شارژ نشد، مغایرت‌گیری دستی لازم است.",
                ))
                db.commit()
                return _callback_static_page("خطای پردازش پرداخت", f"پرداخت شما در درگاه تایید شد ولی به‌خاطر خطای سیستمی در حساب شما ثبت نشد. لطفاً با پشتیبانی تماس بگیرید (شناسه پرداخت: {payment.id})؛ مبلغ شما محفوظ است.", "#dc3545")
            db.refresh(student)  # افزایش خام را ببین تا بالانس درست همگام شود.
            if student:  # همیشه True (گیت بالا)؛ ساختار بلوک پایین حفظ می‌شود.
                # همگام‌سازی بالانس کل دانش‌آموز
                # FIX: Bug 18 - derive the total only through the shared wallet helper.
                student.sync_wallet_balance()

                # ۳. درج فیزیکی در جدول تراکنش‌ها (Transactions) جهت حفظ Traceability مالی کامل بدون حذف
                from dependencies import get_next_sequence_value
                if payment.target_wallet == "teacher":
                    next_remittance = get_next_sequence_value(db, "remittance_teacher", 100001)
                else:
                    next_remittance = get_next_sequence_value(db, "remittance_institute", 100001)

                # FIX (audit-v2/#12-Bug9): شعبه‌ی رسید — شاگرد اول، وگرنه کلاسِ ثبت‌نام لینک‌شده (الگوی H7).
                # اگر هیچ‌کدام نبود: پول وریفای‌شده را گرو نمی‌گیریم (خلاف M12 که پول نامعتبر بود، این‌جا فقط
                # متادیتا ناقص است) — رسید با branch=NULL ثبت + هشدار حسابرسی برای تخصیص دستی. initiate آینده
                # باید شعبه را همان‌جا capture و 400 بدهد (بخش ۲ TODO بالا).
                _cb_branch = student.branch_id
                if _cb_branch is None and payment.enrollment_id:
                    _cb_en = db.query(Enrollment).filter(Enrollment.id == payment.enrollment_id).first()
                    _cb_co = db.query(Course).filter(Course.id == _cb_en.course_id).first() if _cb_en is not None else None
                    _cb_branch = _cb_co.branch_id if _cb_co is not None else None
                if _cb_branch is None:
                    db.add(ActivityLog(
                        admin_username="online_payment_system",
                        action="online_payment_missing_branch",
                        target_id=payment.id,
                        target_name="online_payment",
                        details=f"شعبه‌ی پرداخت وریفای‌شده #{payment.id} (شاگرد #{payment.student_id}) قابل‌تشخیص نیست — رسید بدون‌شعبه ثبت شد، تخصیص دستی لازم است.",
                    ))

                new_trans = Transaction(
                    student_id=payment.student_id,
                    enrollment_id=payment.enrollment_id,
                    branch_id=_cb_branch,
                    amount=payment.amount,
                    payment_method="online",
                    tracking_code=trk_code,
                    date=_jalali_now_str(),  # FIX (audit-v2/#12-H3): شمسی (قبلاً میلادی وسط ستون شمسی).
                    description=f"پرداخت آنلاین موفق بابت {payment.description or 'شهریه'}",
                    type="deposit",
                    target_wallet=payment.target_wallet,
                    remittance_number=next_remittance,
                )
                db.add(new_trans)
                db.flush()  # دریافت آیدی تراکنش جدید

                # 🔗 همگام‌سازی منبع حقیقت بدهی (الگوی submit_payment): پرداخت لینک‌شده total_paid را زیاد می‌کند
                if payment.enrollment_id:
                    # FIX F-B1: افزایش اتمیک مشروط (مالکیت/حذف‌نشده در WHERE؛ نه RMW با قفل نمایشی).
                    _erows = (
                        db.query(Enrollment)
                        .filter(Enrollment.id == payment.enrollment_id, Enrollment.is_deleted == False, Enrollment.student_id == payment.student_id)
                        .update({Enrollment.total_paid: func.coalesce(Enrollment.total_paid, 0) + payment.amount}, synchronize_session=False)
                    )
                    if _erows != 1:
                        # ثبت‌نام هم‌زمان حذف/جابه‌جا شد — پول در کیف امن است؛ فقط لینک بدهی از دست رفت (قابل مغایرت‌گیری).
                        db.add(ActivityLog(
                            admin_username="online_payment_system",
                            action="online_payment_enroll_link_lost",
                            target_id=payment.id,
                            target_name="online_payment",
                            details=f"لینک بدهی پرداخت وریفای‌شده #{payment.id} (ثبت‌نام #{payment.enrollment_id}) حین ثبت از دست رفت — مبلغ {payment.amount:,} در کیف شاگرد #{payment.student_id} شارژ شد، تخصیص دستی لازم است.",
                        ))

                # ۴. تخصیص هوشمند به اقساط پرداخت نشده دانش‌آموز (اولویت با قسط خاص یا قدیمی‌ترین اقساط)
                _use_fallback = not payment.installment_id
                _target_ok = False
                if payment.installment_id:
                    # FIX: Bug 13 - exclude archived Installment rows from this active view.
                    target_inst = db.query(Installment).filter(Installment.is_deleted == False).filter(Installment.id == payment.installment_id).first()
                    if target_inst and not target_inst.is_paid:
                        # FIX (audit-v2/closeout-قدم۳): مالکیت نیت هدفمند — قسط باید متعلق به شاگردِ پرداخت
                        # (و اگر پرداخت لینک است، همان ثبت‌نام) باشد؛ وگرنه (دستکاری installment_id؟) نیت خنثی
                        # و fallback اعمال می‌شود + رد حسابرسی. عمداً 400 نمی‌دهیم: پول درگاه وریفای شده و
                        # rollback کامل، اعتبار مشروع را هم دور می‌ریخت (authority درگاه یک‌بارمصرف است!).
                        _towner = db.query(Enrollment).filter(Enrollment.id == target_inst.enrollment_id).first()
                        if _towner is not None and not _towner.is_deleted and _towner.student_id == payment.student_id and (not payment.enrollment_id or target_inst.enrollment_id == payment.enrollment_id):
                            _target_ok = True
                        else:
                            _use_fallback = True
                            db.add(ActivityLog(
                                admin_username="online_payment_system",
                                action="targeted_installment_mismatch",
                                target_id=payment.id,
                                target_name="online_payment",
                                details=f"نیت هدفمند نامعتبر خنثی شد: قسط #{target_inst.id} (ثبت‌نام #{target_inst.enrollment_id}) متعلق به شاگرد #{payment.student_id} / ثبت‌نام {payment.enrollment_id} نیست — fallback اعمال شد.",
                            ))
                    if _target_ok:
                        # FIX (audit-v2/issue7): تسویه‌ی هدفمند اتمیک + ledger — همان الگوی submit (قبلاً RMW
                        # غیراتمیک که پوشش موازی را گم می‌کرد). مبلغ ledger = سهم واقعی همین پرداخت (کامل −
                        # پوشش قبلی)؛ اگر قسط هم‌زمان تسویه شده بود، ledger نوشته نمی‌شود (پس استردادش قسط
                        # دیگری را باز نمی‌کند) و پول همان اعتبار عمومی می‌ماند — عمداً 409 نمی‌دهیم چون
                        # پرداخت درگاه وریفای شده است. paid_amount هم هرگز به پایین clamp نمی‌شود (حفظ تاریخچه).
                        for _try in range(10):
                            db.refresh(target_inst)
                            if target_inst.is_paid or target_inst.is_deleted:
                                break
                            _talready = target_inst.paid_amount or 0
                            _tfull = target_inst.amount or 0
                            _tset = {Installment.is_paid: True, Installment.paid_at: _jalali_now_str()}
                            if _tfull > _talready:
                                _tset[Installment.paid_amount] = _tfull
                            _trows = (
                                db.query(Installment)
                                .filter(Installment.id == target_inst.id, Installment.is_paid == False, Installment.is_deleted == False, func.coalesce(Installment.paid_amount, 0) == _talready)
                                .update(_tset, synchronize_session=False)
                            )
                            if _trows == 1:
                                if _tfull > _talready:
                                    db.add(TransactionInstallmentAllocation(transaction_id=new_trans.id, installment_id=target_inst.id, amount=_tfull - _talready))
                                break
                if _use_fallback:
                    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
                    # FIX (audit-v2/issue9-الف): مثل submit — لینک‌شده فقط همان ثبت‌نام؛ بی‌لینک cross قدیمی.
                    if payment.enrollment_id:
                        enrollment_ids = [payment.enrollment_id]
                    else:
                        # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
                        enrollments = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.student_id == payment.student_id).all()
                        enrollment_ids = [e.id for e in enrollments]
                    if enrollment_ids:
                        unpaid_installments = (
                            # FIX: Bug 13 - exclude archived Installment rows from this active view.
                            db.query(Installment).filter(Installment.is_deleted == False)
                            .filter(
                                Installment.enrollment_id.in_(enrollment_ids),
                                Installment.is_paid == False
                            )
                            .order_by(Installment.due_date.asc())
                            .all()
                        )
                        remaining_payment = payment.amount
                        # FIX (audit-v2/issue7+9-قدم۳): همان الگوی UPDATE مشروط submit (قبلاً RMW غیراتمیک) +
                        # ledger روی تک‌رسید همین پرداخت (new_trans قبلاً flush شده و آیدی دارد).
                        # 409 در کال‌بک فقط همین پرداخت را rollback می‌کند (تک‌پرداخت در هر کال) — با توجه به
                        # TODO بازنویسی کال‌بک و غیرفعال‌بودن درگاه، قابل‌قبول.
                        for inst in unpaid_installments:
                            if remaining_payment <= 0:
                                break
                            for _try in range(10):
                                db.refresh(inst)
                                if inst.is_paid or inst.is_deleted:
                                    break
                                _already = inst.paid_amount or 0
                                _owed = (inst.amount or 0) - _already
                                if _owed <= 0:
                                    db.query(Installment).filter(Installment.id == inst.id, Installment.is_paid == False).update({Installment.is_paid: True}, synchronize_session=False)
                                    break
                                _cover = min(remaining_payment, _owed)
                                _new_paid = _already + _cover
                                _fully = _new_paid >= (inst.amount or 0)
                                _set = {Installment.paid_amount: _new_paid}
                                if _fully:
                                    _set[Installment.is_paid] = True
                                    _set[Installment.paid_at] = _jalali_now_str()
                                _rows = (
                                    db.query(Installment)
                                    .filter(Installment.id == inst.id, Installment.is_paid == False, Installment.is_deleted == False, func.coalesce(Installment.paid_amount, 0) == _already)
                                    .update(_set, synchronize_session=False)
                                )
                                if _rows == 1:
                                    remaining_payment -= _cover
                                    db.add(TransactionInstallmentAllocation(transaction_id=new_trans.id, installment_id=inst.id, amount=_cover))
                                    break
                            else:
                                # FIX F-B1: اتمام تلاش تخصیص دیگر rollback+409 نمی‌دهد (وریفای تک‌مصرف مصرف شده؛
                                # پول باید همان‌جا در کیف/رسید بنشیند). رد حسابرسی + ادامه به قسط بعدی.
                                db.add(ActivityLog(
                                    admin_username="online_payment_system",
                                    action="online_payment_alloc_deferred",
                                    target_id=payment.id,
                                    target_name="online_payment",
                                    details=f"تخصیص خودکار قسط #{inst.id} برای پرداخت وریفای‌شده #{payment.id} پس از تلاش ناموفق ماند — مبلغ در کیف/رسید ثبت شد، تخصیص دستی لازم است.",
                                ))
                                continue

                # ۵. ثبت لاگ حسابرسی (Audit Log) جهت تغییرات مبالغ
                db.add(ActivityLog(
                    admin_username="online_payment_system",
                    action="online_payment_success",
                    target_id=student.id,
                    target_name=display_name(student, "نامشخص"),
                    details=f"پرداخت آنلاین موفق به مبلغ {payment.amount:,} تومان به کیف پول {payment.target_wallet}. شماره تراکنش: {new_trans.id}"
                ))

                # ۶. ارسال نوتیفیکیشن‌های درون‌برنامه‌ای و پیامکی
                try:
                    today_str = _jalali_now_str()  # FIX (audit-v2/#12-H3): شمسی.
                    msg_sms = f"ولی محترم، پرداخت آنلاین بابت فرزند شما {display_name(student, 'دانش‌آموز')} به مبلغ {payment.amount:,} تومان با موفقیت انجام شد. کد پیگیری: {trk_code}"
                    db.add(SmsLog(
                        target_group=f"online_pay_{payment.id}",
                        message_text=msg_sms,
                        sent_count=1,
                        date=today_str
                    ))

                    from dependencies import NotificationService, ensure_student_shadow_users
                    if student.user_id is None:
                        ensure_student_shadow_users(db, student)
                    # نوتیفیکیشن دانش‌آموز
                    NotificationService.send_notification(
                        db=db, recipient_user_id=student.user_id, recipient_role="student",
                        type="payment", title="✅ پرداخت آنلاین موفق",
                        body=f"پرداخت آنلاین شما به مبلغ {payment.amount:,} تومان با موفقیت ثبت شد. کد پیگیری: {trk_code}"
                    )
                    if student.parent_user_id is None:
                        ensure_student_shadow_users(db, student)
                    # نوتیفیکیشن ولی
                    NotificationService.send_notification(
                        db=db, recipient_user_id=student.parent_user_id, recipient_role="parent",
                        type="payment", title="✅ پرداخت آنلاین موفق فرزند",
                        body=f"پرداخت آنلاین بابت فرزند شما به مبلغ {payment.amount:,} تومان با موفقیت انجام شد. کد پیگیری: {trk_code}"
                    )
                except Exception:
                    pass

            db.commit()
            return HTMLResponse(content=f"""
            <html>
            <head>
                <title>پرداخت موفقیت‌آمیز</title>
                <meta charset="utf-8">
            </head>
            <body style="font-family: Tahoma; text-align: center; direction: rtl; padding-top: 50px; background-color: #f4fdf4;">
                <div style="border: 2px solid #28a745; display: inline-block; padding: 30px; border-radius: 12px; background: white; box-shadow: 0px 4px 12px rgba(0,0,0,0.05); width: 450px;">
                    <div style="font-size: 50px; color: #28a745; margin-bottom: 10px;">✓</div>
                    <h2 style="color: #28a745; margin-bottom: 20px;">پرداخت شما با موفقیت انجام شد</h2>
                    <hr style="border: 0.5px solid #eee; margin-bottom: 20px;">
                    <p>دانش‌آموز گرامی، تراکنش مالی شما تایید شد.</p>
                    <p>کد پیگیری تراکنش: <code>{trk_code}</code></p>
                    <p>مبلغ پرداختی: <strong>{payment.amount:,} تومان</strong></p>
                    <p style="color: #666; font-size: 0.9em; margin-top: 20px;">کیف پول شما بروزرسانی شد و این رسید به عنوان حواله در سیستم ثبت گردید.</p>
                </div>
            </body>
            </html>
            """)
        # FIX F-B1: FAILED مشروط (فقط دارنده‌ی VERIFYING) — اگر دیگری جلوتر وضعیت را برده، رفرش.
        _ffrows = (
            db.query(models.Payment)
            .filter(models.Payment.id == payment.id, models.Payment.status == "VERIFYING")
            .update({models.Payment.status: "FAILED"}, synchronize_session=False)
        )
        db.commit()
        if _ffrows != 1:
            return _callback_refresh_page(payment.id)
        return HTMLResponse(content="""
            <html>
            <head>
                <title>پرداخت ناموفق</title>
                <meta charset="utf-8">
            </head>
            <body style="font-family: Tahoma; text-align: center; direction: rtl; padding-top: 50px; background-color: #fdf4f4;">
                <div style="border: 2px solid #dc3545; display: inline-block; padding: 30px; border-radius: 12px; background: white; box-shadow: 0px 4px 12px rgba(0,0,0,0.05); width: 450px;">
                    <div style="font-size: 50px; color: #dc3545; margin-bottom: 10px;">✗</div>
                    <h2 style="color: #dc3545; margin-bottom: 20px;">پرداخت ناموفق بود</h2>
                    <hr style="border: 0.5px solid #eee; margin-bottom: 20px;">
                    <p style="color: #dc3545; font-weight: bold;">تراکنش توسط درگاه بانک معتبر شناخته نشد.</p>
                    <p>در صورتی که مبلغی از حساب شما کسر شده باشد، تا ۷۲ ساعت آینده به حساب شما بازخواهد گشت.</p>
                </div>
            </body>
            </html>
            """)
    # FIX F-B1: انصراف/شکست سمت درگاه → CANCELLED مشروط (فقط از PENDING؛ SUCCESS/VERIFYING هرگز
    # با هیت لغو رونویسی نمی‌شود). اگر دیگری جلوتر برده، رفرش همان نتیجه را نشان می‌دهد.
    _crows = (
        db.query(models.Payment)
        .filter(models.Payment.id == payment.id, models.Payment.status == "PENDING")
        .update({models.Payment.status: "CANCELLED"}, synchronize_session=False)
    )
    db.commit()
    if _crows != 1:
        return _callback_refresh_page(payment.id)
    return HTMLResponse(content="""
        <html>
        <head>
            <title>پرداخت لغو شد</title>
            <meta charset="utf-8">
        </head>
        <body style="font-family: Tahoma; text-align: center; direction: rtl; padding-top: 50px; background-color: #fdfbf4;">
            <div style="border: 2px solid #ffc107; display: inline-block; padding: 30px; border-radius: 12px; background: white; box-shadow: 0px 4px 12px rgba(0,0,0,0.05); width: 450px;">
                <div style="font-size: 50px; color: #ffc107; margin-bottom: 10px;">!</div>
                <h2 style="color: #d39e00; margin-bottom: 20px;">پرداخت لغو گردید</h2>
                <hr style="border: 0.5px solid #eee; margin-bottom: 20px;">
                <p>عملیات پرداخت آنلاین توسط شما لغو شد یا با شکست مواجه گردید.</p>
                <p>در صورت تمایل می‌توانید مجدداً از طریق پورتال خود برای پرداخت اقدام فرمایید.</p>
            </div>
        </body>
        </html>
        """)


def submit_payment(
    data: FinanceSubmitData, db: Session = Depends(get_db), _: str = Depends(check_admin_or_secretary_access),
    branch_id: int | None = None, authorization: str | None = Header(None),
):
    """بدنهٔ دامنه‌ایِ `submit_payment`؛ توضیحِ HTTP در پوستهٔ روتر است."""
    # FIX (audit-v2/idempotency-قدم۱): کلید اختیاری (سازگار با عقب)؛ اگر آمده و قبلاً پردازش شده → replay بدون هیچ نوشتن.
    _idem_key = (data.idempotency_key or "").strip()
    if _idem_key:
        _hit = _replay_idempotent_payment(db, _idem_key, data)
        if _hit is not None:
            return _hit
    # FIX B1 (الگوی H8-P4): بدون with_for_update (روی SQLite بی‌اثر است) — این خواندن فقط برای
    # اعتبارسنجی/تعیین شعبه است؛ افزایش کیف‌پول با UPDATE اتمیک SQL بعد از شاخه‌ها انجام می‌شود.
    st = db.query(Student).filter(Student.id == data.student_id).first()
    if not st:
        raise HTTPException(404, "دانش‌آموز یافت نشد")

    # FIX: Bug 9 - every receipt inherits the student's branch, or the resolved branch if absent.
    payment_branch = st.branch_id if st.branch_id is not None else get_user_branch_filter(db, authorization, branch_id)
    # FIX: Bug 9 - never create an unassigned financial transaction when neither source has a branch.
    if payment_branch is None:
        raise HTTPException(status_code=400, detail="شعبه پرداخت مشخص نیست؛ شعبه دانش‌آموز یا شعبه پرداخت را تعیین کنید")

    # FIX: Bug 22 - reject non-positive single-wallet credits before counters, wallets or receipts change.
    # The existing Priority 2 split validation already requires nonnegative shares and a positive total.
    if data.target_wallet != "both" and data.amount <= 0:
        raise HTTPException(status_code=400, detail="مبلغ پرداخت باید بیشتر از صفر باشد")
    # FIX M12: کیف‌پول مقصد فقط یکی از سه مقدار معتبر است — هر چیز دیگری 400 می‌گیرد
    # (قبلاً شاخه‌ی else ساکت تراکنش ثبت می‌کرد ولی هیچ کیفی شارژ نمی‌شد: عدم‌تطابق دفتر/کیف،
    # و بدتر: همان مبلغِ شارژنشده قسط‌ها را تسویه می‌کرد — تسویه‌ی مجانی).
    if data.target_wallet not in ("teacher", "institute", "both"):
        raise HTTPException(status_code=400, detail="کیف‌پول مقصد نامعتبر است؛ فقط teacher، institute یا both")
    # FIX M27: تاریخ رسید قبل از ذخیره با مبدل مرکزی H3 اعتبارسنجی می‌شود (نامعتبر = 400).
    # کران منطقی: گذشته آزاد است (ثبت دستی معوقه مجاز)؛ آینده مردود است (رسید یعنی وجه گرفته‌شده —
    # تاریخ آینده گزارش روزانه را فاسد می‌کند). تلرانس +۱ روز برای اختلاف ساعت سرور/کلاینت تا
    # رسید «امروز» به‌خاطر تهران/UTC بودن false-positive نگیرد.
    from today_summary import parse_project_date  # lazy، مثل الگوی H3-B3 همین فایل
    _pay_date = parse_project_date(data.date)
    if _pay_date is None:
        raise HTTPException(status_code=400, detail="فرمت تاریخ پرداخت معتبر نیست (yyyy/MM/dd)")
    if _pay_date > datetime.date.today() + datetime.timedelta(days=1):
        raise HTTPException(status_code=400, detail="تاریخ پرداخت نمی‌تواند در آینده باشد")

    # 🔗 منبع حقیقت واحد بدهی: تعیین ثبت‌نام لینک‌شده (اعتبارسنجی زودهنگام، قبل از هر تغییری)
    linked_enrollment = None
    if data.enrollment_id is not None:
        linked_enrollment = db.query(Enrollment).filter(Enrollment.id == data.enrollment_id).first()
        if not linked_enrollment or linked_enrollment.is_deleted:
            raise HTTPException(status_code=404, detail="ثبت‌نام مورد نظر یافت نشد")
        if linked_enrollment.student_id != data.student_id:
            raise HTTPException(status_code=400, detail="این ثبت‌نام متعلق به این دانش‌آموز نیست")
    else:
        # قانون «تک‌ثبت‌نامی»: اگر شاگرد فقط یک ثبت‌نام فعال دارد، خودکار به همان وصل می‌شود
        active_enroll_ids = db.query(Enrollment.id).filter(Enrollment.is_deleted == False, Enrollment.student_id == data.student_id).all()
        if len(active_enroll_ids) == 1:
            linked_enrollment = db.query(Enrollment).filter(Enrollment.id == active_enroll_ids[0][0]).first()
            if linked_enrollment is None or linked_enrollment.is_deleted:
                linked_enrollment = None  # خطای هم‌زمان نادر: به شارژ عمومی کیف پول برمی‌گردیم تا پرداخت شکست نخورد
        elif len(active_enroll_ids) > 1:
            raise HTTPException(status_code=400, detail="این دانش‌آموز چند ثبت‌نام فعال دارد، enrollment_id مشخص کنید")

    # «حواله برای چند جلسه»: فقط توضیح/گزارش است و محاسبهٔ مالی را تغییر نمی‌دهد؛ ولی باید به یک کلاس مشخص
    # وصل باشد وگرنه معلوم نیست «جلسه‌های کدام کلاس» است.
    if data.sessions_covered is not None and linked_enrollment is None:
        raise HTTPException(status_code=400, detail="برای ثبت تعداد جلسه، کلاس (ثبت‌نام) دانش‌آموز را مشخص کنید")

    # FIX B1: بدون خواندن-جمع‌زدن در پایتون (RMW) — اینجا فقط سهم هر کیف‌پول محاسبه می‌شود؛
    # افزایش واقعی با یک UPDATE اتمیک SQL بعد از شاخه‌ها انجام می‌شود (رجوع به بلوک «آپدیت اتمیک» پایین).
    add_teacher = 0
    add_institute = 0

    desc_full = data.description
    from dependencies import get_next_sequence_value

    transactions_created = []
    total_amount_for_installment = 0

    # ✅ منطق جدید: پشتیبانی از target_wallet = "both" (تقسیم مبلغ بین دو کیف پول)
    if data.target_wallet == "both":
        # FIX: Bug 10 - explicit splits must be complete; omitting both shares requests a half split.
        amt_teacher = 0
        amt_institute = 0

        if data.amount_teacher is not None or data.amount_institute is not None:
            # FIX: Bug 10 - do not silently interpret a missing institute share as zero/100% teacher.
            if data.amount_teacher is None or data.amount_institute is None:
                raise HTTPException(400, "برای پرداخت به هر دو کیف‌پول، هر دو سهم را تعیین کنید؛ برای تقسیم مساوی، هر دو مبلغ را خالی بگذارید")
            amt_teacher = data.amount_teacher
            amt_institute = data.amount_institute
        else:
            # FIX: Bug 10 - amount is the total; preserve every unit, including an odd remainder.
            amt_teacher = data.amount // 2
            amt_institute = data.amount - amt_teacher

        # اعتبارسنجی
        if amt_teacher < 0 or amt_institute < 0:
            raise HTTPException(400, "مبالغ نمی‌توانند منفی باشند")
        if amt_teacher == 0 and amt_institute == 0:
            raise HTTPException(400, "حداقل یکی از مبالغ باید بیشتر از صفر باشد")

        # FIX B1: فقط تعیین سهم (افزایش اتمیک، بعد از شاخه‌ها).
        add_teacher = amt_teacher
        add_institute = amt_institute
        total_amount_for_installment = amt_teacher + amt_institute

        # ثبت دو تراکنش جداگانه برای شفافیت حسابداری
        if amt_teacher > 0:
            next_rem_teacher = get_next_sequence_value(db, "remittance_teacher", 100001)
            trans_t = Transaction(
                student_id=data.student_id,
                branch_id=payment_branch,  # FIX: Bug 9 - persist the branch on split receipts.
                amount=amt_teacher,
                payment_method=data.payment_method,
                date=data.date,
                description=desc_full + " (سهم معلم - تقسیم هر دو)",
                type="deposit",
                target_wallet="teacher",
                remittance_number=next_rem_teacher,
            )
            db.add(trans_t)
            transactions_created.append(trans_t)

        if amt_institute > 0:
            next_rem_inst = get_next_sequence_value(db, "remittance_institute", 100001)
            trans_i = Transaction(
                student_id=data.student_id,
                branch_id=payment_branch,  # FIX: Bug 9 - persist the branch on split receipts.
                amount=amt_institute,
                payment_method=data.payment_method,
                date=data.date,
                description=desc_full + " (سهم آموزشگاه - تقسیم هر دو)",
                type="deposit",
                target_wallet="institute",
                remittance_number=next_rem_inst,
            )
            db.add(trans_i)
            transactions_created.append(trans_i)

        # برای سازگاری، یک تراکنش تجمیعی هم با target_wallet=both ثبت می‌کنیم (اختیاری، برای گزارش)
        # اما اصلی دو تراکنش بالاست

    elif data.target_wallet == "teacher":
        add_teacher = data.amount
        desc_full += " (سهم معلم)"
        total_amount_for_installment = data.amount
        next_remittance = get_next_sequence_value(db, "remittance_teacher", 100001)
        new_trans = Transaction(
            student_id=data.student_id,
            branch_id=payment_branch,  # FIX: Bug 9 - persist the branch on every receipt.
            amount=data.amount,
            payment_method=data.payment_method,
            date=data.date,
            description=desc_full,
            type="deposit",
            target_wallet=data.target_wallet,
            remittance_number=next_remittance,
        )
        db.add(new_trans)
        transactions_created.append(new_trans)

    elif data.target_wallet == "institute":
        add_institute = data.amount
        desc_full += " (سهم آموزشگاه)"
        total_amount_for_installment = data.amount
        next_remittance = get_next_sequence_value(db, "remittance_institute", 100001)
        new_trans = Transaction(
            student_id=data.student_id,
            branch_id=payment_branch,  # FIX: Bug 9 - persist the branch on every receipt.
            amount=data.amount,
            payment_method=data.payment_method,
            date=data.date,
            description=desc_full,
            type="deposit",
            target_wallet=data.target_wallet,
            remittance_number=next_remittance,
        )
        db.add(new_trans)
        transactions_created.append(new_trans)

    else:
        # FIX M12 (دفاعی؛ با اعتبارسنجی بالای تابع عملاً unreachable): هیچ «واریز بدون کیف»ای
        # ثبت نمی‌شود — حالت «بدون کیف مشخص» نامشروع است چون تراکنشِ بدون شارژ کیف یعنی
        # عدم‌تطابق دفتر/کیف و تسویه‌ی مجانی قسط. هیچ تراکنشی هم ثبت نمی‌شود (۴۰۰ قبل از هر نوشتن).
        raise HTTPException(status_code=400, detail="کیف‌پول مقصد نامعتبر است؛ فقط teacher، institute یا both")

    # FIX (audit-v2/idempotency-قدم۱): مهر کلید روی همه‌ی رسیدهای همین پرداخت (both = دو ردیف، یک کلید).
    if _idem_key:
        for t in transactions_created:
            t.idempotency_key = _idem_key

    # FIX B1 (الگوی H8-P4): افزایش اتمیک کیف‌پول‌ها در SQL — جمع در دیتابیس، نه خواندن-جمع‌زدن در پایتون.
    # COALESCE رفتار قدیمی None→0 را حفظ می‌کند (ستون‌ها nullable هستند)؛ rowcount باید ۱ باشد (فقط existence).
    if add_teacher or add_institute:
        wallet_rows = (
            db.query(Student)
            .filter(Student.id == data.student_id)
            .update(
                {
                    Student.wallet_teacher: func.coalesce(Student.wallet_teacher, 0) + add_teacher,
                    Student.wallet_institute: func.coalesce(Student.wallet_institute, 0) + add_institute,
                },
                synchronize_session=False,
            )
        )
        if wallet_rows != 1:
            db.rollback()
            raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")

    # 🔗 لینک تراکنش‌های ساخته‌شده به ثبت‌نام + افزایش اتمیک total_paid (در همان تراکنش دیتابیسی، اتمیک)
    if linked_enrollment is not None and total_amount_for_installment > 0:
        for t in transactions_created:
            t.enrollment_id = linked_enrollment.id
            t.course_id = linked_enrollment.course_id
            t.sessions_covered = data.sessions_covered  # None برای کلاینت قدیمی = رفتار قبلی
        # FIX B1 (الگوی H8-P4): اگر ثبت‌نام بین اعتبارسنجی بالا و این لحظه حذف شده باشد، rowcount صفر می‌شود.
        paid_rows = (
            db.query(Enrollment)
            .filter(Enrollment.id == linked_enrollment.id, Enrollment.is_deleted == False)
            .update(
                {Enrollment.total_paid: func.coalesce(Enrollment.total_paid, 0) + total_amount_for_installment},
                synchronize_session=False,
            )
        )
        if paid_rows != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="ثبت‌نام هم‌زمان حذف شد؛ لطفاً صفحه را رفرش کنید")

    # ترتیب سینک با sync_wallet_balance (مهم): اول UPDATEهای خام بالا، بعد refresh برای گرفتن مقادیر
    # تازه از دیتابیس، بعد سینک بالانس کل. (آپدیت bulk شنونده‌ی before_update را اجرا نمی‌کند، پس سینک صریح لازم است.)
    if add_teacher or add_institute:
        db.refresh(st)
        # FIX: Bug 18 - derive the total only through the shared wallet helper.
        st.sync_wallet_balance()

    # مقادیر نهایی برای پاسخ — از روی آبجکت تازه‌شده (بعد از UPDATE اتمیک)
    final_w_t = st.wallet_teacher if st.wallet_teacher else 0
    final_w_i = st.wallet_institute if st.wallet_institute else 0

    # 💰 تخصیص هوشمند مبلغ پرداختی به قدیمی‌ترین اقساط تسویه نشده دانش‌آموز (در صورت وجود اقساط)
    # FIX: Bug 13 - exclude archived Enrollment rows from this active view.
    # FIX (audit-v2/issue9-الف): پرداخت لینک‌شده فقط اقساط همان ثبت‌نام را می‌پوشاند — هم‌مبنا با
    # total_paid/debt که per-enrollment است (قبلاً cross بود و نمایش قسط با بدهی ناسازگار می‌شد).
    # بی‌لینک (شارژ عمومی کیف) عمداً رفتار cross قدیمی را نگه می‌دارد (جریان تخصیص ندارد — بیرون اسکوپ).
    if linked_enrollment is not None:
        enrollment_ids = [linked_enrollment.id]
    else:
        enrollments = db.query(Enrollment).filter(Enrollment.is_deleted == False).filter(Enrollment.student_id == data.student_id).all()
        enrollment_ids = [e.id for e in enrollments]
    if enrollment_ids:
        unpaid_installments = (
            # FIX: Bug 13 - exclude archived Installment rows from this active view.
            db.query(Installment).filter(Installment.is_deleted == False)
            .filter(
                Installment.enrollment_id.in_(enrollment_ids),
                Installment.is_paid == False
            )
            .order_by(Installment.due_date.asc())
            .all()
        )
        # FIX (audit-v2/issue7): autoflush خاموش است (models.SessionLocal) پس قبل از ledger، flush صریح —
        # رسیدها آیدی می‌گیرند (کامیت همان انتهای تابع؛ اتمیسیته عوض نمی‌شود).
        db.flush()
        # توزیع FIFO پوشش روی رسیدهای همین پرداخت (both = ۲ رسید): استردادِ هر رسید دقیقاً پوششِ
        # سهم خودش را برمی‌گرداند؛ تک‌کیفی (اکثریت) همیشه ایندکس صفر است.
        _alloc_receipts = [x.id for x in transactions_created]
        _alloc_amounts = [(x.amount or 0) for x in transactions_created]
        _alloc_idx = 0
        remaining_payment = total_amount_for_installment if total_amount_for_installment > 0 else data.amount
        # FIX (audit-v2/idempotency-قدم۲، الگوی H8-P4/B1): پوشش اتمیک قسط — هر ردیف فقط با UPDATE مشروط
        # (paid_amount == خوانده‌شده + is_paid == False) جلو می‌رود؛ rowcount صفر یعنی پرداخت موازی همین
        # قسط را تکان داد → رفرش + محاسبه‌ی مجدد (۳ تلاش) وگرنه 409. کسر از remaining فقط بعد از موفقیت
        # UPDATE انجام می‌شود پس lost-update ناممکن است و جمع پوشش‌ها هرگز از بدهی بیشتر نمی‌شود.
        for inst in unpaid_installments:
            if remaining_payment <= 0:
                break
            for _try in range(3):
                db.refresh(inst)  # وضعیت تازه — پرداخت‌های موازیِ کامیت‌شده دیده می‌شوند.
                if inst.is_paid or inst.is_deleted:
                    break  # موازی تسویه/حذفش کرد — remaining دست‌نخورده، قسط بعدی.
                # FIX M13 (گزینه‌ی ب، حفظ شد): تجمعی؛ is_paid فقط با پوشش کامل.
                _already = inst.paid_amount or 0
                _owed = (inst.amount or 0) - _already
                if _owed <= 0:
                    # ناسازگاری قدیمی نادر: فقط فلگ، مشروط (rowcount مهم نیست — موازی هم ممکن است فلیپ کرده باشد).
                    db.query(Installment).filter(Installment.id == inst.id, Installment.is_paid == False).update({Installment.is_paid: True}, synchronize_session=False)
                    break
                _cover = min(remaining_payment, _owed)
                _new_paid = _already + _cover
                _fully = _new_paid >= (inst.amount or 0)
                _set = {Installment.paid_amount: _new_paid}
                if _fully:
                    _set[Installment.is_paid] = True
                    _set[Installment.paid_at] = _jalali_now_str()  # FIX L7: شمسی.
                _rows = (
                    db.query(Installment)
                    .filter(Installment.id == inst.id, Installment.is_paid == False, Installment.is_deleted == False, func.coalesce(Installment.paid_amount, 0) == _already)
                    .update(_set, synchronize_session=False)
                )
                if _rows == 1:
                    remaining_payment -= _cover
                    # FIX (audit-v2/issue7): ثبت ledger — مبلغ دقیق همین پوشش، توزیع FIFO روی رسیدها.
                    _need = _cover
                    while _need > 0 and _alloc_idx < len(_alloc_receipts):
                        _take = min(_need, _alloc_amounts[_alloc_idx])
                        if _take > 0:
                            db.add(TransactionInstallmentAllocation(transaction_id=_alloc_receipts[_alloc_idx], installment_id=inst.id, amount=_take))
                            _need -= _take
                            _alloc_amounts[_alloc_idx] -= _take
                        if _alloc_amounts[_alloc_idx] <= 0:
                            _alloc_idx += 1
                    break
            else:
                db.rollback()
                raise HTTPException(status_code=409, detail="تغییر هم‌زمان در اقساط؛ لطفاً دوباره تلاش کنید")

    # FIX (audit-v2/idempotency-قدم۱): مسابقه‌ی دو retry هم‌زمان — هر دو pre-check را رد می‌کنند؛
    # دومی روی UNIQUE ایندکس می‌افتد → به‌جای 500، نتیجه‌ی برنده replay می‌شود.
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if _idem_key:
            _won = _replay_idempotent_payment(db, _idem_key, data)
            if _won is not None:
                return _won
        raise
    # رفرش تراکنش‌های ایجاد شده
    for t in transactions_created:
        db.refresh(t)

    primary_receipt_id = transactions_created[0].id if transactions_created else 0

    return {
        "message": "مبلغ ثبت و حساب بروزرسانی شد." + (" (تقسیم هر دو)" if data.target_wallet == "both" else ""),
        "receipt_id": primary_receipt_id,
        "receipt_ids": [t.id for t in transactions_created],
        "new_balance_teacher": final_w_t,
        "new_balance_institute": final_w_i,
        "sessions_covered": data.sessions_covered,
    }


def refund_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    authorization: str | None = Header(None),
    _: str = Depends(check_admin_access)  # فقط مخصوص ادمین
):
    """بدنهٔ دامنه‌ایِ `refund_transaction`؛ توضیحِ HTTP در پوستهٔ روتر است."""
    # FIX: Bug 11 - this audit lookup deliberately includes reversed rows to reject repeat refunds.
    # FIX B2 (الگوی H8-P4): بدون with_for_update — این خواندن فقط اعتبارسنجی اولیه است؛ گیت واقعی، UPDATE مشروط پایین است.
    trans = db.query(Transaction).filter(Transaction.id == transaction_id, Transaction.is_deleted == False).first()
    if not trans:
        raise HTTPException(status_code=404, detail="تراکنش مورد نظر یافت نشد")
    # FIX M16: فقط واریز واقعی از مسیر استرداد عمومی برمی‌گردد — قبل از تسخیر اتمیک، پس چیزی ثبت نمی‌شود.
    # session_charge مسیر مخصوص خودش را دارد (reverse_session_financial_impacts هنگام حذف جلسه)؛
    # استرداد عمومی آن هم کیف را دست‌نخورده می‌گذاشت، هم is_reversed را می‌سوزاند (مسیر درست را برای همیشه می‌بست).
    # settlement_payout پول‌خروجی و reversal معکوس است و استرداد عمومی برایشان بی‌معناست.
    if trans.type not in ("deposit", "enrollment_payment"):
        _m16_hint = "؛ برگشت هزینه‌ی جلسه فقط با حذف جلسه انجام می‌شود" if trans.type == "session_charge" else ""
        raise HTTPException(status_code=400, detail=f"تراکنش نوع «{trans.type}» از مسیر استرداد عمومی قابل برگشت نیست{_m16_hint}")

    if trans.is_reversed:
        raise HTTPException(status_code=400, detail="این تراکنش قبلاً استرداد شده است (Idempotent Refund)")

    # فریز مبلغ در لحظه‌ی اعتبارسنجی (آبجکت ORM بعد از UPDATE خام، در فیلد is_reversed stale می‌شود).
    t_amount = trans.amount

    # FIX B2 (الگوی H8-P4): تسخیر اتمیک تراکنش — فقط اگر هنوز استردادنشده و حذف‌نشده باشد فلیپ می‌خورد.
    # ۱. علامت‌گذاری تراکنش اصلی به عنوان بازگردانده شده
    claimed_rows = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.is_reversed == False, Transaction.is_deleted == False)
        .update({Transaction.is_reversed: True}, synchronize_session=False)
    )
    if claimed_rows != 1:
        db.rollback()
        raise HTTPException(status_code=400, detail="این تراکنش قبلاً استرداد شده است (Idempotent Refund)")

    # FIX: Bug 11 - issue a new reference, including protection against pre-counter legacy numbers.
    from dependencies import get_next_sequence_value
    # FIX: Bug 11 - initialize above historical references, including archived transactions.
    first_refund_number = max(100000, db.query(func.max(Transaction.remittance_number)).scalar() or 0) + 1
    # FIX: Bug 11 - share the wallet's counter so its next deposit cannot reuse the refund reference.
    counter_name = "remittance_teacher" if trans.target_wallet == "teacher" else "remittance_institute"
    next_remittance = get_next_sequence_value(db, counter_name, first_refund_number)
    # FIX: Bug 11 - reference uniqueness must consider archived/reversed rows, not just active revenue.
    while db.query(Transaction.id).filter(Transaction.remittance_number == next_remittance).first():
        next_remittance = get_next_sequence_value(db, counter_name, first_refund_number)

    # ۲. ثبت یک تراکنش معکوس (با مقدار منفی) جهت حفظ تاریخچه کامل
    reversal_trans = Transaction(
        student_id=trans.student_id,
        enrollment_id=trans.enrollment_id,
        # FIX: Bug 11 - preserve the original branch/course/session audit links on the reversal.
        branch_id=trans.branch_id,
        course_id=trans.course_id,
        session_id=trans.session_id,
        amount=-trans.amount,
        payment_method=trans.payment_method,
        tracking_code=f"REFUND_{trans.tracking_code or trans.id}",
        date=_jalali_now_str(),  # FIX (audit-v2/refund-date): شمسی (قبلاً میلادی وسط ستون شمسی — همان الگوی L7/#12).
        description=f"استرداد تراکنش شماره #{trans.id} - شرح قبلی: {trans.description}",
        type="reversal",
        target_wallet=trans.target_wallet,
        remittance_number=next_remittance  # FIX: Bug 11 - never reuse the original reference.
    )
    db.add(reversal_trans)

    # ۳. کسر مبلغ استرداد شده از کیف پول دانش‌آموز
    # FIX B2: بدون with_for_update — فقط خواندن برای وجودسنجی/نام؛ کسر با UPDATE اتمیک پایین است.
    student = db.query(Student).filter(Student.id == trans.student_id).first()
    if student:
        # FIX B2: بدون خواندن-جمع‌زدن در پایتون — اینجا فقط سهم کسر هر کیف‌پول محاسبه می‌شود.
        sub_teacher = 0
        sub_institute = 0
        if trans.target_wallet == "teacher":
            sub_teacher = t_amount
        elif trans.target_wallet == "institute":
            sub_institute = t_amount
        elif trans.target_wallet == "both":
            # FIX: Bugs 10/11 - legacy combined receipts must reverse both actual wallet shares.
            teacher_amount = trans.share_teacher or 0
            institute_amount = trans.share_institute or 0
            if teacher_amount + institute_amount != trans.amount:
                teacher_amount = trans.amount // 2
                institute_amount = trans.amount - teacher_amount
            sub_teacher = teacher_amount
            sub_institute = institute_amount
        elif trans.type == "enrollment_payment":
            # FIX M16: واریز ثبت‌نامی همیشه به کیف آموزشگاه رفته (هر دو سایت ساخت) ولی target_wallet=None دارد —
            # بدون این شاخه، استردادش تراکنش معکوس ثبت می‌کرد ولی کیف را دست‌نخورده می‌گذاشت (همان تله‌ی session_charge).
            sub_institute = t_amount
        # (شاخه‌ی else قدیمی سهمی کسر نمی‌کرد؛ مثل الگوی بچ ۱، بدون UPDATE و بدون سینک رد می‌شود.)

        # FIX B2 (الگوی H8-P4): کسر اتمیک از کیف‌پول‌ها در SQL — منها در دیتابیس، نه خواندن-منها در پایتون.
        # COALESCE رفتار قدیمی None→0 را حفظ می‌کند (ستون‌ها nullable هستند)؛ rowcount باید ۱ باشد (فقط existence).
        if sub_teacher or sub_institute:
            wallet_rows = (
                db.query(Student)
                .filter(Student.id == trans.student_id)
                .update(
                    {
                        Student.wallet_teacher: func.coalesce(Student.wallet_teacher, 0) - sub_teacher,
                        Student.wallet_institute: func.coalesce(Student.wallet_institute, 0) - sub_institute,
                    },
                    synchronize_session=False,
                )
            )
            if wallet_rows != 1:
                db.rollback()
                raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")

        # ترتیب سینک (مثل بچ ۱): اول UPDATE خام، بعد refresh برای مقادیر تازه، بعد سینک بالانس کل.
        if sub_teacher or sub_institute:
            db.refresh(student)
            # FIX: Bug 18 - derive the total only through the shared wallet helper.
            student.sync_wallet_balance()

        # 🔗 همگام‌سازی منبع حقیقت بدهی: استردادِ پرداختِ لینک‌شده، total_paid ثبت‌نام را کم می‌کند
        if trans.enrollment_id and trans.type in ("deposit", "enrollment_payment", "tuition") and (trans.amount or 0) > 0:
            # FIX B2 (الگوی H8-P4): کسر اتمیک با کف صفر (همان max(0,...) قبلی، به‌صورت CASE اتمیک در SQL).
            # مثل رفتار قبلی (if تأییدی)، rowcount صفر (ثبت‌نام حذف‌شده/نبود) بی‌صدا رد می‌شود — چون اینجا
            # برخلاف submit_payment، ثبت‌نام از قبل اعتبارسنجی نشده و نبودش خطا نیست.
            db.query(Enrollment).filter(
                Enrollment.id == trans.enrollment_id, Enrollment.is_deleted == False
            ).update(
                {
                    Enrollment.total_paid: case(
                        (func.coalesce(Enrollment.total_paid, 0) - t_amount < 0, 0),
                        else_=func.coalesce(Enrollment.total_paid, 0) - t_amount,
                    )
                },
                synchronize_session=False,
            )

        # FIX (audit-v2/issue7): برگرداندن پوشش‌های اقساط از روی ledger — در همان تراکنش دیتابیسی،
        # اتمیک با کیف/total_paid (کامیت واحد انتهای تابع). فقط پوشش‌های همین رسید برمی‌گردند؛
        # ردیف‌های ledger نگه داشته می‌شوند (تاریخچه) و استرداد تکراری با گیت is_reversed ناممکن است.
        # تاریخچه‌ی قبل-از-ledger ردیفی ندارد → همان رفتار امروز (قسط دست‌نخورده).
        _allocs = db.query(TransactionInstallmentAllocation).filter(TransactionInstallmentAllocation.transaction_id == transaction_id).order_by(TransactionInstallmentAllocation.id.asc()).all()
        for _al in _allocs:
            for _try in range(3):
                _rinst = db.query(Installment).filter(Installment.id == _al.installment_id, Installment.is_deleted == False).first()
                if _rinst is None:
                    break  # قسط آرشیو/حذف شده — پوشش عملاً بی‌اثر است.
                _ralready = _rinst.paid_amount or 0
                _rnew = max(0, _ralready - (_al.amount or 0))
                _rstill = _rnew >= (_rinst.amount or 0)
                _rrows = (
                    db.query(Installment)
                    .filter(Installment.id == _rinst.id, Installment.is_deleted == False, func.coalesce(Installment.paid_amount, 0) == _ralready)
                    .update({Installment.paid_amount: _rnew, Installment.is_paid: _rstill, Installment.paid_at: (_rinst.paid_at if _rstill else None)}, synchronize_session=False)
                )
                if _rrows == 1:
                    break
            else:
                db.rollback()
                raise HTTPException(status_code=409, detail="تغییر هم‌زمان در اقساط؛ لطفاً دوباره تلاش کنید")

        # ۴. ثبت فعالیت حسابرسی (Audit Log) تغییر مبلغ
        # FIX H9: admin_username باید کاربر واقعی همین درخواست باشد، نه هاردکد "admin_portal".
        # همان الگوی H8-P2؛ چون check_* بالا توکن خراب را از قبل رد کرده، فالبک "unknown"
        # عملاً نباید هیچ‌وقت اجرا شود (فقط safety net).
        from dependencies import get_session_from_token  # lazy، مثل H8
        _audit_username = "unknown"
        if authorization:
            try:
                _parts = authorization.split()
                _token = _parts[1] if len(_parts) == 2 and _parts[0].lower() == "bearer" else None
                _sess, _ = get_session_from_token(db, _token) if _token else (None, None)
                if _sess is not None and getattr(_sess, "user_id", None):
                    _audit_user = db.query(User).filter(User.id == _sess.user_id).first()
                    if _audit_user is not None and _audit_user.username:
                        _audit_username = _audit_user.username
            except Exception:
                pass
        db.add(ActivityLog(
            admin_username=_audit_username,
            action="transaction_refund",
            target_id=student.id,
            target_name=display_name(student, "نامشخص"),
            details=f"استرداد تراکنش #{trans.id} به مبلغ {trans.amount:,} تومان و کسر از کیف پول {trans.target_wallet}."
        ))

    db.commit()
    return {
        "status": "success",
        "message": "تراکنش مالی با موفقیت استرداد و کیف پول مربوطه کسر گردید.",
        "refund_transaction_id": reversal_trans.id
    }
