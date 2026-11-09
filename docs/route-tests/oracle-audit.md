# ممیزی استقلال oracle

## دستور grep

```text
$ grep -nE '^(from|import).*financial_calculations|^(from|import).*dependencies|^(from|import).*routers' tests/route_audit/oracle.py
<خروجی خالی>
```

فقط `models` داخل `build_oracle` برای خواندن rowهای دیتابیس import می‌شود؛ هیچ تابع production از `financial_calculations.py`، `dependencies.py` یا routerها وارد oracle نشده است.

## ناوردایی‌های دفترکل مستقل

فرمول‌ها در `tests/route_audit/oracle.py:31-117` پیاده‌سازی شده‌اند و از event/rowهای seed محاسبه می‌شوند:

1. تخفیف درصدی، تخفیف ثابت و تخفیف بزرگ‌تر از شهریه به `discount <= gross` clamp می‌شوند.
2. شهریهٔ خالص هر enrollment برابر `max(0, gross - discount)` است.
3. پرداخت معتبر فقط transaction مثبت و غیرحذف‌شده/غیرreversed است.
4. بدهی هر enrollment و جمع بدهی هر دانش‌آموز منفی نمی‌شود.
5. سهم teacher/institute از فیلدهای صریح receipt جمع می‌شود و target `both` دوباره‌شماری نمی‌شود.
6. وصولی نقدی آموزشگاه و جمع روزانه/ماهانه از eventهای institute به‌صورت مستقل جمع می‌شوند.
7. charge جلسه فقط برای session فعال و attendance حاضر/تأخیر یا غیبت غیرموجه وارد دفترکل می‌شود.
8. جمع طلب معلم و سهم آموزشگاه از snapshot جلسه جدا نگه داشته می‌شود.
9. تسویهٔ معلم فقط settlement غیرreversed را از طلب کم می‌کند.
10. invariantهای پایه در `assert_invariants` (`oracle.py:120-127`) برای بدهی غیرمنفی و cash غیرمنفی اجرا می‌شوند.

این oracle فعلاً رفتار مبهم واحد تومان/ریال یا تعریف محصولی «درآمد» را حدس نمی‌زند؛ موارد Q-001 تا Q-005 در `questions.md` باز هستند.
