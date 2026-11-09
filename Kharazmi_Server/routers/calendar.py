import os
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

import models
from models import Room, Course, Teacher, Student, Enrollment, SessionLog, Grade, Installment, Homework, Resource, ResourceBooking
from dependencies import get_db, check_user_login, require_permission, get_session_student, get_session_parent

router = APIRouter()

# Pydantic Schemas
class RoomCreateRequest(BaseModel):
    name: str
    capacity: int = 30
    location: str
    equipment: Optional[str] = None
    branch_id: Optional[int] = 1  # Added branch_id 🆕

class RoomResponseModel(BaseModel):
    id: int
    name: str
    capacity: int
    location: str
    equipment: Optional[str] = None
    active: bool
    branch_id: Optional[int] = None

class ConflictCheckRequest(BaseModel):
    teacher_id: int
    room_id: Optional[int] = None
    days_of_week: str  # e.g., "شنبه"
    class_time: str   # e.g., "16:00"
    student_ids: List[int] = []
    resource_ids: Optional[List[int]] = []  # Added resource_ids 🆕

class ConflictCheckResponse(BaseModel):
    has_conflict: bool
    message: str
    details: List[str]

# --- 1. Admin/Secretary: Create Physical Room ---
@router.post("/rooms/create", response_model=RoomResponseModel)
def create_physical_room(
    req: RoomCreateRequest,
    db: Session = Depends(get_db),
    role: str = Depends(require_permission("class.create"))
):
    # Check duplicate room name
    existing = db.query(Room).filter(Room.name == req.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="اتاقی با این نام قبلاً در سیستم ثبت شده است")
        
    new_room = Room(
        name=req.name,
        capacity=req.capacity,
        location=req.location,
        equipment=req.equipment,
        active=True,
        branch_id=req.branch_id
    )
    db.add(new_room)
    db.commit()
    db.refresh(new_room)
    return new_room

# --- 2. View All Rooms ---
@router.get("/rooms/list", response_model=List[RoomResponseModel])
def get_all_rooms(db: Session = Depends(get_db), _: str = Depends(check_user_login)):
    return db.query(Room).all()

# --- 3. Centralized Conflict Detection & Validation ---
@router.post("/calendar/check_conflicts", response_model=ConflictCheckResponse)
def check_scheduling_conflicts(req: ConflictCheckRequest, db: Session = Depends(get_db), _: str = Depends(check_user_login)):
    has_conflict = False
    details = []
    
    # A) Teacher Conflict check
    teacher_clash = db.query(Course).filter(
        Course.teacher_id == req.teacher_id,
        Course.days_of_week == req.days_of_week,
        Course.class_time == req.class_time,
        Course.is_deleted == False,
        Course.is_suspended == False
    ).first()
    if teacher_clash:
        has_conflict = True
        details.append(f"👨‍🏫 تداخل معلم: این مربی قبلاً در همین روز و ساعت در کلاس '{teacher_clash.title}' حضور دارد.")

    # B) Room Conflict check
    if req.room_id:
        room_clash = db.query(Course).filter(
            Course.room_id == req.room_id,
            Course.days_of_week == req.days_of_week,
            Course.class_time == req.class_time,
            Course.is_deleted == False,
            Course.is_suspended == False
        ).first()
        if room_clash:
            has_conflict = True
            details.append(f"🏫 تداخل اتاق: اتاق مورد نظر قبلاً هم‌زمان به کلاس '{room_clash.title}' اختصاص داده شده است.")

    # C) Student Conflict check
    for sid in req.student_ids:
        student = db.query(Student).filter(Student.id == sid).first()
        if student:
            # Find if student is registered in any clashing active course
            st_clash = (
                db.query(Enrollment)
                .join(Course)
                .filter(
                    Enrollment.student_id == sid,
                    Course.days_of_week == req.days_of_week,
                    Course.class_time == req.class_time,
                    Course.is_deleted == False,
                    Course.is_suspended == False
                )
                .first()
            )
            if st_clash:
                has_conflict = True
                details.append(f"👥 تداخل دانش‌آموز: شاگرد '{student.first_name} {student.last_name}' هم‌زمان در کلاس '{st_clash.course.title}' حضور دارد.")

    # D) Resource Conflict check
    if req.resource_ids:
        for rid in req.resource_ids:
            res_clash = db.query(ResourceBooking).join(Course, ResourceBooking.course_id == Course.id).filter(
                ResourceBooking.resource_id == rid,
                ResourceBooking.days_of_week == req.days_of_week,
                ResourceBooking.class_time == req.class_time,
                Course.is_deleted == False,
                Course.is_suspended == False
            ).first()
            if res_clash:
                res_obj = db.query(Resource).filter(Resource.id == rid).first()
                res_name = res_obj.name if res_obj else f"منبع #{rid}"
                course_obj = db.query(Course).filter(Course.id == res_clash.course_id).first()
                c_title = course_obj.title if course_obj else "کلاس دیگر"
                has_conflict = True
                details.append(f"🔌 تداخل منبع: منبع '{res_name}' قبلاً در همین روز و ساعت در کلاس '{c_title}' رزرو شده است.")

    msg = "تداخل زمانی یافت شد!" if has_conflict else "برنامه زمانی کاملاً آزاد و بدون تداخل است."
    return ConflictCheckResponse(
        has_conflict=has_conflict,
        message=msg,
        details=details
    )

# --- 4. Centralized Calendar Events (Class, Exam, Deadlines, Due dates) ---
@router.get("/calendar/events")
def get_calendar_events(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    role: str = Depends(check_user_login)
):
    session = db.query(models.UserSession).filter(models.UserSession.token == authorization.split()[1]).first()
    user_id = session.user_id
    
    events = []
    
    # Fetch based on Role:
    # 1. Admin/Secretary -> see all classes
    if role in ["admin", "secretary"]:
        courses = db.query(Course).filter(Course.is_deleted == False).all()
        for c in courses:
            events.append({
                "type": "class",
                "title": f"🎓 کلاس: {c.title}",
                "detail": f"کد: {c.code} | مربی: {c.teacher.first_name if c.teacher else ''} {c.teacher.last_name if c.teacher else ''}",
                "schedule": f"{c.days_of_week} {c.class_time}"
            })
            
    # 2. Teacher -> see only own classes
    elif role == "teacher":
        from routers.reports import get_logged_in_teacher
        logged_teacher = get_logged_in_teacher(db, authorization)
        if logged_teacher:
            courses = db.query(Course).filter(Course.teacher_id == logged_teacher.id, Course.is_deleted == False).all()
            for c in courses:
                events.append({
                    "type": "class",
                    "title": f"🎓 کلاس من: {c.title}",
                    "detail": f"برگزاری کلاس {c.title}",
                    "schedule": f"{c.days_of_week} {c.class_time}"
                })
                
    # 3. Student / Parent -> see enrolled classes
    elif role in ["student", "parent"]:
        own = get_session_student(db, session) if role == "student" else get_session_parent(db, session)
        if not own:
            raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")
        student_id = own.id
        enrolls = db.query(Enrollment).filter(Enrollment.student_id == student_id).all()
        course_ids = [en.course_id for en in enrolls if en.course]
        courses = db.query(Course).filter(Course.id.in_(course_ids), Course.is_deleted == False).all()
        for c in courses:
            events.append({
                "type": "class",
                "title": f"🎓 کلاس من: {c.title}",
                "detail": f"حضور در کلاس {c.title}",
                "schedule": f"{c.days_of_week} {c.class_time}"
            })
            
        # Add Exams
        grades = db.query(Grade).filter(Grade.student_id == student_id).all()
        for g in grades:
            events.append({
                "type": "exam",
                "title": f"📅 امتحان: {g.exam_title}",
                "detail": f"نمره کسب شده: {g.score} از {g.max_score} در {g.course.title if g.course else ''}",
                "schedule": g.date
            })
            
        # Add Homework deadlines
        hws = db.query(Homework).filter(Homework.course_id.in_(course_ids)).all()
        for hw in hws:
            events.append({
                "type": "homework deadline",
                "title": f"📝 سررسید تکلیف: {hw.title}",
                "detail": hw.description,
                "schedule": hw.due_date
            })
            
        # Add Payment dues
        # FIX: Bug 13 - exclude archived Installment rows from this active view.
        insts = db.query(Installment).filter(Installment.is_deleted == False).filter(Installment.enrollment_id.in_([en.id for en in enrolls]), Installment.is_paid == False).all()
        for inst in insts:
            events.append({
                "type": "payment due",
                "title": f"💰 سررسید قسط شهریه",
                "detail": f"مبلغ: {inst.amount:,} تومان بابت کلاس {inst.enrollment.course.title if inst.enrollment and inst.enrollment.course else ''}",
                "schedule": inst.due_date
            })
            
    return events
