
import os

from fastapi import Depends, HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from dependencies import check_admin_access, get_db
from models import Enrollment, Student, Transaction
from schemas import TransactionTestData, TransactionUpdate

"""لایهٔ سرویسِ «مدیریت تراکنش‌ها از سمت ادمین».

شامل: حذف تراکنش (با برگشت اثر مالی)، ویرایش تراکنش (با بازمحاسبهٔ سهم
معلم/مؤسسه)، اندپوینت تشخیصیِ منطق تراکنش، و هلپر خالصِ تقسیم مبلغ.

قرارداد لایه در `services/__init__.py`: بدون route و بدون APIRouter؛ بدنه‌ها
بایت‌به‌بایت از `routers/admin.py` منتقل شده‌اند و handlerها در روتر به‌صورت
پوستهٔ HTTP باقی مانده‌اند (تست‌ها آن‌ها را مستقیم و گاهی پوزیشنال صدا می‌زنند،
مثلاً `admin.delete_transaction(transaction.id, db=..., _="admin")`).
"""


def _split_amount_integer(amount: int, share_a: int, share_b: int):
    """FIX F-W1a/F-W2: تقسیمِ قطعیِ یک مبلغ بین دو سهم، با جمعِ **دقیقاً** برابر amount.

    - خروجی همیشه عدد صحیح (تومان) است؛ هیچ مقدار اعشاری (float) تولید نمی‌شود.
    - قاعده‌ی قطعیِ باقیمانده: باقیمانده (**در قدر مطلق**، هم برای مبلغ مثبت و هم منفی) همیشه
      به سهم دوم (آموزشگاه) می‌رسد — همان قرارداد موجودِ پروژه در `submit_payment`
      (Bug 10: `amt_teacher = amount // 2` و `amt_institute = amount - amt_teacher`) و در مسیر
      refund رسیدهای قدیمی `both`.
    - اگر هر دو سهم صفر/غایب باشند، تقسیم نصف-نصف (۱:۱) با همان قاعده‌ی باقیمانده است —
      دقیقاً fallback مستندشده‌ی مسیر refund برای رسیدهای legacy.
    """
    share_a = int(share_a or 0)
    share_b = int(share_b or 0)
    total = abs(share_a) + abs(share_b)
    if total <= 0:
        share_a, share_b, total = 1, 1, 2
    amount = int(amount)
    sign = -1 if amount < 0 else 1
    part_a = sign * (abs(amount) * abs(share_a) // total)   # قطعی و مستقل از علامت/ترتیب فراخوانی
    return part_a, amount - part_a


def delete_transaction(id: int, db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    """بدنهٔ دامنه‌ایِ `delete_transaction`؛ توضیح HTTP در پوستهٔ روتر است."""
    # FIX: Bug 12 - exclude archived Transaction rows from this active view.
    trans = db.query(Transaction).filter(Transaction.is_deleted == False, Transaction.is_reversed == False).filter(Transaction.id == id).first()
    if not trans:
        raise HTTPException(status_code=404, detail="تراکنش یافت نشد")

    # فریز مبلغ در لحظه‌ی اعتبارسنجی (سطر در انتهای تابع hard-delete می‌شود).
    t_amount = trans.amount

    # FIX B3 (الگوی H8-P4): گیت اتمیک گذرا — is_deleted مشروط فقط برای mutual exclusion؛ چون این تابع
    # hard-delete می‌کند (تصمیم محصولی H11، خارج از این ممیزی)، این فلیپ در state نهایی نامرئی است
    # (همان تراکنش سطر را با db.delete پاک می‌کند). rowcount≠۱ ← همان 404 حذف تکراری ترتیبی.
    claimed_rows = (
        db.query(Transaction)
        .filter(Transaction.id == id, Transaction.is_deleted == False, Transaction.is_reversed == False)
        .update({Transaction.is_deleted: True}, synchronize_session=False)
    )
    if claimed_rows != 1:
        db.rollback()
        raise HTTPException(status_code=404, detail="تراکنش یافت نشد")

    # اگر تراکنش مربوط به شهریه کلاس بوده، باید از پرداختی دانش‌آموز کم کنیم
    # 🔗 لینک دقیق ثبت‌نام مقدم است (منبع حقیقت واحد)؛ وگرنه رفتار قدیمی حفظ می‌شود
    if trans.enrollment_id and trans.type in ("deposit", "enrollment_payment", "tuition") and (trans.amount or 0) > 0:
        exact_enrollment = db.query(Enrollment).filter(Enrollment.id == trans.enrollment_id).first()
        if exact_enrollment is not None and not exact_enrollment.is_deleted:
            # FIX B3: کسر اتمیک با کف صفر (همان max(0,...) قبلی، به‌صورت CASE اتمیک) — شاخه‌ی لینک دقیق.
            db.query(Enrollment).filter(
                Enrollment.id == exact_enrollment.id, Enrollment.is_deleted == False
            ).update(
                {
                    Enrollment.total_paid: case(
                        (func.coalesce(Enrollment.total_paid, 0) - t_amount < 0, 0),
                        else_=func.coalesce(Enrollment.total_paid, 0) - t_amount,
                    )
                },
                synchronize_session=False,
            )
    elif trans.course_id and trans.type == "tuition":
        enrollment = (
            db.query(Enrollment)
            .filter(
                Enrollment.student_id == trans.student_id,
                Enrollment.course_id == trans.course_id,
            )
            .first()
        )

        if enrollment:
            # کسر مبلغ حذف شده از کل پرداختی
            # FIX B3: کسر اتمیک با کف صفر (همان floor دستی قبلی، به‌صورت CASE اتمیک) — شاخه‌ی legacy.
            # عین رفتار قبلی بدون شرط is_deleted (خواندن قدیمی هم فیلتر deleted نداشت — آینه‌ی مسیر B در update_transaction).
            db.query(Enrollment).filter(Enrollment.id == enrollment.id).update(
                {
                    Enrollment.total_paid: case(
                        (func.coalesce(Enrollment.total_paid, 0) - t_amount < 0, 0),
                        else_=func.coalesce(Enrollment.total_paid, 0) - t_amount,
                    )
                },
                synchronize_session=False,
            )

    # بروزرسانی کیف پول دانش‌آموز بر اساس نوع تراکنش
    if not trans.student_id:
        db.delete(trans)
        db.commit()
        return {"message": "تراکنش حذف شد (تراکنش بدون دانش‌آموز)"}

    student = db.query(Student).filter(Student.id == trans.student_id).first()
    if not student:
        db.delete(trans)
        db.commit()
        return {"message": "تراکنش حذف شد (دانش‌آموز یافت نشد)"}

    # FIX B3: بدون خواندن-جمع‌زدن در پایتون — فقط دلتای signed هر کیف‌پول محاسبه می‌شود (در انتها یک UPDATE اتمیک).
    # (متغیر wallet_balance قدیمی عملاً دور ریخته می‌شد — write-back فقط مؤلفه‌ها + sync بود؛ آینه‌ی update_transaction.)
    d_teacher = 0
    d_institute = 0

    if trans.type == "deposit":
        # برای تراکنش‌های واریز (مثبت)، مبلغ را از کیف پول کم می‌کنیم (برگشت واریز)
        if trans.target_wallet == "teacher":
            d_teacher = -t_amount
        elif trans.target_wallet == "institute":
            d_institute = -t_amount
        elif trans.target_wallet == "both":
            # FIX F-D1: رسیدهای legacy با target_wallet="both" (امروز submit_payment دو رسید جدا
            # می‌سازد) هنگام حذف هیچ اثری از کیف برنمی‌گرداندند ⇒ واگرایی دفتر/کیف — دقیقاً همان
            # شکافی که مسیر refund برای همین ردیف‌ها پوشش می‌دهد.
            # قاعده‌ی کانونیکال (آینه‌ی refund_transaction، بدون تغییر اعداد):
            #   جمع سهم‌های ذخیره‌شده == مبلغ ⇒ همان سهم‌ها کسر می‌شوند،
            #   وگرنه fallback مستند پروژه: نصف-نصف با باقیمانده به آموزشگاه.
            share_teacher = int(trans.share_teacher or 0)
            share_institute = int(trans.share_institute or 0)
            if share_teacher + share_institute != t_amount:
                share_teacher = t_amount // 2
                share_institute = t_amount - share_teacher
            d_teacher = -share_teacher
            d_institute = -share_institute
        # (هدف نامشخص (None): مثل رفتار قبلی هیچ تغییری اعمال نمی‌شود — wallet_balance قدیمی دور ریخته می‌شد.)

    elif trans.type == "session_charge":
        # برای تراکنش‌های هزینه جلسه (منفی)، مبلغ را به کیف پول برمی‌گردانیم
        # session_charge تراکنش‌ها مقدار منفی دارند (کسری از کیف پول)
        # برای برگرداندن باید مقدار مثبت اضافه کنیم
        share_teacher = trans.share_teacher if trans.share_teacher is not None else 0
        share_institute = (
            trans.share_institute if trans.share_institute is not None else 0
        )

        if share_teacher != 0:
            d_teacher = abs(share_teacher)
        if share_institute != 0:
            d_institute = abs(share_institute)

    elif trans.type == "tuition" or trans.type == "enrollment_payment":
        # (no-op عمدی — رفتار قبلی هم فقط wallet_balance محلی را عوض می‌کرد که دور ریخته می‌شد.)
        pass

    else:
        # (no-op عمدی — همان دلیل بالا.)
        pass

    # FIX B3 (الگوی H8-P4): اعمال اتمیک دلتاها در SQL — COALESCE + دلتای signed (منفی=کسر، مثبت=برگرداندن).
    if d_teacher or d_institute:
        wallet_rows = (
            db.query(Student)
            .filter(Student.id == trans.student_id)
            .update(
                {
                    Student.wallet_teacher: func.coalesce(Student.wallet_teacher, 0) + d_teacher,
                    Student.wallet_institute: func.coalesce(Student.wallet_institute, 0) + d_institute,
                },
                synchronize_session=False,
            )
        )
        if wallet_rows != 1:
            db.rollback()
            raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")

    # ترتیب سینک (مثل بچ ۱/۲): اول UPDATE خام، بعد refresh برای مقادیر تازه، بعد سینک بالانس کل.
    if d_teacher or d_institute:
        db.refresh(student)
        # FIX: Bug 18 - derive the total only through the shared wallet helper.
        student.sync_wallet_balance()

    # hard-delete سر جایش (بعد از همه‌ی UPDATEهای مشروط موفق) — تصمیم H11، خارج از این ممیزی.
    db.delete(trans)
    db.commit()
    return {"message": "تراکنش حذف شد و حساب‌ها اصلاح گردید."}


def update_transaction(id: int, data: TransactionUpdate, db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    """بدنهٔ دامنه‌ایِ `update_transaction`؛ توضیح HTTP در پوستهٔ روتر است."""
    # FIX: Bug 12 - exclude archived Transaction rows from this active view.
    trans = db.query(Transaction).filter(Transaction.is_deleted == False, Transaction.is_reversed == False).filter(Transaction.id == id).first()
    if not trans:
        raise HTTPException(status_code=404, detail="تراکنش یافت نشد")

    # FIX: Bug 22 - payment edits stay positive; signed charges/reversals keep their existing semantics.
    if trans.type in ("deposit", "enrollment_payment", "tuition") and data.amount <= 0:
        raise HTTPException(status_code=400, detail="مبلغ پرداخت باید بیشتر از صفر باشد")

    old_amount = trans.amount
    new_amount = data.amount

    # آپدیت فیلدها
    trans.amount = new_amount
    trans.description = data.description
    trans.date = data.date

    # اصلاح حساب کلاس (اگر شهریه بوده)
    # 🔗 لینک دقیق ثبت‌نام مقدم است (منبع حقیقت واحد)؛ وگرنه رفتار قدیمی حفظ می‌شود
    if trans.enrollment_id and trans.type in ("deposit", "enrollment_payment", "tuition") and (trans.amount or 0) > 0 and (new_amount or 0) > 0:
        exact_enrollment = db.query(Enrollment).filter(Enrollment.id == trans.enrollment_id).first()
        if exact_enrollment is not None and not exact_enrollment.is_deleted:
            # اختلاف مبلغ جدید و قدیم را حساب میکنیم
            diff = new_amount - old_amount
            # FIX B2 (الگوی H8-P4): افزایش/کاهش اتمیک با کف صفر (همان max(0,...) قبلی، به‌صورت CASE اتمیک).
            # diff از قبل (مبلغ جدید − مبلغ فریزشده‌ی قبل‌از‌تغییر) محاسبه شده؛ trans.amount اینجا دیگر new است.
            db.query(Enrollment).filter(
                Enrollment.id == exact_enrollment.id, Enrollment.is_deleted == False
            ).update(
                {
                    Enrollment.total_paid: case(
                        (func.coalesce(Enrollment.total_paid, 0) + diff < 0, 0),
                        else_=func.coalesce(Enrollment.total_paid, 0) + diff,
                    )
                },
                synchronize_session=False,
            )
    elif trans.course_id and trans.type == "tuition":
        enrollment = (
            db.query(Enrollment)
            .filter(
                Enrollment.student_id == trans.student_id,
                Enrollment.course_id == trans.course_id,
            )
            .first()
        )

        if enrollment:
            # اختلاف مبلغ جدید و قدیم را حساب میکنیم
            diff = new_amount - old_amount
            # FIX B2 (الگوی H8-P4): افزایش/کاهش اتمیک — عین رفتار قبلی (بدون کف صفر و بدون شرط is_deleted،
            # چون خواندن مسیر قدیمی هم هیچ‌کدام را نداشت؛ تغییر منطق محصولی در اسکوپ بچ ۲ نیست).
            db.query(Enrollment).filter(Enrollment.id == enrollment.id).update(
                {Enrollment.total_paid: func.coalesce(Enrollment.total_paid, 0) + diff},
                synchronize_session=False,
            )

    # بروزرسانی کیف پول دانش‌آموز بر اساس نوع تراکنش
    if not trans.student_id:
        db.commit()
        return {"message": "تراکنش ویرایش شد (تراکنش بدون دانش‌آموز)"}

    # FIX B2 (الگوی H8-P4): بدون with_for_update — این خواندن فقط وجودسنجی است؛ اصلاح کیف‌پول با UPDATE اتمیک پایین است.
    student = db.query(Student).filter(Student.id == trans.student_id).first()
    if not student:
        db.commit()
        return {"message": "تراکنش ویرایش شد (دانش‌آموز یافت نشد)"}

    # FIX B2: بدون خواندن-جمع‌زدن در پایتون — فقط دلتای هر کیف‌پول محاسبه می‌شود (در انتها یک UPDATE اتمیک).
    # (متغیر wallet_balance قدیمی عملاً دور ریخته می‌شد — write-back فقط مؤلفه‌ها + sync بود؛ پس حذفش بی‌اثر است.)
    d_teacher = 0
    d_institute = 0

    # diff از روی مبلغ فریزشده‌ی قبل‌از‌تغییر (old_amount) محاسبه می‌شود، نه trans.amount (که دیگر new است).
    diff = new_amount - old_amount

    if trans.type == "deposit":
        # برای تراکنش‌های واریز (مثبت)، اختلاف مبلغ را به کیف پول اضافه/کم می‌کنیم
        if trans.target_wallet == "teacher":
            d_teacher = diff
        elif trans.target_wallet == "institute":
            d_institute = diff
        elif trans.target_wallet == "both":
            # FIX F-W2: رسیدهای legacy با target_wallet="both" (امروز submit_payment دو رسید جدا
            # می‌سازد) پیش‌تر هیچ دلتایی نمی‌گرفتند ⇒ دفتر و کیف‌پول از هم واگرا می‌شدند، در حالی که
            # دو مسیر دیگر (refund و delete) همین رسیدها را می‌شناسند.
            # قاعده: delta = new_amount - old_amount، تقسیم با **همان نسبت سهم قبلی**؛
            # اگر سهم قبلی موجود/معتبر نباشد، fallback نصف-نصف (باقیمانده به آموزشگاه) — همان قاعده‌ی refund.
            prior_teacher = int(trans.share_teacher or 0)
            prior_institute = int(trans.share_institute or 0)
            if abs(prior_teacher) + abs(prior_institute) > 0:
                # نسبت قبلی موجود است ⇒ سهم‌های جدید با **همان نسبت** تقسیم می‌شوند و دلتای هر کیف
                # دقیقاً «سهم جدید − سهم قبلی» است. برای ردیف سازگار (جمع سهم قبلی == مبلغ قبلی)
                # جمع دلتاها == delta = new_amount − old_amount؛ و کیف‌ها همیشه با سهم‌های ذخیره‌شده
                # هم‌راستا می‌مانند — همان چیزی که مسیر refund (که همین ستون‌ها را برمی‌گرداند) لازم دارد.
                new_teacher, new_institute = _split_amount_integer(
                    new_amount, prior_teacher, prior_institute
                )
                d_teacher = new_teacher - prior_teacher
                d_institute = new_institute - prior_institute
                trans.share_teacher, trans.share_institute = new_teacher, new_institute
            else:
                # fallback مستند (سهم قبلی موجود نیست — ردیف‌های legacy بدون سهم): delta طبق
                # فرمول new − old نصف-نصف تقسیم می‌شود (باقیمانده به آموزشگاه) و سهم‌های ردیف هم
                # با همان نسبت ۵۰/۵۰ با مبلغ جدید هم‌راستا می‌شوند.
                d_teacher, d_institute = _split_amount_integer(diff, 1, 1)
                trans.share_teacher, trans.share_institute = _split_amount_integer(new_amount, 1, 1)
        # (هدف نامشخص (None): مثل رفتار قبلی هیچ تغییری در کیف‌پول اعمال نمی‌شود — wallet_balance قدیمی دور ریخته می‌شد.)

    elif trans.type == "session_charge":
        # FIX F-W1a/F-W1b: در session_charge قرارداد پروژه این است: amount منفی و
        # share_teacher/share_institute مثبت‌اند و `amount == -(share_teacher + share_institute)`
        # (سازنده: routers/attendance.py). ویرایش قبلی دلتا را با نسبتِ **اعشاری** حساب می‌کرد
        # (`diff * teacher_ratio`) و روی ستون BigInteger می‌نوشت ⇒ پول اعشاری؛ و share_* را هم
        # با مبلغ جدید همراستا نمی‌کرد ⇒ گزارش سهم‌ها (financial_calculations) کهنه می‌ماند.
        prior_teacher = int(trans.share_teacher or 0)
        prior_institute = int(trans.share_institute or 0)
        prior_total = abs(prior_teacher) + abs(prior_institute)

        if prior_total > 0:
            # سهم‌های جدید = تقسیم صحیحِ |مبلغ جدید| با همان نسبت قبلی (باقیمانده به آموزشگاه).
            new_teacher, new_institute = _split_amount_integer(
                abs(int(new_amount)), prior_teacher, prior_institute
            )
            # دلتای هر کیف = سهم قبلی − سهم جدید ⇒ جمع دلتاها دقیقاً برابر تغییر مبلغ است
            # و بعد از ویرایش، کسرِ قابل‌انتساب به این ردیف دقیقاً همان سهم ذخیره‌شده می‌شود.
            d_teacher = prior_teacher - new_teacher
            d_institute = prior_institute - new_institute
            trans.share_teacher = new_teacher
            trans.share_institute = new_institute
        # (ردیف legacy بدون هیچ سهم: مثل رفتار قبلی هیچ دلتایی اعمال نمی‌شود و سهم صفر دست‌نخورده
        #  می‌ماند — تا مسیر delete سهمی را به کیف برنگرداند که هرگز از آن کسر نشده بود.)

    elif trans.type == "tuition" or trans.type == "enrollment_payment":
        # (no-op عمدی — رفتار قبلی هم فقط wallet_balance محلی را عوض می‌کرد که در write-back دور ریخته می‌شد.)
        pass

    else:
        # (no-op عمدی — همان دلیل بالا.)
        pass

    # FIX B2 (الگوی H8-P4): اعمال اتمیک دلتاها در SQL — جمع در دیتابیس، نه خواندن-جمع‌زدن در پایتون.
    # COALESCE رفتار قدیمی None→0 را حفظ می‌کند؛ diff می‌تواند منفی هم باشد (کم‌کردن، عین رفتار قبلی).
    if d_teacher or d_institute:
        wallet_rows = (
            db.query(Student)
            .filter(Student.id == trans.student_id)
            .update(
                {
                    Student.wallet_teacher: func.coalesce(Student.wallet_teacher, 0) + d_teacher,
                    Student.wallet_institute: func.coalesce(Student.wallet_institute, 0) + d_institute,
                },
                synchronize_session=False,
            )
        )
        if wallet_rows != 1:
            db.rollback()
            raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")

    # ترتیب سینک (مثل بچ ۱/قدم ۱): اول UPDATE خام، بعد refresh برای مقادیر تازه، بعد سینک بالانس کل.
    # (قاعده‌ی واحد: سینک فقط وقتی UPDATE انجام شده؛ وقتی دلتا صفر است total هم دست‌نخورده می‌ماند.)
    if d_teacher or d_institute:
        db.refresh(student)
        # FIX: Bug 18 - derive the total only through the shared wallet helper.
        student.sync_wallet_balance()

    db.commit()
    return {"message": "تراکنش ویرایش و تراز مالی به‌روز شد."}


def test_transaction_logic(data: TransactionTestData, db: Session = Depends(get_db), _: str = Depends(check_admin_access)):
    """بدنهٔ دامنه‌ایِ `test_transaction_logic`؛ توضیح HTTP در پوستهٔ روتر است."""
    # FIX (F-C5): این اندپوینت روی دیتای واقعی می‌نویسد (round-trip خود-تمیزشونده) — در
    # پروداکشن غیرفعال، دقیقاً با همان الگوی docs در main.py (M2).
    if os.getenv("ENV", "development").lower() == "production":
        raise HTTPException(status_code=404, detail="یافت نشد")

    # 1. ایجاد تراکنش تستی
    student = db.query(Student).filter(Student.id == data.student_id).first()
    if not student:
        raise HTTPException(404, "دانش‌آموز یافت نشد")

    # ذخیره مقادیر اولیه کیف پول
    initial_wallet_teacher = (
        student.wallet_teacher if student.wallet_teacher is not None else 0
    )
    initial_wallet_institute = (
        student.wallet_institute if student.wallet_institute is not None else 0
    )
    initial_wallet_balance = (
        student.wallet_balance if student.wallet_balance is not None else 0
    )

    # ایجاد تراکنش
    new_trans = Transaction(
        student_id=data.student_id,
        amount=data.amount,
        payment_method=data.payment_method,
        date=data.date,
        description=data.description,
        type="deposit",
        target_wallet=data.target_wallet,
    )
    db.add(new_trans)

    # بروزرسانی کیف پول (مانند submit_payment)
    if data.target_wallet == "teacher":
        student.wallet_teacher = initial_wallet_teacher + data.amount
    elif data.target_wallet == "institute":
        student.wallet_institute = initial_wallet_institute + data.amount
    else:
        # FIX: Bug 18 - derive the total only through the shared wallet helper.
        student.sync_wallet_balance()

    # بروزرسانی کیف پول کل
    final_w_t = student.wallet_teacher if student.wallet_teacher is not None else 0
    final_w_i = student.wallet_institute if student.wallet_institute is not None else 0
    # FIX: Bug 18 - derive the total only through the shared wallet helper.
    student.sync_wallet_balance()

    db.commit()
    db.refresh(new_trans)

    # 2. ویرایش تراکنش (تست منطق update_transaction)
    update_data = TransactionUpdate(
        amount=data.amount + 5000,  # افزایش 5000 تومانی
        description=f"{data.description} (ویرایش شده)",
        date=data.date,
    )

    # شبیه‌سازی منطق update_transaction
    trans_for_update = (
        # FIX: Bug 12 - exclude archived Transaction rows from this active view.
        db.query(Transaction).filter(Transaction.is_deleted == False, Transaction.is_reversed == False).filter(Transaction.id == new_trans.id).first()
    )
    old_amount = trans_for_update.amount
    new_amount = update_data.amount

    trans_for_update.amount = new_amount
    trans_for_update.description = update_data.description
    trans_for_update.date = update_data.date

    diff = new_amount - old_amount

    # بروزرسانی کیف پول
    if trans_for_update.type == "deposit":
        if trans_for_update.target_wallet == "teacher":
            student.wallet_teacher = (student.wallet_teacher or 0) + diff
        elif trans_for_update.target_wallet == "institute":
            student.wallet_institute = (student.wallet_institute or 0) + diff
        else:
            # FIX: Bug 18 - derive the total only through the shared wallet helper.
            student.sync_wallet_balance()

    # بروزرسانی کیف پول کل
    final_w_t = student.wallet_teacher if student.wallet_teacher is not None else 0
    final_w_i = student.wallet_institute if student.wallet_institute is not None else 0
    # FIX: Bug 18 - derive the total only through the shared wallet helper.
    student.sync_wallet_balance()

    db.commit()

    # 3. حذف تراکنش (تست منطق delete_transaction)
    trans_for_delete = (
        # FIX: Bug 12 - exclude archived Transaction rows from this active view.
        db.query(Transaction).filter(Transaction.is_deleted == False, Transaction.is_reversed == False).filter(Transaction.id == new_trans.id).first()
    )

    # بروزرسانی کیف پول قبل از حذف
    if trans_for_delete.type == "deposit":
        if trans_for_delete.target_wallet == "teacher":
            student.wallet_teacher = (
                student.wallet_teacher or 0
            ) - trans_for_delete.amount
        elif trans_for_delete.target_wallet == "institute":
            student.wallet_institute = (
                student.wallet_institute or 0
            ) - trans_for_delete.amount
        else:
            # FIX: Bug 18 - derive the total only through the shared wallet helper.
            student.sync_wallet_balance()

    # بروزرسانی کیف پول کل
    final_w_t = student.wallet_teacher if student.wallet_teacher is not None else 0
    final_w_i = student.wallet_institute if student.wallet_institute is not None else 0
    # FIX: Bug 18 - derive the total only through the shared wallet helper.
    student.sync_wallet_balance()

    db.delete(trans_for_delete)
    db.commit()

    # مقایسه مقادیر نهایی با مقادیر اولیه
    final_wallet_teacher = (
        student.wallet_teacher if student.wallet_teacher is not None else 0
    )
    final_wallet_institute = (
        student.wallet_institute if student.wallet_institute is not None else 0
    )
    final_wallet_balance = (
        student.wallet_balance if student.wallet_balance is not None else 0
    )

    wallet_correct = (
        final_wallet_teacher == initial_wallet_teacher
        and final_wallet_institute == initial_wallet_institute
        and final_wallet_balance == initial_wallet_balance
    )

    return {
        "test_passed": wallet_correct,
        "initial_wallets": {
            "teacher": initial_wallet_teacher,
            "institute": initial_wallet_institute,
            "balance": initial_wallet_balance,
        },
        "final_wallets": {
            "teacher": final_wallet_teacher,
            "institute": final_wallet_institute,
            "balance": final_wallet_balance,
        },
        "test_description": "ایجاد → ویرایش (+5000) → حذف تراکنش",
        "expected_result": "کیف پول باید به مقدار اولیه برگردد",
        "actual_result": "برگشت به مقدار اولیه" if wallet_correct else "عدم تطابق",
    }
