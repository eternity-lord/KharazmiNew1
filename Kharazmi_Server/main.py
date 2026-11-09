import datetime
import os
from typing import List, Optional, Union

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import text

import models
from models import (
    Attendance, Course, Enrollment, Grade, InstituteShare, SessionLog, SmsLog, Student, Teacher, Transaction, User, UserSession, Settlement, Installment, ParentOTP, PricingTable
)
from routers import auth, students, teachers, classes, finance, reports, attendance, admin, parent, homework, calendar, messages, exams, crm, branches, automation, analytics, ai, audit, timeline, dunning, dashboard, exports, audit_trail

# ساخت اپلیکیشن
# FIX M2: مستندات تعاملی فقط در توسعه؛ در پروداکشن (ENV=production) خاموش.
_ENV = os.getenv("ENV", "development").lower()
app = FastAPI(
    title="Gaj Institute System",
    version="1.0.0",
    docs_url=None if _ENV == "production" else "/docs",
    redoc_url=None if _ENV == "production" else "/redoc",
    openapi_url=None if _ENV == "production" else "/openapi.json",
)

from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from dependencies import limiter, check_user_login
from storage import storage_dir, resolve_existing

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

from fastapi.middleware.cors import CORSMiddleware
# FIX M1: بدون "*" — مصرف‌کننده‌ها اپ موبایل (native، بی‌نیاز از CORS) و پورتال ولی
# (same-origin، بی‌نیاز از CORS) هستند؛ دامنه‌ی اضافه فقط از ENV می‌آید.
_CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi.responses import FileResponse

class PublicRouteIsolationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        host = request.headers.get("host", "").lower()
        path = request.url.path.lower()
        
        # Check if the request is coming via Cloudflare Quick Tunnel (*.trycloudflare.com)
        is_public_tunnel = ".trycloudflare.com" in host or "trycloudflare.com" == host
        
        if is_public_tunnel:
            # Strictly allow ONLY routes starting with /parent/ or /uploads/ (for child profile photo)
            allowed = (
                path.startswith("/parent") or 
                path.startswith("/uploads") or
                path == "/favicon.ico"
            )
            if not allowed:
                # Return raw 404 to pretend these endpoints don't exist publicly!
                return Response(content="Not Found", status_code=404)
                
        return await call_next(request)

app.add_middleware(PublicRouteIsolationMiddleware)


# FIX M26: جلوگیری از MIME-sniffing مرورگر روی همه‌ی پاسخ‌ها (از جمله /uploads و پورتال).
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# FIX Audit-Trail: میدل‌ور زمینه‌ی کاربر برای listener های لاگ مالی (فقط متدهای تغییردهنده).
app.add_middleware(audit_trail.AuditContextMiddleware)

# FIX M3: پوشه‌ی آپلود نگه داشته می‌شود ولی سرو عمومی StaticFiles حذف شد.
# FIX(storage): پوشهٔ آپلود با مسیر مطلقِ مستقل از cwd ساخته می‌شود (قبلاً "uploads/profiles"
# یعنی بسته به پوشهٔ اجرای سرور، فایل‌ها جای دیگری می‌رفتند و سرو شدنشان ۴۰۴ می‌شد).
storage_dir("profiles")


# FIX M3: سرو فایل آپلودی فقط برای لاگین‌کرده‌ها (به‌جای StaticFiles عمومی).
# NOTE (M3-portal): پورتال وب <img> بدون هدر دارد — راه‌حل: blob-fetch در parent.py (پياده شد: loadAuthImage + data-auth-src).
@app.get("/uploads/{filename}")
def serve_upload(filename: str, _: str = Depends(check_user_login)):
    if not filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="نام فایل معتبر نیست")
    safe = os.path.basename(filename)
    if not safe or safe.startswith("."):
        raise HTTPException(status_code=400, detail="نام فایل معتبر نیست")
    # FIX(storage): اول ریشهٔ فعلی، بعد مسیرهای قدیمی (سازگاری عقب‌رو ⇒ عکس‌های قدیمی ۴۰۴ نمی‌شوند)
    path = resolve_existing("profiles", safe)
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="فایل یافت نشد")
    return FileResponse(path)

# اتصال به دیتابیس
models.Base.metadata.create_all(bind=models.engine)

# FIX Audit-Trail: فعال‌سازی listener های ردگیری تغییرات مالی (جدول financial_audit_logs
# هم در همین فراخوانی idempotent ساخته می‌شود).
audit_trail.setup_audit_listeners()

# پچر خودکار جداول دیتابیس
def auto_patch_database():
    db = models.SessionLocal()
    
    def column_exists(table_name, col_name):
        try:
            if "sqlite" in str(db.bind.url):
                cursor = db.execute(text(f"PRAGMA table_info({table_name});"))
                for row in cursor.fetchall():
                    if row[1] == col_name:
                        return True
                return False
            else:
                res = db.execute(text(
                    f"SELECT column_name FROM information_schema.columns "
                    f"WHERE table_name='{table_name}' AND column_name='{col_name}';"
                )).first()
                return res is not None
        except Exception as _exists_err:
            # FIX L12: خطای واقعی (نه «ستون نیست») بی‌صدا قورت داده نمی‌شود — هشدار چاپ می‌شود؛
            # رفتار fallback (False یعنی «پچ را بزن») نگه داشته شد تا خودترمیمی نشکند.
            print(f"⚠️ Warning during column_exists('{table_name}', '{col_name}'): {_exists_err}")
            return False

    try:
        # ایجاد شعبه پیش‌فرض برای همگام‌سازی داده‌های قدیمی (Idempotent)
        try:
            from models import Branch
            # Ensure table exists first by creating metadata
            models.Base.metadata.create_all(bind=models.engine)
            default_branch = db.query(Branch).filter(Branch.id == 1).first()
            if not default_branch:
                print("🔧 Creating default central branch for backward compatibility...")
                db.execute(text(
                    "INSERT INTO branches (id, name, address, phone, manager, active) "
                    "VALUES (1, 'شعبه مرکزی', 'تهران، خیابان ولیعصر', '021-88888888', 'مدیریت کل', 1);"
                ))
                db.commit()
                print("✅ Default branch created successfully.")
        except Exception as b_err:
            print(f"⚠️ Warning during branch backfill: {b_err}")
            db.rollback()

        # Seed default automation rules (Idempotent)
        try:
            from models import AutomationRule
            # Ensure table exists first by creating metadata
            models.Base.metadata.create_all(bind=models.engine)
            rule_count = db.query(AutomationRule).count()
            if rule_count == 0:
                print("🔧 Seeding 8 default automation rules...")
                default_rules = [
                    AutomationRule(id=1, name="Attendance < 80%", condition_type="attendance_low", threshold=80.0, action_type="parent_notification", active=True),
                    AutomationRule(id=2, name="Absence >= 2", condition_type="absence_high", threshold=2.0, action_type="parent_alert", active=True),
                    AutomationRule(id=3, name="Installment due tomorrow", condition_type="installment_due", threshold=1.0, action_type="parent_notification", active=True),
                    AutomationRule(id=4, name="Overdue installment", condition_type="installment_overdue", threshold=0.0, action_type="parent_notification", active=True),
                    AutomationRule(id=5, name="Homework deadline < 24h", condition_type="homework_deadline", threshold=24.0, action_type="student_notification", active=True),
                    AutomationRule(id=6, name="Grade below 10", condition_type="grade_low", threshold=10.0, action_type="parent_alert", active=True),
                    AutomationRule(id=7, name="Student inactive > 15 days", condition_type="student_inactive", threshold=15.0, action_type="crm_reminder", active=True),
                    AutomationRule(id=8, name="CRM Lead uncontacted > 5 days", condition_type="lead_uncontacted", threshold=5.0, action_type="crm_reminder", active=True),
                ]
                db.add_all(default_rules)
                db.commit()
                print("✅ 8 default automation rules seeded.")
        except Exception as r_err:
            print(f"⚠️ Warning during automation rule seed: {r_err}")
            db.rollback()

        # Check & Add 'sub_role' in 'users' table
        if not column_exists('users', 'sub_role'):
            print("🔧 Auto-patching database: Adding 'sub_role' to 'users' table...")
            # FIX(A1): ستون بدون DEFAULT ساخته می‌شود تا ردیف‌های legacy با NULL بمانند و
            # بتوان نقش واقعی‌شان را تعیین کرد (DEFAULT 'admin' همه را مدیر می‌کرد).
            db.execute(text("ALTER TABLE users ADD COLUMN sub_role VARCHAR;"))
            # FIX(A1): بک‌فیل نقش‌آگاه — هر کاربر نقش واقعی خودش را می‌گیرد و فقط کاربرانی که
            # role آن‌ها خالی/«admin» است ادمین می‌مانند (سازگاری با ادمین‌های legacy).
            # پیش‌تر همهٔ ردیف‌ها «admin» می‌شدند ⇒ سایهٔ معلم/شاگرد/ولی به سطح دسترسی مدیر ارتقا می‌یافت.
            db.execute(text(
                "UPDATE users SET sub_role = CASE "
                "WHEN role IN ('teacher', 'student', 'parent', 'secretary') THEN role "
                "WHEN username LIKE 'teacher:%' THEN 'teacher' "
                "WHEN username LIKE 'student:%' THEN 'student' "
                "WHEN username LIKE 'parent:%' THEN 'parent' "
                "ELSE 'admin' END "
                "WHERE sub_role IS NULL OR TRIM(sub_role) = ''"
            ))
            db.commit()

        # Check & Add 'profile_image' in 'students' table
        if not column_exists('students', 'profile_image'):
            print("🔧 Auto-patching database: Adding 'profile_image' to 'students' table...")
            db.execute(text("ALTER TABLE students ADD COLUMN profile_image VARCHAR;"))
            db.commit()

        # Check & Add 'discount_type' and 'discount_value' in 'enrollments' table
        if not column_exists('enrollments', 'discount_type'):
            print("🔧 Auto-patching database: Adding 'discount_type' to 'enrollments' table...")
            db.execute(text("ALTER TABLE enrollments ADD COLUMN discount_type VARCHAR DEFAULT 'none';"))
            db.execute(text("UPDATE enrollments SET discount_type = 'none' WHERE discount_type IS NULL;"))
            db.commit()

        if not column_exists('enrollments', 'discount_value'):
            print("🔧 Auto-patching database: Adding 'discount_value' to 'enrollments' table...")
            db.execute(text("ALTER TABLE enrollments ADD COLUMN discount_value BIGINT DEFAULT 0;"))
            db.execute(text("UPDATE enrollments SET discount_value = 0 WHERE discount_value IS NULL;"))
            db.commit()

        # بررسی و پچ خودکار تمام ستون‌های جدید تاریخی دیتابیس (idempotent و امن)
        patches = [
            # FIX: Bugs 13/14 - upgrade existing databases as well as fresh model-created schemas.
            ("enrollments", "is_deleted", "BOOLEAN NOT NULL DEFAULT FALSE", None),
            ("installments", "is_deleted", "BOOLEAN NOT NULL DEFAULT FALSE", None),
            ("session_logs", "is_deleted", "BOOLEAN NOT NULL DEFAULT FALSE", None),
            ("users", "branch_id", "INTEGER", "UPDATE users SET branch_id = 1 WHERE branch_id IS NULL;"),
            ("teachers", "branch_id", "INTEGER", "UPDATE teachers SET branch_id = 1 WHERE branch_id IS NULL;"),
            ("students", "branch_id", "INTEGER", "UPDATE students SET branch_id = 1 WHERE branch_id IS NULL;"),
            ("courses", "branch_id", "INTEGER", "UPDATE courses SET branch_id = 1 WHERE branch_id IS NULL;"),
            ("enrollments", "branch_id", "INTEGER", "UPDATE enrollments SET branch_id = 1 WHERE branch_id IS NULL;"),
            ("transactions", "branch_id", "INTEGER", "UPDATE transactions SET branch_id = 1 WHERE branch_id IS NULL;"),
            ("rooms", "branch_id", "INTEGER", "UPDATE rooms SET branch_id = 1 WHERE branch_id IS NULL;"),
            ("students", "is_suspended", "BOOLEAN DEFAULT FALSE", "UPDATE students SET is_suspended = FALSE WHERE is_suspended IS NULL;"),
            ("courses", "is_suspended", "BOOLEAN DEFAULT FALSE", "UPDATE courses SET is_suspended = FALSE WHERE is_suspended IS NULL;"),
            ("courses", "is_deleted", "BOOLEAN DEFAULT FALSE", "UPDATE courses SET is_deleted = FALSE WHERE is_deleted IS NULL;"),
            ("teachers", "is_deleted", "BOOLEAN DEFAULT FALSE", "UPDATE teachers SET is_deleted = FALSE WHERE is_deleted IS NULL;"),
            ("students", "is_deleted", "BOOLEAN DEFAULT FALSE", "UPDATE students SET is_deleted = FALSE WHERE is_deleted IS NULL;"),
            ("students", "user_id", "INTEGER", None),
            ("students", "parent_user_id", "INTEGER", None),
            ("courses", "class_type", "VARCHAR DEFAULT 'خصوصی'", "UPDATE courses SET class_type = 'خصوصی' WHERE class_type IS NULL;"),
            ("courses", "rule_prepay_institute", "BOOLEAN DEFAULT FALSE", "UPDATE courses SET rule_prepay_institute = FALSE WHERE rule_prepay_institute IS NULL;"),
            ("courses", "rule_prepay_teacher", "BOOLEAN DEFAULT FALSE", "UPDATE courses SET rule_prepay_teacher = FALSE WHERE rule_prepay_teacher IS NULL;"),
            ("courses", "rule_calc_absent", "BOOLEAN DEFAULT TRUE", "UPDATE courses SET rule_calc_absent = TRUE WHERE rule_calc_absent IS NULL;"),
            ("courses", "is_admin_approved", "BOOLEAN DEFAULT FALSE", "UPDATE courses SET is_admin_approved = FALSE WHERE is_admin_approved IS NULL;"),
            # گروه ۶: workflow کلاس و کنترل توقف/ظرفیت؛ همه idempotent و بدون تغییر دادهٔ موجود.
            ("courses", "is_paused", "BOOLEAN DEFAULT FALSE", "UPDATE courses SET is_paused = FALSE WHERE is_paused IS NULL;"),
            ("courses", "capacity", "INTEGER", None),
            ("courses", "rejection_reason", "TEXT", None),
            ("courses", "pending_since", "TIMESTAMP", None),
            ("settlements", "session_ids_json", "TEXT", None),
            ("settlements", "payout_transaction_id", "INTEGER", None),
            ("settlements", "is_reversed", "BOOLEAN DEFAULT FALSE", "UPDATE settlements SET is_reversed = FALSE WHERE is_reversed IS NULL;"),
            ("settlements", "reversal_reason", "TEXT", None),
            ("settlements", "reversed_at", "TIMESTAMP", None),
            ("transactions", "settlement_id", "INTEGER", None),
            ("courses", "bg_color", "VARCHAR DEFAULT '#FFFFFF'", "UPDATE courses SET bg_color = '#FFFFFF' WHERE bg_color IS NULL;"),
            ("courses", "teacher_session_price", "BIGINT DEFAULT 0", "UPDATE courses SET teacher_session_price = 0 WHERE teacher_session_price IS NULL;"),
            ("transactions", "type", "VARCHAR", None),
            ("transactions", "share_teacher", "BIGINT DEFAULT 0", "UPDATE transactions SET share_teacher = 0 WHERE share_teacher IS NULL;"),
            ("transactions", "share_institute", "BIGINT DEFAULT 0", "UPDATE transactions SET share_institute = 0 WHERE share_institute IS NULL;"),
            ("transactions", "target_wallet", "VARCHAR", None),
            ("transactions", "is_deleted", "BOOLEAN DEFAULT FALSE", "UPDATE transactions SET is_deleted = FALSE WHERE is_deleted IS NULL;"),
            ("transactions", "is_reversed", "BOOLEAN DEFAULT FALSE", "UPDATE transactions SET is_reversed = FALSE WHERE is_reversed IS NULL;"),
            ("attendances", "is_billed", "BOOLEAN DEFAULT FALSE", "UPDATE attendances SET is_billed = FALSE WHERE is_billed IS NULL;"),
            ("attendances", "excused", "BOOLEAN DEFAULT FALSE", "UPDATE attendances SET excused = FALSE WHERE excused IS NULL;"),
            # FIX (F-S2): آرشیو نرم حضور — دیتابیس‌های قدیمی ستون را ندارند؛ پیش‌فرض FALSE یعنی
            # ردیف‌های موجود «فعال» می‌مانند (هیچ سابقه‌ای بی‌دلیل آرشیو نمی‌شود). idempotent است
            # چون فقط وقتی column_exists منفی باشد ALTER می‌خورد.
            ("attendances", "is_deleted", "BOOLEAN DEFAULT FALSE", "UPDATE attendances SET is_deleted = FALSE WHERE is_deleted IS NULL;"),
            ("teachers", "wallet_balance", "BIGINT DEFAULT 0", "UPDATE teachers SET wallet_balance = 0 WHERE wallet_balance IS NULL;"),
            ("students", "version", "INTEGER DEFAULT 1", "UPDATE students SET version = 1 WHERE version IS NULL;"),
            ("teachers", "version", "INTEGER DEFAULT 1", "UPDATE teachers SET version = 1 WHERE version IS NULL;"),
            ("teachers", "teacher_code", "INTEGER", None),
            ("students", "student_code", "INTEGER", None),
            ("session_logs", "session_code", "INTEGER", None),
            ("transactions", "remittance_number", "INTEGER", None),
            # FIX (idempotency-gap): مدل idempotency_key دارد (nullable+unique) ولی پچ نبود —
            # دیتابیس‌های قدیمی ستون را نداشتند و لمس ORM (فایننس/بک‌فیل) warn/خطا می‌داد.
            # FIX (sqlite-uq): بدون UNIQUE اینلاین — SQLite روی ADD COLUMN خطای
            # «Cannot add a UNIQUE column» می‌دهد؛ یکتایی با ایندکس جداگانه پایین اعمال می‌شود.
            ("transactions", "idempotency_key", "VARCHAR", None),
            ("transactions", "session_id", "INTEGER", None),
            # حواله‌ی «برای N جلسه»: ستون اختیاری گزارشی؛ ردیف‌های قدیمی NULL می‌مانند (بی‌اثر روی مالی).
            ("transactions", "sessions_covered", "INTEGER", None),
            ("institute_settings", "footer_text", "VARCHAR DEFAULT 'با تشکر'", None),
            ("institute_settings", "card_number", "VARCHAR DEFAULT '۶۰۳۷۹۹۷۹۷۹۷۹۷۹۷۹'", None),
            ("institute_settings", "manager_mobile_1", "VARCHAR DEFAULT '09121112222'", None),
            ("institute_settings", "manager_mobile_2", "VARCHAR DEFAULT '09123334444'", None),
            ("institute_settings", "card_number_1", "VARCHAR DEFAULT '۶۰۳۷۹۹۷۹۷۹۷۹۷۹۷۹'", None),
            ("institute_settings", "card_holder_1", "VARCHAR DEFAULT 'خانم لطفی'", None),
            ("institute_settings", "card_number_2", "VARCHAR DEFAULT '۵۸۹۲۱۰۱۰۱۰۱۰۱۰۱۰'", None),
            ("institute_settings", "card_holder_2", "VARCHAR DEFAULT 'آقای علوی'", None),
            ("institute_settings", "teachers_active", "BOOLEAN DEFAULT TRUE", None),
            ("courses", "room_id", "INTEGER", None),
            ("institute_settings", "live_session_max_minutes", "INTEGER DEFAULT 180", None),
            ("institute_settings", "teacher_settlement_alert_days", "INTEGER DEFAULT 30", "UPDATE institute_settings SET teacher_settlement_alert_days = 30 WHERE teacher_settlement_alert_days IS NULL;"),
            ("crm_leads", "branch_id", "INTEGER DEFAULT 1", "UPDATE crm_leads SET branch_id = 1 WHERE branch_id IS NULL;"),
            ("crm_leads", "converted_at", "TIMESTAMP", None),
            ("crm_leads", "converted_student_id", "INTEGER", "UPDATE crm_leads SET converted_student_id = (SELECT students.id FROM students WHERE students.student_mobile = crm_leads.mobile LIMIT 1) WHERE status = 'REGISTERED' AND converted_student_id IS NULL;"),
            ("session_logs", "start_time", "VARCHAR", None),
            ("session_logs", "end_time", "VARCHAR", None),
            ("session_logs", "absent_penalty_teacher", "BIGINT DEFAULT 0", "UPDATE session_logs SET absent_penalty_teacher = 0 WHERE absent_penalty_teacher IS NULL;"),
            ("session_logs", "absent_penalty_institute", "BIGINT DEFAULT 0", "UPDATE session_logs SET absent_penalty_institute = 0 WHERE absent_penalty_institute IS NULL;"),
            # FIX M13: پوشش تجمعی پرداخت جزئی؛ قسط‌های تسویه‌شده‌ی قدیمی یعنی پوشش کامل.
            ("installments", "paid_amount", "BIGINT DEFAULT 0", "UPDATE installments SET paid_amount = CASE WHEN is_paid THEN amount ELSE 0 END WHERE paid_amount IS NULL;"),  # FIX (audit-v2/ livedb-comma): کامای گمشده — بدون آن کل auto_patch با TypeError می‌مرد.
            # FIX H8-gap: فلگ تسویه‌ی جریمه + بک‌فیل یک‌باره (فقط هنگام ADD COLUMN اجرا می‌شود):
            # جلسه‌ای که قبل از این فیکس تسویه شده (ردیف Present/Late با billed دارد) جریمه‌اش هم همان‌موقع
            # پرداخت شده پس TRUE؛ بقیه FALSE. (الگوی CASE مثل M13.)
            ("session_logs", "is_penalty_settled", "BOOLEAN DEFAULT FALSE", "UPDATE session_logs SET is_penalty_settled = CASE WHEN id IN (SELECT DISTINCT session_id FROM attendances WHERE is_billed = TRUE AND status IN ('Present', 'Late')) THEN TRUE ELSE FALSE END WHERE is_penalty_settled IS NULL;"),
            # FIX F-B1: ستون‌های کال‌بک پرداخت (درگاه همان‌مسیر + مهر تسخیر VERIFYING).
            ("payments", "gateway", "VARCHAR", None),
            ("payments", "claimed_at", "TIMESTAMP", None),
        ]

        for table, col, sql_type, update_sql in patches:
            if not column_exists(table, col):
                print(f"🔧 Auto-patching database: Adding '{col}' to '{table}' table...")
                db.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {sql_type};"))
                if update_sql:
                    db.execute(text(update_sql))
                db.commit()

        # FIX M5: تعریض students.wallet_* به BIGINT (فقط Postgres؛ SQLite نوع را enforce نمی‌کند
        # پس آنجا همان تعریف مدل کافی است). int→bigint تعریض بدون‌اتلاف است — دیتای موجود دست‌نخورده می‌ماند.
        try:
            if "sqlite" not in str(db.bind.url):
                for _wcol in ("wallet_teacher", "wallet_institute"):
                    _wtype = db.execute(text(
                        "SELECT data_type FROM information_schema.columns "
                        f"WHERE table_name='students' AND column_name='{_wcol}';"
                    )).first()
                    if _wtype is not None and _wtype[0] != "bigint":
                        print(f"🔧 Auto-patching database: widening 'students.{_wcol}' to BIGINT (M5)...")
                        db.execute(text(f"ALTER TABLE students ALTER COLUMN {_wcol} TYPE BIGINT;"))
                db.commit()
        except Exception as _m5_err:
            print(f"⚠️ Warning during M5 wallet widening: {_m5_err}")
            db.rollback()

        # FIX: Bug 17 - enforce duplicate-session protection in existing SQLite/PostgreSQL databases.
        # Existing duplicate active sessions must be resolved explicitly, never silently deleted.
        db.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_session_course_date_active "
            "ON session_logs (course_id, date) WHERE is_deleted = FALSE"
        ))
        db.commit()

        # FIX: H6(C2) - یک رکورد حضور/غیاب برای هر (جلسه، دانش‌آموز) در دیتابیس‌های موجود.
        db.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_attendance_session_student "
            "ON attendances (session_id, student_id)"
        ))
        db.commit()
        # FIX L4: ایندکس مرکب تراکنش‌ها در دیتابیس‌های موجود (الگوی Bug 17؛
        # SQLite و PG هر دو IF NOT EXISTS دارند پس idempotent است).
        db.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_transactions_student_date "
            "ON transactions (student_id, date)"
        ))
        db.commit()

        # FIX (sqlite-uq): یکتایی ۳ ستون کد (teacher_code/student_code/session_code) —
        # UNIQUE اینلاین در ALTER TABLE روی SQLite همیشه fail می‌شود («Cannot add a UNIQUE column»)
        # پس ستون ساده اضافه شد و یکتایی این‌جا با ایندکس جداگانه اعمال می‌شود (الگوی Bug 17/H6؛
        # NULLهای متعدد در هر دو دیتابیس مجازند).
        for _uq_sql in (
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_teachers_teacher_code ON teachers (teacher_code)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_students_student_code ON students (student_code)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_session_logs_session_code ON session_logs (session_code)",
        ):
            db.execute(text(_uq_sql))
        db.commit()
        # FIX (E2E-B2): idempotency_key عمداً NON-UNIQUE است (معنایش شناسه‌ی عملیات است؛ حالت both
        # دو ردیف با یک کلید دارد) — ایندکس ساده برای سرعت replay-lookup. اگر نسخه‌ی میانی، ایندکس
        # یکتا ساخته بود، اول حذفش می‌کنیم (SQLite و PG هر دو DROP IF EXISTS دارند).
        db.execute(text("DROP INDEX IF EXISTS uq_transactions_idempotency_key"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_transactions_idempotency_key ON transactions (idempotency_key)"))
        db.commit()

        # 🔥 مقداردهی خودکار کدهای ترتیبی برای داده‌های قدیمی دیتابیس (Backfill)
        try:
            from models import Teacher, Student, Course, SessionLog, Transaction
            # 1. معلمان قدیمی
            uncoded_teachers = db.query(Teacher).filter(Teacher.teacher_code == None).order_by(Teacher.id.asc()).all()
            if uncoded_teachers:
                from dependencies import get_next_sequence_value
                for t in uncoded_teachers:
                    code = get_next_sequence_value(db, "teacher", 101)
                    t.teacher_code = code
                db.commit()
                print(f"✅ کدهای ترتیبی برای {len(uncoded_teachers)} معلم قدیمی صادر شد (پسوردها دست‌نخورده باقی ماندند).")
                
            # 2. دانش‌آموزان قدیمی
            uncoded_students = db.query(Student).filter(Student.student_code == None).order_by(Student.id.asc()).all()
            if uncoded_students:
                from dependencies import get_next_sequence_value
                for s in uncoded_students:
                    s.student_code = get_next_sequence_value(db, "student", 100001)
                db.commit()
                print(f"✅ کدهای ترتیبی برای {len(uncoded_students)} دانش‌آموز قدیمی صادر شد.")
                
            # 3. کلاس‌های قدیمی
            uncoded_courses = db.query(Course).filter((Course.code == None) | (Course.code == "")).order_by(Course.id.asc()).all()
            if uncoded_courses:
                from dependencies import get_next_sequence_value
                for c in uncoded_courses:
                    c.code = str(get_next_sequence_value(db, "class", 100001))
                db.commit()
                print(f"✅ کدهای ترتیبی برای {len(uncoded_courses)} کلاس قدیمی صادر شد.")
                
            # 4. جلسات قدیمی
            uncoded_sessions = db.query(SessionLog).filter(SessionLog.session_code == None).order_by(SessionLog.id.asc()).all()
            if uncoded_sessions:
                from dependencies import get_next_sequence_value
                for s in uncoded_sessions:
                    s.session_code = get_next_sequence_value(db, "session", 100001)
                db.commit()
                print(f"✅ کدهای ترتیبی برای {len(uncoded_sessions)} جلسه قدیمی صادر شد.")
                
            # 5. تراکنش‌های قدیمی
            uncoded_trans = db.query(Transaction).filter(Transaction.remittance_number == None, Transaction.type == "deposit").order_by(Transaction.id.asc()).all()
            if uncoded_trans:
                from dependencies import get_next_sequence_value
                for t in uncoded_trans:
                    if t.target_wallet == "teacher":
                        t.remittance_number = get_next_sequence_value(db, "remittance_teacher", 100001)
                    else:
                        t.remittance_number = get_next_sequence_value(db, "remittance_institute", 100001)
                db.commit()
                print(f"✅ شماره حواله‌های ترتیبی برای {len(uncoded_trans)} تراکنش قدیمی صادر شد.")
                
        except Exception as b_err:
            print(f"⚠️ Warning during sequence backfill: {b_err}")
            db.rollback()

        # پاک‌سازی خودکار سشن‌های منقضی شده قدیمی (بیش از ۳۰ روز)
        try:
            expiry_limit = datetime.datetime.utcnow() - datetime.timedelta(days=30)
            deleted_count = db.query(UserSession).filter(UserSession.created_at < expiry_limit).delete()
            if deleted_count > 0:
                print(f"🧹 Auto-cleanup: Removed {deleted_count} expired user sessions.")
            db.commit()
        except Exception as se_err:
            print(f"⚠️ Error cleaning up expired sessions: {se_err}")
            db.rollback()

        # FIX H14: پاک‌سازی تلاش‌های لاگین قدیمی‌تر از ۲۴ ساعت (پنجره‌ی throttle فقط ۵ دقیقه است؛ بقیه فقط forensics).
        try:
            from models import LoginAttempt  # lazy، مثل سایر بلوک‌های همین تابع
            attempt_cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
            deleted_attempts = db.query(LoginAttempt).filter(LoginAttempt.attempted_at < attempt_cutoff).delete()
            if deleted_attempts > 0:
                print(f"🧹 Auto-cleanup: Removed {deleted_attempts} old login attempts.")
            db.commit()
        except Exception as la_err:
            print(f"⚠️ Error cleaning up old login attempts: {la_err}")
            db.rollback()

        # 6. اجرای تسک خودکار یادآوری اقساط شهریه به اولیا
        try:
            from today_summary import parse_project_date  # FIX H3-B1: due_date is Jalali; compare as real dates via central converter (lazy import, same pattern as routers/analytics.py)
            today_str = datetime.datetime.now().strftime("%Y/%m/%d")
            today_date = datetime.datetime.now().date()
            # FIX: Bug 13 - exclude archived Installment rows from this active view.
            unpaid = db.query(Installment).filter(Installment.is_deleted == False).filter(Installment.is_paid == False).all()
            for inst in unpaid:
                due = parse_project_date(inst.due_date)
                if due is not None and due <= today_date:
                    enroll = db.query(Enrollment).filter(Enrollment.id == inst.enrollment_id).first()
                    if enroll:
                        st = db.query(Student).filter(Student.id == enroll.student_id).first()
                        if st and st.parent_mobile:
                            msg = f"سلام ولی محترم دانش‌آموز {st.first_name} {st.last_name}، بدینوسیله به اطلاع می‌رساند قسط شهریه فرزند شما به مبلغ {inst.amount:,} تومان سررسید {inst.due_date} شده است. لطفاً جهت واریز اقدام فرمایید."
                            already_sent = db.query(SmsLog).filter(SmsLog.target_group == f"installment_{inst.id}", SmsLog.date.like(f"{today_str}%")).first()
                            if not already_sent:
                                print(f"📱 Auto-SMS: Sent installment reminder for student {st.id} (amount: {inst.amount})")
                                db.add(SmsLog(
                                    target_group=f"installment_{inst.id}",
                                    message_text=msg,
                                    sent_count=1,
                                    date=datetime.datetime.now().strftime("%Y/%m/%d %H:%M")
                                ))
                                
                                # Send In-App & Push Notifications
                                try:
                                    # FIX (F-R2): recipient_user_id اعلان‌ها در فضای User.id است، نه Student.id.
                                    # مپ مرکزی پروژه (dependencies.resolve_notification_recipient) برای
                                    # نقش student از Student.user_id و برای parent از Student.parent_user_id
                                    # استفاده می‌کند (و در نبودشان shadow-user می‌سازد). اگر مخاطب رزولو نشد،
                                    # همان نقش skip می‌شود؛ هرگز Student.id (یا None) به‌عنوان fallback نمی‌رود.
                                    from dependencies import NotificationService, resolve_notification_recipient
                                    # Parent Notification
                                    parent_recipient = resolve_notification_recipient(db, st.id, "parent")
                                    if parent_recipient is None:
                                        print(f"⚠️ Installment reminder skipped (parent) for student {st.id}: no resolvable parent_user_id")
                                    else:
                                        NotificationService.send_notification(
                                            db=db,
                                            recipient_user_id=parent_recipient,
                                            recipient_role="parent",
                                            type="installment",
                                            title="💰 سررسید قسط شهریه فرزند شما",
                                            body=f"بدینوسیله به اطلاع می‌رساند قسط شهریه فرزند شما {st.first_name} به مبلغ {inst.amount:,} تومان سررسید {inst.due_date} شده است. لطفاً جهت تسویه حساب اقدام فرمایید."
                                        )
                                    # Student Notification
                                    student_recipient = resolve_notification_recipient(db, st.id, "student")
                                    if student_recipient is None:
                                        print(f"⚠️ Installment reminder skipped (student) for student {st.id}: no resolvable user_id")
                                    else:
                                        NotificationService.send_notification(
                                            db=db,
                                            recipient_user_id=student_recipient,
                                            recipient_role="student",
                                            type="installment",
                                            title="💰 سررسید قسط شهریه شما",
                                            body=f"بدینوسیله به اطلاع می‌رساند قسط شهریه شما به مبلغ {inst.amount:,} تومان سررسید {inst.due_date} شده است. لطفاً اقدام فرمایید."
                                        )
                                except Exception as n_err:
                                    print(f"⚠️ Error sending automated installment notification: {n_err}")
            db.commit()
        except Exception as sms_err:
            print(f"⚠️ Error in automated installment SMS job: {sms_err}")
            db.rollback()

        # ۷. مقداردهی اولیه‌ی جدول قیمت‌گذاری ۵ نفره در صورت خالی بودن
        try:
            if not db.query(PricingTable).first():
                p_elem = PricingTable(category="elementary", count_1=100000, count_2=160000, count_3=210000, count_4=240000, count_5=250000)
                p_mid = PricingTable(category="middle_school", count_1=120000, count_2=180000, count_3=240000, count_4=280000, count_5=300000)
                p_high = PricingTable(category="high_school", count_1=150000, count_2=240000, count_3=300000, count_4=360000, count_5=400000)
                p_inst = PricingTable(category="institute", count_1=50000, count_2=80000, count_3=100000, count_4=120000, count_5=150000)
                db.add_all([p_elem, p_mid, p_high, p_inst])
                db.commit()
                print("✅ [Auto-Patch] جدول قیمت‌گذاری ۵ نفره با موفقیت مقداردهی شد.")
        except Exception as p_err:
            print(f"⚠️ Error seeding PricingTable on boot: {p_err}")
            db.rollback()

        # 🔥 [Auto-Patch] Backfill: Securely Hash existing plaintext passwords in Users and Teachers tables
        try:
            from dependencies import hash_password
            from models import User, Teacher
            # 1. Backfill Users
            plaintext_users = db.query(User).all()
            for u in plaintext_users:
                if u.password and not (u.password.startswith("$2b$") or u.password.startswith("$2a$") or u.password.startswith("$2y$") or u.password.startswith("$pbkdf2-")):
                    print(f"🔒 Hashing legacy plaintext password for user {u.username}...")
                    u.password = hash_password(u.password)
            # 2. Backfill Teachers
            plaintext_teachers = db.query(Teacher).all()
            for t in plaintext_teachers:
                if t.password and not (t.password.startswith("$2b$") or t.password.startswith("$2a$") or t.password.startswith("$2y$") or t.password.startswith("$pbkdf2-")):
                    print(f"🔒 Hashing legacy plaintext password for teacher {t.mobile}...")
                    t.password = hash_password(t.password)
            db.commit()
            print("✅ [Auto-Patch] All legacy plaintext passwords successfully migrated to secure PBKDF2 hashes!")
        except Exception as hash_err:
            print(f"⚠️ Error backfilling hashed passwords on boot: {hash_err}")
            db.rollback()
            
    except Exception as e:
        print("\n" + "🔥" * 30)
        print("🚨 DATABASE AUTO-PATCHING ERROR! CRITICAL FAILURE! 🚨")
        print(f"Error details: {str(e)}")
        print("The system might be running with an outdated or incomplete database schema!")
        print("Action required: Check database connection and schema integrity immediately!")
        print("🔥" * 30 + "\n")
        db.rollback()
    finally:
        db.close()

# Run auto-patcher on startup
auto_patch_database()

# =========================================================================
# 🆕 Job پس‌زمینه: پایان خودکار کلاس‌های زنده‌ی رهاشده (تمایلی به فراموشی)
# هر `LIVE`-session که بیش از آستانه‌ی تعیین‌شده در تنظیمات مرکزی
# (live_session_max_minutes، پیش‌فرض ۱۸۰ دقیقه) در حالت زنده بماند،
# با ended_automatically=True به ENDED تبدیل و محاسبه‌ی مالی با دیتای
# لحظه‌ای ثبت‌شده اجرا می‌شود. این تابع فقط وضعیت را می‌بندد و هیچ
# محاسبه‌ای را تغییر نمی‌دهد.
# =========================================================================

_live_job_started = False


def _live_auto_end_worker():
    global _live_job_started
    if _live_job_started:
        return
    _live_job_started = True

    import threading
    import time as _t

    def _loop():
        from routers.attendance import finalize_live_session, _get_live_max_minutes, claim_live_session_for_finalize, _now_str, DuplicateSessionDate
        from models import LiveSession, SessionLocal, Course
        while True:
            try:
                db = SessionLocal()
                try:
                    threshold = _get_live_max_minutes(db)
                    lives = db.query(LiveSession).filter(LiveSession.status == "LIVE").all()
                    now_ts = _t.time()
                    for live in lives:
                        started_ts = live.started_at_ts or 0
                        elapsed = now_ts - started_ts if started_ts else 0
                        if elapsed > (threshold * 60):
                            # FIX F-C9: کلاس معلق — بستن مستقیم بدون submit. ثبت جلسه روی کلاس
                            # معلق اصلاً ممنوع است (H10→403) پس finalize/submit صدا زده نمی‌شود؛
                            # در عوض جلسه مستقیم ENDED می‌شود تا لوپ retry بی‌پایان (claim→403→
                            # rollback→LIVE هر ۶۰ ثانیه) رخ ندهد. کوئری course تازه در همین تیک
                            # زده می‌شود چون وضعیت suspend بین تیک‌ها ممکن است عوض شده باشد.
                            # UPDATE مشروط (H8-P4): اگر مسیر دستی هم‌زمان تسخیر کرده باشد،
                            # rowcount صفر می‌شود و رد می‌شویم (finalize دستی روی معلق 403
                            # می‌دهد و به LIVE برمی‌گردد؛ تیک بعد ورکر می‌بندد — همگرا است).
                            _c9_course = db.query(Course).filter(Course.id == live.course_id).first()
                            if _c9_course is not None and _c9_course.is_suspended:
                                _c9_closed = (
                                    db.query(LiveSession)
                                    .filter(LiveSession.id == live.id, LiveSession.status == "LIVE")
                                    .update(
                                        {
                                            LiveSession.status: "ENDED",
                                            LiveSession.ended_automatically: True,
                                            LiveSession.end_time: _now_str(),
                                        },
                                        synchronize_session=False,
                                    )
                                )
                                db.commit()
                                if _c9_closed == 1:
                                    print(f"🤖 [Live Auto-End] جلسه‌ی #{live.id} روی کلاس معلق مستقیم بسته شد (بدون ثبت جلسه).")
                                continue
                            # FIX F-C6(c): تسخیر اتمیک مشترک با مسیر دستی — اگر معلم هم‌زمان
                            # end_live زده باشد، فقط یکی finalize را اجرا می‌کند؛ بازنده رد می‌شود.
                            if not claim_live_session_for_finalize(db, live.id, auto=True):
                                db.rollback()
                                print(f"🤖 [Live Auto-End] جلسه‌ی #{live.id} هم‌زمان دستی بسته شد؛ رد شد.")
                                continue
                            print(f"🤖 [Live Auto-End] بستن خودکار کلاس زنده #{live.id} (خیلی طولانی شد)")
                            try:
                                finalize_live_session(db, live)
                            except DuplicateSessionDate as dup:
                                # FIX (گروه۱/آیتم۱): جلسهٔ این تاریخ قبلاً ثبت شده ⇒ retry بی‌معناست.
                                # بدون ساخت SessionLog/تراکنش، جلسهٔ زنده مستقیم بسته می‌شود تا ورکر
                                # هر ۶۰ ثانیه claim → خطا → rollback → LIVE را تکرار نکند (هم‌الگو با F-C9).
                                db.rollback()
                                db.query(LiveSession).filter(LiveSession.id == live.id).update(
                                    {
                                        LiveSession.status: "ENDED",
                                        LiveSession.ended_automatically: True,
                                        LiveSession.end_time: _now_str(),
                                    },
                                    synchronize_session=False,
                                )
                                db.commit()
                                print(f"🤖 [Live Auto-End] جلسه‌ی #{live.id} بسته شد؛ جلسهٔ کلاس در تاریخ "
                                      f"{dup.date} از قبل ثبت شده بود (کد {dup.session_code}).")
                            except Exception as fe:
                                print(f"⚠️ [Live Auto-End] خطا در بستن جلسه {live.id}: {fe}")
                                db.rollback()
                                db.query(LiveSession).filter(LiveSession.id == live.id).update(
                                    {LiveSession.status: "LIVE"}, synchronize_session=False
                                )
                                db.commit()
                finally:
                    db.close()
            except Exception as e:
                print(f"⚠️ [Live Auto-End] خطای کلی: {e}")
                try:
                    pass
                except Exception:
                    pass
            _t.sleep(60)

    threading.Thread(target=_loop, daemon=True, name="live-session-auto-ender").start()
    print("🤖 [Live Auto-End] Worker پس‌زمینه‌ی کلاس‌های زنده راه‌اندازی شد (هر ۶۰ ثانیه).")


try:
    _live_auto_end_worker()
except Exception as _e:
    print(f"⚠️ خطا در راه‌اندازی worker کلاس زنده: {_e}")

# Include Routers
# FIX(route-shadowing): ترتیب include تعیین‌کننده است (Starlette: اولین تطبیق برنده می‌شود).
# admin.router مسیرهای literal مثل GET /teachers/pending دارد؛ اگر teachers.router (که
# GET /teachers/{teacher_id} را دارد) زودتر ثبت شود، «/teachers/pending» به آن می‌خورد و
# رکوئست با خطای 422 (int parsing روی "pending") رد می‌شود ⇒ لیست درخواست‌های تایید معلم
# هرگز بارگذاری نمی‌شد. با ترتیب زیر (admin قبل از teachers) هیچ مسیری سایه نمی‌شود.
app.include_router(auth.router)
app.include_router(students.router)
app.include_router(admin.router)
app.include_router(teachers.router)
app.include_router(classes.router)
app.include_router(finance.router)
app.include_router(reports.router)
app.include_router(attendance.router)
app.include_router(parent.router)
app.include_router(homework.router)
app.include_router(calendar.router)
app.include_router(messages.router)
app.include_router(exams.router)
app.include_router(crm.router)
app.include_router(branches.router)
app.include_router(automation.router)
app.include_router(analytics.router)
app.include_router(ai.router)
app.include_router(audit.router, prefix="/audit")
app.include_router(timeline.router)
app.include_router(dunning.router)
app.include_router(dashboard.router, prefix="/dashboard")
app.include_router(exports.router)
app.include_router(audit_trail.router)
