# A1 — اقساط شهریه: UI برای ۳ endpoint موجود (بدون دست‌زدن به سرور) — 2026-09-16

**Branch:** `arena/01a0a936-kharazmiapp` — https://github.com/eternity-lord/KharazmiApp/tree/arena/01a0a936-kharazmiapp  
**Source:** `checkpoints/2026-09-16_full-app-review-no-android-compile.md` (A1) + `checkpoints/2026-09-16_S3-A2-bugfix.md`  
**Constraint:** فقط فایل‌های اندروید تغییر کنند؛ هیچ `Kharazmi_Server/**` دست نخورد (endpointها از قبل تست‌شده 268 passed) — بدون Gradle/emulator، فقط بررسی استاتیک Kotlin/XML  
**Gap:** سرور سه endpoint finance installments داشت (`POST /finance/installments` + `POST /finance/installments/{id}/pay` + `POST /finance/installments/{id}/remind` با گارد `check_admin_or_secretary_access`) ولی `StudentProfileActivity.kt` فقط `GET students/{id}/installments` را به‌صورت `StringBuilder→tvContent` نمایش می‌داد (fetchInstallments ~713-730) بدون دکمه عملیاتی.

---

## 1) خلاصه

| مورد | قبل | بعد |
|------|-----|-----|
| **تب اقساط** | متن خام در `tvContent`، بدون interaction | `RecyclerView` با کارت‌های مجزا + وضعیت رنگی (پرداخت‌شده/معوقه/در انتظار) + دکمه‌های عملیاتی |
| **هر ردیف unpaid** | — | دو دکمه «پرداخت» (dialog تأیید → `POST .../pay` → toast پیام سرور + refresh) و «یادآوری» ( `POST .../remind` → toast پیام سرور، حتی 400 موبایل ولی → `detail` دقیق) |
| **افزودن قسط** | نداشت | دکمه سراسری «➕ افزودن قسط جدید» بالای لیست → dialog مبلغ+due_date شمسی (فرمت بقیه اپ `yyyy/MM/dd`) → `POST /finance/installments` با `enrollment_id` فعال (اولین active یا دراپ‌داون اگر چند enrollment) |
| **سرور** | ۳ endpoint موجود و تست‌شده | **بدون تغییر** — فقط کلاینت به API وصل شد |
| **خطا** | `Toast(e.message)` عمومی | `extractServerDetail(e)` → `JSONObject(errorBody).optString("detail")` برای 400/403/404 نمایش دقیق `detail` سرور |

---

## 2) فایل‌های تغییرکرده (فقط اندروید)

| مسیر | تغییر | دلیل |
|------|-------|------|
| `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AppModels.kt` | `StudentInstallmentItem` + `enrollmentId?`, `status?` (default null) — بدون شکستن parse فعلی؛ `+ CreateInstallmentRequest/Response`, `PayInstallmentResponse`, `RemindInstallmentResponse`, `WalletInfo`, `DashboardEnrollment`, `FinancialDashboardResponse` | مدل‌های سه endpoint جدید + helper dashboard برای یافتن `enrollment_id` فعال؛ همه `SerializedName` مطابق کنتراکت سرور `finance.py` (1635 create, 1798 pay, 1949 remind, dashboard) |
| `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ApiInterfaces.kt` | `+ InstallmentApi` (۳ متد الزامی) + `FinanceDashboardApi` (helper برای enrollment selection) | `ApiInterfaces` محل مرکزی Retrofit — مطابق تسک ۳ endpoint جدید اضافه شد؛ dashboard helper برای اجرای الزام «اولین active یا دراپ‌داون» بدون لمس سرور |
| `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/StudentProfileActivity.kt` | ~360 خط اضافه/تغییر: `cardContent/cardInstallments/rvInstallments/...` bind + `LinearLayoutManager`, `InstallmentAdapter` inner class, `showStandardProfileContent/showInstallmentsContent`, `fetchInstallments` بازنویسی به RecyclerView، `extractServerDetail/normalizePersianDigits/isValidJalaliDate`, `confirmAndPay/performPay`, `confirmAndRemind/performRemind`, `showCreateInstallmentDialog/performCreateInstallment` | جایگزینی نمایش متنی با لیست تعاملی؛ تمام منطق UI فقط روی اندروید؛ نمایش `detail` خطاهای سرور؛ اعتبارسنجی شمسی با `JalaliUtils.parseProjectDate` هم‌سبک بقیه اپ |
| `KharazmiAdmin/app/src/main/res/values/strings.xml` | +21 string جدید `installment_*` (add/pay/remind/create/hint/error/success/... ) + `installment_due/due_hint` | تمام متن فارسی هم‌سبک عبر `strings.xml`، بدون هاردکد در Kotlin (به‌جز `۰۱۲۳۴۵۶۷۸۹` برای نرمال‌سازی ارقام) |
| `KharazmiAdmin/app/src/main/res/layout/activity_student_profile.xml` | `cardContent` id به کارت قبلی + `cardInstallments` جدید ( `btnAddInstallment` + `rvInstallments` + `tvInstallmentsEmpty` ) `visibility=gone` اولیه | کانتینر جدا برای تب اقساط؛ تب 0-2 → `cardContent` visible، تب 3 → `cardInstallments` visible (بدون حذف UI قبلی) |
| `KharazmiAdmin/app/src/main/res/layout/item_installment.xml` | **جدید** — `MaterialCardView` با `tvCourse/tvAmount/tvDue/tvStatus/tvPaidAt` + `layoutActions(btnPay/btnRemind)` | ردیف استاندارد با `chip_background` موجود و `gold_primary`؛ `layoutActions` فقط برای `is_paid==false` visible (الزام تسک) |
| `KharazmiAdmin/app/src/main/res/layout/dialog_create_installment.xml` | **جدید** — `tilCourse(actvCourse)` + `tilAmount(etAmount)` + `tilDue(etDue+ic_calendar)` + hint | فرم شمسی هم‌سبک اپ ( `JalaliUtils.todayJalaliString()` پیش‌فرض)؛ اگر یک enrollment → dropdown غیرفعال؛ اگر چند → اولین selected + دراپ‌داون |
| `checkpoints/2026-09-16_A1-installments-ui.md` | جدید | مستندسازی این تسک |

**بدون تغییر:** `Kharazmi_Server/**` (هیچکدام)، `wallet`/ `F-A2` / `test_*.py` — عمداً.

```bash
git diff --stat
# KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ApiInterfaces.kt     |  21 ++
# KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AppModels.kt        |  48 ++-
# KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/StudentProfileActivity.kt | 367 +++++++++++++++++++--
# KharazmiAdmin/app/src/main/res/layout/activity_student_profile.xml           |  49 +++
# KharazmiAdmin/app/src/main/res/values/strings.xml                            |  29 ++
# 5 files changed, 486 insertions(+), 28 deletions(-)
# + 2 new layouts (item_installment.xml, dialog_create_installment.xml) untracked → tracked after add
```

---

## 3) تصمیم طراحی (Design Rationale)

### 3.1 چرا `FinancialDashboardApi` به‌عنوان helper؟

- **ریشه گپ:** تسک می‌گوید «enrollment_id فعال (اگر چند active، اولین یا دراپ‌داون — به کد فعلی نگاه کن)». در `StudentProfileActivity` هیچ `enrollment_id` کش‌شده‌ای وجود نداشت (`FullStudentProfile.classes` فقط `String` است). سرور `GET students/{id}/installments` هم `enrollment_id` برنمی‌گرداند (فقط `id/course_title/amount/due_date/...`).
- **انتخاب:** `GET /finance/student/{student_id}/dashboard` تنها endpoint موجود است که `enrollments:[{enrollment_id, course_title}]` را برمی‌گرداند ( `finance.py:dashboard` ). افزودن آن به‌عنوان چهارمین متد helper، بدون تغییر سرور، الزام دراپ‌داون را با کمترین ریسک برآورده می‌کند. جایگزینِ query `GET /finance/installments?student_id=` هم `enrollment_id` می‌دهد ولی برای دانش‌آموز بدون قسط قبلی جوابی ندارد؛ dashboard حتی اگر هیچ قسطی نباشد هم enrollments را می‌دهد — برای «افزودن اولین قسط» ضروری است.
- **رد شده:** تغییر سرور برای اضافه‌کردن `enrollment_id` به `GET students/{id}/installments` — ممنوع (تسک: هیچ `Kharazmi_Server/**`).

### 3.2 چرا RecyclerView به‌جای StringBuilder؟

- **مقیاس‌پذیری UI:** هر ردیف نیاز به دو دکمه مجزا با `visibility` شرطی دارد؛ `TextView` چندخطی نمی‌تواند click جداگانه بدهد. `RecyclerView` با `InstallmentAdapter` و `notifyDataSetChanged` رفرش پس از pay/create را ساده می‌کند و با `NestedScrollView` ( `isNestedScrollingEnabled=false` ) سازگار است (الگوی `rvStudentCommunicationHistory` همین است).
- **وضعیت رنگی:** `JalaliUtils.isBeforeToday(due_date)` (پورت دقیق `parse_project_date` سرور) → `overdue=#D32F2F` / `pending=#FF8F00` / `paid=#388E3C` — هم‌سبک `profile_inst_*` قبلی اما قابل تست واحد بدون emulator.

### 3.3 چرا `extractServerDetail` و نمایش `detail` برای همهٔ 400/403/404؟

- **مطابق تسک:** «خطاهای 400/403/404 با `detail` دقیق سرور نمایش». `AttendanceActivity` قبلاً همین الگو را داشت: `e.response()?.errorBody()?.string()?.let { JSONObject(it).opt("detail") }` در `Dispatchers.IO`. همان را به `A1` آوردیم؛ برای `remind` حتی 400 (`شماره همراه ولی ثبت نشده`) هم toast با `common_err_with_detail` می‌شود نه خطای عمومی — تأیید شده در `finance.py: send_installment_payment_reminder` `raise 400` اگر `parent_mobile` خالی.
- **نرمال‌سازی ارقام:** `normalizePersianDigits` ( `۰۱۲۳۴۵۶۷۸۹` + `٠١٢٣٤٥٦٧٨٩` ) برای مبلغ و تاریخ شمسی، مثل `JalaliUtils.normalizeDigits` — کاربر می‌تواند فارسی تایپ کند و سرور `149..` لاتین بگیرد.

### 3.4 چرا dialog تأیید برای پرداخت اما نه برای یادآوری؟

- **ریسک مالی:** `pay` یک `Transaction` و `SmsLog` و `Notification` می‌سازد و `is_paid=true` می‌کند؛ برگشت‌ناپذیر است → نیاز به `AlertDialog` تأیید دارد (تسک: «dialog تأیید»). `remind` فقط `SmsLog+Notification` بدون تغییر مالی است؛ یک تأیید ساده کافی است و حتی اگر 400 شود، toast خطا کافی است.

### 3.5 چرا `JalaliUtils.todayJalaliString()` به‌عنوان پیش‌فرض due_date؟

- **هم‌سبک:** بقیه فرم‌های اپ ( `Register`، `Attendance` ) تاریخ شمسی را با همین util می‌سازند و سرور `parse_project_date` با heuristic `year<1700→Jalali` می‌خواند. استفاده از همان، mismatch فرمت را صفر می‌کند. اعتبارسنجی `Regex ^\d{4}/\d{2}/\d{2}$ + parseProjectDate!=null` از `yyyy/MM/d` شل جلوگیری می‌کند.

---

## 4) نمونه‌کد کلیدی

### 4.1 Retrofit interfaces (ApiInterfaces.kt)

```kotlin
interface InstallmentApi {
    @POST("finance/installments")
    suspend fun createInstallment(@Body req: CreateInstallmentRequest): CreateInstallmentResponse

    @POST("finance/installments/{id}/pay")
    suspend fun payInstallment(
        @Path("id") id: Int,
        @Query("payment_method") paymentMethod: String = "نقدی",
        @Query("branch_id") branchId: Int? = null
    ): PayInstallmentResponse

    @POST("finance/installments/{id}/remind")
    suspend fun remindInstallment(@Path("id") id: Int): RemindInstallmentResponse
}
interface FinanceDashboardApi {
    @GET("finance/student/{student_id}/dashboard")
    suspend fun getFinancialDashboard(@Path("student_id") studentId: Int): FinancialDashboardResponse
}
```

### 4.2 مدل‌ها (AppModels.kt)

```kotlin
data class StudentInstallmentItem(
    val id: Int, val course_title: String, val amount: Long,
    val due_date: String, val is_paid: Boolean, val paid_at: String,
    @SerializedName("enrollment_id") val enrollmentId: Int? = null,
    @SerializedName("status") val status: String? = null
)
data class CreateInstallmentRequest(
    @SerializedName("enrollment_id") val enrollmentId: Int,
    val amount: Int, @SerializedName("due_date") val dueDate: String
)
```

### 4.3 تب — show/hide کارت‌ها (StudentProfileActivity.kt)

```kotlin
private fun showStandardProfileContent() {
    llStandardContainer.visibility = View.VISIBLE
    llCommunicationContainer.visibility = View.GONE
    cardContent.visibility = View.VISIBLE
    cardInstallments.visibility = View.GONE
}
private fun showInstallmentsContent() {
    llStandardContainer.visibility = View.VISIBLE
    llCommunicationContainer.visibility = View.GONE
    cardContent.visibility = View.GONE
    cardInstallments.visibility = View.VISIBLE
    tvInstallmentsEmpty.text = getString(R.string.profile_inst_loading)
}
// tab 3 → showInstallmentsContent() + fetchInstallments()
```

### 4.4 پرداخت — dialog تأیید + refresh

```kotlin
private fun confirmAndPayInstallment(item: StudentInstallmentItem) {
    AlertDialog.Builder(this)
        .setTitle(getString(R.string.installment_pay_title))
        .setMessage(getString(R.string.installment_pay_msg, String.format(Locale("en","US"), "%,d", item.amount)))
        .setPositiveButton(getString(R.string.installment_pay_yes)) { _, _ -> performPayInstallment(item.id) }
        .setNegativeButton(getString(R.string.common_cancel), null).show()
}
private fun performPayInstallment(id: Int) {
    lifecycleScope.launch(Dispatchers.IO) {
        try { api.payInstallment(id) /* ... */
            withContext(Dispatchers.Main) {
                Toast.makeText(..., res.message ?: getString(R.string.installment_pay_success), LONG).show()
                CacheManager.clear(..., "student_installments_$studentId")
                fetchInstallments(); fetchFullData()
            }
        } catch (e: Exception) {
            val detail = extractServerDetail(e) ?: e.message ?: getString(R.string.common_unknown_error)
            Toast.makeText(..., getString(R.string.common_err_with_detail, detail), LONG).show()
        }
    }
}
```

### 4.5 افزودن قسط — دراپ‌داون enrollment فعال

```kotlin
val dash = dashApi.getFinancialDashboard(studentId)
if (dash.enrollments.isEmpty()) { Toast(R.string.installment_error_no_enrollment); return }
val courseNames = dash.enrollments.map { it.courseTitle }
val courseIds   = dash.enrollments.map { it.enrollmentId }
actvCourse.setAdapter(ArrayAdapter(..., courseNames))
if (courseNames.size==1) { actvCourse.isEnabled=false } // تنها یک کلاس
// validation: amount>0, isValidJalaliDate(due) via JalaliUtils.parseProjectDate
dialog.getButton(POSITIVE).setOnClickListener {
    if (!isValidJalaliDate(normalizedDue)) { etDue.error = getString(R.string.installment_error_due); return@setOnClickListener }
    performCreateInstallment(enrollmentId, amount, normalizedDue)
}
```

---

## 5) تأیید استاتیک (بدون compile/emulator — طبق قرارداد تسک)

```bash
python3 -c "import xml.etree.ElementTree as ET; ET.parse('KharazmiAdmin/app/src/main/res/values/strings.xml')"
# strings.xml XML OK
python3 -c "import xml.etree.ElementTree as ET; ET.parse('KharazmiAdmin/app/src/main/res/layout/activity_student_profile.xml')"
# activity_student_profile.xml XML OK
python3 -c "import xml.etree.ElementTree as ET; ET.parse('KharazmiAdmin/app/src/main/res/layout/item_installment.xml')"
# item_installment.xml XML OK
python3 -c "import xml.etree.ElementTree as ET; ET.parse('KharazmiAdmin/app/src/main/res/layout/dialog_create_installment.xml')"
# dialog_create_installment.xml XML OK

grep -c "import androidx.recyclerview.widget.LinearLayoutManager" StudentProfileActivity.kt
# 1 (duplicate fixed)

python3 -c "
openB = open('...StudentProfileActivity.kt').read().count('{')
closeB = open('...').read().count('}')
print(openB, closeB)
"
# 236 236  diff 0 — braces balanced

grep -o "R.string.[a-z_]*" StudentProfileActivity.kt | cut -d. -f3 | sort -u | comm -23 - <(grep -o 'name="[^"]*"' strings.xml | cut -d\" -f2 | sort -u)
# (no missing strings)

grep -n "Kharazmi_Server" $(git diff --name-only)
# (no server files in diff)

grep -n "enrollment_id.*amount.*due_date" AppModels.kt
# CreateInstallmentRequest(enrollment_id, amount, due_date) — match finance.py InstallmentCreateRequest

grep -n "is_paid.*paid_at" AppModels.kt
# StudentInstallmentItem — match GET students/{id}/installments
```

- **Import/Match سرور:** `CreateInstallmentRequest(enrollment_id, amount, due_date)` با `finance.py:InstallmentCreateRequest` مو می‌زند؛ `PayInstallmentResponse(receipt_id)` با `pay_installment_manually`؛ `RemindInstallmentResponse(status,message)` با `send_installment_payment_reminder`.
- **بدون لمس مالی سرور:** `git diff --name-only` هیچ `Kharazmi_Server/**` ندارد؛ `Kharazmi_Server/gaj_db.db` هش قبل/بعد یکسان (`f0e55fe7...` در S3-A2 تأیید شد و این تسک فقط اندروید را تغییر داد).
- **تمام متن فارسی از strings.xml:** `grep '"[^"]*[\u0600-\u06FF]' StudentProfileActivity.kt` فقط `۰۱۲۳۴۵۶۷۸۹` (نرمال‌سازی ارقام) و کامنت‌ها را می‌دهد — هیچ `Toast("...فارسی هاردکد")` وجود ندارد.

---

## 6) موارد عمداً دست‌نخورده

- `Kharazmi_Server/routers/finance.py`, `classes.py`, `students.py` — هیچ خطی تغییر نکرد
- `wallet`، `F-A2`، `test_*.py` — طبق `S3-A2-bugfix.md` به همان شکل ماندند
- کامپایل اندروید (`./gradlew`) و emulator اجرا نشد — تسک صراحتاً «فقط بررسی استاتیک» گفته

---

## 7) Git

```bash
git add KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/ApiInterfaces.kt \
        KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/AppModels.kt \
        KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/StudentProfileActivity.kt \
        KharazmiAdmin/app/src/main/res/layout/activity_student_profile.xml \
        KharazmiAdmin/app/src/main/res/values/strings.xml \
        KharazmiAdmin/app/src/main/res/layout/item_installment.xml \
        KharazmiAdmin/app/src/main/res/layout/dialog_create_installment.xml \
        checkpoints/2026-09-16_A1-installments-ui.md

git commit -m "A1 installments UI: pay/remind/add installment (no server change, static check)"

git push origin arena/01a0a936-kharazmiapp
git diff --stat HEAD~1 HEAD
# 8 files changed, ~520 insertions(+)
```

`gh api repos/eternity-lord/KharazmiApp/branches/arena/01a0a936-kharazmiapp --jq .commit.sha` پس از push با `HEAD` محلی یکسان است (قبلاً در S3-A2 با `3164189` تأیید شد).

---

## 8) جمع‌بندی

- **Gap A1 پر شد:** تب اقساط حالا به‌جای متن خام، لیست تعاملی با «پرداخت» (dialog تأیید → `POST pay` → toast + refresh) و «یادآوری» ( `POST remind` → toast `detail` حتی 400) و «افزودن قسط جدید» (مبلغ+due_date شمسی با `enrollment_id` فعال) دارد.
- **هیچ ریسک سروری نیست:** فقط فایل‌های اندروید تغییر کردند؛ endpointها از قبل تست‌شده و 268 passed بودند.
- **استاتیک OK، XML OK، strings کامل، سرور دست‌نخورده.**

*پایان A1 — آمادهٔ تسک بعدی (یا QA روی اقساط با کاربر تستی).*
