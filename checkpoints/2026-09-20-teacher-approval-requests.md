# چک‌پوینت: رفع مشکل نمایش نشدن درخواست تأیید معلم بعد از ثبت‌نام توسط ادمین

- **عنوان:** نمایش صحیح «درخواست‌های تأیید معلم» پس از ثبت‌نام ادمین (رفع route shadowing + جداسازی شعبه)
- **تاریخ:** 2026-09-20
- **Branch:** `arena/01a0bf8d-kharazmiapp` (تنها branch کاری)
- **Base HEAD قبل از تغییرات:** `3e9da855fcc3bcf4fa3d200ef319d223f87fbabb` — `fix: improve admin archived classes management`

---

## ۱) مشکل و ریشه‌ی واقعی (Root Cause)

**گزارش کاربر:** بعد از اینکه ادمین یک معلم جدید ثبت‌نام می‌کند، درخواست تأیید او در اپ اندروید (صفحه‌ی «درخواست‌های تأیید معلم») نمایش داده نمی‌شود.

**ریشه‌ی واقعی — سایه‌افتادن مسیر (route shadowing):**

Starlette مسیرها را **اولین-تطبیق-برنده** ارزیابی می‌کند. در `main.py` ترتیب include این بود:

```python
app.include_router(teachers.router)   # شامل GET /teachers/{teacher_id}
...
app.include_router(admin.router)      # شامل GET /teachers/pending
```

بنابراین `GET /teachers/pending` (literal) بعد از `GET /teachers/{teacher_id}` (پارامتری) ثبت می‌شد و **هرگز به handler خودش نمی‌رسید**؛ به‌جایش به `get_teacher_profile` می‌خورد و پارامتر `"pending"` به‌عنوان `teacher_id: int` پارس می‌شد:

```
GET /teachers/pending  →  422 Unprocessable Entity
{"detail":[{"type":"int_parsing","loc":["path","teacher_id"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"pending"}]}
```

سمت اندروید، `PendingTeachersActivity.fetchPendingList()` این خطا را در `catch` فقط `Log.e` می‌کرد (بدون هیچ خطای دیدنی) و لیست هم هرگز پر نمی‌شد ⇒ کاربر «هیچ درخواستی وجود ندارد»/صفحه‌ی خالی می‌دید. **اپ اندروید از این نظر تقصیری نداشت؛ باگ کاملاً سمت سرور بود.**

**اثبات با probe زنده (کد قبل از فیکس):** `GET /teachers/pending` دقیقاً همان 422 با `input: "pending"` را برمی‌گرداند، در حالی که مسیرهای `approve`/`reject`/ثبت‌نام درست کار می‌کردند (چون مسیرهایشان با `{teacher_id}` تداخل نداشت).

**Audit کل اپ:** با شبیه‌سازی ترتیب include از سورس `main.py` (۲۴ روتر، ۲۰۳ route) دقیقاً **یک** مسیر سایه‌شده در کل اپ وجود داشت: `GET /teachers/pending ← GET /teachers/{teacher_id}`. با ترتیب جدید (admin قبل از teachers): **۰ مسیر سایه‌شده و ۰ سایه‌ی جدید**.

---

## ۲) رفتار قبل از تغییر

| موضوع | قبل |
|---|---|
| `GET /teachers/pending` | همیشه 422 (`int_parsing` روی `"pending"`) — به‌دلیل سایه‌افتادن، handler هرگز اجرا نمی‌شد |
| لیست درخواست‌های تأیید در اپ | همیشه خالی (صفحه‌ی سفید)، بدون هیچ خطای دیدنی |
| ثبت معلم توسط ادمین | `branch_id` هرگز ست نمی‌شد ⇒ همه‌ی معلم‌های جدید `branch_id = NULL` |
| جداسازی شعبه در صف تأیید | وجود نداشت (وقتی هم مسیر اجرا می‌شد، همه‌ی شعبه‌ها به همه نشان داده می‌شد) |
| تأیید/رد توسط ادمینِ شعبه‌ی دیگر | مسدود نبود — ادمینِ شعبه‌ی A می‌توانست درخواست شعبه‌ی B را تأیید/رد کند |
| داده‌های NULL (نام/موبایل/شعبه) | در مدل اپ، `TeacherPending` قبلاً null-safe شده بود (Task 1)، ولی فیلد شعبه اصلاً وجود نداشت |
| خطای شبکه در اپ | فقط `Log.e`؛ کاربر هیچ بازخوردی نمی‌گرفت |
| رفرش لیست | فقط یک‌بار در `onCreate`؛ برگشتن به صفحه داده را تازه نمی‌کرد |

---

## ۳) رفتار بعد از تغییر

| موضوع | بعد |
|---|---|
| `GET /teachers/pending` | **200** و لیست واقعی معلم‌های `is_approved=False` و `is_deleted=False` (ترتیب قطعی: id صعودی) |
| لیست درخواست‌ها در اپ | بلافاصله بعد از ثبت معلم نمایش داده می‌شود (با شناسه‌ی واقعی دیتابیس) |
| `branch_id` معلم جدید | با سیاست مرکزی `resolve_creation_branch` تعیین می‌شود: ارسال صریح نامعتبر/غیرمجاز → خطای همان سیاست (400/403)؛ بدون ارسال صریح → از هویت فراخوان؛ اگر قابل‌تعیین نبود → `NULL` (بدون حدس، ثبت‌نام رد نمی‌شود — سازگار با اپ فعلی که فیلد را نمی‌فرستد) |
| جداسازی شعبه در صف | کاربرِ شعبه‌دار فقط «شعبه‌ی خودش + رکوردهای بدون شعبه»؛ هرگز شعبه‌ی دیگر. ادمین کل همه را می‌بیند |
| فیلتر صریح `?branch_id=` | فیلتر **دقیق** روی همان شعبه (بدون رکوردهای بدون‌شعبه)؛ برای کاربرِ شعبه‌دار، شعبه‌ی خودش بر پارامتر غلبه می‌کند (isolation با query دور زده نمی‌شود) |
| تأیید/رد از شعبه‌ی دیگر | `404 "معلم یافت نشد"` — بدون نشت وجود رکورد (existence leak) |
| فیلد جدید پاسخ | `branch_id` + `branch_name` (افزودنی؛ کلاینت قدیمی نادیده می‌گیرد ⇒ سازگاری کامل) |
| داده‌های NULL | بدون 500 (تست‌شده: name/mobile/branch/status ناقص) |
| ثبت تکراری | مسدود (400/409 — بستگی به حالت: کد ملی/موبایل تکراری) |
| خطای شبکه در اپ | Toast صریح «خطا در دریافت درخواست‌های تأیید معلم» + خالی‌کردن لیست (بدون نمایش داده‌ی کهنه) |
| رفرش | انتقال fetch به `onResume` — بعد از ثبت معلم یا هر بازگشت به صفحه، داده‌ی تازه |
| کارت درخواست در اپ | خط شعبه («شعبه: X» یا «بدون شعبه» برای رکورد بدون انتساب) |

---

## ۴) فایل‌های تغییر‌یافته

### سرور (`Kharazmi_Server/`)

| فایل | تغییر |
|---|---|
| `main.py` | ترتیب include: `admin.router` قبل از `teachers.router` + کامنت توضیحی `FIX(route-shadowing)` (رفع ریشه‌ای باگ) |
| `schemas.py` | `TeacherCreate.branch_id: Optional[int] = None`؛ اسکیمای جدید `PendingTeacherItem(TeacherListItem)` با `branch_id`/`branch_name` |
| `routers/teachers.py` | `register_teacher`: پارامتر `authorization` + بلوک تعیین شعبه با `resolve_creation_branch` و ست‌کردن `teacher_data["branch_id"]` |
| `routers/admin.py` | بازنویسی `get_pending_teachers` (بررسی شعبه + `branch_name` گروهی + `order_by(id)` + فیلتر دقیق صریح)؛ هلپر `_teacher_in_scope`؛ گارد دامنه‌ی شعبه روی `approve_teacher` و `reject_teacher` |
| `test_teacher_approval_requests.py` | **جدید** — ۱۸ متد تست رگرسیون برای کل مسیر تأیید معلم |

### اندروید (`KharazmiAdmin/`)

| فایل | تغییر |
|---|---|
| `PendingTeachersActivity.kt` | `TeacherPending` +`branchId`/`branchName`؛ fetch در `onResume`؛ Toast خطای بارگذاری + خالی‌کردن لیست؛ نمایش شعبه در کارت |
| `res/layout/item_pending.xml` | `TextView@tvBranch` برای خط شعبه |
| `res/values/strings.xml` | `ptch_load_error`، `ptch_branch_row`، `ptch_no_branch` |

**خارج از دامنه:** هیچ تغییری در جست‌وجوی دانش‌آموز، CRM، فاکتور/پرداخت، حضور و غیاب، اطلاع‌رسانی عمومی، کلاس‌های آرشیو، مالی و تسویه‌ی جلسه داده نشد.

---

## ۵) تست‌های اجراشده و نتیجه

همه‌ی تست‌ها با `DATABASE_URL` موقت (`sqlite:////tmp/...`) و `JWT_SECRET_KEY` اینلاین اجرا شدند؛ دیتابیس واقعی `Kharazmi_Server/gaj_db.db` **دست‌نخورده** است (md5 = `f048f8d118b33c4eaa944490594121d7`، برابر با مرجع قبل از کار).

| مورد | نتیجه |
|---|---|
| `test_teacher_approval_requests.py` (جدید، ۱۸ متد) | ✅ **18 passed** |
| **اثبات رگرسیون:** همان تست‌ها روی HEAD قبل از فیکس (`3e9da85`، در worktree مجزا) | ✅ **16 failed / 2 passed** — یعنی تست‌ها واقعاً باگ را می‌گیرند |
| `test_teachers.py` + `test_admin.py` + `test_teacher_null_data.py` + `test_permissions.py` + `test_permissions_e2e.py` + فایل جدید | ✅ **55 passed** |
| مجموعه‌ی کامل پروژه (`-p no:randomly`) | ✅ **760 passed** + ۵ خطای از قبل موجود (bedrock: `test_audit` ×۳، `test_dashboard`، `test_dashboard_performance`) — همان ۵ مورد گزارش‌شده در Task 2، بی‌ارتباط با این تغییر |
| Audit مسیرها (شبیه‌سازی ترتیب include از `main.py`) | ✅ ۰ مسیر سایه‌شده، ۰ سایه‌ی جدید (۲۴ روتر / ۲۰۳ route) |
| Probe زنده‌ی HTTP (ثبت‌نام → صف → تأیید/رد → جداسازی شعبه → داده‌ی NULL) | ✅ ALL OK |

**پوشش ۱۷ موضوع رگرسیون الزامی:** ثبت‌نام ادمین (test_02)، وضعیت اولیه‌ی معلم (test_01/03)، نمایش در صف (test_02)، معلم تأییدشده در صف نیست (test_04)، موفقیت تأیید (test_05_06)، حذف از صف بعد از تأیید (test_05_06)، موفقیت رد (test_07)، مسدودسازی نقش غیرمجاز (test_08)، جداسازی شعبه (test_09 + `test_branch_admin_cannot_approve_other_branch`)، ادمین کل (test_10)، عدم نشت `branch_id=NULL` (test_11)، داده‌های NULL بدون 500 (test_12)، جلوگیری از ثبت تکراری (test_13)، لیست خالی (test_14)، ۴۰۴ کنترل‌شده (test_15)، شناسه‌ی واقعی در پاسخ (test_16)، سازگاری API با اندروید (test_17).

---

## ۶) وضعیت build اندروید

**build واقعی انجام نشد و ادعا نمی‌شود.** در این محیط JDK و Android SDK نصب نیست (`java: command not found`)، بنابراین امکان `gradle`/کامپایل وجود ندارد. به‌جای آن بررسی استاتیک انجام شد:

- XMLها با `xml.etree` پارس و تأیید شدند (`strings.xml`, `item_pending.xml`).
- بالانس براکت‌های `PendingTeachersActivity.kt` ({} و ()) و ارجاع‌های `R.string.*`/`R.id.tvBranch` بررسی شد.
- امضاهای Retrofit (`teachers/pending`, `teachers/approve/{id}`, `teachers/reject/{id}`) با مسیرهای سرور تطبیق داده شد؛ فیلدهای جدید JSON (`branch_id`, `branch_name`) اختیاری و null-safe اند ⇒ کلاینت قدیمی هم سالم می‌ماند.

**محدودیت:** کامپایل واقعی Kotlin/Gradle در این محیط ممکن نیست و باید روی محیط توسعه‌ی شما تأیید شود.

---

## ۷) محدودیت‌ها و ریسک‌های باقی‌مانده

1. **کامپایل اندروید تأییدنشده** — بررسی استاتیک جای build را نمی‌گیرد (بند ۶).
2. **تغییر ترتیب include** — تأیید شد که تنها یک سایه در کل اپ وجود داشت و جابه‌جایی هیچ سایه‌ی جدیدی نمی‌سازد، اما این یک تغییر ساختاری در ترتیب مسیرهاست؛ تنها اثر قابل‌مشاهده، اجرای درست `/teachers/pending` است (سایر مسیرها بدون تداخل‌اند).
3. **رکوردهای قدیمی `branch_id = NULL`** — عمداً پاک/حدس‌زده نشدند؛ طبق policy فعلی در صف «بدون شعبه» دیده می‌شوند (بدون نشت) و برای اسکوپ‌کردن آن‌ها تصمیم سیاستی جدا لازم است.
4. **ثبت‌نام بدون توکن قابل‌حل (چند شعبه‌ی فعال)** — معلم `NULL` می‌ماند (رفتار محافظه‌کارانه، بدون حدس). اگر سیاست «الزام شعبه در ثبت‌نام» مطلوب باشد، نیاز به تصمیم شماست.
5. **Rate limit ثبت‌نام ۵ در ساعت** — در تست‌ها با reset محدودکننده مدیریت شد؛ در محیط واقعی رفتار قبلی حفظ شده است.
6. خطاهای از قبل موجود `test_audit`/`test_dashboard`/`test_dashboard_performance` (۵ مورد) رفع نشدند — خارج از دامنه‌ی این Task.

---

## ۸) Commit و Push

- **Commit SHA:** در گزارش نهایی پس از commit ثبت می‌شود؛ SHA داخل همان commit قابل درج نیست.
- **وضعیت Push:** در گزارش نهایی اعلام می‌شود.
- **Commit message (ثابت):** `fix: show teacher approval requests correctly`
- **Branch:** `arena/01a0bf8d-kharazmiapp` (تنها branch کاری؛ PR/merge بدون دستور صریح ساخته نمی‌شود).
