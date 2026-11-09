# Checkpoint — follow-up گپ H8: نمایش تماماً-غایب‌ها در گزارش‌های طلب

Date: 2026-09-12. Asserted + read-back. No compile/run.

## سایت‌ها (۶ مورد، همان الگوی pending + منطق دوشاخه‌ی settle)
1. `teachers.py:696-719` — تنها لیست سربه‌سر UI: سطل‌های عادی `penalty_only: False`
   (:704)؛ حلقه‌ی جدید سطل جریمه‌تنها با `penalty_only: True`، ‏present_count=۰ و
   amount=فقط‌جریمه می‌سازد (فیلتر تاریخ via session_map حفظ شده). بدون response_model
   پس additive و سازگار.
2. `analytics.py:320/:324` — ستون flag به کوئری + شاخه‌ی OR در جمع.
3. `finance.py:1947/:1951` — همان.
4. `classes.py:886-887` — همان روی آبجکت ORM (اسنپ‌شات حذف کلاس).
5. `today_summary.py:310-323` — گسترش pending_session_ids آلارم تسویه (IN تکراری‌پذیر پس dedupe لازم نیست).
6. `today_summary.py:560-575` — مبلغ هفتگی: OR مشروط روی فیلتر id (خالی→بدون OR تا IN تهی نسازد؛ or_ از قبل ایمپورت بود).

## عمداً دست‌نخورده
- `teachers.py:589` (اکسل درآمد) و `attendance.py:594` (history جلسه): گیت pending ندارند
  و از قبل همه‌چیز (شامل جریمه‌ی تماماً-غایب) را جمع می‌زنند — الگوی pending نیستند.

## چرا نمایش گمراه‌کننده نیست (قدم ۳)
- تنها نمای سربه‌سر (pending list) پرچم صریح `penalty_only` دارد تا UI بج «فقط جریمه»
  بزند؛ بقیه aggregate تکی‌اند (طلب کامل‌تر، بدون تفکیک سربه‌سر).
- `session_count` آلارم: جلسه‌ی تماماً-غایبِ جریمه‌باز واقعاً «تسویه‌نشده و قابل‌تسویه» است پس شمردنش درست است.
- سازگاری گیت↔گزارش: predicate یکسان (penalty>0 و flag False) یعنی هرچه pending دیده می‌شود دقیقاً قابل settle است.
