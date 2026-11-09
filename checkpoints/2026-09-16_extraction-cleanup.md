# Extraction + Cleanup — kharazmizip.zip → repo root — 2026-09-16

## خلاصه
- درخواست: استخراج کامل `kharazmizip.zip` به روت ریپازیتوری، حذف پوشه زیپ تکراری، و پوش به گیت‌هاب.
- نتیجه: 443 فایل با موفقیت استخراج، وریفای و پوش شد. زیپ حذف شد.

## Step 1 — استخراج
- `unzip -o kharazmizip.zip` به `/tmp/extract_test` (لاگ OK، No errors)
- `unzip -Z1 | wc -l` = 482 entry (شامل پوشه‌ها)، `grep -v "/$"` = 444 فایل
- بعد از حذف `.sudo_as_admin_successful` (فایل سیستمی 0-byte): **443** فایل تمیز
- کپی به روت: `KharazmiAdmin/` (251 فایل) + `Kharazmi_Server/` (90 فایل) + `checkpoints/` (102 فایل) = **443 فایل**

## Step 2 — وریفای قبل از حذف (طبق قانون جدید)
- `unzip -Z1 | sed 's|^kharazmizip/||' | grep -v "^\.sudo" | sort` vs `find KharazmiAdmin Kharazmi_Server checkpoints -type f | sort`
- `comm -23` و `comm -13` هر دو خالی → **صفر فایل کم/زیاد، 100% مطابقت**
- `unzip -t` → No errors detected
- `md5sum` نمونه‌ها: `main.py`, `models.py`, `AndroidManifest.xml` سالم
- `git ls-files | wc -l` = 443 → همه فایل‌ها track شدند

## Step 3 — حذف تکراری‌ها + گیت
- حذف `kharazmizip/` (پوشه تکراری داخل زیپ) — لوکال
- `git add KharazmiAdmin/ Kharazmi_Server/ checkpoints/` → commit `1ca3736` → push `arena/01a0a936-kharazmiapp`
- حذف `kharazmizip.zip` (998KB) → `git rm` → commit `d436a96` → push
- `git log --oneline` = 7ae3578 (base) → 1ca3736 (extract) → d436a96 (remove zip)
- `git status` → working tree clean

## Step 4 — قانون جدید (standing rule)
- از این به بعد: **هر تغییر → وریفای → checkpoint.md → git add/commit/push** (کاربر تاکید کرد)
- نام‌گذاری چک‌پوینت: `YYYY-MM-DD_<CATEGORY>-<slug>.md` مثل قبل (مثال: `2026-09-16_F-B1-...`)
- محتوای چک‌پوینت: عنوان، تاریخ، فایل‌های تغییر، تصمیمات طراحی، راستی‌آزمایی (no compile/run اگر ران نشده)

## وضعیت فعلی ریپازیتوری (2026-09-16)
- `KharazmiAdmin/` — اپ اندروید (Kotlin, compileSdk 34)
- `Kharazmi_Server/` — بک‌اند FastAPI + gaj_db.db + routers + tests
- `checkpoints/` — 102 → 103 فایل (این فایل جدید)
- بدون `kharazmizip*` — تمیز

## Next
- خواندن کامل 102 چک‌پوینت قبلی انجام شد (خلاصه در چت). آماده برای فیکس بعدی با همین workflow.
