# مرحلهٔ صفر — ورودی‌های نقشه و روش audit

ورودی اصلی این audit:

- `docs/app-map/server-routes.csv`: ۲۲۱ route و file:line handler.
- `docs/app-map/android-api-calls.csv`: ۱۶۲ declaration Retrofit؛ `@Url` در مقایسهٔ ثابت حذف نشده و به‌عنوان dynamic ثبت شده است.
- `docs/app-map/mismatches.md`: ۷۲ route بدون caller مستقیم و علت‌های نامشخص.
- `docs/app-map/money-lineage.md`: مسیر مستقل مبلغ از DB/محاسبه تا پاسخ و UI.
- `docs/app-map/flows.md`: پیش‌شرط/پس‌شرط flowهای اصلی.
- `docs/app-map/test-coverage.csv`: mapping اولیه؛ این مرحله آن را با تست‌های واقعی/blocked تکمیل می‌کند.

چهار خطر مرحلهٔ صفر که در زیرساخت منعکس شده‌اند:

1. assertion فقط status code نیست؛ finance مقدارهای فارسی، integer و total را assert می‌کند.
2. ۷۲ route بدون caller حذف نمی‌شوند؛ برای همه registry و route doc تولید شده است.
3. URL پویا مثل `@Url` route ثابت فرض نمی‌شود.
4. contract Kotlin با parser مستقل `tests/route_audit/kotlin_contract.py` شبیه‌سازی می‌شود؛ Android compile اجرا نشده است.
