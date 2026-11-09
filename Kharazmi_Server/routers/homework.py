import os
import datetime
import random
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Header
from pydantic import BaseModel, Field  # FIX: Bug 22 - validate finite grading inputs.
from sqlalchemy.orm import Session
from sqlalchemy import desc

import models
from models import Homework, HomeworkSubmission, Course, Enrollment, Student, Teacher
from storage import storage_dir
from dependencies import get_db, check_user_login, require_permission, NotificationService, get_session_student, get_session_parent, ensure_student_shadow_users

router = APIRouter()

# Secure Storage Configuration
# FIX(storage): مسیر پیش‌فرض داخلی پروژه (قابل تغییر با KHARAZMI_UPLOAD_ROOT) —
# الگوی قبلی مسیر مطلق ماشین توسعه‌دهنده بود و در CI/سرور دیگر import را می‌شکست.
UPLOAD_DIR = storage_dir("homework")

# Size limit: 10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".xlsx"}

def sanitize_filename(filename: str) -> str:
    # Extract extension
    name, ext = os.path.splitext(filename)
    # Remove any non-alphanumeric characters
    name = re.sub(r'[^a-zA-Z0-9_\u0600-\u06FF]', '_', name)
    return f"{name}_{random.randint(1000, 9999)}{ext.lower()}"

def validate_file(file: UploadFile) -> str:
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="فرمت فایل مجاز نیست. فقط PDF، Docx و تصویر مجاز است")
    return ext

# Pydantic Schemas
class HomeworkCreateRequest(BaseModel):
    course_id: int
    title: str
    description: str
    due_date: str
    max_score: float = Field(default=20.0, gt=0, allow_inf_nan=False)  # FIX: Bug 22 - valid grading denominator.

class HomeworkResponseModel(BaseModel):
    id: int
    course_id: int
    course_title: str
    title: str
    description: str
    due_date: str
    max_score: float
    status: str
    created_at: str

class GradeSubmissionRequest(BaseModel):
    score: float = Field(ge=0, allow_inf_nan=False)  # FIX: Bug 22 - reject invalid grades before handling.
    feedback: str

# --- 1. Teacher: Create Homework ---
@router.post("/homework/create", response_model=HomeworkResponseModel)
def create_homework(
    req: HomeworkCreateRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(require_permission("homework.create"))
):
    from routers.reports import get_logged_in_teacher
    logged_teacher = get_logged_in_teacher(db, authorization)
    if not logged_teacher:
        raise HTTPException(status_code=403, detail="مربی لاگین شده یافت نشد")
        
    course = db.query(Course).filter(Course.id == req.course_id, Course.teacher_id == logged_teacher.id).first()
    if not course:
        raise HTTPException(status_code=403, detail="شما مجاز به تعریف تکلیف برای این کلاس نیستید")
        
    new_hw = Homework(
        course_id=req.course_id,
        teacher_id=logged_teacher.id,
        title=req.title,
        description=req.description,
        due_date=req.due_date,
        max_score=req.max_score,
        status="pending"
    )
    db.add(new_hw)
    db.commit()
    db.refresh(new_hw)
    
    # Automation: Homework Created -> Notify all enrolled students
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
            type="homework",
            title=f"📝 تکلیف جدید: {req.title}",
            body=f"تکلیف جدیدی در کلاس {course.title} برای شما ثبت شد. سررسید تحویل: {req.due_date}"
        )
        
    return HomeworkResponseModel(
        id=new_hw.id,
        course_id=new_hw.course_id,
        course_title=course.title,
        title=new_hw.title,
        description=new_hw.description,
        due_date=new_hw.due_date,
        max_score=new_hw.max_score,
        status=new_hw.status,
        created_at=new_hw.created_at.strftime("%Y/%m/%d")
    )

# --- 2. Teacher: Delete Homework ---
@router.delete("/homework/{id}")
def delete_homework(
    id: int,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(require_permission("homework.delete"))
):
    from routers.reports import get_logged_in_teacher
    logged_teacher = get_logged_in_teacher(db, authorization)
    if not logged_teacher:
        raise HTTPException(status_code=403, detail="دسترسی غیرمجاز")
        
    hw = db.query(Homework).filter(Homework.id == id, Homework.teacher_id == logged_teacher.id).first()
    if not hw:
        raise HTTPException(status_code=404, detail="تکلیف یافت نشد")
        
    # Delete submissions
    db.query(HomeworkSubmission).filter(HomeworkSubmission.homework_id == id).delete()
    db.delete(hw)
    db.commit()
    return {"message": "تکلیف با موفقیت حذف شد"}

# --- 3. Student: View Homework List ---
@router.get("/homework/student/list")
def get_student_homework_list(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(require_permission("homework.read"))
):
    session = db.query(models.UserSession).filter(models.UserSession.token == authorization.split()[1]).first()
    own = get_session_student(db, session) if session and session.sub_role == "student" else get_session_parent(db, session)
    if not own:
        raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")
    student_id = own.id

    enrolls = db.query(Enrollment).filter(Enrollment.student_id == student_id,
                                         Enrollment.is_deleted == False).all()  # O-04: کلاس‌های ترک‌شده تکلیف/آزمون نشان داده نمی‌شوند
    course_ids = [en.course_id for en in enrolls if en.course]
    
    hws = db.query(Homework).filter(Homework.course_id.in_(course_ids)).order_by(desc(Homework.id)).all()
    
    result = []
    for hw in hws:
        course = db.query(Course).filter(Course.id == hw.course_id).first()
        # Find if student submitted this hw
        submission = db.query(HomeworkSubmission).filter(HomeworkSubmission.homework_id == hw.id, HomeworkSubmission.student_id == student_id).first()
        status_text = submission.status if submission else "pending"
        
        result.append({
            "id": hw.id,
            "course_title": course.title if course else "کلاس حذف شده",
            "title": hw.title,
            "description": hw.description,
            "due_date": hw.due_date,
            "max_score": hw.max_score,
            "status": status_text,
            "score": submission.score if submission else None,
            "feedback": submission.feedback if submission else None
        })
    return result

# --- 4. Student: Submit Homework with secure File Upload ---
@router.post("/homework/submissions/{homework_id}/submit")
async def submit_homework_file(
    homework_id: int,
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(require_permission("homework.update"))
):
    session = db.query(models.UserSession).filter(models.UserSession.token == authorization.split()[1]).first()
    own = get_session_student(db, session)
    if not own:
        raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")
    student_id = own.id

    # Verify enrollment in this homework's course
    hw = db.query(Homework).filter(Homework.id == homework_id).first()
    if not hw:
        raise HTTPException(status_code=404, detail="تکلیف یافت نشد")
        
    enrolled = db.query(Enrollment).filter(Enrollment.student_id == student_id,
                                           Enrollment.course_id == hw.course_id,
                                           Enrollment.is_deleted == False).first()  # O-04: تحویل فایل فقط با ثبت‌نام فعال
    if not enrolled:
        raise HTTPException(status_code=403, detail="شما در این کلاس ثبت‌نام نکرده‌اید")
        
    # File upload validation
    ext = validate_file(file)
    safe_name = sanitize_filename(file.filename)
    # در زمان نوشتن دوباره resolve می‌شود تا override محیطی/تست معتبر باشد
    file_path = os.path.join(storage_dir("homework"), safe_name)
    
    # Save the file securely
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="سایز فایل بیش از حد مجاز (۱۰ مگابایت) است")
        
    with open(file_path, "wb") as f:
        f.write(contents)
        
    # Save or update submission
    submission = db.query(HomeworkSubmission).filter(HomeworkSubmission.homework_id == homework_id, HomeworkSubmission.student_id == student_id).first()
    
    from today_summary import parse_project_date  # FIX H3-B3: due_date is free text (often Jalali); compare real dates (lazy import)
    today_date = datetime.datetime.now().date()
    _due = parse_project_date(hw.due_date)
    # No valid deadline → can't be late.
    status_val = "submitted" if (_due is None or _due >= today_date) else "late"
    
    if submission:
        # Edit submission before grading
        if submission.status == "graded":
            raise HTTPException(status_code=400, detail="این تکلیف قبلاً تصحیح شده و قابل ویرایش نیست")
        submission.file_path = file_path
        submission.status = status_val
    else:
        submission = HomeworkSubmission(
            homework_id=homework_id,
            student_id=student_id,
            file_path=file_path,
            status=status_val
        )
        db.add(submission)
        
    db.commit()
    return {"message": "تکلیف با موفقیت تحویل داده شد", "file_path": file_path}

# --- 5. Teacher: Grade Submission ---
@router.post("/homework/submissions/{sub_id}/grade")
def grade_homework_submission(
    sub_id: int,
    req: GradeSubmissionRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(require_permission("homework.grade"))
):
    from routers.reports import get_logged_in_teacher
    logged_teacher = get_logged_in_teacher(db, authorization)
    if not logged_teacher:
        raise HTTPException(status_code=403, detail="دسترسی غیرمجاز")
        
    sub = db.query(HomeworkSubmission).filter(HomeworkSubmission.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="پاسخ تکلیف یافت نشد")
        
    hw = db.query(Homework).filter(Homework.id == sub.homework_id, Homework.teacher_id == logged_teacher.id).first()
    if not hw:
        raise HTTPException(status_code=403, detail="شما مجاز به تصحیح این تکلیف نیستید")
        
    # FIX: Bug 22 - the authoritative maximum is on the homework, not the grading request.
    if req.score > hw.max_score:
        raise HTTPException(status_code=400, detail="نمره نمی‌تواند بیشتر از نمرهٔ کل تکلیف باشد")

    sub.score = req.score
    sub.feedback = req.feedback
    sub.status = "graded"
    db.commit()
    
    # Automation: Homework Graded -> Notify student
    st = db.query(Student).filter(Student.id == sub.student_id).first()
    if st:
        if st.user_id is None:
            ensure_student_shadow_users(db, st)
        NotificationService.send_notification(
            db=db,
            recipient_user_id=st.user_id,
            recipient_role="student",
            type="homework",
            title=f"📝 تکلیف تصحیح شد: {hw.title}",
            body=f"نمره شما در تکلیف '{hw.title}' ثبت شد: {req.score} از {hw.max_score}. بازخورد: {req.feedback}"
        )
        
    return {"message": "نمره و بازخورد با موفقیت ثبت شد"}

# --- 6. Parent: View Child's Homework List ---
@router.get("/homework/parent/child/{student_id}")
def get_parent_child_homework(
    student_id: int,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(require_permission("homework.read"))
):
    session = db.query(models.UserSession).filter(models.UserSession.token == authorization.split()[1]).first()
    
    # 🛡️ پیاده‌سازی لایه ضد نشت داده و ضد IDOR برای اولیا
    if session.sub_role == "parent":
        own = get_session_parent(db, session)
        if not own or student_id != own.id:
            raise HTTPException(status_code=403, detail="شما مجاز به مشاهده اطلاعات این دانش‌آموز نیستید (IDOR Protection)")
    # FIX (L14/Y2-F2): else‌ی قبلی «هر غیرِ ولی = ادمین» فرض می‌کرد و شاگرد A را به تکلیف B می‌رساند —
    # حالا صراحتاً فقط ادمین/منشی؛ شاگرد (و نقش ناشناخته) 403.
    elif session.sub_role not in ("admin", "secretary"):
        raise HTTPException(status_code=403, detail="شما مجاز به مشاهده تکالیف این دانش‌آموز نیستید")
        
    enrolls = db.query(Enrollment).filter(Enrollment.student_id == student_id,
                                         Enrollment.is_deleted == False).all()  # O-04: کلاس‌های ترک‌شده تکلیف/آزمون نشان داده نمی‌شوند
    course_ids = [en.course_id for en in enrolls if en.course]
    
    hws = db.query(Homework).filter(Homework.course_id.in_(course_ids)).all()
    
    result = []
    for hw in hws:
        course = db.query(Course).filter(Course.id == hw.course_id).first()
        submission = db.query(HomeworkSubmission).filter(HomeworkSubmission.homework_id == hw.id, HomeworkSubmission.student_id == student_id).first()
        status_text = submission.status if submission else "pending"
        
        result.append({
            "id": hw.id,
                "course_title": course.title if course else "کلاس حذف شده",
                "title": hw.title,
                "description": hw.description or "",
                "due_date": hw.due_date,
                "status": status_text,
                "max_score": hw.max_score,
            "score": submission.score if submission else None,
            "feedback": submission.feedback if submission else None
        })
    return result
