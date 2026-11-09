# ممیزی دسترسی نقش‌ها + mapping اعلان اقساط — TEST-ONLY (۲۰۲۶-۰۹-۱۷)

برنچ: `arena/01a0aac2-kharazmiapp` | ریپو: `eternity-lord/KharazmiApp`
کامیت پایه: `6311022` (fix چهار باگ جلسه/حضور) — درخت تمیز، وابستگی‌ها نصب، `.env` سندباکس موجود.

## ۰) دامنه و قواعد
- **فقط تست/گزارش/بازتولید؛ هیچ خطی از کد اصلی تغییر نکرد** (`git status` فایل جدید تست + همین CHK).
- نقش‌های تحت آزمون: `admin`, `secretary`, `teacher`, `student`, `parent` (+ `mystery_role` و `temp_parent:...`).
- DB واقعی لمس نشد؛ همه‌ی تست‌ها DB درون‌حافظه‌ای (`StaticPool`) یا فایل موقت `tmp_path` می‌سازند.
- پرداخت آنلاین و Android خارج از scope (فقط استاتیک: مسیر کلاینت `StudentPortalActivity.kt:41`).
- فایل تست جدید: `Kharazmi_Server/test_roles_installment_notifications_audit.py` (۷۱۲ خط، ۳۲ تست).

## ۱) دستورات اجراشده و نتایج
```bash
# اجرای فایل ممیزی
cd /home/user/KharazmiApp
DATABASE_URL=sqlite:////tmp/roles_audit.db PYTHONPATH=/home/user/KharazmiApp/Kharazmi_Server \
  python3 -m pytest -q Kharazmi_Server/test_roles_installment_notifications_audit.py
#  → 5 failed, 27 passed, 0 skipped (6.15s)

# سوئیت کامل (برای اطمینان از عدم تداخل)
cp Kharazmi_Server/gaj_db.db /tmp/roles_full_suite.db
DATABASE_URL=sqlite:////tmp/roles_full_suite.db PYTHONPATH=/home/user/KharazmiApp/Kharazmi_Server \
  python3 -m pytest -q Kharazmi_Server
#  → 5 failed, 611 passed, 9 warnings (55.66s)   [قبل از این فایل: 584 passed / 0 failed]
```
هیچ تستی skip نشد. ۵ شکست همه عمدی و یافته‌محور هستند (زیر).

## ۲) یافته‌ها

### F-R2 (High — باگ قطعی) — اعلان خودکار قسط با `Student.id` به‌جای `user_id`
| | |
|---|---|
| **محل کد** | `Kharazmi_Server/main.py:461` و `main.py:470` (بلوک «اجرای تسک خودکار یادآوری اقساط شهریه به اولیا» داخل `auto_patch_database`) |
| **کد فعلی** | `NotificationService.send_notification(db=db, recipient_user_id=st.id, recipient_role="parent"/"student", type="installment", ...)` |
| **expected** | شاگرد: `(recipient_user_id=501, recipient_role="student")` — ولی: `(601, "parent")` طبق `dependencies.resolve_notification_recipient` و همه‌ی مسیرهای دیگر پروژه |
| **actual** | `[(101,'parent'), (101,'student')]` — یعنی `Student.id` در فضای `User.id` |
| **سناریوی داده** | `Student.id=101` / `Student.user_id=501` / `Student.parent_user_id=601` / `User 501.sub_role=student` / `User 601.sub_role=parent` |
| **پیامد ۱** | `get_notifications` با `recipient_user_id == current_user.id` فیلتر می‌کند ⇒ ۵۰۱ و ۶۰۱ **هیچ‌وقت** اعلان قسط خود را نمی‌بینند (صندوق خالی). |
| **پیامد ۲** | اگر در دیتابیس کاربری با `User.id == 101` وجود داشته باشد و نقشش با `recipient_role` بخواند، **اعلان مالی خانواده‌ی دیگر** در صندوق او می‌افتد (نشت اطلاعات). |
| **پیامد ۳** | audit trail هم آلوده است: `SmsLog.target_group = notif_parent_101 / notif_student_101` (شاهد در تست `test_installment_notification_actual_recipient_is_student_id`). |
| **پیامد ۴ (سناریو ۶)** | شاگرد بدون `user_id/parent_user_id` (سناریوی ۱۰۴) هم اعلان با `(104,'parent')`/`(104,'student')` می‌گیرد ⇒ **fallback به `Student.id`** رخ می‌دهد؛ در حالی که resolver مرکزی shadow-user می‌سازد. |
| **تست‌های بازتولید** | `test_installment_notifications_use_user_ids_not_student_id` (نام درخواستی کاربر)، `test_installment_notification_never_targets_student_id_namespace`، `test_auto_reminder_without_user_ids_never_falls_back_to_student_id`، `test_each_user_only_sees_own_installment_notification`، `test_installment_notification_actual_recipient_is_student_id` (مستندساز actual) |
| **خروجی واقعی pytest** | `actual=[(101, 'parent'), (101, 'student'), (104, 'parent'), (104, 'student')]` |

**نکته‌ی مهم:** مسیر **دستی** یادآوری (`POST /finance/installments/{id}/remind` → `finance.py:2014/2021`) و همچنین `automation.trigger_notification_action` و `resolve_notification_recipient` درست کار می‌کنند (`user_id`/`parent_user_id` + shadow-user). فقط job خودکار boot خراب است ⇒ ناهم‌سیاستی درون‌کد.

### F-R1 (High — باگ قطعی، عملکردی نه امنیتی) — مسیر `/students/my_profile` با route داینامیک سایه افتاده است
| | |
|---|---|
| **محل کد** | `Kharazmi_Server/routers/students.py:437` → `@router.get("/students/{student_id}")` **قبل از** `students.py:674` → `@router.get("/students/my_profile")` ثبت شده است |
| **expected** | `GET /students/my_profile` با توکن شاگرد ⇒ ۲۰۰ + پروفایل خودِ شاگرد (تابع `get_student_my_profile` منطق درستی دارد) |
| **actual** | **۴۲۲**: `{"detail":[{"type":"int_parsing","loc":["path","student_id"],"msg":"Input should be a valid integer","input":"my_profile"}]}` — یعنی route داینامیک match می‌شود و endpoint اختصاصی هرگز اجرا نمی‌شود |
| **اثبات** | probe ایزوله (بدون تست): `GET /students/my_profile` = 422 و کنترل `GET /students/101` = 200 با همان توکن و شاگردِ **لینک‌شده‌ی** ۵۰۱ |
| **اثر واقعی** | کلاینت اندروید پورتال شاگرد همان مسیر را صدا می‌زند: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/StudentPortalActivity.kt:41` (`@GET("students/my_profile")`) ⇒ صفحه‌ی پروفایل شاگرد ۴۲۲ می‌گیرد |
| **تست بازتولید** | `test_role_09_student_reads_only_self` |
| **توجه** | تست‌های قبلی `test_students.py:119` این تابع را **مستقیم (unit)** صدا می‌زنند، پس shadowing را نمی‌بینند؛ CHKهای قبلی هم فقط «my_profile 404» را دیده بودند نه root cause |

## ۳) موارد درست طبق policy (۲۷ تست سبز)
| سناریو | نتیجه | تست |
|---|---|---|
| ۱. بدون توکن ⇒ ۴۰۱ (۴ مسیر) | ✅ | `test_role_01_no_token_is_401` |
| ۲. توکن نامعتبر/قالب‌ناقص/JWT منقضی ⇒ ۴۰۱ | ✅ | `test_role_02_*`, `test_role_02b_*` |
| ۳. admin: تنظیمات/تعرفه/تراکنش‌ها/گزارش درآمد + settle مجاز | ✅ | `test_role_03_*` |
| ۴. منشی: تنظیمات آموزشگاه/تعرفه/تراکنش‌ها/حذف شاگرد ۴۰۳؛ پیامک/مخاطبین والدین/پرداخت دستی مجاز | ✅ | `test_role_04_*` |
| ۵. معلم فقط شاگرد کلاس خودش (`/students/101` و grades) | ✅ | `test_role_05_*`, `test_role_05b_*` |
| ۶. معلم با تغییر ID: شاگرد/کلاس/طلب معلم دیگر ۴۰۳ | ✅ | `test_role_06_*` |
| ۷. ولی فقط فرزند خودش (child_profile + students/101) | ✅ | `test_role_07_*` |
| ۸. ولی با تغییر ID/انتخاب فرزند دیگر ۴۰۳ | ✅ | `test_role_08_*` |
| ۹. شاگرد self-scoped (`/students/101` ۲۰۰، دیگران ۴۰۳) | ✅ | `test_role_09_*` (به‌جز my_profile) |
| ۱۰. شاگرد/ولی: ۷ عملیات نوشتاری مالی ⇒ ۴۰۳ + صفر write | ✅ | `test_role_10_*` |
| ۱۱. معلم: تعرفه/تنظیمات/refund/settle/پرداخت/ویرایش خود/قوانین اتوماسیون/حذف تراکنش ⇒ ۴۰۳ | ✅ | `test_role_11_*` |
| ۱۲. `mystery_role` ⇒ ۴۰۳ در همه‌ی مسیرهای حساس؛ `temp_parent` بدون فرزند ⇒ ۴۰۱/۴۰۳؛ JWT با `sub_role=admin` جعلی برای کاربر شاگرد ⇒ ۴۰۳ (نقش از DB) | ✅ | `test_role_12_*`, `test_role_12b_*` |
| ۱۳. اعلان: صندوق هر کاربر فقط ردیف خودش+نقش خودش؛ خواندن اعلان دیگری اثر ندارد؛ `read_all` فقط روی خودش | ✅ | `test_role_13_*` |
| ۶ (واحد). `resolve_notification_recipient` برای user_id خالی shadow-user می‌سازد (نه Student.id) و برای subject ناموجود `None` می‌دهد | ✅ | `test_recipient_resolver_*` |
| کنترل مثبت. مسیر دستی یادآوری قسط ⇒ (501,student)+(601,parent) | ✅ | `test_manual_reminder_endpoint_uses_user_ids` |

## ۴) موارد نیازمند تصمیم محصولی (policy مبهم — نه باگ قطعی)
1. **گیت `parent_mobile` روی اعلان شاگرد:** در `main.py:445` کل بلوک با `if st and st.parent_mobile:` شرطی شده؛ اگر موبایل ولی ثبت نشده باشد، شاگردی که `user_id` دارد و قسطش معوق است **هیچ اعلانی** (نه SMS، نه in-app) نمی‌گیرد. تست مستندساز: `test_auto_reminder_silently_skips_student_when_parent_mobile_missing`.
2. **بدون اعتبارسنجی `recipient_user_id` در `NotificationService.send_notification`:** مقدار `None` را می‌پذیرد و ردیف بی‌صاحب/گم‌شده می‌سازد (کالرها باید None را skip کنند — الگوی `resolve_notification_recipient`). آیا باید defense-in-depth در سرویس اضافه شود؟
3. **جستجوی سراسری کارکنان:** `teacher` می‌تواند همه‌ی شاگردان را جستجو کند (`/students/search`, `/admin/students/search`) و لیست معلمان با موبایل را ببیند (`/teachers/list` فقط خودش برای معلم) — کامنت کد می‌گوید عامدانه «فقط کارکنان»؛ تأیید محصولی لازم است.
4. **پرداخت دستی برای معلم ممنوع است** (`/finance/pay` فقط admin/secretary؛ تست `test_role_11` ۴۰۳ را ثبت می‌کند) — آیا معلم باید بتواند رسید ثبت کند؟ (فعلاً policy صریح کد = نه.)
5. **`temp_parent` در مسیرهای `check_user_login`:** چون `UserSession.user_id = -1` است، پاسخ ۴۰۱ «کاربر یافت نشد» است نه ۴۰۳ «نقش نامعتبر» — رفتار امن است ولی پیام/کد برای کلاینت گویا نیست.

## ۵) محدودیت‌ها
- SQLite (in-memory / فایل tmp) — رفتار قفل/تراکنش با PostgreSQL یکسان نیست (اثر این ممیزی حداقلی است چون منطق نقش‌ها DB-agnostic است).
- `TestClient` رویداد startup اپ را اجرا می‌کند (worker کلاس زنده با `SessionLocal` واقعیِ `.env` روی `/tmp`) — همان الگوی تست‌های موجود پروژه.
- بررسی Android فقط استاتیک بود (صفر کامپایل/gradle) و صرفاً برای اثبات مصرف‌کننده‌ی واقعی مسیر `my_profile` استفاده شد.
- دیتابیس واقعی `gaj_db.db` دست‌نخورده: `sha256 = f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79` (قبل و بعد از اجرا یکسان).
