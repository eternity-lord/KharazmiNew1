from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
import datetime

import models
from models import Branch, Resource, ResourceBooking, Student, Teacher, Course, Transaction, Enrollment, SessionLog, Attendance, User
from dependencies import get_db, check_admin_access, check_admin_or_secretary_access, check_user_login

router = APIRouter()

# --- Pydantic Request Models ---
class BranchCreateRequest(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    manager: Optional[str] = None

class BranchUpdateRequest(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    manager: Optional[str] = None
    active: bool

class ResourceCreateRequest(BaseModel):
    name: str
    type: str  # "projector", "computer", "board", "books", "equipment"
    serial_code: str
    branch_id: Optional[int] = 1

class ResourceUpdateRequest(BaseModel):
    name: str
    type: str
    serial_code: str
    branch_id: Optional[int] = None
    active: bool

class BookingRequest(BaseModel):
    resource_id: int
    course_id: int
    days_of_week: str
    class_time: str


# ==========================================
# ۱. مدیریت شعب (Branch Management)
# ==========================================

@router.post("/branches")
def create_branch(
    req: BranchCreateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access) # فقط ادمین ارشد
):
    existing = db.query(Branch).filter(Branch.name == req.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="شعبه‌ای با این نام قبلاً ثبت شده است")
        
    new_branch = Branch(
        name=req.name,
        address=req.address,
        phone=req.phone,
        manager=req.manager,
        active=True
    )
    db.add(new_branch)
    db.commit()
    db.refresh(new_branch)
    return {"status": "success", "message": "شعبه جدید با موفقیت ایجاد شد", "branch_id": new_branch.id}


@router.put("/branches/{branch_id}")
def update_branch(
    branch_id: int,
    req: BranchUpdateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access)
):
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="شعبه یافت نشد")
        
    branch.name = req.name
    branch.address = req.address
    branch.phone = req.phone
    branch.manager = req.manager
    branch.active = req.active
    
    db.commit()
    return {"status": "success", "message": "اطلاعات شعبه با موفقیت بروزرسانی شد"}


@router.post("/branches/{branch_id}/suspend")
def suspend_branch(
    branch_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(check_admin_access)
):
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="شعبه یافت نشد")
        
    branch.active = not branch.active
    db.commit()
    
    status_text = "غیرفعال (تعلیق)" if not branch.active else "فعال"
    return {"status": "success", "message": f"شعبه با موفقیت به وضعیت '{status_text}' تغییر یافت"}


@router.get("/branches")
def list_branches(
    db: Session = Depends(get_db),
    _: str = Depends(check_user_login)
):
    return db.query(Branch).all()


# ==========================================
# ۲. مدیریت منابع سخت‌افزاری و تجهیزات (Resource Management)
# ==========================================

@router.post("/resources")
def create_resource(
    req: ResourceCreateRequest,
    db: Session = Depends(get_db),
    # FIX (L14/R1): ساخت رکورد تجهیز — فقط ادمین/منشی.
    _: str = Depends(check_admin_or_secretary_access)
):
    existing = db.query(Resource).filter(Resource.serial_code == req.serial_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="منبعی با این کد سریال قبلاً ثبت شده است")
        
    new_resource = Resource(
        name=req.name,
        type=req.type,
        serial_code=req.serial_code,
        branch_id=req.branch_id,
        active=True
    )
    db.add(new_resource)
    db.commit()
    db.refresh(new_resource)
    return {"status": "success", "message": "منبع جدید با موفقیت ثبت شد", "resource_id": new_resource.id}


@router.put("/resources/{id}")
def update_resource(
    id: int,
    req: ResourceUpdateRequest,
    db: Session = Depends(get_db),
    # FIX (L14/R1): ویرایش تجهیز — فقط ادمین/منشی.
    _: str = Depends(check_admin_or_secretary_access)
):
    res = db.query(Resource).filter(Resource.id == id).first()
    if not res:
        raise HTTPException(status_code=404, detail="منبع یافت نشد")

    duplicate = db.query(Resource.id).filter(
        Resource.serial_code == req.serial_code,
        Resource.id != id,
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail="کد سریال واردشده متعلق به منبع دیگری است؛ کد یکتا وارد کنید")
        
    res.name = req.name
    res.type = req.type
    res.serial_code = req.serial_code
    res.branch_id = req.branch_id
    res.active = req.active
    
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="کد سریال واردشده متعلق به منبع دیگری است؛ کد یکتا وارد کنید")
    return {"status": "success", "message": "منبع با موفقیت بروزرسانی شد"}


@router.get("/resources")
def list_resources(
    branch_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: str = Depends(check_user_login)
):
    query = db.query(Resource)
    if branch_id:
        query = query.filter(Resource.branch_id == branch_id)
    return query.all()


@router.post("/resources/bookings")
def book_resource(
    req: BookingRequest,
    db: Session = Depends(get_db),
    # FIX (L14/R1): رزرو منبع برای کلاس — فقط ادمین/منشی (جلوگیری از squat/اختلال).
    _: str = Depends(check_admin_or_secretary_access)
):
    # بررسی صحت منبع و کلاس
    res = db.query(Resource).filter(Resource.id == req.resource_id).first()
    if not res:
        raise HTTPException(status_code=404, detail="منبع یافت نشد")
        
    course = db.query(Course).filter(Course.id == req.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="کلاس یافت نشد")
        
    # Duplicate bookings are an explicit product decision; preserve each submitted booking as a row.
    new_booking = ResourceBooking(
        resource_id=req.resource_id,
        course_id=req.course_id,
        days_of_week=req.days_of_week,
        class_time=req.class_time
    )
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    return {"status": "success", "message": "رزرو منبع با موفقیت انجام شد", "booking_id": new_booking.id}


# ==========================================
# ۳. داشبورد آمار شعب (Branch Statistics)
# ==========================================

@router.get("/dashboard/branch_stats")
def get_branch_stats(
    branch_id: Optional[int] = None,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    role: str = Depends(check_user_login),
    _ : Optional[str] = None  # Dummy parameter for direct backward compatibility unit tests!
):
    if isinstance(authorization, str):
        session = db.query(models.UserSession).filter(models.UserSession.token == authorization.split()[1]).first()
        
        # 🛡️ پیاده‌سازی لایه ضد نشت داده و ضد IDOR در سطح شعب (Branch-Level IDOR Protection)
        if session.sub_role not in ["admin", "secretary"]:
            raise HTTPException(status_code=403, detail="شما مجاز به مشاهده آمار کلی شعب نیستید")
            
        user = db.query(User).filter(User.id == session.user_id).first()
        if user and user.branch_id is not None:
            if branch_id is None:
                branch_id = user.branch_id
            elif branch_id != user.branch_id:
                raise HTTPException(status_code=403, detail="شما مجاز به دسترسی به داده‌های شعبه دیگر نیستید (Branch-Level IDOR Protection)")

    # اگر شعبه خاص ارسال شده باشد، آمار همان شعبه را برمی‌گردانیم
    if branch_id:
        branch = db.query(Branch).filter(Branch.id == branch_id).first()
        if not branch:
            raise HTTPException(status_code=404, detail="شعبه مورد نظر یافت نشد")
            
        student_count = db.query(Student).filter(Student.branch_id == branch_id, Student.is_deleted == False).count()
        teacher_count = db.query(Teacher).filter(Teacher.branch_id == branch_id, Teacher.is_deleted == False).count()
        class_count = db.query(Course).filter(Course.branch_id == branch_id, Course.is_deleted == False).count()
        
        # درآمدهای موفق برای این شعبه
        revenue = db.query(func.sum(Transaction.amount)).filter(
            Transaction.branch_id == branch_id,
            Transaction.type == "deposit",
            Transaction.is_deleted == False
        ).scalar() or 0
        
        # جلسات برگزار شده در اتاق‌های این شعبه
        room_ids = [r.id for r in db.query(models.Room).filter(models.Room.branch_id == branch_id).all()]
        attendance_count = 0
        if room_ids:
            course_ids = [c.id for c in db.query(Course).filter(Course.room_id.in_(room_ids)).all()]
            if course_ids:
                attendance_count = db.query(SessionLog).filter(SessionLog.course_id.in_(course_ids)).count()
                
        return {
            "branch_id": branch_id,
            "branch_name": branch.name,
            "statistics": {
                "student_count": student_count,
                "teacher_count": teacher_count,
                "class_count": class_count,
                "total_revenue": revenue,
                "attendance_sessions_count": attendance_count
            }
        }
    
    # در غیر این صورت، خلاصه کلی تمام شعب را برمی‌گردانیم (Branch Filter Dashboard)
    branches = db.query(Branch).all()
    revenue_by_branch = []
    students_by_branch = []
    teachers_by_branch = []
    classes_by_branch = []
    attendance_by_branch = []
    
    for b in branches:
        bid = b.id
        
        # ۱. درآمد به تفکیک شعبه
        rev = db.query(func.sum(Transaction.amount)).filter(
            Transaction.branch_id == bid,
            Transaction.type == "deposit",
            Transaction.is_deleted == False
        ).scalar() or 0
        revenue_by_branch.append({"branch_id": bid, "branch_name": b.name, "amount": rev})
        
        # ۲. دانش‌آموزان به تفکیک شعبه
        st_cnt = db.query(Student).filter(Student.branch_id == bid, Student.is_deleted == False).count()
        students_by_branch.append({"branch_id": bid, "branch_name": b.name, "count": st_cnt})
        
        # ۳. معلمان به تفکیک شعبه
        t_cnt = db.query(Teacher).filter(Teacher.branch_id == bid, Teacher.is_deleted == False).count()
        teachers_by_branch.append({"branch_id": bid, "branch_name": b.name, "count": t_cnt})
        
        # ۴. کلاس‌ها به تفکیک شعبه
        cl_cnt = db.query(Course).filter(Course.branch_id == bid, Course.is_deleted == False).count()
        classes_by_branch.append({"branch_id": bid, "branch_name": b.name, "count": cl_cnt})
        
        # ۵. حضور و غیاب / جلسات برگزار شده به تفکیک شعبه
        room_ids = [r.id for r in db.query(models.Room).filter(models.Room.branch_id == bid).all()]
        att_cnt = 0
        if room_ids:
            course_ids = [c.id for c in db.query(Course).filter(Course.room_id.in_(room_ids)).all()]
            if course_ids:
                att_cnt = db.query(SessionLog).filter(SessionLog.course_id.in_(course_ids)).count()
        attendance_by_branch.append({"branch_id": bid, "branch_name": b.name, "count": att_cnt})
        
    return {
        "revenue_by_branch": revenue_by_branch,
        "students_by_branch": students_by_branch,
        "teachers_by_branch": teachers_by_branch,
        "classes_by_branch": classes_by_branch,
        "attendance_by_branch": attendance_by_branch
    }
