from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Annotated, List, Optional
from pydantic import BaseModel, StringConstraints
import datetime

import models
from models import AutomationRule, AutomationLog, Student, Teacher, Course, Enrollment, Attendance, Installment, Homework, Grade, Lead, Notification, SmsLog, SessionLog
from dependencies import get_db, check_admin_access, check_user_login, ensure_student_shadow_users, NotificationService

router = APIRouter()

# Pydantic schema
RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class RuleCreateRequest(BaseModel):
    name: RequiredText
    condition_type: str
    threshold: float
    action_type: RequiredText
    confirm_unknown_action: bool = False

class RuleUpdateRequest(BaseModel):
    name: Optional[RequiredText] = None
    threshold: Optional[float] = None
    action_type: Optional[RequiredText] = None
    active: Optional[bool] = None
    confirm_unknown_action: bool = False


VALID_ACTIONS = {
    "parent_notification", "parent_alert", "student_notification",
    "teacher_alert", "crm_reminder", "sms",
}


def _unknown_action_error() -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={
            "code": "unknown_action",
            "message": "نوع عملیات نامعتبر است",
            "can_continue": True,
        },
    )


# Helper function to trigger notification action
def trigger_notification_action(db: Session, rule_id: int, recipient_id: int, recipient_role: str, title: str, body: str, trigger_details: str):
    # FIX (بچ ۲): مپ مرکزی Student.id به آیدی سایه؛ نقش‌های دیگر (مثل admin) دست نخورده می‌مانند
    notif_recipient = recipient_id
    if recipient_role in ("student", "parent"):
        st = db.query(Student).filter(Student.id == recipient_id).first()
        if st is None:
            return
        if recipient_role == "parent":
            if st.parent_user_id is None:
                ensure_student_shadow_users(db, st)
            notif_recipient = st.parent_user_id
        else:
            if st.user_id is None:
                ensure_student_shadow_users(db, st)
            notif_recipient = st.user_id
    # Create notification record
    notif = Notification(
        recipient_user_id=notif_recipient,
        recipient_role=recipient_role,
        type="automation",
        title=title,
        body=body
    )
    db.add(notif)
    
    # Write to AutomationLog
    log = AutomationLog(
        rule_id=rule_id,
        triggered_at=datetime.datetime.utcnow(),
        details=f"Triggered for {recipient_role} #{recipient_id}. {trigger_details}"
    )
    db.add(log)


# ==========================================
# ۱. مدیریت قوانین خودکارسازی (Admin Rules Management)
# ==========================================

@router.post("/automation/rules")
def create_automation_rule(
    req: RuleCreateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access)
):
    valid_conditions = ["attendance_low", "absence_high", "installment_due", "installment_overdue", "homework_deadline", "grade_low", "student_inactive", "lead_uncontacted"]
    
    if req.condition_type not in valid_conditions:
        raise HTTPException(status_code=400, detail="نوع شرط نامعتبر است")
    if req.action_type not in VALID_ACTIONS and not req.confirm_unknown_action:
        raise _unknown_action_error()
        
    new_rule = AutomationRule(
        name=req.name,
        condition_type=req.condition_type,
        threshold=req.threshold,
        action_type=req.action_type,
        active=True
    )
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)
    return {"message": "قانون خودکارسازی جدید با موفقیت ایجاد شد", "rule_id": new_rule.id}


@router.put("/automation/rules/{rule_id}")
def update_automation_rule(
    rule_id: int,
    req: RuleUpdateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access)
):
    rule = db.query(AutomationRule).filter(AutomationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="قانون مورد نظر یافت نشد")
        
    if req.name is not None:
        rule.name = req.name
    if req.threshold is not None:
        rule.threshold = req.threshold
    if req.action_type is not None:
        if req.action_type not in VALID_ACTIONS and not req.confirm_unknown_action:
            raise _unknown_action_error()
        rule.action_type = req.action_type
    if req.active is not None:
        rule.active = req.active
        
    db.commit()
    return {"message": "قانون خودکارسازی با موفقیت بروزرسانی شد"}


@router.get("/automation/rules")
def get_automation_rules(
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access)  # FIX (L14/Y4): قوانین اتوماسیون — فقط ادمین (متقارن با create/update/run)
):
    return db.query(AutomationRule).all()


@router.get("/automation/logs")
def get_automation_logs(
    rule_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access)  # FIX (L14/Y4): لاگ اتوماسیون — فقط ادمین (متقارن با writeها)
):
    query = db.query(AutomationLog)
    if rule_id:
        query = query.filter(AutomationLog.rule_id == rule_id)
    return query.order_by(AutomationLog.triggered_at.desc()).offset(offset).limit(limit).all()


# ==========================================
# ۲. اجرای موتور خودکارسازی (Rule Executor Engine)
# ==========================================

@router.post("/automation/run_rules")
def run_automation_engine(
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access)
):
    active_rules = db.query(AutomationRule).filter(AutomationRule.active == True).all()
    triggered_count = 0
    
    for rule in active_rules:
        # 1. Attendance < 80% (attendance_low)
        if rule.condition_type == "attendance_low":
            students = db.query(Student).filter(Student.is_deleted == False).all()
            for s in students:
                enrollments = db.query(Enrollment).filter(Enrollment.student_id == s.id).all()
                for en in enrollments:
                    # Count attendances
                    total_sessions = db.query(Attendance).join(SessionLog).filter(
                        SessionLog.course_id == en.course_id,
                        Attendance.student_id == s.id,
                        Attendance.is_deleted == False,   # FIX (F-S2)
                    ).count()
                    if total_sessions > 2: # run only if at least 3 sessions held
                        presents = db.query(Attendance).join(SessionLog).filter(
                            SessionLog.course_id == en.course_id,
                            Attendance.student_id == s.id,
                            Attendance.is_deleted == False,   # FIX (F-S2)
                            Attendance.status == "Present"
                        ).count()
                        rate = (presents / total_sessions) * 100
                        if rate < rule.threshold:
                            # Trigger action
                            course_title = en.course.title if en.course else "کلاس"
                            title = "⚠️ هشدار حضور و غیاب دانش‌آموز"
                            body = f"ولی محترم، به اطلاع می‌رساند میزان حضور فرزند شما {s.first_name} در کلاس {course_title} کمتر از {rule.threshold}% ({rate:.1f}%) است. لطفاً پیگیری فرمایید."
                            # check if already logged today to prevent duplicate reminders
                            already = db.query(AutomationLog).filter(
                                AutomationLog.rule_id == rule.id,
                                AutomationLog.details.like(f"%Student #{s.id}%"),
                                AutomationLog.triggered_at >= datetime.datetime.utcnow() - datetime.timedelta(days=1)
                            ).first()
                            if not already:
                                trigger_notification_action(db, rule.id, s.id, "parent", title, body, f"Student #{s.id} in class {en.course_id} has {rate:.1f}% attendance.")
                                triggered_count += 1
                                
        # 2. Absence >= 2 (absence_high)
        elif rule.condition_type == "absence_high":
            students = db.query(Student).filter(Student.is_deleted == False).all()
            for s in students:
                enrollments = db.query(Enrollment).filter(Enrollment.student_id == s.id).all()
                for en in enrollments:
                    absences = db.query(Attendance).join(SessionLog).filter(
                        SessionLog.course_id == en.course_id,
                        Attendance.student_id == s.id,
                        Attendance.is_deleted == False,   # FIX (F-S2)
                        Attendance.status == "Absent",
                        Attendance.excused == False
                    ).count()
                    if absences >= rule.threshold:
                        course_title = en.course.title if en.course else "کلاس"
                        title = "🚨 هشدار غیبت غیرموجه مکرر"
                        body = f"ولی محترم، فرزند شما {s.first_name} دارای {absences} جلسه غیبت غیرموجه در کلاس {course_title} می‌باشد."
                        already = db.query(AutomationLog).filter(
                            AutomationLog.rule_id == rule.id,
                            AutomationLog.details.like(f"%Student #{s.id}%"),
                            AutomationLog.triggered_at >= datetime.datetime.utcnow() - datetime.timedelta(days=1)
                        ).first()
                        if not already:
                            trigger_notification_action(db, rule.id, s.id, "parent", title, body, f"Student #{s.id} has {absences} absences in class {en.course_id}.")
                            triggered_count += 1

        # 3. Installment due tomorrow (installment_due)
        elif rule.condition_type == "installment_due":
            # FIX: Bug 13 - exclude archived Installment rows from this active view.
            # FIX H3-B1: due_date is Jalali (mixed with Gregorian 1st installments); SQL string compare vs Gregorian tomorrow can never match.
            # Fetch unpaid + filter as real dates in Python via the central converter.
            from today_summary import parse_project_date  # lazy import, same pattern as routers/analytics.py
            tomorrow_date = datetime.datetime.now().date() + datetime.timedelta(days=1)
            installments = db.query(Installment).filter(Installment.is_deleted == False).filter(Installment.is_paid == False).all()
            for inst in installments:
                if parse_project_date(inst.due_date) != tomorrow_date:
                    continue
                enroll = db.query(Enrollment).filter(Enrollment.id == inst.enrollment_id).first()
                if enroll:
                    st = db.query(Student).filter(Student.id == enroll.student_id).first()
                    if st:
                        title = "📅 سررسید قسط شهریه فردا"
                        body = f"ولی محترم، به اطلاع می‌رساند قسط شهریه فرزند شما {st.first_name} به مبلغ {inst.amount:,} تومان فردا {inst.due_date} سررسید می‌شود."
                        already = db.query(AutomationLog).filter(
                            AutomationLog.rule_id == rule.id,
                            AutomationLog.details.like(f"%Installment #{inst.id}%")
                        ).first()
                        if not already:
                            trigger_notification_action(db, rule.id, st.id, "parent", title, body, f"Installment #{inst.id} is due tomorrow.")
                            triggered_count += 1

        # 4. Installment overdue (installment_overdue)
        elif rule.condition_type == "installment_overdue":
            # Unpaid installments due before today
            # FIX: Bug 13 - exclude archived Installment rows from this active view.
            # FIX H3-B1: same as installment_due above — overdue must compare real dates, not Jalali-vs-Gregorian strings.
            from today_summary import parse_project_date  # repeated: elif branches are independent scopes at runtime
            today_date = datetime.datetime.now().date()
            overdue = db.query(Installment).filter(Installment.is_deleted == False).filter(Installment.is_paid == False).all()
            for inst in overdue:
                due = parse_project_date(inst.due_date)
                if due is None or due >= today_date:
                    continue
                enroll = db.query(Enrollment).filter(Enrollment.id == inst.enrollment_id).first()
                if enroll:
                    st = db.query(Student).filter(Student.id == enroll.student_id).first()
                    if st:
                        title = "🚨 قسط شهریه معوقه شده"
                        body = f"ولی محترم، قسط شهریه فرزند شما {st.first_name} به مبلغ {inst.amount:,} تومان معوقه شده است. لطفاً نسبت به تسویه حساب اقدام فرمایید."
                        already = db.query(AutomationLog).filter(
                            AutomationLog.rule_id == rule.id,
                            AutomationLog.details.like(f"%Installment #{inst.id}%"),
                            AutomationLog.triggered_at >= datetime.datetime.utcnow() - datetime.timedelta(days=7) # once a week maximum
                        ).first()
                        if not already:
                            trigger_notification_action(db, rule.id, st.id, "parent", title, body, f"Installment #{inst.id} is overdue.")
                            # Send SMS log as well
                            if rule.action_type in ["parent_alert", "sms"]:
                                db.add(SmsLog(
                                    target_group=f"overdue_{inst.id}",
                                    message_text=body,
                                    sent_count=1,
                                    date=datetime.datetime.now().strftime("%Y/%m/%d %H:%M")
                                ))
                            triggered_count += 1

        # 5. Homework deadline < 24h (homework_deadline)
        elif rule.condition_type == "homework_deadline":
            # Find homework assignments due soon
            hws = db.query(Homework).all()
            for hw in hws:
                try:
                    due_dt = datetime.datetime.strptime(hw.due_date, "%Y/%m/%d")
                    diff = due_dt - datetime.datetime.now()
                    if 0 < diff.total_seconds() < (rule.threshold * 3600):
                        # Find students in this course
                        enrolls = db.query(Enrollment).filter(Enrollment.course_id == hw.course_id).all()
                        for en in enrolls:
                            # Check if submitted
                            from models import HomeworkSubmission
                            sub = db.query(HomeworkSubmission).filter(HomeworkSubmission.homework_id == hw.id, HomeworkSubmission.student_id == en.student_id).first()
                            if not sub:
                                title = "📝 یادآوری تمرین درسی"
                                body = f"دانش‌آموز گرامی، کمتر از ۲۴ ساعت به مهلت تحویل تمرین '{hw.title}' باقی مانده است. لطفاً پاسخ خود را بارگذاری کنید."
                                already = db.query(AutomationLog).filter(
                                    AutomationLog.rule_id == rule.id,
                                    AutomationLog.details.like(f"%HW #{hw.id} Student #{en.student_id}%")
                                ).first()
                                if not already:
                                    trigger_notification_action(db, rule.id, en.student_id, "student", title, body, f"HW #{hw.id} Student #{en.student_id} deadline approaching.")
                                    triggered_count += 1
                except ValueError:
                    pass

        # 6. Grade below threshold (grade_low)
        elif rule.condition_type == "grade_low":
            grades = db.query(Grade).filter(Grade.score < rule.threshold).all()
            for g in grades:
                st = db.query(Student).filter(Student.id == g.student_id).first()
                if st:
                    title = "📉 هشدار افت تحصیلی و نمره ضعیف"
                    body = f"ولی محترم، به اطلاع می‌رساند فرزند شما {st.first_name} در آزمون '{g.exam_title}' نمره {g.score} از {g.max_score} را کسب کرده است."
                    already = db.query(AutomationLog).filter(
                        AutomationLog.rule_id == rule.id,
                        AutomationLog.details.like(f"%Grade #{g.id}%")
                    ).first()
                    if not already:
                        trigger_notification_action(db, rule.id, st.id, "parent", title, body, f"Grade #{g.id} score {g.score} is below {rule.threshold}.")
                        triggered_count += 1

        # 7. Student inactive (student_inactive)
        elif rule.condition_type == "student_inactive":
            # Students with no attendances in last X days
            students = db.query(Student).filter(Student.is_deleted == False).all()
            for s in students:
                last_attendance = db.query(Attendance).join(SessionLog).filter(
                    Attendance.student_id == s.id,
                    Attendance.is_deleted == False,   # FIX (F-S2)
                ).order_by(SessionLog.date.desc()).first()
                if last_attendance:
                    try:
                        session_dt = datetime.datetime.strptime(last_attendance.session.date, "%Y/%m/%d")
                        days_diff = (datetime.datetime.now() - session_dt).days
                        if days_diff > rule.threshold:
                            title = "👤 پیگیری وضعیت دانش‌آموز غیرفعال"
                            body = f"دانش‌آموز {s.first_name} {s.last_name} بیش از {days_diff} روز است که فعالیت آموزشی (حضور و غیاب) نداشته است."
                            already = db.query(AutomationLog).filter(
                                AutomationLog.rule_id == rule.id,
                                AutomationLog.details.like(f"%Inactive Student #{s.id}%"),
                                AutomationLog.triggered_at >= datetime.datetime.utcnow() - datetime.timedelta(days=30)
                            ).first()
                            if not already:
                                # Trigger parent or admin alert
                                trigger_notification_action(db, rule.id, s.id, "parent", title, f"دانش‌آموز گرامی، مدتی است در کلاس‌ها غایب هستید. جهت هماهنگی با مدیریت تماس بگیرید.", f"Inactive Student #{s.id} with last activity {days_diff} days ago.")
                                triggered_count += 1
                    except Exception:
                        pass

        # 8. Lead not contacted for X days (lead_uncontacted)
        elif rule.condition_type == "lead_uncontacted":
            leads = db.query(Lead).filter(Lead.status == "NEW").all()
            for ld in leads:
                days_diff = (datetime.datetime.utcnow() - ld.created_at).days
                if days_diff > rule.threshold:
                    title = "📞 پیگیری سرنخ جذب جدید"
                    body = f"سرنخ '{ld.name}' به شماره '{ld.mobile}' به مدت {days_diff} روز است که تماسی با او گرفته نشده است. لطفاً بررسی فرمایید."
                    already = db.query(AutomationLog).filter(
                        AutomationLog.rule_id == rule.id,
                        AutomationLog.details.like(f"%Lead #{ld.id}%"),
                        AutomationLog.triggered_at >= datetime.datetime.utcnow() - datetime.timedelta(days=3)
                    ).first()
                    if not already:
                        # FIX(admin-notifications): قبلاً recipient_id=1 هاردکد بود و نقش admin
                        # دست‌نخورده به Notification می‌رفت ⇒ اعلان به کاربرِ شماره ۱ (که معمولاً
                        # ادمین نیست) می‌رفت و ادمینِ واقعی هیچ‌وقت آن را نمی‌دید. حالا گیرندگان
                        # از فضای User.id و بر اساس شعبه‌ی سرنخ resolve می‌شوند (ادمین‌ها + منشی‌ها).
                        recipients = NotificationService.send_to_staff(
                            db, type="automation", title=title, body=body,
                            data={"lead_id": ld.id, "branch_id": ld.branch_id},
                            branch_id=ld.branch_id,
                        )
                        db.add(AutomationLog(
                            rule_id=rule.id,
                            triggered_at=datetime.datetime.utcnow(),
                            details=(f"Triggered for admin staff ({len(recipients)} recipients). "
                                     f"Lead #{ld.id} uncontacted for {days_diff} days.")
                        ))
                        triggered_count += 1

    db.commit()
    return {"status": "success", "message": "قوانین خودکارسازی با موفقیت بررسی و اجرا شدند.", "triggered_actions_count": triggered_count}
