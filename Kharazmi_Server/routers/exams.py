import os
import datetime
import random
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

import models
from models import Exam, ExamQuestion, ExamAttempt, Course, Student, Teacher, Enrollment, Grade, Attendance, SessionLog
from storage import storage_dir
from dependencies import get_db, check_user_login, require_permission, NotificationService, check_student_access, get_session_student, get_session_parent, ensure_student_shadow_users

router = APIRouter()

# Secure Storage for PDF Report Cards
# FIX(storage): ریشهٔ واحد فایل‌ها (پیش‌فرض داخل پروژه) — به‌جای مسیر مطلق ماشین توسعه‌دهنده.
PDF_DIR = storage_dir("report_cards")

# Pydantic Schemas
class ExamCreateRequest(BaseModel):
    course_id: int
    title: str
    date: str
    duration: int = 60
    max_score: float = 20.0

class QuestionCreateRequest(BaseModel):
    question_text: str
    type: str  # "multiple_choice", "true_false", "short_answer", "descriptive"
    options: Optional[str] = None  # Comma-separated options if multiple_choice
    correct_answer: str
    score_weight: float = 1.0

class AnswerItem(BaseModel):
    question_id: int
    answer_text: str

class AttemptSubmitRequest(BaseModel):
    answers: List[AnswerItem]

# --- 1. Teacher: Create Exam ---
@router.post("/exams/create")
def create_exam(
    req: ExamCreateRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(require_permission("grade.write"))
):
    from routers.reports import get_logged_in_teacher
    logged_teacher = get_logged_in_teacher(db, authorization)
    if not logged_teacher:
        raise HTTPException(status_code=403, detail="مربی یافت نشد")
        
    course = db.query(Course).filter(Course.id == req.course_id, Course.teacher_id == logged_teacher.id).first()
    if not course:
        raise HTTPException(status_code=403, detail="شما مجاز به تعریف آزمون برای این کلاس نیستید")
        
    new_exam = Exam(
        title=req.title,
        course_id=req.course_id,
        teacher_id=logged_teacher.id,
        date=req.date,
        duration=req.duration,
        max_score=req.max_score,
        status="pending"
    )
    db.add(new_exam)
    db.commit()
    db.refresh(new_exam)
    
    # Automation: Notify all students enrolled
    enrolls = db.query(Enrollment).filter(Enrollment.course_id == req.course_id,
                                         Enrollment.is_deleted == False).all()  # O-04: فقط ثبت‌نام‌های فعال — شاگرد حذف‌شده نباید اعلان بگیرد
    for en in enrolls:
        st = db.query(Student).filter(Student.id == en.student_id).first()
        if st is None:
            continue
        if st.user_id is None:
            ensure_student_shadow_users(db, st)
        NotificationService.send_notification(
            db=db,
            recipient_user_id=st.user_id,
            recipient_role="student",
            type="exam",
            title=f"📅 آزمون جدید: {req.title}",
            body=f"آزمون جدیدی در کلاس {course.title} ثبت شد. تاریخ آزمون: {req.date}"
        )
        
    return {"message": "آزمون با موفقیت ایجاد شد", "exam_id": new_exam.id}

# --- 2. Teacher: Add Question to Exam ---
@router.post("/exams/{id}/questions")
def add_exam_question(
    id: int,
    req: QuestionCreateRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(require_permission("grade.write"))
):
    from routers.reports import get_logged_in_teacher
    logged_teacher = get_logged_in_teacher(db, authorization)
    if not logged_teacher:
        raise HTTPException(status_code=403, detail="مربی یافت نشد")
        
    exam = db.query(Exam).filter(Exam.id == id, Exam.teacher_id == logged_teacher.id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="آزمون یافت نشد")
        
    new_q = ExamQuestion(
        exam_id=id,
        question_text=req.question_text,
        type=req.type,
        options=req.options,
        correct_answer=req.correct_answer,
        score_weight=req.score_weight
    )
    db.add(new_q)
    db.commit()
    return {"message": "سوال با موفقیت به آزمون اضافه شد"}

# --- 3. Student: View Active Exam List ---
@router.get("/exams/student/list")
def get_student_exams_list(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(require_permission("grade.read"))
):
    session = db.query(models.UserSession).filter(models.UserSession.token == authorization.split()[1]).first()
    own = get_session_student(db, session) if session and session.sub_role == "student" else get_session_parent(db, session)
    if not own:
        raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")
    student_id = own.id

    enrolls = db.query(Enrollment).filter(Enrollment.student_id == student_id,
                                         Enrollment.is_deleted == False).all()  # O-04: لیست آزمون/کارنامه فقط از ثبت‌نام‌های فعال
    course_ids = [en.course_id for en in enrolls if en.course]

    exams = db.query(Exam).filter(
        Exam.course_id.in_(course_ids),
        Exam.status == "published",
    ).all()
    
    result = []
    for ex in exams:
        course = db.query(Course).filter(Course.id == ex.course_id).first()
        # Find if student attempted this exam
        attempt = db.query(ExamAttempt).filter(ExamAttempt.exam_id == ex.id, ExamAttempt.student_id == student_id).first()
        status_text = "attempted" if attempt else "pending"
        
        result.append({
            "id": ex.id,
            "title": ex.title,
            "course_title": course.title if course else "کلاس حذف شده",
            "date": ex.date,
            "duration": ex.duration,
            # Retrofit currently decodes this endpoint with HomeworkItem; keep the
            # non-null legacy fields present while the Android model is migrated.
            "description": "",
            "due_date": "",
            "max_score": ex.max_score,
            "status": status_text,
            "score": attempt.score if attempt else None
        })
    return result

# --- 4. Student: Start Attempt ---
@router.post("/exams/attempts/{exam_id}/start")
def start_exam_attempt(
    exam_id: int,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(require_permission("grade.read"))
):
    # FIX: JWT-aware session lookup
    try:
        from dependencies import get_session_from_token
        token = authorization.split()[1]
        sess, _ = get_session_from_token(db, token)
    except Exception:
        sess = db.query(models.UserSession).filter(models.UserSession.token == authorization.split()[1]).first()
    session = sess
    if not session or session.sub_role != "student":
        raise HTTPException(status_code=403, detail="فقط دانش‌آموزان مجاز به شرکت در آزمون هستند")
    own = get_session_student(db, session)
    if not own:
        raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")
    student_id = own.id

    # FIX: بررسی ثبت‌نام دانش‌آموز در کلاس مربوط به آزمون (IDOR protection)
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="آزمون یافت نشد")
    enrollment = db.query(Enrollment).filter(
        Enrollment.student_id == student_id,
        Enrollment.course_id == exam.course_id,
        Enrollment.is_deleted == False,  # O-04: شرکت در آزمون فقط با ثبت‌نام فعال
    ).first()
    if not enrollment:
        raise HTTPException(status_code=403, detail="شما در کلاس مربوط به این آزمون ثبت‌نام نشده‌اید")
    
    # Check if already attempted
    existing = db.query(ExamAttempt).filter(ExamAttempt.exam_id == exam_id, ExamAttempt.student_id == student_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="شما قبلاً در این آزمون شرکت کرده‌اید")
        
    new_attempt = ExamAttempt(
        exam_id=exam_id,
        student_id=student_id,
        started_at=datetime.datetime.utcnow()
    )
    db.add(new_attempt)
    db.commit()
    db.refresh(new_attempt)
    
    # Get all questions
    qs = db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam_id).all()
    questions_list = []
    for q in qs:
        questions_list.append({
            "id": q.id,
            "question_text": q.question_text,
            "type": q.type,
            "options": q.options.split(",") if q.options else []
        })
        
    return {
        "attempt_id": new_attempt.id,
        "duration": db.query(Exam).filter(Exam.id == exam_id).first().duration,
        "questions": questions_list
    }

# --- 5. Student: Submit Attempt and Auto-Grade objective questions ---
@router.post("/exams/attempts/{attempt_id}/submit")
def submit_exam_attempt(
    attempt_id: int,
    req: AttemptSubmitRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(require_permission("grade.read"))
):
    session = db.query(models.UserSession).filter(models.UserSession.token == authorization.split()[1]).first()
    if session.sub_role != "student":
        raise HTTPException(status_code=403, detail="فقط دانش‌آموزان مجاز به ثبت پاسخ‌برگ آزمون هستند")
    attempt = db.query(ExamAttempt).filter(ExamAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="نشست آزمون یافت نشد")
        
    if attempt.submitted_at:
        raise HTTPException(status_code=400, detail="این پاسخ‌برگ قبلاً تحویل داده شده است")
        
    exam = db.query(Exam).filter(Exam.id == attempt.exam_id).first()
    questions = db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam.id).all()
    q_map = {q.id: q for q in questions}
    
    total_score = 0.0
    all_objective = True
    
    # Process answers
    for ans in req.answers:
        q = q_map.get(ans.question_id)
        if q:
            if q.type in ["multiple_choice", "true_false", "short_answer"]:
                # Objective grading
                if ans.answer_text.strip().lower() == q.correct_answer.strip().lower():
                    total_score += q.score_weight
            else:
                all_objective = False
                
    attempt.submitted_at = datetime.datetime.utcnow()
    
    # If all questions are objective, auto-grade is final and complete!
    if all_objective:
        attempt.score = min(total_score, exam.max_score)
        attempt.graded_by_teacher = True
        
        # Integrate into final Grades table automatically to avoid duplication!
        new_grade = Grade(
            student_id=attempt.student_id,
            course_id=exam.course_id,
            teacher_id=exam.teacher_id,
            exam_title=f"آزمون آنلاین: {exam.title}",
            score=attempt.score,
            max_score=exam.max_score,
            date=datetime.datetime.now().strftime("%Y/%m/%d"),
            description="تصحیح خودکار سیستم طراحی"
        )
        db.add(new_grade)
        
        # Automation: Homework Graded -> Notify student & parent
        st = db.query(Student).filter(Student.id == attempt.student_id).first()
        if st:
            if st.user_id is None:
                ensure_student_shadow_users(db, st)
            NotificationService.send_notification(
                db=db,
                recipient_user_id=st.user_id,
                recipient_role="student",
                type="grade",
                title=f"📝 نمره ثبت شد: {exam.title}",
                body=f"نمره آزمون آنلاین '{exam.title}' برای شما ثبت شد: {attempt.score} از {exam.max_score}."
            )
            # FIX (H2/exam-parent): الگوی دوگانه مثل ثبت نمره کلاسی (students.py) — کامنت بالا
            # از اول «Notify student & parent» می‌گفت ولی فقط دانش‌آموز نوتیف می‌گرفت.
            if st.parent_user_id is None:
                ensure_student_shadow_users(db, st)
            NotificationService.send_notification(
                db=db,
                recipient_user_id=st.parent_user_id,
                recipient_role="parent",
                type="grade",
                title=f"📝 نمره آزمون فرزند شما ثبت شد: {exam.title}",
                body=f"نمره آزمون آنلاین '{exam.title}' برای فرزند شما {st.first_name} {st.last_name} ثبت شد: {attempt.score} از {exam.max_score}."
            )
            
    db.commit()
    return {
        "message": "پاسخ‌برگ با موفقیت ثبت شد",
        "is_graded": all_objective,
        "score": attempt.score if all_objective else None
    }

# --- 6. View Report Card ---
@router.get("/students/{student_id}/report_card")
def get_student_report_card(
    student_id: int,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(check_user_login)
):
    # IDOR check
    check_student_access(student_id, authorization, db, role)
    
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="دانش‌آموز یافت نشد")
        
    enrolls = db.query(Enrollment).filter(Enrollment.student_id == student_id,
                                         Enrollment.is_deleted == False).all()  # O-04: لیست آزمون/کارنامه فقط از ثبت‌نام‌های فعال
    
    courses_details = []
    total_scores = []
    
    for en in enrolls:
        if en.course:
            c_title = en.course.title
            
            # Attendance percentage for this class
            sessions = db.query(SessionLog).filter(SessionLog.course_id == en.course_id).all()
            session_ids = [s.id for s in sessions]
            
            total_sessions = len(session_ids)
            p_count = 0
            if total_sessions > 0:
                atts = db.query(Attendance).filter(Attendance.student_id == student_id, Attendance.session_id.in_(session_ids), Attendance.is_deleted == False).all()
                p_count = len([a for a in atts if a.status in ["Present", "Late"]])
                
            attendance_pct = (p_count / total_sessions) * 100 if total_sessions > 0 else 100.0
            
            # Grades for this class
            grades = db.query(Grade).filter(Grade.student_id == student_id, Grade.course_id == en.course_id).all()
            g_list = [{"title": g.exam_title, "score": g.score, "max_score": g.max_score} for g in grades]
            
            avg_score = round(sum([g.score for g in grades]) / len(grades), 2) if grades else 0.0
            if grades:
                total_scores.append(avg_score)
                
            courses_details.append({
                "course_title": c_title,
                "teacher_name": f"{en.course.teacher.first_name} {en.course.teacher.last_name}" if en.course.teacher else "حذف شده",
                "attendance_percentage": round(attendance_percentage, 1) if 'attendance_percentage' in locals() else round(attendance_pct, 1),
                "grades": g_list,
                "average_score": avg_score
            })
            
    overall_avg = round(sum(total_scores) / len(total_scores), 2) if total_scores else 0.0
    
    return {
        "student_name": f"{student.first_name} {student.last_name}",
        "national_code": student.national_code,
        "overall_average": overall_avg,
        "courses": courses_details,
        "comments": "بسیار تلاش‌گر و منظم در کلاس‌ها.",
        "final_status": "قبول با تراز الف" if overall_avg >= 17 else "قبول شایسته تقدیر" if overall_avg >= 12 else "در انتظار بررسی"
    }

# --- 7. Generate PDF Report Card ---
@router.get("/students/{student_id}/report_card/pdf")
def export_report_card_pdf(
    student_id: int,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(check_user_login)
):
    # IDOR check
    check_student_access(student_id, authorization, db, role)
    
    report_data = get_student_report_card(student_id, authorization, db, role)
    
    # Draw simple text file representing PDF and save in uploads folder
    safe_name = f"ReportCard_{student_id}.pdf"
    file_path = os.path.join(storage_dir("report_cards"), safe_name)
    
    # Generate simple, beautiful text representation inside the PDF file
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    
    c = canvas.Canvas(file_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(100, 750, f"KHARAZMI SYSTEM - OFFICIAL REPORT CARD")
    c.setFont("Helvetica", 14)
    c.drawString(100, 710, f"Student: {report_data['student_name']}")
    c.drawString(100, 690, f"National Code: {report_data['national_code']}")
    c.drawString(100, 670, f"Overall GPA/Average: {report_data['overall_average']}")
    c.drawString(100, 650, f"Final Status: {report_data['final_status']}")
    
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, 600, "COURSES & GRADES DETAILS:")
    c.setFont("Helvetica", 11)
    
    startY = 570
    for course in report_data["courses"]:
        c.drawString(100, startY, f"- {course['course_title']} (Teacher: {course['teacher_name']})")
        startY -= 15
        c.drawString(120, startY, f"  Average score: {course['average_score']} | Attendance: {course['attendance_percentage']}%")
        startY -= 20
        
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, startY - 20, f"Comments: {report_data['comments']}")
    c.save()
    
    return FileResponse(file_path, media_type="application/pdf", filename=f"ReportCard_{student_id}.pdf")
