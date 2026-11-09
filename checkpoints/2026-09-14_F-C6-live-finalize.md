# F-C6 impl — finalize زنده (a) راستر خالی=صفر حاضر + (c) گیت اتمیک ورکر/دستی (+F-C8) — 2026-09-14

## Edits (سریال)
- `routers/attendance.py` finalize (F-C6a): حذف fallback «همه حاضر»؛ items خالی → submit → SessionLog صفرحاضر + صفر تومان
- `routers/attendance.py` +`claim_live_session_for_finalize(db,id,auto)` (F-C6c): UPDATE مشروط LIVE→FINALIZING + rowcount (H8-P4)؛ بدون کامیت (کرش→rollback→LIVE)
- `routers/attendance.py` end_live: گیت M14 جایگزین با تسخیر مشترک؛ retry همان (FINALIZING→LIVE)
- `main.py` worker: تسخیر با auto=True (پرچم ended_automatically داخل claim)؛ بازنده skip؛ خطا→LIVE+commit (retry تیک بعد)
- قدم ۲: date دست‌نخورده (کامنت M14)
- F-C8 (یافته زنده، مسدودکننده): گارد H-caller پارامتر `_` نداشت → هر end_live از اول ۵۰۰ می‌داد. فیکس: پارامتر `_system_caller` در submit + skip گارد برای "live_system" (مالکیت در end_live احراز شده) + اصلاح call site

## Verify (فقط /tmp کپی)
- AST OK؛ import main CLEAN؛ لایو ۴/۴: A راسترخالی‌دستی (att=0، tx ثابت)؛ D رگرسیون راستر (۱حاضر شارژ درست ۱۰۰k/۵۰k)؛ C همزمانی ([۲۰۰،۴۰۰] + تک‌سشن)؛ B ورکر واقعی (بک‌دیت ۲۰۰دقیقه → ENDED+auto در ~۳۰ثانیه، att=0، tx ثابت). صفر Traceback. هش teardown پایدار.

## ⚠️ INCIDENT (mine): create_admin به پروداکشن نوشت
- `scripts/create_admin.py` آرگومان `--db` را نادیده می‌گیرد (argparse ندارد؛ از engine پیش‌فرض استفاده می‌کند) → ردیف ادمین تستی (id=1) در gaj_db.db اصلی + هش عوض شد
- جبران: DELETE ردیف (کامیت‌شده، تأیید users=0)؛ شمارش‌ها سالم (students 2, teachers 1, courses 1, txns 1, enroll 1, rules 8)؛ بدون sqlite_sequence
- بازیابی بایتی ناممکن → هش کانونیکال جدید: f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79
- درس ماندگار: create_admin فقط با DATABASE_URL=... env (هرگز --db) + همیشه بلافاصله users کپی/اصلی را چک کن

## lessons
- venv اسنپشات نمی‌شود: اول هر سشن verify pip install -r requirements.txt (شامل reportlab)
- گارد تداخل زمانی کلاس: تست‌ها روز/ساعت متفاوت؛ گارد H7 شعبه: UPDATE branch_id=1 روی کپی
- ۱۴۰۴/۰۶/۲۱=۲۰۲۵/۰۹/۱۲؛ ریت‌لیمیت لاگین: توکن از user_sessions کپی
- adjacent (بدون فیکس): ورکر روی کلاس معلق (H10→۴۰۳) هر ۶۰ثانیه retry بی‌پایان می‌زند
