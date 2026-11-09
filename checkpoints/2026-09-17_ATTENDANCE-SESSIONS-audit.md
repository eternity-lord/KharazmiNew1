# ممیزی ثبت جلسه / حضور و غیاب / هزینه‌ی جلسه / جریمه / حذف / برگشت مالی — ۲۰۲۶-۰۹-۱۷

برنچ: `arena/01a0aac2-kharazmiapp` | ریپو: `eternity-lord/KharazmiApp` | HEAD شروع: `102430b`
**فقط تست — هیچ خطی از کد اصلی تغییر نکرد.**

## ۱) baseline (قبل از تست)
| دستور | نتیجه |
|---|---|
| `python -m compileall Kharazmi_Server` | **exit 0** |
| `pytest -q Kharazmi_Server` | **499 passed / 0 failed / 0 skipped** (39.5s) |

(سندباکس بین تسک‌ها ریست شده بود: HEAD روی `2b5ea9f`، بدون deps و بدون `.env`. اول تأیید sha256 شد که
محتوای دیسک عیناً برابر کامیت ریموت `102430b` است، سپس `reset --hard`، نصب deps و ساخت
`Kharazmi_Server/.env` سندباکس (gitignore شده؛ DB روی `/tmp`) — هیچ کاری از دست نرفت.)

## ۲) دستورهای اجراشده
```bash
cd /home/user/KharazmiApp
python3 -m compileall Kharazmi_Server
cp Kharazmi_Server/gaj_db.db /tmp/attendance_audit.db      # کپی — هرگز DB واقعی
cp Kharazmi_Server/gaj_db.db /tmp/full_suite_attendance.db
DATABASE_URL=sqlite:////tmp/attendance_audit.db PYTHONPATH=/home/user/KharazmiApp/Kharazmi_Server \
  python3 -m pytest -q Kharazmi_Server/test_attendance_sessions_audit.py
DATABASE_URL=sqlite:////tmp/full_suite_attendance.db PYTHONPATH=/home/user/KharazmiApp/Kharazmi_Server \
  python3 -m pytest -q Kharazmi_Server
```

## ۳) نتیجه‌ی اجرا
| سنجه | قبل | بعد |
|---|---|---|
| فایل جدید | — | `Kharazmi_Server/test_attendance_sessions_audit.py` (۶۷ تست) |
| فایل جدید | — | **59 passed / 8 failed / 0 skipped** (۶٫۳s) |
| سوئیت کامل | 499P / 0F | **558 passed / 8 failed / 0 skipped** (۴۷٫۴s) |

۸ failure = **۴ یافته‌ی واقعی** (F-S4 پنج پارامتر دارد). بقیه‌ی سناریوهای ۲۷گانه سبزند.

## ۴) نام کامل تست‌های fail شده
1. `test_attendance_sessions_audit.py::test_s08b_finding_deleted_student_counts_as_present_but_charges_nobody` — F-S1
2. `test_attendance_sessions_audit.py::test_s19b_finding_delete_destroys_attendance_history` — F-S2
3. `test_attendance_sessions_audit.py::test_s_ext_items_finding_empty_attendee_list_occupies_the_date` — F-S3
4. `test_attendance_sessions_audit.py::test_s_ext_status_finding_unknown_status_is_silently_free[banana]` — F-S4
5. … `[present]` 6. … `[PRESENT]` 7. … `[حاضر]` 8. … `[]` — همه F-S4

## ۵) شرح هر failure
### F-S1 — دانش‌آموز soft-deleted: «حاضر» شمرده می‌شود ولی کسی شارژ نمی‌شود
* **سناریوی بازتولید:** `is_deleted=True` روی دانش‌آموز ۱۰۱ (enrollment فعال) ← `submit_session` با یک آیتم `Present`.
* **فایل/خط:** `routers/attendance.py:423` (شمارش `present_students` از آیتم‌های خام) + `:449-459`
  (`attendee_count=present_count`) + `:496-498` (`st = ... Student.is_deleted == False` سپس `if st is None: continue`)
  و `dependencies.py:364-400` (validator فقط «معلق» را رد می‌کند — `:395` — نه «حذف‌شده»).
* **expected:** مثل مسیر معلق (۴۲۲) رد شود، یا دست‌کم از شمارش/سهم‌ها حذف شود تا جلسه ادعای حاضر نداشته باشد.
* **actual:** درخواست **موفق**؛ `SessionLog` ساخته می‌شود با `attendee_count=1` و `final_teacher_cost=60`،
  در حالی که `attendance_rows=0`، `charge_rows=0` و کیف دانش‌آموز دست‌نخورده است.
* **severity: High** — سهم معلم بدهکار می‌شود بدون آنکه از کسی وصول شده باشد و شمارش حاضرین گزارش‌ها دروغ است.
* **قطعی:** قطعی (بازتولید شد و مسیر کد مشخص است).

### F-S2 — حذف/برگشت جلسه، سابقه‌ی حضور را فیزیکی پاک می‌کند
* **سناریوی بازتولید:** ثبت جلسه با دو ردیف (Present + Absent) ← `DELETE /attendance/session/{code}`.
* **فایل/خط:** `dependencies.py:359` (`db.query(Attendance)...delete()`) که از `routers/attendance.py:1040`
  (حذف جلسه) و `:887` (ویرایش جلسه) صدا زده می‌شود؛ `models.Attendance` هیچ ستون `is_deleted` ندارد (`models.py:381-397`).
* **expected:** سابقه‌ی حضور مثل بقیه‌ی حذف‌های پروژه (Enrollment/Installment/SessionLog/Transaction) آرشیو بماند.
* **actual:** ردیف‌های حضور کامل حذف می‌شوند (`remaining=0`) و هیچ نشانی از حذف باقی نمی‌ماند.
* **severity: Medium** — سند مالی (Transaction) و سند جلسه می‌مانند ولی سابقه‌ی «چه کسی حاضر بود» نابود می‌شود.
* **قطعی:** رفتار قطعی است؛ «باگ بودن یا policy بودن» نیازمند تصمیم شماست (اصلاحش مایگریشن ستون می‌خواهد).

### F-S3 — `items=[]` پذیرفته می‌شود و تاریخ جلسه را قفل می‌کند
* **سناریوی بازتولید:** `AttendanceSubmitData(items=[])` ← سپس ثبت واقعی همان (کلاس، تاریخ).
* **فایل/خط:** `schemas.py:141` (`items: List[AttendanceItem]` بدون `min_length`) + `routers/attendance.py:449`
  (ساخت SessionLog) و پیش‌چک یکتایی `:406` روی (course_id,date).
* **expected:** درخواست بدون هیچ ردیف حضور/غیاب رد شود (جلسه‌ی بی‌محتوا نباید ساخته شود).
* **actual:** SessionLog ساخته می‌شود (`count=1`) و ثبت واقعی همان روز بعداً **۴۰۹** می‌گیرد.
* **severity: Medium** — یک درخواست خالی/اشتباه، جلسه‌ی واقعی کلاس را برای آن تاریخ قفل می‌کند.
* **قطعی:** قطعی (بازتولید شد).

### F-S4 — وضعیت ناشناخته/کوچک‌نویس بی‌صدا بی‌هزینه ثبت می‌شود
* **سناریوی بازتولید:** `status` ∈ {`banana`, `present`, `PRESENT`, `حاضر`, ``} برای دانش‌آموز حاضر کلاس.
* **فایل/خط:** `schemas.py:135` (`status: str` — بدون `Literal`/enum) + `routers/attendance.py:508-516`
  (شاخه‌ی `should_charge` فقط `Present`/`Late`/`Absent` را می‌شناسد).
* **expected:** فقط `Present`/`Late`/`Absent` (طبق `models.Attendance.status` و همه‌ی فیلترهای is_billed/جریمه)
  پذیرفته شود و بقیه مثل خطای تاریخ/عضویت ⇒ **۴۲۲**.
* **actual:** درخواست بدون هیچ خطایی ثبت می‌شود؛ ردیف Attendance با همان متن نامعتبر ذخیره می‌شود،
  `should_charge` نادرست می‌ماند ⇒ **هیچ شارژی رخ نمی‌دهد** و هیچ هشداری هم داده نمی‌شود.
* **severity: Medium** — یک تایپ ساده در کلاینت بی‌صدا درآمد جلسه را صفر می‌کند (ریسک از دست رفتن درآمد).
* **قطعی:** رفتار قطعی است؛ سخت‌گیری ناگهانی ممکن است کلاینت‌های موجود را بشکند ⇒ قبل از fix بررسی سازگاری لازم است.

## ۶) جدول نهایی
| ID | حوزه | شدت | فایل/خط | شرح | وضعیت |
|---|---|---|---|---|---|
| F-S1 | ثبت جلسه / شمارش حاضرین | **High** | `routers/attendance.py:423,449-459,496-498` + `dependencies.py:395` | دانش‌آموز حذف‌شده «حاضر» شمرده و سهم معلم ثبت می‌شود، بدون رکورد حضور/شارژ | تست failing ثبت شد؛ **fix نشد** |
| F-S2 | حذف/برگشت جلسه | Medium | `dependencies.py:359` (کالر: `attendance.py:887,1040`) | ردیف‌های حضور فیزیکی پاک می‌شوند؛ سابقه‌ی حضور از بین می‌رود | تست failing ثبت شد؛ **fix نشد** (نیاز به تصمیم/مایگریشن) |
| F-S3 | اعتبارسنجی ورودی جلسه | Medium | `schemas.py:141` + `attendance.py:406,449` | `items=[]` جلسه‌ی خالی می‌سازد و تاریخ را قفل می‌کند (ثبت واقعی بعدی ۴۰۹) | تست failing ثبت شد؛ **fix نشد** |
| F-S4 | اعتبارسنجی وضعیت | Medium | `schemas.py:135` + `attendance.py:508-516` | وضعیت ناشناخته/کوچک‌نویس بی‌صدا بدون شارژ ثبت می‌شود | تست failing ثبت شد؛ **fix نشد** |
| O-S1 | پیام خطای تسویه | Low | `routers/teachers.py:805-810` | جلسه‌ی بدون هیچ حاضر/جریمه با پیام گمراه‌کننده‌ی «قبلاً تسویه شده‌اند» رد می‌شود (رفتار درست، پیام نادرست) | فقط مشاهده (تست سبز `test_s24f`) |

## ۷) مواردی که طبق business rule درست هستند (تأییدشده با تست سبز)
1. **ثبت جلسه‌ی عضو فعال** (سناریو ۱): SessionLog + Attendance + یک `session_charge` با
   `share_teacher=60`/`share_institute=40`/`amount=-100`، شعبه‌ی شاگرد (H7) و شمارنده‌ی session.
2. **عضو نبودن / معلق / دانش‌آموز کلاس دیگر** ⇒ **۴۲۲ قبل از هر نوشتن** (سناریو ۲، ۳، ۷): نه SessionLog،
   نه Attendance، نه Transaction، نه تغییر کیف، نه افزایش شمارنده.
3. **duplicate همان (کلاس، تاریخ)** ⇒ **۴۰۹** (سناریو ۴): جلسه/تراکنش/حضور دوم ساخته نمی‌شود، کیف دوباره کم
   نمی‌شود و `SequenceCounter` بی‌دلیل بالا نمی‌رود (پیش‌چک **قبل** از تخصیص کد جلسه است).
4. **همان کلاس در تاریخ دیگر** ⇒ مجاز و مستقل (سناریو ۵)؛ پس از حذف جلسه هم همان تاریخ دوباره قابل ثبت است
   (سناریو ۱۹/۴).
5. **سیاست تکرار (session, student)** در یک درخواست = **رد ۴۲۲** (نه update) و در دو درخواست = **۴۰۹**؛
   وضعیت قبلی دست‌نخورده (سناریو ۶) — مطابق قید یکتای `uq_attendance_session_student`.
6. **تاریخ جلالی** (سناریو ۹): معتبر پذیرفته و **کانونیکال** ذخیره می‌شود؛ نامعتبر (`bad-date`, `1405/13/01`,
   `1405/00/01`, `1405/01/00`, `1405/01/32`, `1405/12/30`, `1405/07/31`, خالی) ⇒ **۴۲۲ بدون هیچ نوشتن**؛
   همان روز با فرمت میلادی **duplicate پنهان نمی‌سازد** (هر دو ترتیب ۴۰۹) — حاصل FIX #13 پروژه.
7. **Present** (سناریو ۱۰): سرانه = نرخ معلم + سهم آموزشگاه، جمع سهم‌های تراکنش‌ها = مبالغ جلسه،
   `amount = -(share_t + share_i)` و کیف دقیقاً به همان مبلغ کم می‌شود.
8. **Late == Present** (سناریو ۱۱): policy فعلی پروژه هیچ جریمه‌ی تأخیر ندارد؛ Late در شمارش حاضرین و شارژ
   هم‌ارز Present است (مستند شد).
9. **غیبت موجه** (سناریو ۱۲): بدون جریمه، بدون شارژ، `excused=True` ذخیره می‌شود و اطلاع‌رسانی والدین
   (نوع attendance) ثبت می‌شود؛ سهم اشتباه مالی ایجاد نمی‌شود.
10. **غیبت غیرموجه** (سناریو ۱۳): جریمه = `U × base` طبق rule همان Course، جدا از `final_*` در
    `absent_penalty_teacher/institute`، و شرح تراکنش «غایب غیرموجه».
11. **جلسه‌ی تماماً غایب** (سناریو ۱۴): `final_teacher_cost=final_institute_share=0` (هزینه‌ی جلسه‌ی حاضرین
    اشتباهاً اعمال نمی‌شود) و جریمه طبق `U` محاسبه می‌شود: با ۲ غایب غیرموجه ⇒ `pen_t=120, pen_i=80` و
    جمع شارژها = ۲۰۰؛ با یک غایب موجه فقط یک نفر جریمه می‌شود.
12. **`rule_calc_absent=False`** (سناریو ۱۵): غایب غیرموجه جریمه نمی‌شود (`pen=0`) و فقط حاضرین شارژ می‌شوند.
13. **`rule_prepay_teacher=True`** (سناریو ۱۶): `T_total=0` و `share_teacher=0` — دوباره از دانش‌آموز گرفته
    نمی‌شود (فقط ۴۰ از آموزشگاه). **`rule_prepay_institute=True`** (سناریو ۱۷): `I_total=0` و
    `share_institute=0` (فقط ۶۰ از معلم) — هر دو با کیف و تراکنش سازگار.
14. **مبلغ فرد ۱۰۱** (سناریو ۱۸): تقسیم ۳ نفره بدون هیچ سهم اعشاری (نوع ستون‌ها در SQLite هم `integer` بود)،
    `[33,34,34]` برای معلم و `[33,33,34]` برای آموزشگاه ⇒ **باقیمانده گم نمی‌شود** و جمع دقیقاً ۱۰۱/۱۰۰ است.
15. **حذف نرم جلسه** (سناریو ۱۹): `SessionLog.is_deleted=True` (سند می‌ماند)، تراکنش‌ها آرشیو می‌شوند
    (سطر و `session_id`/`course_id`/`student_id`/`branch_id` دست‌نخورده)، کیف **یک بار** restore می‌شود،
    `PRAGMA foreign_key_check` پاک است، حذف تکراری ۴۰۴ و بی‌اثر، و همه‌ی گزارش‌های درآمد/گردش صفر می‌شوند.
16. **اجرای دوباره‌ی reverse** (سناریو ۲۰): نه افزایش دوباره‌ی کیف، نه تراکنش تکراری (claim اتمیک per-tx).
17. **ویرایش جلسه** (سناریو ۲۱): مبلغ قدیمی کامل reverse و آرشیو می‌شود، مبلغ جدید **فقط یک بار** اعمال
    می‌شود (کیف نه دوبرابر و نه صفر)، حضور قبلی جایگزین می‌شود (بدون ردیف تکراری) و گزارش‌ها فقط مبلغ
    جدید را نشان می‌دهند.
18. **تغییر وضعیت در ویرایش** (سناریو ۲۲): Present→Absent (پول از قرارداد به جریمه منتقل شد،
    `final_t 120→60`, `pen_t 0→60`)، Absent→Present (جریمه صفر شد، `final_t 60→120`)، Excused→Unexcused
    (جریمه دقیقاً یک بار، ۶۰/۴۰) و برگشت به موجه جریمه را کامل خنثی کرد — در همه کیف هر دانش‌آموز −۱۰۰ ماند.
19. **جلسه‌ی حذف‌شده** (سناریو ۲۳): قابل تسویه نیست (۴۰۰)، از `get_history` حذف می‌شود،
    `get_session_details` ⇒ ۴۰۴، درآمد معلم/آموزشگاه صفر، و refund عمومی روی `session_charge` ⇒ ۴۰۰ با
    راهنمای درست («برگشت هزینه‌ی جلسه فقط با حذف جلسه») و پس از حذف ⇒ ۴۰۴.
20. **settlement معلم** (سناریو ۲۴): `total_amount = final_teacher_cost + absent_penalty_teacher`
    (تطابق کامل با SessionLog و تراکنش `settlement_payout`)، `is_billed=True` روی حاضرین، تسویه‌ی تکراری
    ⇒ ۴۰۰ بدون Settlement/payout دوم، لیست حاوی جلسه‌ی تسویه‌شده کل درخواست را رد می‌کند (۴۰۰)،
    جلسه‌ی reversed/deleted قابل تسویه نیست، و **جلسه‌ی تماماً-غایب** فقط برای جریمه‌اش **یک بار** تسویه
    می‌شود (`is_penalty_settled=True`). جلسه‌ی تسویه‌شده برای ویرایش/حذف قفل است (۴۰۹).
21. **rollback** (سناریو ۲۵): کرش میانه (سینک کیف) و خطای قطعی انتهای حلقه (نبود شعبه، ۴۰۰) هیچ اثری
    باقی نگذاشتند — بدون SessionLog/Attendance/Transaction، کیف‌ها صفر، و شمارنده‌ی session دست‌نخورده.
    ویرایش ناموفق (۴۲۲) هم اثر مالی قبلی را **قبل از reverse** نگه می‌دارد.
22. **invariant `wallet_balance == wallet_teacher + wallet_institute`** (سناریو ۲۶) در همه‌ی گام‌های مالی
    (ثبت، پرداخت، ویرایش، حذف، تسویه) برقرار است — helper هر عملیات خودش assert می‌کند.
23. **هم‌زمانی** (سناریو ۲۷، SQLite-only): دو ثبت موازی همان (کلاس، تاریخ) ⇒ دقیقاً یک موفق و یکی
    **۴۰۹**، یک SessionLog/Attendance/Transaction و کیف فقط یک بار (−۱۰۰). دو reverse موازی ⇒ کیف یک بار
    restore و تراکنش تکراری ساخته نشد (گیت‌های UPDATE مشروط). این تست ۳ بار متوالی بدون flake سبز شد.

## ۸) محدودیت‌های محیط تست / SQLite
- سناریوهای race (۲۷الف/۲۷ب) روی **SQLite فایلی** با `PRAGMA foreign_keys=ON`، `timeout=30` و فایل DB در
  `tmp_path` اجرا شدند. SQLite نوشتن‌ها را در سطح فایل سریالایز (یا با `database is locked` رد) می‌کند،
  پس این تست‌ها **درستی گیت‌های UPDATE مشروط/یکتایی را اثبات می‌کنند، نه رفتار قفل سطری یا MVCC
  PostgreSQL**. برای اثبات واقعی رقابت، اجرا روی Postgres لازم است (SQLite-only علامت خورد).
- بقیه‌ی تست‌ها SQLite **درون‌حافظه** با `StaticPool` هستند (هر تست DB مستقل).
- در سناریوی تسویه، هر بار `db.expire_all()` می‌شود تا رفتار «Session تازه‌ی هر درخواست HTTP»
  (`get_db`) شبیه‌سازی شود؛ بدون آن، آبجکت stale در identity-map باعث ۴۰۹ کاذب «تسویه‌ی هم‌زمان» می‌شود
  (این یک artifact تست است نه باگ API — با state تازه، ۴۰۰ درست برمی‌گردد).
- تاریخ‌های تست نسبی/ثابت‌اند (`1405/06/16` و معادل میلادی‌اش `2026/09/07`) و به ساعت سیستم وابسته نیستند.
- `parse_project_date` رشته‌های سال ≥ ۱۷۰۰ را میلادی می‌فهمد؛ این رفتار قبلی پروژه در تست‌ها دست‌نخورده ماند.

## ۹) تأیید عدم تغییر دیتابیس واقعی
```
Kharazmi_Server/gaj_db.db → f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79  (بدون تغییر ✅)
همه‌ی اجراها با DATABASE_URL=sqlite:////tmp/attendance_audit.db و /tmp/full_suite_attendance.db (کپی‌ها).
.env سندباکس gitignore شده و به /tmp اشاره می‌کند (در کامیت نیست). تست جدید هیچ فایل پروژه را نمی‌خواند/نمی‌نویسد.
```

## ۱۰) git status / git diff (قبل از کامیت)
```
$ git status --porcelain
?? Kharazmi_Server/test_attendance_sessions_audit.py
$ git diff --stat
(خالی — هیچ کد اصلی تغییر نکرده)
routers/attendance.py, routers/finance.py, financial_calculations.py, dependencies.py, models.py, schemas.py
همه sha256 دیسک == HEAD ✅
```

## ۱۱) تأیید نهایی
- **هیچ fix یا تغییر کد اصلی انجام نشد** (طبق دستور): تنها فایل اضافه‌شده این تست + همین چک‌پوینت است.
- ۴ یافته فقط **مستند** شده‌اند و تست failing بازتولیدشان موجود است؛ برای بستنشان منتظر دستور شما هستم.
