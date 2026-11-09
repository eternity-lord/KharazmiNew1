# فاز B — تماس‌های Android با سرور

## خروجی اصلی

- CSV کامل declarationهای Retrofit: [`android-api-calls.csv`](android-api-calls.csv)
- تعداد declarationهای استخراج‌شده: **162**
- تعداد زوج یکتای method/path: **151**؛ تکرارها عمدتاً به‌علت تعریف همان route در چند interface/activity هستند.
- شمارش declarationها: GET=80، POST=64، PUT=10، DELETE=8.
- هر ردیف CSV شامل interface/method، method، path، پارامترهای `@Path/@Query/@Header/@Body/@Part/@Url`، request body، response class، فیلدهای data class و type آن‌ها، و `فایل:خط` است.
- `ResponseBody` یا responseهایی که data class محلی ندارند با `نامشخص`/`ResponseBody:binary` علامت‌گذاری شده‌اند؛ حدس جایگزین نشده است.

## روش استخراج

منبع declarationها تمام `*.kt` زیر `KharazmiAdmin/app/src/main/java` و annotationهای Retrofit است. فهرست data classها از همان درخت فایل‌ها خوانده شده و به response type وصل شده است. CSV تولیدشده قابل جست‌وجو است؛ مرجع نهایی هر ردیف همان فایل:خط است.

## base URL و ساخت Retrofit

1. `RetrofitClient.getBaseUrl` مقدار `SERVER_IP` را از SharedPreferences با نام `AppConfig` می‌خواند و در نبود آن `ServerAddress.DEFAULT_ADDRESS` را استفاده می‌کند: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/RetrofitClient.kt:33-47`.
2. آدرس پیش‌فرض و نرمال‌سازی scheme/host/port در `ServerAddress.DEFAULT_ADDRESS` و `ServerAddress.normalize`: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ServerAddress.kt:6-26`.
3. `Retrofit.Builder().baseUrl(baseUrl)` و Gson converter در `RetrofitClient.getInstance`: `RetrofitClient.kt:110-126`.
4. مسیرهای annotation که با `/` شروع می‌شوند (مثل receipt) همان path را به Retrofit می‌دهند؛ تشخیص route کامل در CSV بر اساس متن annotation ثبت شده است: `InvoiceActivity.kt:57-82`.
5. مسیر دانلود عمومی با `@Url` ثابت نیست و از caller می‌آید: `ReportExporter.kt:24-29` و مصرف در `ReportExporter.kt:107-130`.

## تماس‌های غیر-Retrofit

این موارد declaration route جدید نیستند و جدا از CSV Retrofit ثبت شده‌اند:

| مورد | مرجع | رفتار قابل تأیید |
|---|---|---|
| گزارش HTML/PDF سمت کلاینت در حضور | `AttendanceActivity.kt:718-876` | WebView و `PdfDocument` ساخته می‌شود؛ داده از همان state گزارش/صفحه مصرف می‌شود. |
| گزارش PDF سمت کلاینت پروفایل دانش‌آموز | `StudentProfileActivity.kt:865-907` | HTML/PDF و upload عکس؛ `baseUrl` برای عکس در `StudentProfileActivity.kt:344-364`. |
| گزارش PDF/HTML فاکتور | `InvoiceActivity.kt:824-955` | WebView و `PdfDocument`؛ جزئیات رسید پیش از چاپ از `ReceiptDetailsApi` می‌آید (`InvoiceActivity.kt:82` و `InvoiceActivity.kt:824-866`). |
| گزارش WebView گزارش مالی | `ReportActivity.kt:611-631` | URL گزارش با `RetrofitClient.baseUrl()` ساخته و با header بارگذاری می‌شود؛ route/string در `ReportActivity.kt:628-631` است، بنابراین path literal باید از همان سطر خوانده شود. |
| export فایل با URL runtime | `ReportExporter.kt:107-147` | `DownloadApi.downloadFile(@Url url)` و نوشتن `ResponseBody` در فایل external app. |
| exportهای dashboard | `AdminDashboardActivity.kt:149-225` | سه Retrofit streaming call و سپس `FileOutputStream`; routeها در CSV و ذخیره فایل در `AdminDashboardActivity.kt:199-225`. |
| PDF کارنامه | `ExamActivity.kt:390-415` | base URL و `Intent.ACTION_VIEW` برای endpoint گزارش کارنامه. |
| PDF/Excel سمت صفحه کلاس | `ClassDetailActivity.kt:251` و interface همان فایل در `ClassDetailActivity.kt:105-136` | download/export از routeهای class. |
| upload عکس مؤسسه | `InstituteSettingsActivity.kt:24-34,304-318` | Multipart Retrofit و ساخت `MultipartBody.Part`. |
| upload عکس دانش‌آموز/معلم | `StudentProfileActivity.kt:73-83,892-907` | Multipart Retrofit و فایل local. |
| dial/SMS سیستم عامل | `StudentProfileActivity.kt:691`, `ParentContactsActivity.kt:135-146`, `LiveRosterActivity.kt:170`, `PersonListActivity.kt:251`, `TeacherProfileActivity.kt:100` | تماس/پیامک Android؛ route سرور نیست. |

## نامشخص‌های این فاز

- فیلدهای responseهای binary/HTML و `@Url` از خود declaration نوع JSON ندارند؛ عمداً `نامشخص` باقی مانده‌اند.
- این فاز Android compile اجرا نکرده است.
