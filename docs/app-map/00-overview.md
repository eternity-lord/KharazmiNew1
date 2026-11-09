# نقشهٔ کامل و قابل‌ردگیری KharazmiApp

**تاریخ snapshot:** 2026-09-28 (Asia/Tehran)  
**branch:** [`arena/01a0c9b8-kharazmiapp`](https://github.com/eternity-lord/KharazmiApp/tree/arena/01a0c9b8-kharazmiapp)  
**دامنه:** فقط مستندسازی و اسکریپت extractor؛ هیچ خط Kotlin، کد server موجود، تست موجود یا manual test list تغییر نکرده است.

## وضعیت تحویل فازها

| فاز | خروجی | شمارش/نتیجه | commit |
|---|---|---:|---|
| A | `server-routes.csv` + `server-routes-extracted.csv` + extractor | 221 route؛ روش و limitation در `phase-a-server.md` | [`1dc7f05`](https://github.com/eternity-lord/KharazmiApp/commit/1dc7f051cffa71b78c21d9f4a979e52588f17466) |
| A correction | حفظ prefixهای nested router و بازتولید CSV | `/audit/suspicious_patterns` و `/dashboard/kpis` به‌صورت full path ثبت می‌شوند | [`47973bb`](https://github.com/eternity-lord/KharazmiApp/commit/47973bb) |
| B | `android-api-calls.csv` + `phase-b-android.md` | 162 declaration؛ 151 method/path یکتا؛ GET=80، POST=64، PUT=10، DELETE=8 | [`659f224`](https://github.com/eternity-lord/KharazmiApp/commit/659f224d0513e612494604e79a00e9c76acda96a) |
| C | 51 screen doc + `navigation.md` | 51 Activity؛ 180 edge صریح Intent | [`5bf7a58`](https://github.com/eternity-lord/KharazmiApp/commit/5bf7a58490b974c44138e9d37b5cd47efd9cf623) |
| D | `mismatches.md`, `money-lineage.md`, `findings.md` | ناهماهنگی‌ها، money lineage و finding بدون fix | [`ec8aa87`](https://github.com/eternity-lord/KharazmiApp/commit/ec8aa8706600e913bb608011044878efa13f1b26) |
| E | `flows.md` | 12 flow اصلی با source refs | [`3c9f9cb`](https://github.com/eternity-lord/KharazmiApp/commit/3c9f9cb2352b02b3d103a51eb4f1385d441e396) |
| F | `test-coverage.csv` | 221 route row + 12 flow candidate row؛ تست اجرا نشد | [`2936e80`](https://github.com/eternity-lord/KharazmiApp/commit/2936e80) |

## فهرست اسناد

- روش route و محدودیت: [`phase-a-server.md`](phase-a-server.md)
- inventory کامل route: [`server-routes.csv`](server-routes.csv) و raw output: [`server-routes-extracted.csv`](server-routes-extracted.csv)
- روش و inventory Android: [`phase-b-android.md`](phase-b-android.md)، [`android-api-calls.csv`](android-api-calls.csv)
- روش screen: [`phase-c-screens.md`](phase-c-screens.md)، زیرپوشهٔ [`screens/`](screens/)
- navigation: [`navigation.md`](navigation.md)
- مقایسهٔ server/app و field/body mismatch: [`mismatches.md`](mismatches.md)
- زنجیرهٔ مبلغ تا UI: [`money-lineage.md`](money-lineage.md)
- flowهای اصلی: [`flows.md`](flows.md)
- پوشش تست route/flow: [`test-coverage.csv`](test-coverage.csv)
- findingهای بدون fix: [`findings.md`](findings.md)
- extractor قابل بازتولید: [`Kharazmi_Server/scripts/extract_server_routes.py`](../../Kharazmi_Server/scripts/extract_server_routes.py)

## اعداد نهایی map

| حوزه | مقدار | مرجع قابل بازتولید |
|---|---:|---|
| routeهای server | 221 | سطرهای دادهٔ `server-routes.csv:2-222` |
| declarationهای Retrofit | 162 | سطرهای دادهٔ `android-api-calls.csv:2-163` |
| method/path یکتا در Android | 151 | محاسبهٔ نرمال‌شده در مقایسهٔ فاز D؛ روش در `mismatches.md:5-10` |
| Activityهای مستند | 51 | فایل‌های `docs/app-map/screens/*.md` و شمارش روش در `phase-c-screens.md` |
| edge صریح navigation | 180 | جدول edgeهای `navigation.md` |
| route در server بدون caller Retrofit مستقیم | 72 | جدول کامل `mismatches.md:16-90` |
| caller Retrofit بدون route server | 0 | `mismatches.md:7-12` |
| flowهای اصلی | 12 | `flows.md:9-20` و ردیف‌های `test-coverage.csv:223-234` |
| route rowهای test coverage | 221 | `test-coverage.csv:2-222` |

## ده ناهماهنگی مهم برای پیگیری

این‌ها «مورد پیگیری» هستند، نه ادعای dead code قطعی. علت هر مورد فقط تا جایی نوشته شده که source ثابت می‌کند.

| # | مورد | اثر قابل مشاهده | مرجع دقیق |
|---:|---|---|---|
| 1 | **72 route server بدون declaration مستقیم Retrofit** | ممکن است وب، admin، legacy، runtime URL یا ابزار داخلی باشند؛ از روی static scan حذف‌پذیر نیستند. | فهرست کامل `mismatches.md:16-90` |
| 2 | `GET /finance/invoice/{enrollment_id}` caller ثابت ندارد | Android فاکتور را از `finance/student_class_status` می‌خواند و چاپ را client-side انجام می‌دهد؛ علت نبود caller invoice endpoint نامشخص است. | `InvoiceActivity.kt:305-365,809-960`; handler `Kharazmi_Server/routers/finance.py:2264` |
| 3 | `/students/register` در برابر مسیر فعال `/students/register_and_enroll` | ثبت‌نام Android مسیر همراه enrollment را مصرف می‌کند؛ route legacy caller مستقیم ندارد. | `StudentRegisterActivity.kt:471`; `Kharazmi_Server/routers/students.py:40,83` |
| 4 | routeهای installment مدیریت (`GET /finance/installments`، `PUT/DELETE /finance/installments/{installment_id}`) caller مستقیم ندارند | UI profile create/pay/remind را دارد، اما edit/delete/list admin declaration ثابت پیدا نشد. | `ApiInterfaces.kt:101-115`; `Kharazmi_Server/routers/finance.py:1588,1698,1764` |
| 5 | routeهای live attendance متعدد بدون caller direct | مسیر فعلی Android برای submit/get/update مشخص است؛ `start_live/cancel_live/end_live/live_status` در inventory direct جفت نشده‌اند. | `AttendanceActivity.kt:35-41,249-634`; `Kharazmi_Server/routers/attendance.py:313,369,449,509` |
| 6 | PDF report card با URL runtime | `ExamActivity.kt:406-415` URL می‌سازد، ولی Retrofit declaration ثابت ندارد؛ path نهایی وابسته به runtime است. | `Kharazmi_Server/routers/exams.py:383`; `mismatches.md:85` در نسخهٔ raw scan نامشخص ثبت شده است. |
| 7 | `uploads/{filename}` JSON Retrofit نیست | profile image از URL/file path مصرف می‌شود، نه declaration API؛ مسیر دقیق request از caller ثابت نیست. | `StudentProfileActivity.kt:344-364`; `Kharazmi_Server/main.py:94` |
| 8 | دو تعریف برای `total_paid_institute` | full profile سهم `both` را حساب می‌کند، statement فقط target مستقیم institute را sum می‌کند؛ خروجی‌ها برای receipt split می‌توانند متفاوت شوند. | `Kharazmi_Server/routers/admin.py:524-566`; `Kharazmi_Server/routers/reports.py:756-764`; `findings.md:7` |
| 9 | مدل گزارش `SearchStudentItem` نسبت به پاسخ advanced کوچک‌تر است | ReportActivity فقط فیلدهای پایه را deserialize/مصرف می‌کند؛ InvoiceActivity مدل غنی‌تر دارد. فیلدهای debt در گزارش قابل نمایش مستقیم نیستند. | `ReportActivity.kt:93-100,131-134`; `AppModels.kt:401-420`; `Kharazmi_Server/routers/finance.py:92-117,161-174` |
| 10 | واحد پول عددی از source قطعی نیست | UI label تومان و formatter دارد اما schema/model فقط integer/Long را نشان می‌دهد؛ تبدیل ریال↔تومان پیدا نشد. | `InvoiceActivity.kt:305-310,851-935`; `Kharazmi_Server/models.py:268-282`; `money-lineage.md:92` در scan «نامشخص» ثبت شده است. |

## موارد نامشخص

1. **callerهای dynamic:** `@Url` در `ReportExporter`، URL فایل در profile و PDF report card مقدار runtime دارند؛ static inventory نمی‌تواند یک endpoint منفرد را اثبات کند: `ReportExporter.kt:24-29,107-137`؛ `ExamActivity.kt:406-415`؛ `StudentProfileActivity.kt:344-364`.
2. **علت واقعی 72 route uncalled:** طبقهٔ path/handler ثبت شده، اما source نمی‌گوید route web، legacy، dead یا caller غیر Retrofit است: `mismatches.md:16-90`.
3. **responseهای نامشخص:** routeهایی که `response_model` یا dict literal کامل ندارند در CSV «نامشخص» باقی مانده‌اند؛ نمونهٔ روش و limitation در `phase-a-server.md` و ستون response در `server-routes.csv` است.
4. **واحد پول:** عددهای DB/API/UI قابل دنبال‌کردن هستند ولی واحد ذخیره‌شده و conversion تاریخی از source ثابت نیست: `money-lineage.md:7,105-112`.
5. **تست اجرایی:** `test-coverage.csv` candidate و static reference را ثبت می‌کند؛ در این فاز suite و Android compile اجرا نشده‌اند.

## صحت git و دیتابیس

Snapshot نهایی پس از commit/push فاز F و اصلاح لینک overview:

```text
git branch --show-current
arena/01a0c9b8-kharazmiapp

git diff --stat -- Kharazmi_Server ':!Kharazmi_Server/scripts/extract_server_routes.py' KharazmiAdmin
<خروجی خالی — هر دو محدوده clean هستند>
```

- تغییر مستقل extractor/CSV در [`47973bb`](https://github.com/eternity-lord/KharazmiApp/commit/47973bb7611c361c2da95fa5ca1a43f707cdda3a) commit و push شد.
- D در [`ec8aa87`](https://github.com/eternity-lord/KharazmiApp/commit/ec8aa8706600e913bb608011044878efa13f1b26) و E در [`3c9f9cb`](https://github.com/eternity-lord/KharazmiApp/commit/3c9f9cb2352b02b3d103a51eb4f1385d441e396) commit و push شدند؛ توضیح exclusion برای URL پویا در [`b9a8183`](https://github.com/eternity-lord/KharazmiApp/commit/b9a8183) و lineage دقیق dashboard مالی در [`05796bc`](https://github.com/eternity-lord/KharazmiApp/commit/05796bc) تکمیل شد.
- در این snapshot هیچ تغییر خارج از `docs/app-map/` و extractor مجاز وجود ندارد.
- Android compile **اجرا نشد**.
- probe اختیاری روی دیتابیس اصلی انجام نشد؛ extractor با copy در `/tmp` اجرا شد.
- md5 دیتابیس اصلی، قبل و بعد یکسان است:

```text
baseline: f048f8d118b33c4eaa944490594121d7
after:    f048f8d118b33c4eaa944490594121d7
file: Kharazmi_Server/gaj_db.db
```

`git diff --check` و `git status` پس از تحویل نهایی دوباره اجرا می‌شوند؛ نتیجهٔ آن‌ها در گزارش پایانی turn ثبت خواهد شد.
