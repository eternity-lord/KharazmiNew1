# چک‌پوینت: رفع مشکل ارسال و نمایش اعلان‌ها برای ادمین

- **عنوان:** بازگرداندن ارسالِ درست اعلان ادمین (فضای User.id) + بازکردن و نمایش‌دادن «مرکز اعلان‌ها» در اپ
- **تاریخ:** 2026-09-20
- **Branch:** `arena/01a0bf8d-kharazmiapp` (تنها branch کاری)
- **Base HEAD قبل از تغییرات:** `470fe96f3cc46f7d50a18a04a169c22d2a697b3e` — `fix: show teacher approval requests correctly`

---

## ۱) ریشه‌ی مشکل (Root Cause) — دو مشکل مستقل، هر دو اثبات‌شده

مشکل «اعلان ادمین نمی‌آید/دیده نمی‌شود» **دو ریشه‌ی جدا** داشت؛ نه یکی:

### الف) ارسال: اعلان ادمین به کاربر اشتباه می‌رفت (سرور)

تنها جایی در کل سرور که اعلان با نقش `admin` می‌سازد، قانون اتوماسیون «سرنخ تماس‌نگرفته» بود:

```python
trigger_notification_action(db, rule.id, 1, "admin", title, body, ...)   # ← recipient_id = 1 هاردکد
```

یعنی اعلان **همیشه** به کاربری با `User.id = 1` می‌رفت، بدون توجه به اینکه ادمین واقعی چه کسی است. در تست زنده (پروپ) کاربر شماره ۱ را عمداً یک **دانش‌آموز** گذاشتم:

```
recipients=[1]      ← اعلان به دانش‌آموز رسید
```

و چون خواندن با فیلتر `recipient_user_id == خودم AND recipient_role == نقش خودم` است، آن اعلان برای ادمین‌ها **هرگز وجود نداشت** (نه اینکه مخفی باشد؛ اصلاً ساخته نمی‌شد). پس این بخش «ارسال» بود، نه «نمایش».

### ب) نمایش: صفحه‌ی «مرکز اعلان‌ها» در اپ هیچ‌جا باز نمی‌شد (اندروید)

`NotificationCenterActivity` در `AndroidManifest.xml` ثبت بود و کل کد نمایش (لیست، mark-read، فیلتر) را هم داشت، اما **هیچ کد یا منویی در کل اپ آن را باز نمی‌کرد**:

```bash
grep -rn "NotificationCenterActivity" KharazmiAdmin/app/src/main
# → فقط: AndroidManifest.xml:119 (ثبت) و خودِ فایل اکتیویتی. هیچ startActivity و هیچ آیتم منو.
```

یعنی حتی اگر اعلان ادمین ساخته می‌شد، ادمین **راهی برای دیدنش نداشت**.

### ج) سه باگ جانبی که همان اثر را تشدید می‌کردند (سرور) — همه اثبات‌شده با probe

| # | باگ | اثبات |
|---|---|---|
| ۱ | `created_at = NULL` (رکورد legacy) ⇒ `None.strftime(...)` ⇒ **۵۰۰** برای **کل** صندوق اعلان | `AttributeError: 'NoneType' object has no attribute 'strftime'` در `routers/auth.py:631` — یک رکورد قدیمی، همه‌ی اعلان‌های ادمین را از کار می‌انداخت |
| ۲ | نقش در خواندن با `sub_role or "student"` resolve می‌شد ولی بقیه‌ی پروژه `sub_role or "admin"` ⇒ ادمین legacy (رکوردی با `sub_role = NULL`) اعلان نقش admin خودش را **نمی‌دید** | پروپ: کاربر با `role=admin, sub_role=NULL` ⇒ `GET /notifications` = `200 []` در حالی که اعلانش در دیتابیس بود |
| ۳ | `POST /notifications/{id}/read` روی اعلان ناموجود/دیگران **۲۰۰ با پیام موفقیت** برمی‌گرداند (no-op خاموش) | پروپ: `status=200 {"message":"اعلان به عنوان خوانده شده ثبت شد"}` |
| ۴ | endpoint شمارش خوانده‌نشده‌ها وجود نداشت | `grep -rn "unread" Kharazmi_Server` = خالی؛ `GET /notifications/unread_count` = 404 |

> نکته‌ی مهم: `type`/`title`/`body`/`is_read`/`created_at` در جدول `notifications` همه **nullable** هستند؛ سرور برای رکوردهای ناقص `null` برمی‌گرداند و مدل Kotlin (`val title: String`) آن را با NPE کرش می‌کرد.

---

## ۲) رفتار قبل و بعد

| موضوع | قبل | بعد |
|---|---|---|
| اعلان رویداد «سرنخ تماس‌نگرفته» | به `User.id = 1` هاردکد (معمولاً ادمین نیست) | به کارکنانِ مجاز از فضای `User.id`: ادمین مرکزی + ادمینِ همان شعبه + منشی‌ها |
| ادمینِ شعبه‌ی دیگر | — | اعلان سرنخِ شعبه‌ی دیگر را **نمی‌بیند** (تست: `[2,3,4]` برای شعبه ۱ و `[2,7]` برای شعبه ۲) |
| باز کردن مرکز اعلان‌ها در اپ | **غیرممکن** (هیچ ورودی‌ای نبود) | آیتم «اعلان‌ها» در منوی کشویی + ورودیِ `MainActivity` |
| `created_at = NULL` | ۵۰۰ برای کل لیست | ۲۰۰؛ همان رکورد با `created_at = ""` نمایش داده می‌شود |
| ادمین legacy (`sub_role = NULL`) | اعلان‌های نقش admin خودش را نمی‌دید | می‌بیند (نقش با `sub_role → role → "student"` resolve می‌شود) |
| `is_read = NULL` | به‌عنوان `null` به کلاینت می‌رفت | روی سرور `false` نرمال می‌شود (خوانده‌نشده) و در اپ هم `is_read != true` = خوانده‌نشده |
| mark-as-read اعلان ناموجود/دیگری | ۲۰۰ کاذب | **۴۰۴ کنترل‌شده** و بدون هیچ تغییری روی داده‌ی کاربر دیگر |
| شمارش خوانده‌نشده | وجود نداشت | `GET /notifications/unread_count` → `{"unread": n, "total": m}` + نمایش «n اعلان خوانده‌نشده» بالای لیست |
| رفرش لیست در اپ | فقط یک‌بار در `onCreate` | در `onResume` (هر بازگشت به صفحه) |
| لیست خالی در اپ | صفحه‌ی سفید بدون پیام | پیام روشن: «هیچ اعلانی وجود ندارد» / «اعلانی با این فیلتر وجود ندارد» |
| خطای شبکه در اپ | Toast + باقی‌ماندن لیست کهنه | Toast + پاک‌شدن لیست (بدون داده‌ی گمراه‌کننده) |
| فیلتر «سیستمی و کلاس» | فقط `type == "system"` ⇒ اعلان‌های `type="automation"` (نوع اصلی اعلان ادمین) **پنهان** می‌شد | گروه‌بندی درست: `money = installment/payment`، `attendance`، بقیه = سیستمی/کلاس |
| فیلدهای NULL در اپ | کرش با NPE | fallback امن («اعلان بدون عنوان»، متن خالی) |

---

## ۳) مسیر تولید تا نمایش اعلان (نقشه‌ی کامل بعد از فیکس)

```
رویداد: قانون اتوماسیون lead_uncontacted  (routers/automation.py:run_automation_engine)
   ↓
تعیین گیرنده:  NotificationService.send_to_staff(branch_id = Lead.branch_id)
     → get_staff_recipients(): SELECT از users با نقش کانونیکال admin/secretary
       و فیلتر (User.branch_id == شعبه‌ی رویداد) OR (User.branch_id IS NULL = ادمین کل)
   ↓
ذخیره:  Notification(recipient_user_id = User.id ✅، recipient_role = نقش کانونیکالِ همان کاربر)
        + AutomationLog (گارد ضدتکرار ۳ روزه برای هر سرنخ)
   ↓
خواندن:  GET /notifications                → فیلتر (recipient_user_id == خودم AND recipient_role == نقش کانونیکال من)
         GET /notifications/unread_count   → همان فیلتر، شمارش unread/total
         POST /notifications/{id}/read     → فقط اعلان خودم؛ در غیر این صورت ۴۰۴
         POST /notifications/read_all      → فقط اعلان‌های خودم
   ↓
اندروید:  منوی کشویی «اعلان‌ها» → MainActivity → NotificationCenterActivity
         → Retrofit (notifications / unread_count / {id}/read / read_all)
         → onResume → لیست + شمارش خوانده‌نشده + نشانگر ردیفی + دیالوگ جزئیات (null-safe)
```

**فضای شناسه‌ها (نکته‌ی کلیدی):** `Notification.recipient_user_id` **همیشه** `User.id` است؛ برای شاگرد/ولی از `resolve_notification_recipient` (سایه‌ها) و برای ادمین‌ها از `get_staff_recipients` تأمین می‌شود. `Student.id`/`Teacher.id` هرگز در این ستون نمی‌نشیند (تست‌های ۰۲/۰۲ب).

---

## ۴) فایل‌های تغییرکرده

### سرور (`Kharazmi_Server/`)

| فایل | تغییر |
|---|---|
| `dependencies.py` | `resolve_notification_role()` (نقش کانونیکال مشترک نوشتن/خواندن) + `STAFF_NOTIFICATION_ROLES` + `NotificationService.get_staff_recipients()` + `NotificationService.send_to_staff()` |
| `routers/auth.py` | سه endpoint اعلان با نقش کانونیکال؛ `created_at` و `is_read` نال‌سیف؛ **جدید:** `GET /notifications/unread_count`؛ mark-read ناموجود → ۴۰۴ |
| `routers/automation.py` | حذف `recipient_id = 1` هاردکد و استفاده از `send_to_staff` (شعبہ‌ی سرنخ) + ثبت `AutomationLog` با تعداد گیرندگان |
| `test_admin_notifications.py` | **جدید** — ۱۹ تست رگرسیون (۱۲ موضوع الزامی + موارد تکمیلی) |

### اندروید (`KharazmiAdmin/`)

| فایل | تغییر |
|---|---|
| `res/menu/drawer_menu.xml` | آیتم جدید `nav_notifications` («اعلان‌ها») — ورودیِ گمشده |
| `MainActivity.kt` | هندل `nav_notifications` → باز کردن `NotificationCenterActivity` |
| `NotificationCenterActivity.kt` | مدل نال‌سیف (`type/title/body/is_read/created_at`)؛ `UnreadCountResponse` + `getUnreadCount()`؛ بارگذاری در `onResume`؛ حالت خالی؛ شمارش خوانده‌نشده؛ فیلتر گروهی درست؛ متن‌های نال‌سیف در adapter و دیالوگ |
| `res/layout/activity_notification_list.xml` | `tvUnreadCount` (شمارش) + `tvNotifEmpty` (حالت خالی) |
| `res/values/strings.xml` | `nav_notifications`, `notif_unread_count`, `notif_empty`, `notif_empty_filter`, `notif_untitled` |

**خارج از دامنه (دست نخورد):** CRM، invoice/پرداخت، search، attendance، archive، و همچنین مسیر مجزای اعلان‌های پورتال (`students/my_profile`) که داده‌های نمایشیِ hardcode دارد.

---

## ۵) تست‌ها و نتیجه

همه با DB موقت (`sqlite:////tmp/...`) و `JWT_SECRET_KEY` اینلاین؛ DB واقعی `gaj_db.db` دست‌نخورده (md5 = `f048f8d118b33c4eaa944490594121d7`).

| مورد | نتیجه |
|---|---|
| فایل جدید `test_admin_notifications.py` (۱۹ تست) | ✅ **19 passed** |
| **اثبات رگرسیون:** همان تست‌ها روی HEAD قبل از فیکس (worktree مجزا، با shim موقتِ import) | ✅ **11 failed / 8 passed** |
| Probe زنده‌ی HTTP (`/home/user/probe_admin_notifications.py`) روی کد قبل از فیکس | ❌ 10 OK / **4 BUG** (گیرنده=۱، ۲۰۰ کاذب، نبود unread_count) |
| همان Probe روی کد بعد از فیکس | ✅ **16 OK / 0 BUG** |
| اثبات ۵۰۰ (NULL واقعی با SQL خام) | ✅ traceback: `auth.py:631 strftime on None` |
| تست‌های مرتبط (notifications/automation/installments/roles/permissions/admin/teachers) | ✅ **340 passed** |
| مجموعه‌ی کامل (`-p no:randomly`) | ✅ **779 passed** + همان ۵ خطای از قبل موجود (`test_audit`×۳، `test_dashboard`، `test_dashboard_performance`) |
| Audit سایه‌افتادن مسیرها | ✅ ۰ مسیر سایه‌شده (۲۴ روتر / ۲۰۴ route) |

**پوشش ۱۲ موضوع الزامی:** ۱) ساخت رویداد و اعلان ادمین → `test_01` • ۲) mapping به فضای User.id → `test_02/02b/02c` • ۳) دریافت توسط ادمین درست → `test_03` • ۴) عدم دریافت کاربر نامرتبط → `test_04` • ۵) branch isolation → `test_05` • ۶) unread count → `test_06/06b` • ۷) mark-as-read → `test_07` • ۸) ضدتکرار در retry → `test_08/08b` • ۹) اعلان ناموجود → خطای controlled → `test_09` • ۱۰) لیست خالی → `test_10` • ۱۱) داده nullable → `test_11` • ۱۲) حفظ اعلان‌های قبلی → `test_12` (+ `test_13` ادمین legacy، `test_14` دسترسی، `test_15` fan-out ادمین legacy).

---

## ۶) وضعیت build اندروید

**build واقعی انجام نشد و ادعا نمی‌شود** (در این محیط JDK/SDK نصب نیست: `java: command not found`). بررسی استاتیک انجام‌شده:

- پارس موفق سه فایل XML تغییرکرده (`strings.xml`, `activity_notification_list.xml`, `drawer_menu.xml`).
- بالانس براکت‌های `NotificationCenterActivity.kt` (۵۴/۵۴ و ۱۷۳/۱۷۳) و `MainActivity.kt` (۱۷۰/۱۷۰ و ۶۲۱/۶۲۱).
- تطبیق همه‌ی `R.id`/`R.string` جدید با منابع تعریف‌شده؛ تطبیق امضاهای Retrofit با مسیرهای سرور (`notifications`, `notifications/unread_count`, `notifications/{id}/read`, `notifications/read_all`).
- بررسی اینکه `NotificationItem`/`UnreadCountResponse` در هیچ فایل دیگری استفاده نمی‌شوند (تغییر مدل جای دیگری را نمی‌شکند) و `SimpleResponse` موجود است.

**محدودیت:** کامپایل واقعی Gradle/Kotlin در این محیط ممکن نیست و باید روی محیط توسعه تأیید شود.

---

## ۷) ریسک‌ها و تصمیم‌های باقی‌مانده (برای تصمیم شما)

1. **جدول `notifications` ستون `branch_id` ندارد.** جداسازی شعبه در **زمانِ ارسال** اعمال شد (گیرندگان = کارکنانِ همان شعبه + ادمین کل) و در **زمانِ خواندن** هر کاربر فقط اعلان‌های خودش را می‌بیند. پیامد: اگر کارمندی بعداً به شعبه‌ی دیگری منتقل شود، اعلان‌های قدیمی‌اش همچنان در صندوق خودش می‌ماند. اگر می‌خواهید جداسازی در سطح ردیف هم باشد، افزودن ستون `branch_id` به جدول + migration لازم است (تصمیم شما).
2. **ارسال واقعی Push (FCM) وجود ندارد:** در `NotificationService.send_notification` حلقه‌ی ارسال به دستگاه‌ها خالی است (`for token_record in device_tokens: pass`). یعنی اعلان فقط داخل اپ (صفحه‌ی اعلان‌ها) دیده می‌شود و نوتیفیکیشن سیستمی/آفلاین نمی‌رود. این مورد رفع نشد (خارج از دامنه‌ی این Task) — تصمیم بگیرید.
3. **پچ خودکار قدیمی در `main.py`:** هنگام بالا آمدن سرور اجرا می‌شود: `UPDATE users SET sub_role = 'admin' WHERE sub_role IS NULL` — این روی **همه‌ی** کاربران (از جمله رکوردهای قدیمی شاگرد/ولی که sub_role ندارند) اثر می‌گذارد. دست نخورد (خارج از دامنه)، ولی یک ریسک داده‌ای واقعی است.
4. **پورتال شاگرد/ولی** اعلان‌هایش را از مسیر جدا و **hardcode** می‌گیرد (`students/my_profile`)، نه از جدول `notifications`. این مسیر دست نخورد؛ اگر می‌خواهید پورتال‌ها هم اعلان واقعی نشان دهند، کار جداگانه‌ای است.
5. مرزهای امنیتی حفظ شد: بدون توکن ۴۰۱، نقش کانونیکال در همه‌ی مسیرها، ۴۰۴ بدون نشت وجود رکورد، و `read_all` فقط روی اعلان‌های خودِ کاربر.

---

## ۸) Commit و Push

- **Commit SHA:** در گزارش نهایی پس از commit ثبت می‌شود؛ SHA داخل همان commit قابل درج نیست.
- **وضعیت Push:** در گزارش نهایی اعلام می‌شود.
- **Commit message (ثابت):** `fix: restore admin notification delivery and display`
- **Branch:** `arena/01a0bf8d-kharazmiapp` (تنها branch کاری؛ PR/merge بدون دستور صریح ساخته نمی‌شود).
