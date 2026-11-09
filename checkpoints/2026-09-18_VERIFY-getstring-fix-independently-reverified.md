# CHK 2026-09-18 — VERIFY: بازرسی مستقل فیکس «Unresolved reference: getString» روی برنچ `arena/01a0b352-kharazmiapp`

برنچ: `arena/01a0b352-kharazmiapp` | نوع تسک: **بازنمرایی مستقل** — فیکس getString (کامیت `3ff738e` از
`arena/01a0aac2-kharazmiapp`) با `cherry-pick` به این برنچ آمده (`eb4ea0d`) و این فایل، اثبات‌های مستقل
روی همان درخت است. صفر تغییر کد در این مرحله (فقط این چک‌پوینت اضافه شد).

---

## ۱) وضعیت برنچ‌ها (ثبت اولیه)

- این سشن Arena روی `arena/01a0b352-kharazmiapp` قفل است؛ برنچ‌های دیگر قابل push نیستند.
- تیک ریموت `arena/01a0aac2-kharazmiapp` در زمان کار = `3ff738e` (آخرین آپدیت؛ `main` قدیمی‌تر است).
- درخت `arena/01a0b352-kharazmiapp` **بیت‌به‌بیت یکسان** با تیک `01a0aac2`:
  `git diff --stat origin/arena/01a0aac2-kharazmiapp HEAD` → خالی.
- ثبت قبل از هر کاری: `git status --short` → خالی | `git log -1 --oneline` → `049c085` | `git diff --stat` → خالی.

## ۲) خطای ورودی (تکرار تسک)

`Unresolved reference 'getString'` در `compileDebugKotlin` — ۲۱ فایل اعلام‌شده کاربر:
`CachedApiCall, CalendarActivity, ClassDetailActivity, ClassSetupActivity, CommunicationHistory, CrmLeadsActivity,
DeletionRequestsActivity, HomeworkActivity, InvoiceActivity, LiveClassesActivity, LiveRosterActivity,
ParentPortalActivity, PendingClassesActivity, PersonListActivity, ReportExporter, RetrofitClient,
SessionHistoryActivity, SmsActivity, TeacherCredentialsActivity, TeacherDashboardActivity, TeacherProfileActivity`.

## ۳) اسکنر مستقل (بازتولیدشدنی: `/home/user/kt_gs_scan.py`)

- ماسک درست رشته/کاراکتر/کامنت (offset-preserving)، شناسایی `class|object` با بازه‌ی کوردل‌ها، زنجیره‌ی
  `inner`، و حل گراف super-class در کل پروژه (مثلاً `BaseActivity → AppCompatActivity`) با fixed-point.
- bare `getString(` فقط در scope‌ای که receiver ضمنی Context دارد معتبر است؛ `object`، adapter غیر-inner،
  nested class و top-level فاقد receiver ضمنی Context هستند ⇒ خطادار.

### قبل از فیکس (درخت `049c085`)
| شاخص | مقدار |
|---|---|
| فایل‌های Kotlin | ۸۳ (main+test) |
| فراخوانی‌های bare کل پروژه | ۱۲۸۳ |
| **سایت‌های خطادار** | **۱۲۶** (اسکنر masked: ۱۲۵ + ۱ سایت داخل string-template که masked می‌شد) |
| فایل‌های خطادار | **۲۱ — دقیقاً همان ۲۱ فایل تسک (۲۱/۲۱)** |

نمونه‌های تسک هم دقیقاً گرفته شد: `CachedApiCall.kt:28-31 و 74`، `CalendarActivity.kt:326-333 و 358-360`.
تفاوت ۱۲۶/۱۲۵ توضیح دارد: `ReportExporter.kt:88` داخل `` `${getString(R.string.rexp_footer)}` `` (string-template)
است؛ ماسک‌کننده‌های معمول این را نمی‌بینند، اسکنر خطا اما کامپایلر می‌بیند.

### بعد از فیکس (درخت `eb4ea0d`)
| شاخص | مقدار |
|---|---|
| **سایت‌های خطادار (masked)** | **۰** |
| **سایت‌های خطادار (شامل string-template)** | **۰** |
| سایت‌های bare باقی‌مانده (همه معتبر) | ۱۱۵۸ masked + ۴۸ داخل template — همه در scope خودِ Activityها |

## ۴) بازبینی جفت‌خطی diff (`049c085 → eb4ea0d`)

- ۱۱۸ خط `-` / ۱۱۸ خط `+` = جفت‌های یک‌به‌یک (zero leftover).
- **۱۱۶ جفت:** خط جدید = خط قدیم **کم** پیشوند receiver؛ یعنی تنها تغییر، افزودن receiver است —
  صفر تغییر در آرگومان‌ها، ترتیب، شرط‌ها، `String.format` و متن‌ها.
- **۲ جفت ساختاری (اعلام‌شده در تسک):**
  - `fun getOfflineTimeString(timestamp: Long)` → `fun getOfflineTimeString(context: Context, timestamp: Long)`
  - caller: `getOfflineTimeString(timestamp)` → `getOfflineTimeString(activity, timestamp)`
- هیستوگرام receiverهای افزوده‌شده (۱۲۶ site):
  `holder.itemView.context` ×۱۱۲ | `context` ×۱۰ | `appContext` ×۲ | `view.context` ×۱ | `activity` ×۱

## ۵) اثبات in-scope بودن receiverهای جدید

- ۱۱۲ سایت `holder.`: سمت چپ همان خط از قبل `holder.` را refer می‌کند (مثلاً `holder.schedule.text = ...`)
  ⇒ scopeی `holder` قبلاً در همان کد کامپایل‌می‌شده بود.
- `context` در `ReportExporter`: پارامتر `printPdfReport(context: Context, ...)` و `exportToExcel(context: Context, ...)` ✓
- `context`/`appContext` در `RetrofitClient`: پارامتر `warnIfInsecure`/`getBaseUrl`/`buildClient` ✓
- `activity` در `CachedApiCall.showOfflineBanner`: پارامتر موجود ✓
- `view` در `LiveRosterAdapter.call(view: View, phone: String)`: پارامتر موجود ✓
- **هیچ** متد جعلی `getString`، هیچ extension و هیچ Context سراسری/Application جدید افزوده نشده.

## ۶) callerهای `getOfflineTimeString` (کل پروژه)

فقط یک caller داخلی: `CachedApiCall.showOfflineBanner` (خط ۷۳) که `activity` پاس می‌دهد.
مصرف‌کننده‌ی خارجی نیست ⇒ تغییر signature شکستی نساخته. رفتار cache/زمان/banner/متن‌ها دست‌نخورده.

## ۷) کلیدهای `lrost_*` (قید صریح تسک) — همه از context ویو

`lrost_late/present` (136) | `lrost_excused/absent` (140) | `lrost_unknown` (144) |
`lrost_st_phone`/`lrost_par_phone`/`lrost_unset` (149-150) | `lrost_no_phone` (173، داخل `call(view, ...)` با `view.context`) ✓

## ۸) خطاهای زنجیره‌ای `show`

- اسکن `\.show()` روی ۲۱ فایل: همه‌ی receiverها = `Toast.makeText(...)`،
  `AlertDialog.Builder(...).set...Button(...).show()` و `dialog.show()` از `builder.create()`.
  صفر `show` روی receiver ناشناخته ⇒ **۰ site باقی‌مانده**؛ خطاهای `show` قبل از فیکس صرفاً پیامد
  error-type شدن `Toast.makeText(ctx, getString(...), ...)` بودند و با رفع getString خودبه‌خود حل شدند.

## ۹) محافظت‌ها (حجم‌سنجی scope)

| بررسی | نتیجه |
|---|---|
| `git diff --name-status 049c085..eb4ea0d` | فقط ۲۱ فایل `.kt` + ۱ فایل چک‌پوینت `.md` |
| فایل Python / `Kharazmi_Server` / endpoint / API | **صفر تغییر** |
| `res/`، layout فاز ۱/۲، `strings.xml`، `AndroidManifest` | **صفر تغییر** |
| multiset کلیدهای `R.string/R.id/R.layout/R.drawable/R.color/R.dimen/R.array` هر ۷۴ فایل main، قبل/بعد | **کاملاً یکسان** — هیچ key حذف/rename/تغییر نشده |
| توازن `{}`/`()`/`[]` (روی متن ماسک‌خورده، ماسک رشته/کامنت) | **۰ فایل نامتوازن** در ۸۳ فایل |
| ۶ فایل با adapter داخلی `inner class` (ClassManagement, ParentContacts, TransactionManage, AuditTrail, Dunning, AdminDashboard) | دست‌نخورده (receiver ضمنی `this@Activity` دارند؛ در فهرست خطای کاربر هم نبودند) |
| ۴۸ site bare داخل string-templateهای Activityها (AdminDashboard/Attendance/ClassSetup/Dunning/Invoice/TeacherRegister) | همه `BARE-in-context` — معتبر، دست‌نخورده |

## ۱۰) compile/test/lint — واقعیت سندباکس (بدون جعل نتیجه)

| ابزار/مورد | وضعیت واقعی |
|---|---|
| `bash ./gradlew :app:compileDebugKotlin --stacktrace` | اجرا شد → `ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH.` |
| `assembleDebug` / `test` / `lint` | همان ریشه (JDK نیست؛ اجرا بی‌معناست) |
| شبکه | `services.gradle.org`/`dl.google.com`/`repo.maven.apache.org`/`repo1.maven.org` → `000` (بلاک)؛ فقط github/pypi باز ⇒ حتی با JDK هم Gradle نتوانسته AGP/وابستگی‌ها را بکشد |
| نتیجه | **بیلد واقعی در این سندباکس ممکن نیست.** تمام تأییدهای بالا استاتیک و بازتولیدپذیرند؛ داور نهایی بیلد کاربر است. |

## ۱۱) بازتولید

```bash
python3 /home/user/kt_gs_scan.py KharazmiAdmin /tmp/gs.json   # 0 error sites روی HEAD فعلی
git diff --stat 049c085..eb4ea0d                               # ۲۱ فایل .kt + ۱ md
cd KharazmiAdmin && bash ./gradlew :app:compileDebugKotlin    # در ماشین کاربر
```

پایان: درخت `arena/01a0b352-kharazmiapp` = درخت `arena/01a0aac2-kharazmiapp` (آخرین) + این چک‌پوینت.
