# فاز C — نقشهٔ صفحه‌به‌صفحه

## پوشش

- تعداد فایل‌های screen برای Activityها: **51** در `docs/app-map/screens/`.
- شامل `MainActivityRefactored` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ui/MainActivityRefactored.kt:12` است؛ چون کلاس Activity است، حتی اگر نام آن suffix معمول `Activity` نداشته باشد.
- هر سند صفحه شامل این بخش‌هاست:
  1. Kotlin و `file:line` تعریف کلاس؛
  2. `setContentView(R.layout...)` و layout؛
  3. عناصر تعاملی که source آن‌ها `setOnClickListener`/تب/دیالوگ/transition را نشان می‌دهد؛
  4. فراخوانی‌های `api.method` و اتصال method به routeهای CSV فاز B؛
  5. assignmentهای نمایشی مثل `.text`, `.adapter`, chart/WebView و مرجع route/data class.
- هر سندی که source برای آن موردی نشان نمی‌دهد، صریحاً `نامشخص` دارد؛ هیچ رفتار از نام Activity حدس زده نشده است.

## navigation

گراف لبه‌های `Intent(... TargetActivity::class.java)` در [`navigation.md`](navigation.md) آمده است. استخراج شامل 180 edge صریح است. Intentهایی که مقصد را از string/extra/runtime می‌سازند عمداً edge حدسی ندارند و در بخش نامشخص همان سند ثبت شده‌اند.

## محدودیت دقت

- متن نهایی فارسی بعضی viewها از resource XML می‌آید، نه Kotlin؛ در این فاز id و source handler ثبت شده و برای متن runtime، مرجع layout/XML یا `R.string` نگه داشته شده است.
- mapping یک data field تا ستون DB فقط وقتی در screen doc قطعی نوشته شده که route/handler آن را در CSV سرور یا کد محاسباتی نشان دهد؛ در غیر این صورت `نامشخص` است و finding محسوب نمی‌شود.
- Android compile طبق درخواست اجرا نشده است.
