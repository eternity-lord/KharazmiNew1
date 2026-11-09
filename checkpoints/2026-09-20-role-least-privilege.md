# چک‌پوینت A1 — کمترین سطح دسترسی برای نقش کاربران (`sub_role`)

- **عنوان:** رفع ارتقای سطح دسترسی در کاربران بدون نقش (legacy) — سیاست fail-closed
- **تاریخ:** 2026-09-20
- **Branch:** `arena/01a0bf8d-kharazmiapp` (تنها branch کاری)
- **Base HEAD:** `68d2fb2041787f6fd72999357e3f43d3fac7b76b` (`docs: record institute roadmap decisions`)
- **نوبت:** ۱ از نقشه‌ی اجرای `checkpoints/2026-09-20-open-decisions.md` (فاز A — امنیت داده، اولویت ۱)
- **اصل حاکم:** «کمترین سطح دسترسی» — هیچ‌کس با ابهام، مدیر آموزشگاه فرض نمی‌شود.

---

## ۱) مشکل (سه لایه‌ی مستقل که همه به یک نتیجه می‌رسیدند)

**نتیجه‌ی مشترک:** هر کاربری که نقشش ثبت نشده بود، **ادمین آموزشگاه** فرض می‌شد.

| لایه | کد قبلی | اثر |
|---|---|---|
| گاردها | `sub_role = user.sub_role if user.sub_role else "admin"` در `check_admin_access`، `check_admin_or_secretary_access`، `check_user_login` | کاربر بی‌نقش ⇒ دسترسی کامل به همه‌ی اندپوینت‌های ادمین (مالی، حذف کلاس، تنظیمات، گزارش‌ها) |
| ورود | `sub_role = admin.sub_role if admin.sub_role else "admin"` در `routers/auth.py` | سایهٔ معلم/شاگرد legacy بدون `sub_role` **توکن با نقش admin** می‌گرفت |
| مدل + migration | `models.User.sub_role = Column(String, default="admin")` و در `main.py`: `UPDATE users SET sub_role='admin' WHERE sub_role IS NULL` | الف) هر کاربر تازه که نقشش تعیین نشود، خودکار ادمین می‌شود ب) هنگام ارتقای دیتابیس‌های قدیمی، **همه‌ی** ردیف‌ها (از جمله سایه‌های شاگرد/ولی) «admin» می‌شوند |

**چرا مهم است (آموزشگاه):** سایه‌ی شاگرد/ولی/معلم ساخته‌شده پیش از افزوده‌شدن ستون، عملاً می‌توانست به گزارش‌های مالی، حذف کلاس‌ها و تنظیمات آموزشگاه دسترسی بگیرد — یک نشتِ مالکیتی، نه فقط یک باگ UI.

---

## ۲) رفتار قبل و بعد

| حالت کاربر | قبل | بعد |
|---|---|---|
| ادمین واقعی (`sub_role='admin'`) | ✅ ۲۰۰ | ✅ ۲۰۰ (بی‌تغییر) |
| ادمین legacy فقط با `role='admin'` | ✅ ۲۰۰ | ✅ ۲۰۰ (سازگاری حفظ شد) |
| کاربر با `role` خالی و `sub_role` خالی (legacy بی‌اطلاع) | ✅ ۲۰۰ | ✅ ۲۰۰ (سازگاری حفظ شد) |
| **سایهٔ معلم legacy** (`role='teacher'`, بدون `sub_role`) | ❌ ۲۰۰ (ادمین!) | ✅ **۴۰۳** + ورود با نقش `teacher` |
| **سایهٔ شاگرد/ولی legacy** | ❌ ۲۰۰ (ادمین!) | ✅ **۴۰۳** |
| `sub_role` فقط فاصله (`"   "`) | ❌ ۲۰۰ (ادمین) | ✅ مثل «خالی» ⇒ بر اساس `role` |
| منشی (`sub_role='secretary'`) | ۴۰۳ روی گارد ادمین، ۲۰۰ روی گارد کارکنان | بی‌تغییر |
| نقش ناشناخته (مثل `مهمان`) | ❌ ادمین | ✅ ۴۰۳ (fail-closed) |
| ساخت کاربر جدید بدون تعیین نقش (ORM) | `admin` خودکار | `NULL` ⇒ نقش از `role` تعیین می‌شود |
| migration دیتابیس قدیمی | همه‌ی ردیف‌ها `admin` | نقش‌آگاه: teacher/student/parent/secretary + فقط ادمین‌های واقعی `admin` |

---

## ۳) فایل‌های تغییرکرده

| فایل | تغییر |
|---|---|
| `Kharazmi_Server/dependencies.py` | helper مشترک `resolve_effective_sub_role(user)` + استفاده در سه گارد (`check_admin_access`، `check_admin_or_secretary_access`، `check_user_login`) |
| `Kharazmi_Server/models.py` | حذف `default="admin"` از `User.sub_role` — نقش دیگر خودکار به مدیر ارتقا نمی‌یابد |
| `Kharazmi_Server/main.py` | migration نقش‌آگاه: `ALTER TABLE ... ADD COLUMN sub_role VARCHAR;` (بدون DEFAULT) + `UPDATE ... CASE` بر اساس `role` و پیشوند `username` |
| `Kharazmi_Server/routers/auth.py` | ورود: نقش با همان helper تعیین می‌شود (سایهٔ معلم legacy توکن admin نمی‌گیرد) |
| `Kharazmi_Server/routers/reports.py` | همان اصلاح در مسیر گزارش (سهم معلم/آموزشگاه فقط برای ادمین واقعی) + import helper |
| `Kharazmi_Server/test_role_least_privilege.py` | **جدید** — ۱۴ تست (لایه‌ی منطقی + گاردها + ورود + migration واقعی) |

**هیچ migration/schema-change در دیتابیس اجرا نشد** — تغییر `models.py` فقط پیش‌فرض سمت پایتون است (ستون `sub_role` از قبل در DBها با همان نوع وجود دارد) و مسیر ارتقای دیتابیس‌های قدیمی هم اصلاح شد (فقط برای DBهایی که هنوز این ستون را ندارند اجرا می‌شود).

---

## ۴) تست‌ها

| اجرا | نتیجه |
|---|---|
| `test_role_least_privilege.py` (جدید، ۱۴ تست) | ✅ **14 passed** |
| **اثبات رگرسیون** — همان تست‌ها روی HEAD قبل از فیکس (`68d2fb2`، با shim برای نماد جدید) | ✅ **8 failed / 6 passed** |
| **کل suite از ریشهٔ ریپو** (`pytest Kharazmi_Server -q`) | ✅ **815 passed / 0 failed** (قبل: ۸۰۱ تست) |
| DB واقعی `gaj_db.db` | دست‌نخورده (md5 `f048f8d118b33c4eaa944490594121d7`) |

**پوشش تست‌ها:**
- منطق نقش: `sub_role` صریح برنده است · `role` جایگزین می‌شود · `""`/فاصله مثل خالی · ادمین legacy ادمین می‌ماند · نقش ناشناخته ادمین نمی‌شود
- گاردها (HTTP واقعی): معلم/شاگرد/ولی legacy روی `/admin/deleted_classes` ⇒ **۴۰۳** · ادمین‌ها ⇒ ۲۰۰ · منشی: گارد ادمین ۴۰۳ ولی گارد کارکنان ۲۰۰ · بدون توکن ۴۰۱
- ورود: سایهٔ معلم legacy با رمز صحیح ⇒ توکن با نقش **غیر admin** (هم پاسخ، هم ردیف `UserSession`)
- **migration واقعی:** `main.auto_patch_database()` روی یک DB موقت با جدول `users` **بدون** ستون `sub_role` ⇒ معلم/شاگرد/ولی نقش درست، ادمین واقعی ادمین، و **هیچ‌کس بی‌دلیل ارتقا نمی‌یابد**

---

## ۵) ریسک‌ها و محدودیت‌های باقی‌مانده

1. **ردیف‌های موجود که از قبل اشتباهاً `admin` شده‌اند اصلاح نمی‌شوند.** اگر دیتابیس تولیدی از قبل ارتقا یافته، ممکن است سایه‌های شاگرد/ولی با `sub_role='admin'` ذخیره شده باشند. این تسک فقط migration **آینده** و گاردها را امن می‌کند. SQL بازبینی (فقط خواندن) برای اجرای دستی شما:
   ```sql
   SELECT id, username, role, sub_role FROM users
   WHERE sub_role = 'admin' AND (role IN ('teacher','student','parent') OR username LIKE 'student:%' OR username LIKE 'parent:%' OR username LIKE 'teacher:%');
   ```
   در دیتابیس فعلی (`gaj_db.db`) جدول `users` **خالی** است ⇒ موردی برای پاک‌سازی وجود ندارد. اگر روی DB تولیدی خروجی داشت، با تأیید صریح شما در یک تسک داده‌ای اصلاح می‌شود (الان دست نزدم).
2. **کامپایل Kotlin بررسی نشد** — این تسک هیچ تغییری در اپ اندروید ندارد.
3. تغییر رفتار عمدی: کاربر بی‌نقشِ غیرمدیر دیگر ۴۰۳ می‌گیرد. اگر در عمل کاربری بود که «باید» ادمین می‌بود ولی نقشش ثبت نشده، باید نقشش را صریحاً در پنل تنظیم کنید (fail-closed به‌عمد).

---

## ۶) Commit و Push

- **Commit SHA:** در گزارش نهایی پس از commit ثبت می‌شود؛ SHA داخل همان commit قابل درج نیست.
- **وضعیت Push:** در گزارش نهایی اعلام می‌شود.
- **Commit message:** `fix: enforce least privilege for user roles`
- **Branch:** `arena/01a0bf8d-kharazmiapp` — PR/merge بدون دستور صریح ساخته نمی‌شود.
- **نوبت بعدی نقشه:** A2 — یکسان‌سازی مسیر سوم حذف کلاس (`DELETE /admin/reject_class/{id}`).
