# Financial Audit Trail — ردگیری کامل تغییرات مالی — 2026-09-16 (FEATURE)

## درخواست
لاگ خودکار **همه‌ی** تغییرات مالی (create/update/delete) روی `Transaction` و `Installment`:
«چه کسی، چه زمانی، چه چیزی را عوض کرد» + اندپوینت کوئری صفحه‌بندی‌شده (فقط ادمین) + صفحه‌ی اندروید.

## قیود رعایت‌شده
- **۶ فایل ممنوعه بایت‌به‌بایت دست‌نخورده** (اکنون `exports.py` هم ممنوعه است): مقایسه‌ی sha256 با HEAD در بخش Verification.
- جداسازی کامل: تمام منطق لاگ/کوئری در فایل جدید `routers/audit_trail.py` (۴۸۲ خط)؛ اندروید در `AuditTrailActivity.kt` جدید.
- فقط ادمین: `Depends(check_admin_access)`.
- صفحه‌بندی: پیش‌فرض ۵۰، سقف ۲۰۰.

## ۱) مدل دیتابیس — `models.py` (≈۴۰ خط، فقط append)
`FinancialAuditLog` / جدول `financial_audit_logs` با ستون‌های دقیقاً طبق اسپک
(id, timestamp, user_id→users.id, username, action, entity_type, entity_id, old_values, new_values, ip_address)
+ `relationship("User")` + چهار ایندکس برای صفحه‌بندی/فیلترهای اندپوینت:
`timestamp`، `(entity_type, entity_id)`، `action`، `user_id`.
مایگریشن طبق الگوی پروژه: `create_all` در main.py **و** `CREATE TABLE IF NOT EXISTS` idempotent در
`setup_audit_listeners()` (برای دیتابیس‌های موجود). تاچ‌نکردن جداول دیگر.

## ۲) لاگ‌گیری خودکار — listener های SQLAlchemy
طرح در سه فاز (هر سه با probe تجربی روی SQLAlchemy 2.0.54 انتخاب شدند):

| فاز | کار | چرا این فاز |
|---|---|---|
| `before_flush` | **مقادیر قبلی** از DB با یک SELECT + تشخیص رکوردهای جدید/حذف‌شده | هنوز UPDATE اجرا نشده ⇒ مقدار قبلی واقعی. **reading از state آبجکت غلط است**: بعد از commit آبجکت‌ها expire‌اند و «مقدار قبلی» در حافظه وجود ندارد (probe: `old={"amount": null}` می‌داد). |
| `after_flush_postexec` | **مقادیر جدید** + `entity_id` + درج لاگ | در create، PK فقط بعد از INSERT تعیین می‌شود (probe: در before_flush همیشه `None` بود) و defaultهای ستون هم تازه اعمال شده‌اند. |
| `after_rollback` / `after_soft_rollback` | دور ریختن رکوردهای معلق | rollback ⇒ هیچ لاگ نیمه‌کاری در `session.info` نمی‌ماند. |

- **درج با Core-insert روی `session.connection()`** (نه `session.add`) → در همان تراکنشِ نوشتن ⇒
  rollback لاگ را هم برمی‌گرداند (تست دارد) و recursion/flush اضافه ایجاد نمی‌شود
  (probe: `session.add` در before_flush ردیف را با `entity_id=None` درج می‌کرد — نپذیرفتیم).
- **UPDATE بی‌اثر لاگ نمی‌شود**: بعد از commit، `obj.amount = <همان مقدار>` یک UPDATE خالی می‌فرستد؛
  با مقایسه‌ی اسنپ‌شات DB با state، این نویزِ آزمون‌شده حذف شد (probe بدون این محافظ یک ردیف update کاذب ساخت).
- **مقاوم**: هیچ استثنایی از listener بیرون نمی‌زند. اگر جدول لاگ نباشد یا درج شکست بخورد،
  نوشتن مالی سالم می‌ماند و فقط `⚠️ Audit Trail: ...` در لاگ سرور چاپ می‌شود (تصمیم آگاهانه:
  «در‌دسترس‌بودن» مهم‌تر از «کامل‌بودن» است — خطای لاگ نباید ثبت پرداخت را ۵۰۰ کند).
- سقف ۱۰۰۰ کاراکتر برای هر مقدار متنی در JSON (محافظت از سلول‌های غول‌پیکر).

## ۳) زمینه‌ی کاربر — میدل‌ور + ContextVar
میدل‌ور طبق اسپک در `main.py` ثبت شد (`app.add_middleware(audit_trail.AuditContextMiddleware)`،
بلافاصله بعد از SecurityHeadersMiddleware).
**انحراف آگاهانه از اسپک:** جای `request.state` از `contextvars.ContextVar` استفاده شد — دلیل تجربی:
listener های SQLAlchemy به درخواست دسترسی ندارند و اندپوینت‌های **sync** این پروژه در threadpool
اجرا می‌شوند؛ ContextVar هم در async و هم به‌صورت خودکار در threadpool کپی می‌شود (تست اختصاصی دارد).
`request.state` هم دسترسی‌پذیر نبود و هم به global mutable نیاز داشت.
- فقط متدهای `POST/PUT/PATCH/DELETE` ⇒ GET ها **صفر سربار/صفر کوئری**.
- کش ۳۰ ثانیه‌ای توکن→کاربر (حداکثر ۲۵۶ ورودی): درخواست‌های نوشتنِ پشت‌سرهم یک کاربر، یک کوئری اضافه ندارند.
- پاک‌سازی context در `finally` ⇒ کاربر درخواست قبلی به درخواست بعدی **نشت نمی‌کند** (تست دارد).
- IP: اولین مقدار `X-Forwarded-For` وگرنه هاست اتصال (سقف ۴۵ کاراکتر).
- این میدل‌ور فقط «برچسب» می‌سازد؛ احراز هویت واقعی همان `check_admin_access`/`get_db` است.

## ۴) اندپوینت — `GET /audit-trail/logs`
پارامترها: `entity_type`، `entity_id`، `action`، `user_id`، `start_date`، `end_date`، `page`(≥1)، `limit`(۱..۲۰۰، پیش‌فرض ۵۰).
- فیلتر نامعتبر ⇒ **۴۰۰** (entity_type/action خارج از مقادیر مجاز، start>end، تاریخ بی‌معنا)؛ limit/page نامعتبر ⇒ ۴۲۲.
- تاریخ‌ها **هم ISO و هم جلالی** (`1405/06/25`، سال<1700 ⇒ تبدیل با `today_summary.jalali_to_gregorian`)،
  و برای تاریخ خالص در `end_date` **کل آن روز** پوشش داده می‌شود (نیمه‌باز به روز بعد).
  زون: `timestamp` به UTC ذخیره می‌شود (استاندارد پروژه) و در پاسخ به **وقت محلی سرور** برمی‌گردد؛
  فیلترها هم از محلی به UTC تبدیل می‌شوند ⇒ نمایش و فیلتر با هم سازگارند.
- ترتیب: `timestamp DESC, id DESC`؛ پاسخ: `logs, total, page, limit, pages`.
- `changed_fields`: create/delete = فیلدهای مقداردار؛ update = **فقط فیلدهای واقعاً تغییریافته**.
- JSON خراب در ستون ⇒ پاسخ ۵۰۰ نمی‌دهد؛ `{"raw": ...}` برمی‌گرداند و «raw» در changed_fields شمرده نمی‌شود.
- `entity_id` در پاسخ **nullable** است (نه int اجباری): ردیف قدیمی/خراب نباید کل لیست را ۵۰۰ کند.

## ۵) اندروید (فقط بررسی استاتیک — بدون gradle)
| فایل | تغییر |
|---|---|
| `AuditTrailActivity.kt` (**جدید**، ۵۷۰ خط) | نوار فیلتر (۲ Spinner: نوع/عملیات، TextInput شناسه، دو دکمه‌ی تاریخ جلالی) + RecyclerView + «بارگذاری بیشتر» + دیالوگ دیف کامل + خروجی CSV + مدیریت ۴۰۱/۴۰۳ |
| `app/src/main/res/layout/activity_audit_trail.xml` (**جدید**) | چیدمان RTL طلایی مطابق دیزاین‌سیستم موجود + ProgressBar + Empty + LoadMore |
| `app/src/main/res/layout/item_audit_trail_log.xml` (**جدید**) | هر ردیف: آیکن عملیات (➕/✏️/🗑️)، کاربر+زمان، نوع+شناسه (کلیک ⇒ صفحه‌ی مرتبط)، خلاصه‌ی تغییر («مبلغ: 100,000 → 250,000»)، IP |
| `ApiInterfaces.kt` | `interface AuditTrailApi` (getLogs با همه‌ی فیلترها) — یک متد `exportLogsCsv` هم اضافه شد ولی **مصرف نمی‌شود** (تصمیم زیر) |
| `AppModels.kt` | `AuditTrailLog` + `AuditTrailResponse` با `@SerializedName` دقیقاً منطبق بر پاسخ سرور |
| `activity_admin_dashboard.xml` + `AdminDashboardActivity.kt` | کارت «تاریخچه تغییرات مالی» + دکمه‌ی `btnDashboardAuditTrail` |
| `strings.xml` | ۵۷ رشته‌ی `audit_trail_*` + `dashboard_action_audit_trail` |
| `AndroidManifest.xml` | ثبت `.AuditTrailActivity` (`exported=false`) |

- **تصمیم درباره‌ی «Export filtered logs to CSV»**: سرور در این تسک **دست‌نخورده** می‌ماند (قید)، پس
  CSV **سمت اپ** از همان مدل داده ساخته می‌شود: چند صفحه تا سقف ۲۰۰۰ ردیف، BOM،
  quote/escape استاندارد و مهار فرمول‌اینجکشن (= + - @) مثل خروجی‌های سرور؛ سپس
  `getExternalFilesDir` + FileProvider + ACTION_VIEW/SEND (باز/اشتراک‌گذاری).
- تاریخ: الگوی `PersianDatePickerDialog` **عیناً** مثل `EditStudentActivity` (کانونیکال پروژه:
  `setInitDate` + `Listener` آبجکتی)، تا هیچ متد تست‌نشده‌ی کتابخانه در کد نباشد.
- «بازکردن صفحه‌ی مرتبط»: تراکنش ⇒ `TransactionManageActivity`، قسط ⇒ `ReportActivity`
  (هر دو در مانیفست هستند؛ پارامترِ ناشناخته پاس داده نمی‌شود).

## ۶) تست — `test_audit_trail.py` (جدید، ۲۸ تست، همه pass)
- **Capture (۱۱)**: PK و اسنپ‌شات کامل در create؛ مقدار قبلی از DB در update؛ **UPDATE بی‌اثر لاگ نمی‌شود**؛
  delete؛ اقساط به‌عنوان installment؛ **rollback لاگ را برمی‌گرداند**؛ جدول لاگ غایب ⇒ نوشتن بیزینس سالم + هشدار؛
  بریدن مقدار ۵۰۰۰ کاراکتری؛ مدل‌های غیرمالی لاگ نمی‌شوند؛ انتساب کاربر از context؛ idempotent بودن setup.
- **Endpoint (۱۰)**: ۴۰۱ / ۴۰۳ (منشی و معلم) / ۲۰۰؛ صفحه‌بندی (total/pages/ترتیب نزولی/صفحه‌ی آخر)؛
  فیلترهای entity/action/user؛ ۴۰۰ و ۴۲۲ برای ورودی نامعتبر؛ فیلتر تاریخ ISO و **جلالی**؛
  timestamp محلی؛ changed_fields در سه عملیات؛ JSON خراب؛ DB خالی (pages=0).
- **میدل‌ور (۵)**: دیدن کاربر در اندپوینت async **و sync (threadpool)**؛ IP از X-Forwarded-For؛
  GET بدون سربار؛ توکن نامعتبر ⇒ زمینه‌ی خالی؛ **عدم نشت بین درخواست‌ها**.
- **E2E (۱)**: نوشتن از مسیر HTTP واقعی ⇒ لاگ با username و IP درست.
- **جداسازی (۱)**: هیچ‌کدام از ۶ روتر محافظت‌شده به `audit_trail`/`FinancialAuditLog` وابسته نشده است.

## Verification (همه واقعی — روی کپی /tmp، نه DB پروداکشن)
```
1) ast.parse(audit_trail.py, main.py, models.py, test_audit_trail.py)     → OK
2) import main واقعی روی کپی /tmp                                        → OK
   listeners installed=True | جدول ثبت‌شده=True | مسیر /audit-trail/logs فعال
3) سوئیت کامل از ریشه‌ی ریپو (روش کانونیکال)                             → 333 passed, 0 failed
   (۳۳۳ = ۳۰۵ قبلی + ۲۸ تست جدید؛ رگرسیون صفر)
4) ۶ فایل ممنوعه — sha256(current) == sha256(HEAD):
   finance   fca8c7aff4037cc2…   UNCHANGED
   timeline  522d138366451896…   UNCHANGED
   audit     2fd9b13a5c4d6e58…   UNCHANGED
   dunning   a17b5d579dd72a1a…   UNCHANGED
   dashboard 3e338f15b5b6d45f…   UNCHANGED
   exports   ae99abbdaf684f96…   UNCHANGED
5) DB پروداکشن: sha256 = f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79 (بدون تغییر)
6) نمونه‌ی زنده (کپی /tmp/trail_live.db + uvicorn :8033 + توکن ادمین):
   بدون توکن → 401 | با توکن → 200 | total=5, page=1, limit=3, pages=2
   سه لاگ با action متفاوت (پاسخ کامل در ادامه‌ی چکپوینت) و فیلتر
   entity_type=installment&action=delete → total=1
7) بنچمارک سربار (۳۰۰ INSERT + ۳۰۰ UPDATE، SQLite، همان ماشین):
   INSERT: 1.50ms → 1.97ms  (+0.47ms/رکورد)
   UPDATE: 1.72ms → 2.48ms  (+0.76ms/رکورد؛ شامل SELECT مقدار قبلی + INSERT لاگ)
   تعداد لاگ‌های ثبت‌شده: 600 دقیقاً (۳۰۰ create + ۳۰۰ update، بدون ردیف کاذب)
8) اندروید — بررسی استاتیک: XML هر ۵ فایل parse شد؛ ۵۷ رشته‌ی audit_trail_* تعریف‌شده و
   همه استفاده‌شده‌ها موجود؛ همه‌ی id ها و resourceهای layout جدید resolve شدند؛
   brace/paren و import بی‌استفاده در هر ۴ فایل Kotlin پاک؛ `.AuditTrailActivity` در مانیفست.
```

### کدهای ۳ لاگ نمونه (خروجی واقعی GET /audit-trail/logs)
```json
[
  {
    "id": 5, "timestamp": "2026-09-16 19:20:06.274217", "username": "09120000000",
    "action": "delete", "entity_type": "installment", "entity_id": 1,
    "old_values": {"id": 1, "enrollment_id": 1, "amount": 300000, "due_date": "1405/07/01",
                   "is_paid": true, "paid_at": "1405/06/26", "paid_amount": 0, "is_deleted": false},
    "new_values": null, "ip_address": "203.0.113.7",
    "changed_fields": ["amount","due_date","enrollment_id","id","is_deleted","is_paid","paid_amount","paid_at"]
  },
  {
    "id": 4, "timestamp": "2026-09-16 19:20:06.271063", "username": "09120000000",
    "action": "update", "entity_type": "installment", "entity_id": 1,
    "old_values": {"amount": 300000, "is_paid": false, "paid_at": null, "...": "..."},
    "new_values": {"amount": 300000, "is_paid": true,  "paid_at": "1405/06/26", "...": "..."},
    "ip_address": "203.0.113.7", "changed_fields": ["is_paid", "paid_at"]
  },
  {
    "id": 3, "timestamp": "2026-09-16 19:20:06.267014", "username": "09120000000",
    "action": "create", "entity_type": "installment", "entity_id": 1,
    "old_values": null,
    "new_values": {"id": 1, "enrollment_id": 1, "amount": 300000, "due_date": "1405/07/01",
                   "is_paid": false, "paid_at": null, "paid_amount": 0, "is_deleted": false},
    "ip_address": "203.0.113.7",
    "changed_fields": ["amount","due_date","enrollment_id","id","is_deleted","is_paid","paid_amount"]
  }
]
```

## محدودیت‌ها و نکات عملیاتی (صادقانه)
1. **bulk update/delete سبک Core** (`db.query(X).update(...)` یا `query.delete()`) رویداد ORM تولید
   نمی‌کند ⇒ لاگ نمی‌شود. مسیرهای مالی این پروژه از ORM استفاده می‌کنند؛ اگر جایی bulk اضافه شد،
   باید آگاهانه تصمیم گرفت.
2. **نوشتن‌های غیر-HTTP** (ورکر پس‌زمینه، اسکریپت‌ها، automation) `user_id/username/ip` تهی دارند —
   لاگ ثبت می‌شود ولی «کاربر» ندارد (دقیق و مطلوب است: تغییر سیستمی است).
3. **اسکریپت‌های مستقل** (که `main` را ایمپورت نمی‌کنند) باید خودشان `audit_trail.setup_audit_listeners()`
   را صدا بزنند؛ در غیر این‌صورت نه listener نصب می‌شود و نه جدول ساخته می‌شود.
   (همین را در seed اولیه‌ی خودم دیدم و در چکپوینت باقی مانده است.)
4. `AuditTrailApi.exportLogsCsv` در اینترفیس هست ولی مصرف نمی‌شود و **کار نمی‌کند** (سرور CSV نمی‌دهد)؛
   اگر بعداً خواستید CSV سرورساید شود، باید یک endpoint در همان ماژول `audit_trail.py` اضافه شود
   (فایل ممنوعه نیست) — یا این متد منسوخ حذف شود.
5. لاگ‌های این جدول خودشان audit نمی‌شوند (self-logging نمی‌کنیم؛ ریسک recursion).

## فایل‌های تغییر‌یافته
```
M  Kharazmi_Server/models.py                 (+ FinancialAuditLog)
M  Kharazmi_Server/main.py                   (import + middleware + setup + include_router)
?? Kharazmi_Server/routers/audit_trail.py    (جدید — listener ها + اندپوینت + میدل‌ور)
?? Kharazmi_Server/test_audit_trail.py       (جدید — ۲۸ تست)
?? KharazmiAdmin/.../AuditTrailActivity.kt   (جدید)
?? KharazmiAdmin/app/src/main/res/layout/activity_audit_trail.xml   (جدید)
?? KharazmiAdmin/app/src/main/res/layout/item_audit_trail_log.xml   (جدید)
M  KharazmiAdmin/.../ApiInterfaces.kt        (+ AuditTrailApi)
M  KharazmiAdmin/.../AppModels.kt            (+ AuditTrailLog/Response)
M  KharazmiAdmin/.../AdminDashboardActivity.kt (+ دکمه‌ی ورود)
M  KharazmiAdmin/app/src/main/res/layout/activity_admin_dashboard.xml (+ کارت جدید)
M  KharazmiAdmin/app/src/main/res/values/strings.xml  (+ ۵۸ رشته)
M  KharazmiAdmin/app/src/main/AndroidManifest.xml     (+ ثبت اکتیویتی)
```
