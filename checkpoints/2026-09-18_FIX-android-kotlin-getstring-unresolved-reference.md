# CHK 2026-09-18 — FIX: خطای compile اندروید (`Unresolved reference: getString` و زنجیره‌ی `.show()`)

برنچ: `arena/01a0aac2-kharazmiapp` | نوع تسک: **فقط receiver کاتلین (Context)** — صفر تغییر business logic، صفر تغییر API/مدل/permission/navigation، صفر تغییر Python/backend، صفر تغییر XML/UI.

---

## ۱) خطای گزارش‌شده‌ی کاربر (ورودی تسک)

```
Unresolved reference: getString     (و در پی آن: Unresolved reference: show)
```

فایل‌های اعلامی کاربر (۲۱ فایل): `CachedApiCall`, `CalendarActivity`, `ClassDetailActivity`, `ClassSetupActivity`,
`CommunicationHistory`, `CrmLeadsActivity`, `DeletionRequestsActivity`, `HomeworkActivity`, `InvoiceActivity`,
`LiveClassesActivity`, `LiveRosterActivity`, `ParentPortalActivity`, `PendingClassesActivity`, `PersonListActivity`,
`ReportExporter`, `RetrofitClient`, `SessionHistoryActivity`, `SmsActivity`, `TeacherCredentialsActivity`,
`TeacherDashboardActivity`, `TeacherProfileActivity`.

## ۲) ریشه‌ی خطا (تأیید‌شده با تحلیل استاتیک دقیق)

`getString(...)` یک متد **`Context`** است. هر جا فراخوانی بدون receiver و در کلاسی باشد که هیچ نسخه‌ی
`Context` در زنجیره‌ی receiver‌های ضمنی‌اش نباشد ⇒ `Unresolved reference: getString`. سه زیرحالت واقعی:

| حالت | چرا خطا می‌دهد | تعداد site |
|---|---|---|
| `object` مستقل (`CachedApiCall` / `ReportExporter` / `RetrofitClient`) | `object` هیچ Context ندارد | ۱۳ |
| adapter **غیر-`inner`** (top-level یا nested بدون `inner`) | nested class در کاتلین receiver بیرونی **ندارد** | ۱۱۳ |
| `class VH(view: View) : RecyclerView.ViewHolder(view)` | ViewHolder متدی به نام `getString` ندارد | ۰ (هیچ site‌ای نبود) |

در مقابل، فراخوانی bare در دو حالت **کاملاً معتبر** است و باید دست‌نخورده بماند:

- داخل متدهای خود Activity/Fragment (`AppCompatActivity → ContextWrapper → Context`) — ۱۱۷۳ مورد؛
- داخل **`inner class`** تعریف‌شده در Activity (مثل `inner class ClassAdapter`) — ۳۴ مورد، که receiver ضمنی `this@Activity` را دارد.

**شاهد قاطع درستی این تحلیل:** اسکنر دقیق (`/tmp/gs_scan3.py`) برای کل ۷۸ فایل Kotlin پروژه، ۲۷ فایل با site خطادار پیدا کرد —
و آن ۲۱ فایلی که دقیقاً تطبیق دارند با فهرست خطای بیلد کاربر (`۲۱ از ۲۱`)، و ۶ فایل باقی‌مانده (`ClassManagementActivity`,
`ParentContactsActivity`, `TransactionManageActivity`, `AuditTrailActivity`, `DunningActivity`, `AdminDashboardActivity`)
**همه** adapterشان `inner class` است و در فهرست خطای کاربر هم نیستند ⇒ **دست‌نخورده** ماندند
(هیچ لاگ بیلدی هم آن‌ها را خطادار اعلام نکرده؛ تغییرشان فقط noise در diff بود).

## ۳) روش fix به‌ازای هر دسته (بدون Context سراسری، بدون متد جعلی، بدون تغییر رفتار)

| دسته | روش | تعداد |
|---|---|---|
| adapterها | `holder.itemView.context.getString(...)` (holder پارامتر `onBindViewHolder` است) | ۱۱۲ |
| `LiveRosterAdapter.call(view: View, phone: String)` | `view.context.getString(...)` (طبق قید صریح کاربر: کلیدهای `lrost_*` از context ویو) | ۱ |
| `ReportExporter` (پارامتری Context دارد) | `context.getString(...)` | ۴ |
| `RetrofitClient.warnIfInsecure/getBaseUrl` | `context.getString(...)` ← پارامتر همان تابع | ۲ |
| `RetrofitClient` اینترسپتور | `appContext.getString(...)` ← پارامتر `buildClient(appContext)` | ۲ |
| `CachedApiCall.getOfflineTimeString` | **تغییر signature**: `getOfflineTimeString(context: Context, timestamp: Long)` + `context.getString(...)` | ۴ |
| `CachedApiCall.showOfflineBanner` | `activity.getString(...)` + پاس‌دادن `activity` به `getOfflineTimeString(activity, timestamp)` | ۲ |

`getOfflineTimeString` تنها caller داخلی دارد (`showOfflineBanner`) ⇒ بدون شکستن مصرف‌کننده‌ی خارجی.
هیچ `getString` جعلی/extension/global Context اضافه نشد؛ رفتار کش، بنر آفلاین، متن‌ها و ترتیب نمایش **عیناً** ثابت است.

## ۴) آمار قبل/بعد (اسکنر بازتولیدپذیر روی HEAD و درخت فعلی)

| دسته | قبل | بعد |
|---|---|---|
| خطادار — adapter بدون Context | ۱۱۳ | **۰** |
| خطادار — object بدون Context | ۱۳ | **۰** |
| معتبر — `inner class` داخل Contextدار | ۳۴ | ۳۴ (بدون تغییر) |
| معتبر — متدهای خود کلاس Contextدار | ۱۱۷۳ | ۱۱۷۳ (بدون تغییر) |
| مجموع فراخوانی‌های bare | ۱۳۳۳ | ۱۲۰۷ |

خطادار: **۱۲۶ → ۰** | فایل‌های تغییریافته: **۲۱** | site‌های جانشین‌شده: **۱۲۶** (لاگ: `/tmp/getstring_final_verify.log`)

## ۵) اثبات کمینه‌بودن تغییر (diff دقیقاً همان چیزی است که باید باشد)

- بازبینی جفت‌خطی diff: **۱۱۶ از ۱۱۸** خط تغییرکرده، تنها «افزودن receiver پیش از `getString`» است
  (`strip_ctx(new) == old` ⇒ صفر تغییر در آرگومان‌ها، ترتیب، شرط‌ها، `String.format` و متن‌ها).
- ۲ خط باقی‌مانده همان تغییر ساختاری اعلام‌شده‌ی `CachedApiCall` است (signature + caller).
- multiset ارجاع‌های `R.string.*` برای هر ۲۱ فایل قبل/بعد **یکسان** ⇒ صفر تغییر کلید/متن رشته (فایل `strings.xml` هم اصلاً تغییر نکرد).
- توازن `{} () []` هر ۷۸ فایل Kotlin (با ماسک درست رشته/کامنت): **۰ فایل نامتوازن** ⇒ بدون نشانه‌ی parse error.

## ۶) بازبینی خطای زنجیره‌ای `show`

خطای `Unresolved reference: show` صرفاً **پیامد** getString ناموجود بود: وقتی `getString(...)` خطا دارد،
عبارت `Toast.makeText(ctx, getString(...), …)` هم error-typed می‌شود و `.show()` روی آن resolve نمی‌شود.
پس از fix، همه‌ی زنجیره‌ها معتبرند: گیرنده‌های `.show()` در ۲۱ فایل = `Toast.makeText`/`AlertDialog.Builder(...).show()` (۱۲۰ مورد)
و `dialog.show()` که `dialog` از `builder.create()` می‌آید (۱۱ مورد) ⇒ **صفر site نیازمند تغییر اضافه**
(هیچ `show` مستقلی خارج از این دو الگو وجود ندارد).

## ۷) تست/بیلد — اجرا در این سندباکس **ممکن نیست** (بدون هیچ ادعای بیلد سبز)

| بررسی | نتیجه‌ی واقعی |
|---|---|
| `bash ./gradlew :app:compileDebugKotlin --stacktrace` | `ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH.` (exit=1) |
| `:app:assembleDebug` / `:app:test` / `:app:lint` | همان خطای JAVA_HOME (اجرا شد؛ هیچ‌کدام کامپایل نشد) |
| `java` در PATH / `JAVA_HOME` / `ANDROID_HOME` / `ANDROID_SDK_ROOT` / `/usr/lib/jvm` | هر پنج: موجود نیست |
| `gradlew` | mode `644` (غیراجرایی — پیش‌موجود؛ `chmod` انجام نشد) |
| شبکه به `services.gradle.org` / `dl.google.com` / `repo.maven.apache.org` | `000` (بدون دسترسی) |

⇒ **بیلد واقعی و تأیید نهایی، دست کاربر است.** تمام تأییدهای بالا استاتیک و بازتولیدپذیرند (اسکنرها در `/tmp`).

## ۸) دامنه (proof)

```
$ git status --short        → (پیش از تغییر) خالی ؛ (بعد) فقط ۲۱ فایل .kt
$ git diff --name-only | grep -v '\.kt$'      → هیچ (صفر فایل غیر-Kotlin)
$ git diff --name-only | grep -Ei '\.py$|Kharazmi_Server|\.xml$'  → صفر Python/backend/XML
```

| مورد | وضعیت |
|---|---|
| Python/backend/API/مدل/permission/navigation | **صفر تغییر** (هیچ فایلی خارج از `KharazmiAdmin/.../*.kt` ویرایش نشد) |
| `res/` + UI فاز ۱ و فاز ۲ + اندرویدمنیفست + `strings.xml` | **صفر تغییر** |
| منطق ۷ صفحه‌ی فاز ۲ (مالی/شهریه/اقساط/تراکنش/پروفایل) | **صفر تغییر** |
| فایل‌های UI/منابع | عمداً دست‌نخورده (شکست در لایه‌ی Kotlin بود، نه منابع) |

## ۹) تکرار بازرسي

```bash
python3 /tmp/kt_balance.py         # توازن ۷۸ فایل Kotlin → همه متوازن
python3 /tmp/gs_scan3.py           # توزیع bare getString → صفر «خطادار»
python3 /tmp/gs_final_verify.py    # جدول قبل/بعد (HEAD vs working tree) → خطادار ۱۲۶ → ۰
```

پس از این چک‌پوینت: commit + push روی `arena/01a0aac2-kharazmiapp`. اگر بیلد کاربر خطای بعدی داد، ورودی بعدی همین است.
