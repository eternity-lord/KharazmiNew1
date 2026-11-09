# FIX F-R1 + F-R2 — route پروفایل دانش‌آموز + mapping اعلان قسط (۲۰۲۶-۰۹-۱۷)

برنچ: `arena/01a0aac2-kharazmiapp` | ریپو: `eternity-lord/KharazmiApp`
کامیت پایه: `d2333ee` (ممیزی نقش‌ها/اعلان‌ها با ۵ تست یافته‌محور که همین دو باگ را قرمز کرده بود).
سندباکس سالم بود: `HEAD=d2333ee` مطابق ریموت، درخت تمیز، وابستگی‌ها نصب، `.env` سندباکس موجود.

## ۰) محدوده
فقط دو باگ F-R1 و F-R2. هیچ policy جدیدی برای معلم / parent_mobile / temp_parent تعریف نشد؛
منطق مالی، مالیات، نقش‌ها و مسیرهای دیگر پروژه دست‌نخورده‌اند. DB واقعی (`gaj_db.db`) لمس نشد
(همه‌ی اجراها روی کپی `/tmp` یا DB درون‌حافظه/فایل موقت).

## ۱) baseline (قبل از fix، روی `d2333ee`)
| دستور | نتیجه |
|---|---|
| `python -m compileall Kharazmi_Server` | exit 0 |
| `pytest -q Kharazmi_Server/test_roles_installment_notifications_audit.py` | **27 passed / 5 failed** (5.86s) |
| `pytest -q Kharazmi_Server` | **611 passed / 5 failed** (53.30s) |

## ۲) failing-first (قبل از fix)
**F-R1:**
```
>   assert mine.status_code == 200, (...)
E   AssertionError: F-R1: /students/my_profile برای شاگرد = 422 (route shadowing) —
    {"detail":[{"type":"int_parsing","loc":["path","student_id"],"msg":"Input should be a valid integer",...}]}
E   assert 422 == 200
```
**F-R2:**
```
E   AssertionError: اعلان شاگرد باید به user_id=501 برود (Student.id=101 اشتباه است)؛
    actual=[(101, 'parent'), (101, 'student'), (104, 'parent'), (104, 'student')]
E   AssertionError: اعلان‌هایی با recipient_user_id=Student.id ساخته شد: [(1, 101, 'parent'), (2, 101, 'student')]
E   AssertionError: برای شاگرد ۱۰۴ اعلان با Student.id ساخته شد: [(3, 'parent'), (4, 'student')]
E   AssertionError: صندوق شاگرد ۵۰۱ باید دقیقاً یک اعلان قسط داشته باشد
```

## ۳) فایل‌های تغییرکرده
| فایل | تغییر |
|---|---|
| `Kharazmi_Server/routers/students.py` | جابه‌جایی بلوک `get_student_my_profile` به بالای route داینامیک + ۳ خط کامنت هشدار (بدنه‌ی تابع byte-identical) |
| `Kharazmi_Server/main.py` | بازنویسی بلوک ارسال اعلان در auto-reminder اقساط (استفاده از resolver مرکزی + skip به‌جای fallback) |
| `Kharazmi_Server/test_roles_installment_notifications_audit.py` | تبدیل ۵ تست یافته‌محور به رگرسیون + ۵ تست جدید (route resolution، mapping خالی، automation) |

## ۴) شرح fix

### F-R1 — route ثابت قبل از route داینامیک
- بلوک `@router.get("/students/my_profile")` (به‌همراه تابعش) از انتهای `students.py` به **قبل از**
  `@router.get("/students/{student_id}")` منتقل شد (الان خط ۴۴۰ در برابر ۵۹۹). در FastAPI ترتیب ثبت
  route تعیین‌کننده است؛ مسیر ثابت باید اول باشد.
- قرارداد Android تغییر نکرد: همان `@GET("students/my_profile")` (فایل `StudentPortalActivity.kt:41`)
  حالا درست پاسخ می‌گیرد؛ هیچ route جدید یا تغییر client اضافه نشد.
- ۳ خط کامنت «FIX (F-R1): این بلوک را پایین‌تر از route داینامیک منتقل نکنید» برای جلوگیری از بازگشت باگ.
- اثبات دست‌نخوردگی: بدنه‌ی `get_student_my_profile` و `get_student_profile` با نسخه‌ی `HEAD` **byte-identical**
  است؛ فقط یک بلوک جابه‌جا شده (diff کامل: ۰ خط گم‌شده).

### F-R2 — اعلان قسط با `User.id` (resolver مرکزی)
- در `main.py` بلوک auto-reminder اقساط حالا از `dependencies.resolve_notification_recipient(db, st.id, role)`
  استفاده می‌کند (همان helper مرکزی پروژه که مسیر دستی `finance.py` و `automation.py` هم بر آن استوارند):
  - نقش `student` ⇒ `Student.user_id`
  - نقش `parent` ⇒ `Student.parent_user_id`
  - اگر مقدار خالی باشد، helper همان `ensure_student_shadow_users` را اجرا می‌کند (رفتار موجود پروژه) و
    id واقعی `User` برمی‌گرداند؛ اگر رزولو نشود `None` ⇒ همان نقش **skip** می‌شود با log صریح
    (`⚠️ Installment reminder skipped (parent/student) for student {id}: no resolvable user_id`).
- هرگز `Student.id` و هرگز `None` به‌عنوان `recipient_user_id` فرستاده نمی‌شود (تست `..._never_none`).
- gateهای قبلی (از جمله `st.parent_mobile`) **دست‌نخورده** ماندند — هیچ policy جدیدی ساخته نشد.
- مسیر دستی `finance.py` و `automation.trigger_notification_action` تغییر نکردند (کنترل مثبت رگرسیون دارند).

## ۵) تست‌ها
جدید/به‌روزشده در `test_roles_installment_notifications_audit.py` (۳۲ ⇒ ۳۶ تست):
| تست | نقش |
|---|---|
| `test_role_09_student_reads_only_self` | ✅ رگرسیون F-R1 با TestClient: ۲۰۰، داده‌ی همان سشن (کلاس الف، نه ب)، مقاوم به `?student_id=102`، مسیر عددی سالم |
| `test_role_09c_numeric_route_and_role_policies_unchanged_after_fr1` | ✅ سیاست admin/secretary/teacher/parent/student روی مسیر عددی + ۴۰۱ برای نقش‌های غیرشاگرد روی my_profile + ۴۰۱ بدون توکن |
| `test_installment_notifications_use_user_ids_not_student_id` | ✅ (نام درخواستی) 501/student و 601/parent |
| `test_installment_notification_never_targets_student_id_namespace` | ✅ صفر ردیف با Student.id |
| `test_installment_notification_actual_recipient_is_user_id` | ✅ مقادیر واقعی پس از fix + SmsLog درست |
| `test_installment_notification_recipients_are_never_none` | ✅ صفر ردیف با recipient خالی |
| `test_each_user_only_sees_own_installment_notification` | ✅ صندوق ۵۰۱ و ۶۰۱ جدا |
| `test_auto_reminder_without_user_ids_never_falls_back_to_student_id` | ✅ بدون fallback |
| `test_auto_reminder_with_missing_parent_user_id_still_notifies_student` | ✅ اعلان شاگرد می‌رود، ولی رزولوشن امن |
| `test_auto_reminder_with_missing_user_id_never_uses_student_id` | ✅ بدون fallback/بدون خطا |
| `test_automation_notification_mapping_regression` | ✅ رگرسیون مسیر automation |
| `test_manual_reminder_endpoint_uses_user_ids` + `test_recipient_resolver_*` | ✅ رگرسیون resolver و مسیر دستی |
| `test_role_10/11/12/13` | ✅ regression کامل نقش‌ها/IDOR/temp_parent/توکن/مالکیت اعلان (بدون تغییر) |

## ۶) نتایج نهایی
| دستور | نتیجه |
|---|---|
| `python -m compileall Kharazmi_Server` | exit 0 |
| `pytest -q Kharazmi_Server/test_roles_installment_notifications_audit.py -vv` | **36 passed / 0 failed / 0 skipped** (7.47s) |
| `pytest -q Kharazmi_Server` | **620 passed / 0 failed / 0 skipped** (55.87s) |
| `import main` واقعی روی DB موقت | OK — 29 route |

## ۷) نتیجه‌ی TestClient واقعی برای route (F-R1)
```
GET /students/my_profile        (توکن شاگرد ۵۰۱)          → 200 ✅  (قبل: 422)
GET /students/my_profile?student_id=102 (توکن شاگرد ۵۰۱)  → 200 و همچنان داده‌ی خودِ ۱۰۱ (بدون IDOR)
GET /students/my_profile        (بدون توکن)                → 401 ✅
GET /students/my_profile        (admin/secretary/teacher/parent/unknown) → 401 (قرارداد خودِ endpoint، بدون تغییر)
GET /students/101               (شاگرد/ولی/معلم الف/ادمین) → 200 ✅
GET /students/102               (شاگرد/ولی/معلم الف)       → 403 ✅
```

## ۸) نتیجه‌ی mapping اعلان‌ها (Student.id=101 / user_id=501 / parent_user_id=601)
اجرای واقعی auto-reminder روی DB موقت (probe مستقل، خروجی عیناً):
```
notif#1: recipient_user_id=601 role=parent   | 💰 سررسید قسط شهریه فرزند شما
notif#2: recipient_user_id=501 role=student  | 💰 سررسید قسط شهریه شما
SmsLog groups: ['notif_parent_601', 'notif_student_501', ...]
هر ردیفی با شناسه‌ی Student.id (101/104/105/106/107)؟ خیر ✅
```
سناریوهای شناسه‌ی خالی (همان اجرا):
| شاگرد | وضعیت ورودی | نتیجه |
|---|---|---|
| 104 | بدون user_id و parent_user_id | shadow-user ساخته شد ⇒ (504,'student') و (604,'parent') — نه ۱۰۴ |
| 106 | user_id=506، parent_user_id خالی | اعلان شاگرد (506) ✅ + shadow-user ولی (608) — نه ۱۰۶ |
| 107 | user_id خالی، parent_user_id=607 | shadow-user شاگرد (507) ✅ + اعلان ولی (607) — نه ۱۰۷ |

## ۹) ایمنی DB و git
- `sha256 gaj_db.db = f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79` — قبل و بعد یکسان ✅
- `git status` فقط سه فایل بالا؛ `git diff --stat`: main.py ‎+47/-‎، students.py (جابه‌جایی بلوک)، تست ‎+229.

## ۱۰) محدودیت‌ها
- تست‌ها روی SQLite (فایل موقت/درون‌حافظه) اجرا شدند؛ رفتار route resolution و mapping نقش‌ها DB-agnostic است.
- `my_profile` برای نقش‌های غیرشاگرد ۴۰۱ می‌دهد (قرارداد فعلی endpoint) — طبق محدودیت تسک تغییر داده نشد.
