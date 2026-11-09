from sqlalchemy.orm import Session
import models
from models import Teacher, Student, Course, Enrollment, Transaction, SessionLocal, engine, InstituteShare, PricingTable
import datetime

# اتصال به دیتابیس
models.Base.metadata.create_all(bind=engine)
db = SessionLocal()

def seed_real_data():
    print("⏳ در حال بررسی و تزریق داده‌های اولیه...")

    # بذرافشانی جدول قیمت‌گذاری مقطعی ۵ نفره
    if not db.query(PricingTable).first():
        p_elem = PricingTable(category="elementary", count_1=100000, count_2=160000, count_3=210000, count_4=240000, count_5=250000)
        p_mid = PricingTable(category="middle_school", count_1=120000, count_2=180000, count_3=240000, count_4=280000, count_5=300000)
        p_high = PricingTable(category="high_school", count_1=150000, count_2=240000, count_3=300000, count_4=360000, count_5=400000)
        p_inst = PricingTable(category="institute", count_1=50000, count_2=80000, count_3=100000, count_4=120000, count_5=150000)
        db.add_all([p_elem, p_mid, p_high, p_inst])
        db.commit()
        print("✅ جدول قیمت‌گذاری ۵ نفره با موفقیت مقداردهی شد.")

    # 0. تنظیمات اولیه سهم آموزشگاه (حیاتی برای سیستم جدید)
    # اگر وجود نداشت، می‌سازیم
    if not db.query(InstituteShare).first():
        share_config = InstituteShare(
            count_1=50000,   # اگر 1 نفر بود، 50 تومن سهم آموزشگاه
            count_2=80000,   # اگر 2 نفر بودند، 80 تومن
            count_3=100000,  # 3 نفر = 100 تومن
            count_4=120000,
            count_5=150000,
            count_6=180000,
            count_7=200000,
            count_8=220000,
            count_9=250000,
            count_10=280000,
            count_11=300000,
            count_12=320000,
            count_13=350000,
            count_14=380000,
            count_15=400000
        )
        db.add(share_config)
        db.commit()
        print("✅ جدول تعرفه سهم آموزشگاه ایجاد شد.")

    # 1. ساخت معلم (سید محمد موسوی)
    # چک میکنیم تکراری نسازیم
    teacher = db.query(Teacher).filter(Teacher.national_code == "0001000004").first()
    if not teacher:
        teacher = Teacher(
            first_name="سید محمد", last_name="موسوی",
            mobile="09120000000", national_code="0001000004",
            password="123", # رمز عبور برای تست
            gender="آقا", employment_type="رسمی",
            is_approved=True # تایید شده توسط مدیر
        )
        db.add(teacher)
        db.commit()
        print("✅ معلم (سید محمد موسوی) ایجاد شد.")

    # 2. ساخت کلاس (کد 3406 - ریاضی کنکور) - منطق جدید
    course = db.query(Course).filter(Course.code == "3406").first()
    if not course:
        course = Course(
            title="ریاضی کنکور", code="3406",
            teacher_id=teacher.id,
            grade_level="کنکور", education_type="کنکور",
            class_type="خصوصی", 
            
            # 👇 فیلدهای جدید
            days_of_week="زوج",
            class_time="16:30",
            teacher_session_price=500000, # معلم جلسه‌ای 500 هزار تومن می‌خواهد
            is_admin_approved=True # تایید شده
        )
        db.add(course)
        db.commit()
        print("✅ کلاس (ریاضی کنکور - 3406) با تعرفه جدید ایجاد شد.")

    # 3. ساخت دانش‌آموز (الارا صیامی)
    student1 = db.query(Student).filter(Student.national_code == "0001000012").first()
    if not student1:
        student1 = Student(
            first_name="الارا", last_name="صیامی",
            national_code="0001000012", student_mobile="09351111111",
            gender="خانم", study_status="در حال تحصیل"
        )
        db.add(student1)
        db.commit()

    # 4. ساخت دانش‌آموز (فخرالنسا پوریافرانی)
    student2 = db.query(Student).filter(Student.national_code == "0001000020").first()
    if not student2:
        student2 = Student(
            first_name="فخرالنسا", last_name="پوریافرانی",
            national_code="0001000020", student_mobile="09352222222",
            gender="خانم", study_status="در حال تحصیل"
        )
        db.add(student2)
        db.commit()
        print("✅ دانش‌آموزان ایجاد شدند.")

    # 5. ثبت نام اولیه (Enrollment)
    if not db.query(Enrollment).filter(Enrollment.student_id == student1.id, Enrollment.course_id == course.id).first():
        enroll1 = Enrollment(
            student_id=student1.id, course_id=course.id,
            register_date="1404/09/06", 
            shift="عصر",
            total_tuition=0, # در سیستم جدید محاسبه دینامیک است، اینجا صفر یا مبلغ اولیه
            total_paid=2000000
        )
        db.add(enroll1)
        
        # شارژ کیف پول دانش آموز (چون 2 تومن داده)
        # FIX: Bug 18 - update a component, then derive the total through the shared helper.
        student1.wallet_institute = (student1.wallet_institute or 0) + 2000000
        student1.sync_wallet_balance()
        
        # ثبت تراکنش
        trans1 = Transaction(
            student_id=student1.id, # اتصال به شاگرد
            amount=2000000, 
            payment_method="دستی", date="1404/09/06",
            receiver="Institute", description="علی‌الحساب شهریه"
        )
        db.add(trans1)
        db.commit()
        print("✅ ثبت‌نام و تراکنش مالی الارا انجام شد.")

    print("🎉 تمام داده‌های اولیه با موفقیت با ساختار جدید هماهنگ شدند.")

if __name__ == "__main__":
    seed_real_data()
