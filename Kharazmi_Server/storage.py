# storage.py
# مسیرهای ذخیره‌سازی فایل (آپلودها) — مستقل از ماشین، مستقل از پوشهٔ اجرا.
#
# باگی که این ماژول رفع می‌کند (کشف‌شده توسط CI نوبت ۶ — تصمیم B2):
#   سه روتر مسیر مطلقِ ماشین توسعه‌دهنده را هاردکد کرده بودند:
#       homework.py : UPLOAD_DIR = "/home/user/uploads/homework"
#       exams.py    : PDF_DIR    = "/home/user/uploads/report_cards"
#       messages.py : UPLOAD_DIR = "/home/user/uploads/messages"
#   و مسیر پروفایل/لوگو **نسبت به پوشهٔ اجرا** ساخته می‌شد: os.path.join("uploads/profiles", ...)
#   پیامدها:
#     ۱) روی هر ماشینی که `/home/user` را ندارد (سرور آموزشگاه با کاربر دیگر، CI، docker)،
#        برنامه **در زمان import** با PermissionError بالا نمی‌آید ⇒ آپلود تکالیف، تولید کارنامه
#        و پیوست پیام‌رسان کاملاً از کار می‌افتد (خطای ۵۰۰ برای کاربر).
#     ۲) حتی وقتی کار می‌کرد، فایل‌ها بیرون از پروژه/بکاپ ذخیره می‌شدند ⇒ ریسک گم‌شدن سابقهٔ
#        تکالیف و کارنامه‌ها (اصل ۱ سند تصمیم‌ها: سابقه هرگز بی‌صدا گم نشود).
#     ۳) عکس پروفایل/لوگو بسته به پوشهٔ اجرای سرور در دو مسیر مختلف ذخیره می‌شد و بعد از تغییر
#        پوشهٔ اجرا (مثلاً systemd WorkingDirectory) با ۴۰۴ «فایل یافت نشد» روبه‌رو می‌شد.
#
# تصمیم: یک ریشهٔ واحد برای همهٔ فایل‌های کاربران:
#   پیش‌فرض = `Kharazmi_Server/uploads/` (همیشه در دسترس، داخل پروژه و بکاپ‌پذیر)
#   قابل تغییر با متغیر محیطی `KHARAZMI_UPLOAD_ROOT` (مثلاً دیسک دادهٔ جدا روی سرور آموزشگاه).
# مسیرهای قدیمی فقط برای **خواندن/حذف** بررسی می‌شوند (سازگاری عقب‌رو ⇒ سابقه گم نمی‌شود).
#
# تست‌ها: `test_storage_paths.py`
import os

# ریشهٔ سرور = پوشهٔ همین فایل (Kharazmi_Server/) — مستقل از پوشهٔ اجرا
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_ROOT_ENV = "KHARAZMI_UPLOAD_ROOT"
DEFAULT_UPLOAD_ROOT = os.path.join(BASE_DIR, "uploads")


def upload_root() -> str:
    """ریشهٔ فعلی ذخیره‌سازی (در هر فراخوانی خوانده می‌شود تا تست/استقرار بتواند تغییرش دهد)."""
    override = (os.environ.get(UPLOAD_ROOT_ENV) or "").strip()
    if override:
        return os.path.abspath(os.path.expanduser(override))
    return DEFAULT_UPLOAD_ROOT


def storage_dir(*parts) -> str:
    """پوشهٔ ذخیره‌سازی را (در صورت نبود) می‌سازد و مسیر مطلقش را برمی‌گرداند."""
    path = os.path.join(upload_root(), *parts)
    os.makedirs(path, exist_ok=True)
    return path


def storage_path(*parts) -> str:
    """مسیر مطلق یک فایل داخل ریشهٔ فعلی — بدون ساختن پوشه (برای خواندن/حذف)."""
    return os.path.join(upload_root(), *parts)


def legacy_upload_roots() -> list:
    """ریشه‌های قدیمی که فایل‌های قبلی ممکن است آنجا مانده باشند (فقط برای خواندن/حذف)."""
    candidates = [
        os.path.join(os.path.dirname(BASE_DIR), "uploads"),  # <ریشهٔ ریپو>/uploads (پوشهٔ اجرای قدیمی)
        os.path.abspath("uploads"),                          # پوشهٔ اجرای فعلی
        "/home/user/uploads",                                # مسیر مطلقِ قدیمی (ماشین توسعه‌دهنده)
    ]
    current = os.path.abspath(upload_root())
    seen, result = set(), []
    for candidate in candidates:
        resolved = os.path.abspath(candidate)
        if resolved != current and resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return result


def resolve_existing(*parts):
    """مسیر فایلی که واقعاً روی دیسک هست: اول ریشهٔ فعلی، بعد مسیرهای قدیمی. نبود ⇒ None."""
    canonical = storage_path(*parts)
    if os.path.exists(canonical):
        return canonical
    for root in legacy_upload_roots():
        candidate = os.path.join(root, *parts)
        if os.path.exists(candidate):
            return candidate
    return None
