# Checkpoint — M3-portal: blob-fetch با احراز برای پورتال وب والد

Date: 2026-09-12. Asserted + read-back. No compile/run.

## دامنه (grounding)
- تنها پورتال دارای عکس: routers/parent.py (finance.py و reports.py خروجی
  HTML دارند ولی هیچ <img> یا uploads ندارند — grep خالی).
- توکن پورتال: localStorage با کلید "parent_token" (خواندن :538، ست :613/:635،
  حذف :648/:660). sessionStorage استفاده نمی‌شود.
- دو سایت عکس آپلودی: رندر اولیه‌ی سرور (:417/:478، لوگو) + ست JS آواتار (:675).

## تغییرات (همه در routers/parent.py)
- :417-421 (P-portal-vars): src اولیه همیشه placeholder عمومی icons8؛
  URL آپلودی لوگو جدا در inst_logo_auth (یا "" اگر لوگو نیست).
- :481 (P-portal-img): تگ img حالا data-auth-src="{inst_logo_auth}" هم دارد.
- :800 (P-portal-replace): زنجیره‌ی .replace پوشش {inst_logo_auth}.
- :539-561 (P-portal-helper): تابع عمومی loadAuthImage(imgEl, url):
  توکن از localStorage، fetch با Bearer، blob -> createObjectURL -> img.src؛
  URL خارجی مستقیم ست می‌شود؛ توکن‌نداشتن/401/404/خطای شبکه = حفظ placeholder، بدون کرش.
  + بوت DOMContentLoaded که همه‌ی img[data-auth-src] را خودکار لود می‌کند
  (هر img آپلودی آینده فقط با افزودن همین اتریبیوت پوشش می‌گیرد).
- :702 (P-portal-avatar): ست مستقیم .src آواتار فرزند -> فراخوانی loadAuthImage.
- main.py:87 (P-portal-note): NOTE به‌روز شد (پیاده شد).

## رفتار نهایی
- لاگین معتبر: لوگو و آواتار با 200 لود می‌شوند. توکن منقضی: 401 -> placeholder
  می‌ماند (مدیریت خروج همان loadChildProfile موجود). بدون لوگو: icons8 مستقیم.
