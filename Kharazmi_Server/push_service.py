# push_service.py
# ارسال نوتیفیکیشن سیستمی (Push / FCM) با گارد محیطی — تصمیم C2 سند checkpoints/2026-09-20-open-decisions.md
#
# باگی که این ماژول رفع می‌کند:
#   در `dependencies.NotificationService.send_notification` این کد وجود داشت:
#       device_tokens = db.query(DeviceToken).filter(...).all()
#       for token_record in device_tokens:
#           pass                       # ← حلقهٔ خالی!
#   یعنی **هیچ push ای هرگز ارسال نمی‌شد**: اعلان فقط داخل جدول ذخیره می‌شد و کاربری که
#   اپ را باز نمی‌کرد (آفلاین) هیچ خبری از پرداخت/قسط/غیبت/پیام نمی‌گرفت — دقیقاً همان لحظه‌ای
#   که اعلان باید به کار بیفتد (یادآوری بدهی، غیبت، پایان جلسه).
#
# تصمیم (C2): ارسال واقعی با «گارد محیطی»
#   • تا وقتی اعتبارنامهٔ FCM تنظیم نشده (`FCM_SERVER_KEY`)، هیچ درخواست شبکه‌ای زده نمی‌شود؛
#     فقط یک لاگ شفاف ثبت می‌شود (بدون خطا) تا رفتار برنامه دست‌نخورده بماند.
#   • وقتی تنظیم شد، توکن‌های دستگاه هر کاربر اعلان را دریافت می‌کنند.
#   • توکن‌های نامعتبر (NotRegistered/InvalidRegistration/MismatchSenderId) از DB پاک می‌شوند
#     تا انبار توکن مرده در طول زمان اعلان‌ها را کند نکند.
#   • این ماژول **هرگز exception بیرون نمی‌دهد**: شکست push نباید ثبت اعلان یا تراکنش مالی را بشکند.
#   • برای تست واحد، sender تزریقی است (`sender=` یا `set_sender_override`) ⇒ تست‌ها هیچ
#     درخواست شبکه‌ای واقعی نمی‌زنند.
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

import requests

logger = logging.getLogger("kharazmi.push")

# کلید سرور FCM (legacy HTTP API). روی سرور آموزشگاه در فایل محیطی تنظیم می‌شود.
ENV_FCM_KEY = "FCM_SERVER_KEY"
# نقطهٔ پایانی قابل تغییر (پروکسی داخلی/تست)؛ پیش‌فرض سرویس گوگل است.
ENV_FCM_ENDPOINT = "FCM_ENDPOINT"
ENV_FCM_TIMEOUT = "FCM_TIMEOUT_SECONDS"
DEFAULT_ENDPOINT = "https://fcm.googleapis.com/fcm/send"
DEFAULT_TIMEOUT = 5.0
BATCH_SIZE = 100  # سقف registration_ids در هر درخواست FCM

# توکن‌هایی که FCM قطعی می‌گوید دیگر معتبر نیستند ⇒ باید از DB پاک شوند
PERMANENT_TOKEN_ERRORS = {"NotRegistered", "InvalidRegistration", "MismatchSenderId"}

_sender_override: Optional[Callable[..., dict]] = None


@dataclass
class PushResult:
    """نتیجهٔ یک تلاش ارسال — برای لاگ/تست (هرگز از این تابع exception بیرون نمی‌رود)."""
    attempted: int = 0                     # تعداد توکن‌هایی که برایشان تلاش شد
    sent: int = 0                          # تعداد موفق
    failed: int = 0                        # تعداد ناموفق
    invalid_tokens: list = field(default_factory=list)  # توکن‌های پاک‌شده (نامعتبر)
    skipped_reason: str = ""               # اگر ارسال انجام نشد: دلیل شفاف
    errors: list = field(default_factory=list)

    @property
    def skipped(self) -> bool:
        return bool(self.skipped_reason)


def fcm_configured() -> bool:
    """آیا اعتبارنامهٔ FCM تنظیم شده است؟ (گارد محیطی — منبع: متغیر محیطی)"""
    return bool((os.environ.get(ENV_FCM_KEY) or "").strip())


def set_sender_override(sender: Optional[Callable[..., dict]]) -> None:
    """تزریق sender برای تست‌ها (None ⇒ بازگشت به sender واقعی)."""
    global _sender_override
    _sender_override = sender


def _post_to_fcm(url: str, headers: dict, payload: dict, timeout: float) -> dict:
    response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
    try:
        return response.json()
    except ValueError:  # پاسخ غیر-JSON (خطای شبکه/پروکسی)
        return {"failure": len(payload.get("registration_ids", [])), "raw_status": response.status_code}


def _default_sender(tokens: list, title: str, body: str, data: Optional[dict]) -> dict:
    """ارسال واقعی به FCM — فقط وقتی گارد محیطی اجازه داده باشد فراخوانی می‌شود."""
    key = (os.environ.get(ENV_FCM_KEY) or "").strip()
    endpoint = (os.environ.get(ENV_FCM_ENDPOINT) or "").strip() or DEFAULT_ENDPOINT
    try:
        timeout = float(os.environ.get(ENV_FCM_TIMEOUT) or DEFAULT_TIMEOUT)
    except ValueError:
        timeout = DEFAULT_TIMEOUT
    payload = {
        "registration_ids": tokens,
        "notification": {"title": title, "body": body, "sound": "default"},
        "priority": "high",
    }
    if data:
        payload["data"] = data
    headers = {"Authorization": f"key={key}", "Content-Type": "application/json"}
    return _post_to_fcm(endpoint, headers, payload, timeout)


def deliver_push(db, tokens: Iterable, *, title: str, body: str,
                 data: Optional[dict] = None, sender: Optional[Callable] = None,
                 commit: bool = True) -> PushResult:
    """ارسال اعلان سیستمی به توکن‌های دستگاه — با گارد محیطی و بدون ریسک برای کالر.

    db      : Session (برای پاک‌کردن توکن‌های نامعتبر)
    tokens  : ردیف‌های DeviceToken (یا هر شیئی با .id/.token)
    sender  : تابع (tokens, title, body, data) → dict پاسخ FCM؛ برای تست تزریق می‌شود
              (تزریق sender گارد اعتبارنامه را دور نمی‌زند؛ تست‌ها متغیر محیطی را هم تنظیم می‌کنند).
    commit  : اگر False باشد، پاک‌سازی توکن‌ها به تراکنش کالر واگذار می‌شود.
    """
    result = PushResult()
    try:
        token_rows = [t for t in (tokens or []) if getattr(t, "token", None)]
        if not token_rows:
            result.skipped_reason = "no_device_tokens"
            return result

        if not fcm_configured():
            # گارد محیطی (تصمیم C2): بدون اعتبارنامهٔ تنظیم‌شده هیچ درخواست شبکه‌ای زده نمی‌شود —
            # حتی اگر sender تزریقی باشد؛ چون «تزریق sender» جایگزینِ اعتبارنامه نیست.
            result.skipped_reason = "fcm_not_configured"
            logger.info(
                "Push ارسال نشد: اعتبارنامهٔ FCM تنظیم نشده است (متغیر محیطی %s). "
                "%d توکن دستگاه بدون ارسال باقی ماند.", ENV_FCM_KEY, len(token_rows),
            )
            return result

        send = sender or _sender_override or _default_sender
        by_token = {row.token: row for row in token_rows}
        all_tokens = list(by_token.keys())
        result.attempted = len(all_tokens)

        for start in range(0, len(all_tokens), BATCH_SIZE):
            batch = all_tokens[start:start + BATCH_SIZE]
            try:
                response = send(batch, title, body, data) or {}
            except Exception as exc:  # شبکه/تایم‌اوت/پروکسی — push نباید کالر را بشکند
                result.failed += len(batch)
                result.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning("ارسال Push شکست خورد (%d توکن): %s", len(batch), exc)
                continue

            per_token = response.get("results")
            if not isinstance(per_token, list):
                # پاسخ بدون ریز-نتیجه: شمارش کل با معیار موفق/ناموفق
                success = int(response.get("success", 0) or 0)
                failure = int(response.get("failure", 0) or 0)
                if success == 0 and failure == 0:
                    result.failed += len(batch)
                else:
                    result.sent += min(success, len(batch))
                    result.failed += failure
                continue

            for token, item in zip(batch, per_token):
                error = (item or {}).get("error")
                if error:
                    result.failed += 1
                    if error in PERMANENT_TOKEN_ERRORS:
                        row = by_token.get(token)
                        if row is not None:
                            db.delete(row)
                            result.invalid_tokens.append(token)
                else:
                    result.sent += 1

        if result.invalid_tokens:
            if commit:
                db.commit()
            else:
                db.flush()
            logger.info("Push: %d توکن نامعتبر پاک شد.", len(result.invalid_tokens))
        return result
    except Exception as exc:  # هیچ مسیری نباید ثبت اعلان/تراکنش را بشکند
        result.errors.append(f"{type(exc).__name__}: {exc}")
        logger.warning("Push: خطای غیرمنتظره (نادیده گرفته شد): %s", exc)
        return result
