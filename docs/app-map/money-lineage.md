# فاز D — money lineage

این سند مسیر دادهٔ مبلغ، پرداخت، کیف و بدهی را از ستون‌های دیتابیس تا پاسخ سرور و نمایش Android دنبال می‌کند. واحد مبلغ در کد «تومان» فرض/نمایش داده می‌شود، اما تبدیل واحدی در این scan پیدا نشد؛ این مورد در بخش نامشخص ثبت شده است. بحث token، access control و امنیت خارج از scope است.

## 1. واژه‌ها و منبع‌های اصلی

| مفهوم | منبع داده | معنی قابل اثبات | مرجع دقیق |
|---|---|---|---|
| شهریهٔ پایه | `enrollments.total_tuition` | مبلغ قرارداد ثبت‌نام قبل از discount | `Kharazmi_Server/models.py:230-239` |
| discount | `enrollments.discount_type`, `discount_value` | درصد: `(base * value) // 100`؛ ثابت: `value`؛ سپس `max(0, base-discount)` | `Kharazmi_Server/dependencies.py:347-359` |
| پرداخت ثبت‌نام | `enrollments.total_paid` | aggregate legacy/compatibility برای مبالغ ثبت‌شده روی enrollment | `Kharazmi_Server/models.py:230-239`؛ update در `Kharazmi_Server/routers/finance.py:426-442` |
| رسید پرداخت | `transactions.amount`, `target_wallet`, `enrollment_id`, `course_id` | ledger تراکنش؛ مبلغ مثبت برای پرداخت، با سهم‌های teacher/institute در حالت both | `Kharazmi_Server/models.py:250-282`؛ ساخت رسید در `Kharazmi_Server/routers/finance.py:295-395` |
| سهم تفکیکی | `transactions.share_teacher`, `share_institute` | سهم واقعی هر طرف در charge/both | `Kharazmi_Server/models.py:277-282`؛ fallback سهم both در `Kharazmi_Server/financial_calculations.py:367-378` |
| کیف معلم/آموزشگاه | `students.wallet_teacher`, `wallet_institute` | موجودی component؛ مثبت بستانکاری و منفی بدهی legacy | `Kharazmi_Server/models.py:119-150` |
| کیف کل | `students.wallet_balance` | cache برابر جمع دو component، نه منبع مستقل | `Kharazmi_Server/models.py:156-169` |
| قسط | `installments.amount`, `paid_amount`, `is_paid` | پوشش FIFO مبلغ پرداخت؛ `is_paid` فقط با پوشش کامل true می‌شود | `Kharazmi_Server/routers/finance.py:466-527` |

## 2. فرمول canonical بدهی

### 2.1 بدهی کل دانش‌آموز

1. ثبت‌نام‌های دانش‌آموز خوانده می‌شوند و فقط active (`is_deleted=False`) باقی می‌مانند: `Kharazmi_Server/financial_calculations.py:320-324`.
2. اگر حداقل یک enrollment با شهریهٔ مثبت وجود داشته باشد، بدهی از قراردادهای قیمت‌دار می‌آید، نه جمع منفی کیف: `Kharazmi_Server/financial_calculations.py:324-329`.
3. برای هر enrollment: `final_tuition - total_paid` با کف صفر محاسبه می‌شود: `Kharazmi_Server/financial_calculations.py:310-316`.
4. اگر enrollment قیمت‌دار وجود نداشته باشد، fallback legacy جمع منفی‌های `wallet_teacher` و `wallet_institute` است: `Kharazmi_Server/financial_calculations.py:327-329`.

فرمول فشرده:

```text
if priced_active_enrollments:
    total_debt = sum(max(0, discounted_tuition(en) - en.total_paid) for en in active_priced)
else:
    total_debt = max(0, -wallet_teacher) + max(0, -wallet_institute)
```

### 2.2 بدهی یک enrollment و انتساب به طرف‌ها

`calculate_enrollment_debt_breakdown` پرداخت‌ها را ابتدا با `enrollment_id` واقعی و برای legacy با `student_id + course_id` scope می‌کند؛ پرداخت عمومی بدون course/enrollment به کلاس نسبت داده نمی‌شود: `Kharazmi_Server/financial_calculations.py:332-362`.

- `target_wallet=teacher`: کل amount به `paid_teacher`.
- `target_wallet=institute`: کل amount به `paid_institute`.
- `target_wallet=both`: سهم‌های ذخیره‌شده مصرف می‌شوند؛ اگر جمع سهم‌ها با amount نخواند، split نصف/باقی‌مانده انجام می‌شود: `Kharazmi_Server/financial_calculations.py:363-378`.
- اگر ledger و `Enrollment.total_paid` هر دو موجود باشند، مقدار بزرگ‌تر به‌عنوان effective paid استفاده می‌شود و delta legacy به institute می‌رود تا دوباره‌شماری نشود: `Kharazmi_Server/financial_calculations.py:380-391`.
- بدهی کل enrollment برابر `max(0, final_tuition-effective_paid)` است؛ با وجود `session_charge`، بدهی teacher/institute از billed shares منهای paid shares محاسبه می‌شود، و بدون charge کل مانده به institute نسبت داده می‌شود: `Kharazmi_Server/financial_calculations.py:393-415`.

### 2.3 تغییرات یک پرداخت

`POST /finance/pay` payload را از `FinanceSubmitData` می‌گیرد: `Kharazmi_Server/routers/finance.py:224-227` و `Kharazmi_Server/schemas.py:416-426`.

- enrollment صریح validate می‌شود؛ بدون آن، فقط یک enrollment فعال به‌صورت خودکار link می‌شود و چند enrollment فعال خطا می‌دهد: `Kharazmi_Server/routers/finance.py:266-282`.
- برای `both` مبلغ به دو سهم تقسیم یا از دو مقدار صریح گرفته می‌شود: `Kharazmi_Server/routers/finance.py:295-321`.
- receiptهای deposit ساخته می‌شوند: `Kharazmi_Server/routers/finance.py:323-395`.
- component walletها با UPDATE اتمیک زیاد می‌شوند: `Kharazmi_Server/routers/finance.py:408-424`.
- receiptهای link‌شده به enrollment متصل می‌شوند و `total_paid` همان enrollment زیاد می‌شود: `Kharazmi_Server/routers/finance.py:426-442`.
- cache کل wallet پس از refresh از جمع دو component sync می‌شود: `Kharazmi_Server/routers/finance.py:444-453` و `Kharazmi_Server/models.py:156-159`.
- سپس مبلغ باقیمانده به قدیمی‌ترین قسط‌های همان enrollment (برای پرداخت link‌شده) می‌رود و allocation ledger ساخته می‌شود: `Kharazmi_Server/routers/finance.py:455-475,485-527`.

## 3. مسیرهای خروجی سرور تا UI

| خروجی | محاسبهٔ سرور | مصرف Android | نمایش/مصرف محلی |
|---|---|---|---|
| وضعیت فاکتور کلاس | breakdown همان enrollment: total/paid/due/remaining/credit | `GET finance/student_class_status` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ApiInterfaces.kt:57-62` | مبلغ کل و باقیمانده/سهم‌ها در `InvoiceActivity.kt:305-310,350-365`؛ receipt مبلغ ورودی در `InvoiceActivity.kt:529-643` |
| dashboard مالی دانش‌آموز | wallet teacher/institute، total paid per active enrollment، total debt canonical، installments و سه transaction اخیر | interface/model در `ApiInterfaces.kt:117-120` و `AppModels.kt:722-739` | برای انتخاب enrollment قسط در `StudentProfileActivity.kt:1094-1103` مصرف می‌شود؛ summary debt در `InvoiceActivity.kt:1019-1020` از مدل search است، نه این dashboard. |
| portal والد | پاسخ `parent/child_profile` شامل wallet/debt و profile کودک | `ParentPortalActivity.kt:70-81`؛ handler `Kharazmi_Server/routers/parent.py:299` | دریافت و نمایش balance/debt در `ParentPortalActivity.kt:288-298` |
| portal دانش‌آموز | پاسخ `students/my_profile` شامل wallet/debt | declaration در `StudentPortalActivity.kt:41-42`؛ handler `Kharazmi_Server/routers/students.py:559` | دریافت و نمایش balance/debt در `StudentPortalActivity.kt:199-209` |
| full profile | walletها، total debt، wallet_total، total_paid_institute و `teachers_financial` per enrollment | `NewInvoiceApi.getFullStudentProfile` در `ApiInterfaces.kt:54-55`؛ مدل‌ها `AppModels.kt:465-513` | فراخوانی در `EditStudentActivity.kt:155-198` و `StudentProfileActivity.kt:335,501-527`؛ مبلغ بدهی برای فیش در `StudentProfileActivity.kt:439`. |
| student statement | total_paid_institute، total_debt_institute، teacher details، timeline و payment link | `ReportNewApi.getStudentStatement` در `ReportActivity.kt:136-139`؛ مدل `ReportActivity.kt:68-90` | summary/statement در `ReportActivity.kt:450-530` |
| کلاس | جمع breakdown همه enrollmentهای active کلاس؛ `total_paid` teacher+institute | `ClassApi`/مدل کلاس در screen docs و `ClassDetailActivity.kt:34-42` | جدول/CSV کلاس در `ClassDetailActivity.kt:260-285` |
| KPI امروز | `calculate_institute_cash_collected` برای وصولی نقدی آموزشگاه؛ جدا از بدهی قرارداد | تابع در `Kharazmi_Server/financial_calculations.py:114` و مصرف در `Kharazmi_Server/routers/dashboard.py:76-85`؛ declaration `ApiInterfaces.kt:152-154` و مدل `AppModels.kt:902-909` | دریافت در `AdminDashboardActivity.kt:310-321` و bind مبلغ در `AdminDashboardActivity.kt:350-369`. |

## 4. دو مسیر متفاوت با نام‌های مشابه

### 4.1 `total_debt`

- `finance/student/{student_id}/dashboard` از canonical `calculate_student_debt` استفاده می‌کند: `Kharazmi_Server/routers/finance.py:2090-2094` و پاسخ در `2163-2169`.
- full profile نیز همین canonical total را می‌دهد و بدهی legacyِ بدون enrollment را جداگانه در row unassigned نگه می‌دارد: `Kharazmi_Server/routers/admin.py:460-490,506-522,560-568`.
- class detail و گزارش کلاس بدهی هر enrollment را از breakdown جمع می‌زنند: `Kharazmi_Server/routers/classes.py:212-254`.

بنابراین «بدهی کل دانش‌آموز»، «بدهی کلاس» و «بدهی unassigned» قابل جمع‌زدن‌اند فقط وقتی scope آنها رعایت شود؛ wallet منفی نباید به هر کلاس کپی شود.

### 4.2 `total_paid_institute`

full profile صراحتاً سهم institute رسیدهای `both` را هم جمع می‌کند: `Kharazmi_Server/routers/admin.py:524-566`.

اما statement در HEAD فعلی فقط تراکنش‌هایی را با `target_wallet == "institute"` جمع می‌کند و رسیدهای split/both را در این scalar وارد نمی‌کند: `Kharazmi_Server/routers/reports.py:756-764`. این اختلاف به‌عنوان finding ثبت شده و در این فاز fix نشده است؛ تا زمان تصمیم محصول، این دو خروجی هم‌معنای قطعی فرض نشوند.

## 5. خط انتهایی نمایش مبلغ در Android

- ورودی پرداخت در `InvoiceActivity` به `Long` parse و با جداکنندهٔ هزارگان نمایش داده می‌شود: `InvoiceActivity.kt:485-510,529-538`.
- مبلغ status از response `Long` خوانده و با `String.format("%,d", ...)` نمایش داده می‌شود: `InvoiceActivity.kt:305-310`.
- dashboard/portal نیز اعداد را به formatter می‌دهد: `ParentPortalActivity.kt:297-298`.
- Main صفحهٔ هشدار installment مبلغ response را با `formatMoney(Long)` نمایش می‌دهد: `MainActivity.kt:475-483`.

هیچ تقسیم بر 10، تبدیل ریال/تومان، یا rounding در این مسیرهای مشاهده‌شده پیدا نشد. **واحد واقعی ذخیره‌شده در دیتابیس نامشخص است** چون schema/model فقط عدد صحیح را نشان می‌دهد و assertion واحدی در source پیدا نشد.

## 6. موارد نامشخص و محدودیت scan

1. مبلغ‌های `@Url`/export و PDF جریان runtime دارند؛ بدون مقدار URL در caller نمی‌توان lineage یک endpoint منفرد را قطعی کرد: `ReportExporter.kt:24-29,107-137`.
2. مسیرهای legacy که فقط `wallet_*` دارند ممکن است قبل از وجود enrollment قیمت‌دار ساخته شده باشند؛ کد fallback را ثبت کرده ولی تاریخچهٔ ایجاد هر row از static scan معلوم نیست: `financial_calculations.py:319-329`.
3. یکسان بودن واحد پول در database قدیمی، API و label UI از source قابل اثبات نیست؛ «تومان» از resource متن UI/نام‌گذاری برداشت می‌شود، نه از type.
4. این سند منطق موجود را ثبت می‌کند؛ هیچ route، Kotlin، مدل سرور یا دیتابیس در فاز D تغییر نکرده است.
