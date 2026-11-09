# FIX: Priority 3 / Bug 22 - one checksum/normalization rule for identity write requests.
import math
import re
from typing import List, Tuple

from pydantic import BaseModel, field_validator


_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# FIX (F-T1/F-T2): یک قاعده‌ی واحد قسط برای همه‌ی مسیرهای ساخت قسط.
# قالب تاریخ عمداً فقط ASCII است ([0-9] نه \d) تا ارقام فارسی/عربی به‌شکل خام در DB ذخیره نشوند
# (مقایسه‌ی رشته‌ای سررسید در داشبورد/dunning روی ارقام ASCII کار می‌کند).
_JALALI_DATE_PATTERN = re.compile(r"[0-9]{4}/(0[1-9]|1[0-2])/(0[1-9]|[12][0-9]|3[01])")
_INT_PATTERN = re.compile(r"[+-]?[0-9]+")


def validate_iranian_national_code(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("کد ملی باید یک رشتهٔ ۱۰ رقمی معتبر باشد")
    code = value.strip().translate(_DIGITS)
    if len(code) != 10 or any(c not in "0123456789" for c in code) or len(set(code)) == 1:
        raise ValueError("کد ملی وارد شده معتبر نیست")
    remainder = sum(int(code[i]) * (10 - i) for i in range(9)) % 11
    expected = remainder if remainder < 2 else 11 - remainder
    if int(code[-1]) != expected:
        raise ValueError("رقم کنترل کد ملی معتبر نیست")
    return code


def is_valid_iranian_national_code(value: str) -> bool:
    try:
        validate_iranian_national_code(value)
        return True
    except ValueError:
        return False


class NationalCodeRequest(BaseModel):
    # FIX: Bug 22 - omitted update fields remain optional; an explicitly invalid/null identity is rejected.
    @field_validator("national_code", mode="before", check_fields=False)
    @classmethod
    def validate_national_code(cls, value):
        return validate_iranian_national_code(value)


# ---------------------------------------------------------------------------
# FIX (F-T1/F-T2): اعتبارسنجی مرکزی اقساط شهریه
# مسیر مستقل `POST /finance/installments`، مسیر «ثبت‌نام همراه اقساط» در classes.py و مسیر
# ثبت دانش‌آموز + ثبت‌نام در students.py همگی از همین توابع استفاده می‌کنند تا سیاست یکی باشد.
# ---------------------------------------------------------------------------
def validate_installment_amount(value) -> int:
    """مبلغ قسط باید عدد صحیح و مثبت باشد.

    مقدار اعشاری هرگز silently truncate نمی‌شود: `100.5` (چه عدد چه رشته) رد می‌شود؛ فقط
    اعشاری‌های صحیح‌مقدار مثل `100.0` و رشته‌ی عدد صحیح مثل `"100"` می‌پذیرند (سازگار با
    رفتار سست قبلی pydantic برای ورودی‌های غیراعشاری).
    """
    if isinstance(value, bool):   # bool زیرکلاس int است؛ برای مبلغ مالی بی‌معناست (true→1).
        raise ValueError("مبلغ قسط باید یک عدد صحیح مثبت باشد")
    if isinstance(value, int):
        amount = value
    elif isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise ValueError("مبلغ قسط باید عدد صحیح باشد؛ مقدار اعشاری پذیرفته نمی‌شود")
        amount = int(value)
    elif isinstance(value, str):
        text = value.strip()
        if not _INT_PATTERN.fullmatch(text):
            raise ValueError("مبلغ قسط باید عدد صحیح باشد؛ مقدار اعشاری پذیرفته نمی‌شود")
        amount = int(text)
    else:
        raise ValueError("مبلغ قسط باید یک عدد صحیح مثبت باشد")
    if amount <= 0:
        raise ValueError("مبلغ قسط باید بزرگتر از صفر باشد")
    return amount


def validate_jalali_due_date(value) -> str:
    """سررسید قسط: هم قالب `yyyy/mm/dd` و هم وجود واقعی روز در تقویم پروژه.

    مرحله‌ی دوم با `parse_project_date` (همان تقویم شمسی/میلادی پروژه) انجام می‌شود تا
    تاریخ‌های ناموجود مثل `1405/07/31` (ماه ۳۰روزه) یا `1405/12/30` (سال غیرکبیسه) رد شوند —
    پیش‌تر regex تنها «شکل» را می‌سنجید و این ردیف‌ها ذخیره می‌شدند (F-T2).
    """
    if not isinstance(value, str):
        raise ValueError("تاریخ سررسید باید به قالب yyyy/mm/dd باشد")
    if not _JALALI_DATE_PATTERN.fullmatch(value):
        raise ValueError("قالب تاریخ سررسید باید yyyy/mm/dd باشد (مثال: 1405/06/16)")
    # lazy import مثل سایر نقاط پروژه: تفسیر تاریخ یک منبع حقیقت دارد (today_summary).
    from today_summary import parse_project_date
    if parse_project_date(value) is None:
        raise ValueError("تاریخ وارد شده در تقویم شمسی وجود ندارد")
    return value


def normalize_installment_fields(amount, due_date) -> Tuple[int, str]:
    """اعتبارسنجی مرکزی یک قسط ⇒ (مبلغ صحیح، تاریخ اعتبارسنجی‌شده)."""
    return validate_installment_amount(amount), validate_jalali_due_date(due_date)


def normalize_installments(installments) -> List[Tuple[int, str]]:
    """همه‌ی اقساط یک درخواست؛ اولین قسط نامعتبر ValueError با پیام فارسی می‌دهد."""
    return [normalize_installment_fields(inst.amount, inst.due_date) for inst in (installments or [])]


# ---------------------------------------------------------------------------
# FIX (F-S4): وضعیت حضور/غیاب — یک قرارداد واحد برای همه‌ی مسیرهای ثبت جلسه
# مقادیر از کلاینت رسمی استخراج شد (KharazmiAdmin: AttendanceActivity.kt / LiveClassActivity.kt /
# LiveApi.kt) و با همه‌ی فیلترهای سرور (is_billed، جریمه‌ی غیبت، گزارش‌ها) یکی است:
# فقط Present / Late / Absent. هیچ نسخه‌ی کوچک‌نویس/فارسی در قرارداد وجود ندارد، پس normalize
# نمی‌کنیم؛ ورودی دیگر رد می‌شود (پیش‌تر بی‌صدا و بدون شارژ ثبت می‌شد).
# ---------------------------------------------------------------------------
ATTENDANCE_STATUSES = ("Present", "Late", "Absent")


def validate_attendance_status(value) -> str:
    """وضعیت حضور باید عیناً یکی از مقادیر رسمی قرارداد باشد (حساس به حروف)."""
    if not isinstance(value, str) or value not in ATTENDANCE_STATUSES:
        raise ValueError("وضعیت حضور باید یکی از Present / Late / Absent باشد")
    return value

