import os
import datetime
import random
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, or_

import models
from models import Conversation, ConversationParticipant, Message, Course, Student, Teacher, Enrollment, User
from storage import storage_dir
from dependencies import get_db, check_user_login, require_permission, NotificationService, resolve_participant_keys, resolve_notification_recipient

router = APIRouter()

# Secure Storage Configuration for Messenger Attachments
# FIX(storage): ریشهٔ واحد فایل‌ها (پیش‌فرض داخل پروژه) — به‌جای مسیر مطلق ماشین توسعه‌دهنده.
UPLOAD_DIR = storage_dir("messages")

# Size limit: 10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".xlsx"}

def sanitize_filename(filename: str) -> str:
    name, ext = os.path.splitext(filename)
    name = re.sub(r'[^a-zA-Z0-9_\u0600-\u06FF]', '_', name)
    return f"{name}_{random.randint(1000, 9999)}{ext.lower()}"

def validate_file(file: UploadFile) -> str:
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="فرمت فایل مجاز نیست.")
    return ext

# Pydantic Schemas
class ConversationCreateRequest(BaseModel):
    title: Optional[str] = None
    type: str  # "private" or "group"
    participant_ids: List[int]  # List of user_ids (Wait, they are other teachers/students/admins)
    participant_roles: List[str] # Match with participant_ids

class MessageSendRequest(BaseModel):
    body: str

class BroadcastMessageRequest(BaseModel):
    target_type: str  # "class", "everyone"
    target_id: Optional[int] = None  # e.g., class_id if target_type == "class"
    body: str

# --- 1. View My Conversations List ---
@router.get("/messages/conversations")
def get_my_conversations(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(require_permission("messages.read"))
):
    session = db.query(models.UserSession).filter(models.UserSession.token == authorization.split()[1]).first()
    keys = resolve_participant_keys(db, session, role)
    if not keys:
        raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")
    user_id = keys[0]

    # Find all conversations where current user is participant
    parts = db.query(ConversationParticipant).filter(ConversationParticipant.user_id.in_(keys), ConversationParticipant.role == role).all()
    conv_ids = [p.conversation_id for p in parts]
    
    convs = db.query(Conversation).filter(Conversation.id.in_(conv_ids)).all()
    
    result = []
    for c in convs:
        # Get last message
        last_msg = db.query(Message).filter(Message.conversation_id == c.id, Message.is_deleted == False).order_by(desc(Message.id)).first()
        snippet = last_msg.body if last_msg else "هنوز پیامی ارسال نشده است"
        last_time = last_msg.created_at.strftime("%Y/%m/%d %H:%M") if last_msg else c.created_at.strftime("%Y/%m/%d %H:%M")
        
        # Pinned check
        pinned_list = (c.pinned_by or "").split(",")
        is_pinned = f"{user_id}_{role}" in pinned_list
        
        result.append({
            "id": c.id,
            "title": c.title or "گفتگوی خصوصی",
            "type": c.type,
            "last_message": snippet,
            "last_time": last_time,
            "is_pinned": is_pinned
        })
    return sorted(result, key=lambda x: (x["is_pinned"], x["last_time"]), reverse=True)

# --- 2. Start New Conversation ---
@router.post("/messages/conversations/create")
def create_conversation(
    req: ConversationCreateRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(require_permission("messages.send"))
):
    session = db.query(models.UserSession).filter(models.UserSession.token == authorization.split()[1]).first()
    keys = resolve_participant_keys(db, session, role)
    if not keys:
        raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")

    if len(req.participant_ids) != len(req.participant_roles):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "recipient_information_incomplete",
                "message": "اطلاعات را تکمیل کنید",
            },
        )

    # 1. Create Conversation
    new_conv = Conversation(
        title=req.title,
        type=req.type
    )
    db.add(new_conv)
    db.flush()

    # 2. Add current user as participant
    self_part = ConversationParticipant(
        conversation_id=new_conv.id,
        user_id=keys[0],
        role=role
    )
    db.add(self_part)
    
    # 3. Add other participants (IDOR validation: ensure other student/teacher IDs exist)
    for idx, pid in enumerate(req.participant_ids):
        prole = req.participant_roles[idx]
        if prole == "student":
            exists = db.query(Student).filter(Student.id == pid, Student.is_deleted == False).first()
        elif prole == "teacher":
            exists = db.query(Teacher).filter(Teacher.id == pid, Teacher.is_deleted == False).first()
        else:
            exists = db.query(User).filter(User.id == pid).first()
            
        if not exists:
            raise HTTPException(status_code=400, detail=f"کاربر مخاطب با شناسه {pid} و نقش {prole} یافت نشد")
            
        other_part = ConversationParticipant(
            conversation_id=new_conv.id,
            user_id=pid,
            role=prole
        )
        db.add(other_part)
        
    db.commit()
    return {"message": "گفتگو با موفقیت آغاز شد", "conversation_id": new_conv.id}

# --- 3. View Conversation Message History ---
@router.get("/messages/conversations/{id}/history")
def get_conversation_history(
    id: int,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(require_permission("messages.read"))
):
    if not authorization or len(authorization.split()) != 2:
        raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")
    session = db.query(models.UserSession).filter(models.UserSession.token == authorization.split()[1]).first()
    keys = resolve_participant_keys(db, session, role)
    if not keys:
        raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")

    # Safety Check: Verify user is participant
    is_part = db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id == id, ConversationParticipant.user_id.in_(keys), ConversationParticipant.role == role).first()
    if not is_part:
        raise HTTPException(status_code=403, detail="شما مجاز به مشاهده پیام‌های این گفتگو نیستید (IDOR)")
        
    msgs = db.query(Message).filter(Message.conversation_id == id, Message.is_deleted == False).order_by(Message.id.asc()).all()
    return [
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "sender_role": m.sender_role,
            "body": m.body,
            "attachment": m.attachment,
            "created_at": m.created_at.strftime("%Y/%m/%d %H:%M")
        }
        for m in msgs
    ]

# --- 4. Send Message ---
@router.post("/messages/conversations/{id}/send")
def send_message(
    id: int,
    req: MessageSendRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(require_permission("messages.send"))
):
    if not req.body or not req.body.strip():
        raise HTTPException(status_code=400, detail="متن پیام نمی‌تواند خالی باشد")
    if not authorization or len(authorization.split()) != 2:
        raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")
    session = db.query(models.UserSession).filter(models.UserSession.token == authorization.split()[1]).first()
    keys = resolve_participant_keys(db, session, role)
    if not keys:
        raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")

    # Safety Check: Verify user is participant
    is_part = db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id == id, ConversationParticipant.user_id.in_(keys), ConversationParticipant.role == role).first()
    if not is_part:
        raise HTTPException(status_code=403, detail="شما مجاز به ارسال پیام در این گفتگو نیستید (IDOR)")

    new_msg = Message(
        conversation_id=id,
        sender_id=keys[0],
        sender_role=role,
        body=req.body
    )
    db.add(new_msg)
    db.commit()
    
    # Notification integration: notify other participants
    other_parts = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == id,
        ~and_(
            ConversationParticipant.user_id.in_(keys),
            ConversationParticipant.role == role,
        ),
    ).all()
    for p in other_parts:
        rid = resolve_notification_recipient(db, p.user_id, p.role)
        if rid is None:
            continue
        NotificationService.send_notification(
            db=db,
            recipient_user_id=rid,
            recipient_role=p.role,
            type="message",
            title=f"📩 پیام جدید",
            body=f"پیام جدیدی برای شما ارسال شد: {req.body[:30]}..."
        )
        
    return {"message": "پیام با موفقیت ارسال شد"}

# --- 5. Soft Delete Message ---
@router.delete("/messages/{id}")
def delete_own_message(
    id: int,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(require_permission("messages.send"))
):
    session = db.query(models.UserSession).filter(models.UserSession.token == authorization.split()[1]).first()
    keys = resolve_participant_keys(db, session, role)
    if not keys:
        raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")

    msg = db.query(Message).filter(Message.id == id, Message.sender_id.in_(keys), Message.sender_role == role).first()
    if not msg:
        raise HTTPException(status_code=404, detail="پیام یافت نشد یا شما فرستنده آن نیستید")
        
    msg.is_deleted = True
    db.commit()
    return {"message": "پیام با موفقیت حذف شد"}

# --- 6. Broadcast Message ---
@router.post("/messages/broadcast")
def send_broadcast_message(
    req: BroadcastMessageRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    # FIX (L14/Y2-F1): پرمیژن جدا — شاگرد/ولی (و نقش ناشناخته) 403؛ DMهای شاگرد روی messages.send دست‌نخورده
    role: str = Depends(require_permission("messages.broadcast"))
):
    if not req.body or not req.body.strip():
        raise HTTPException(status_code=400, detail="متن پیام نمی‌تواند خالی باشد")
    if req.target_type not in {"everyone", "class"}:
        raise HTTPException(status_code=400, detail="نوع گیرنده پیام گروهی نامعتبر است")
    if not authorization or len(authorization.split()) != 2:
        raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")
    session = db.query(models.UserSession).filter(models.UserSession.token == authorization.split()[1]).first()
    keys = resolve_participant_keys(db, session, role)
    if not keys:
        raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")

    # Generate broad conversation
    conv = Conversation(title="اعلان عمومی", type="broadcast")
    db.add(conv)
    db.flush()

    # Add sender
    self_part = ConversationParticipant(conversation_id=conv.id, user_id=keys[0], role=role)
    db.add(self_part)
    
    recipients = []
    
    if req.target_type == "everyone":
        # All students & teachers
        students = db.query(Student).filter(Student.is_deleted == False).all()
        teachers = db.query(Teacher).filter(Teacher.is_deleted == False).all()
        for s in students:
            recipients.append((s.id, "student"))
        for t in teachers:
            recipients.append((t.id, "teacher"))
    elif req.target_type == "class":
        # The Android broadcast card has no class selector yet. For a teacher,
        # a missing target_id therefore means "my active classes"; the old code
        # silently created a successful-looking broadcast with zero recipients.
        from routers.reports import get_logged_in_teacher
        course_ids = []
        if role == "teacher":
            logged_teacher = get_logged_in_teacher(db, authorization)
            if not logged_teacher:
                raise HTTPException(status_code=403, detail="معلم جاری یافت نشد")
            if req.target_id is not None:
                course = db.query(Course).filter(
                    Course.id == req.target_id,
                    Course.is_deleted == False,
                ).first()
                if not course:
                    raise HTTPException(status_code=404, detail="کلاس مورد نظر یافت نشد")
                if course.teacher_id != logged_teacher.id:
                    raise HTTPException(status_code=403, detail="شما مجاز به ارسال پیام گروهی به شاگردان کلاس دیگران نیستید (IDOR)")
                course_ids = [course.id]
            else:
                course_ids = [course_id for course_id, in db.query(Course.id).filter(
                    Course.teacher_id == logged_teacher.id,
                    Course.is_deleted == False,
                ).all()]
        else:
            if req.target_id is None:
                raise HTTPException(status_code=400, detail="شناسه کلاس برای اطلاعیه آموزشگاه الزامی است")
            course = db.query(Course).filter(
                Course.id == req.target_id,
                Course.is_deleted == False,
            ).first()
            if not course:
                raise HTTPException(status_code=404, detail="کلاس مورد نظر یافت نشد")
            course_ids = [course.id]

        if not course_ids:
            raise HTTPException(status_code=400, detail="برای این اطلاعیه هیچ کلاس فعالی وجود ندارد")
        enrolls = db.query(Enrollment).filter(
            Enrollment.course_id.in_(course_ids),
            Enrollment.is_deleted == False,
        ).all()
        # A student enrolled in two of the teacher's classes must receive one
        # broadcast, not duplicate participants/notifications.
        recipients = list({(en.student_id, "student") for en in enrolls})

    # Add recipients
    for pid, prole in recipients:
        part = ConversationParticipant(conversation_id=conv.id, user_id=pid, role=prole)
        db.add(part)
        
    # Write Message
    msg = Message(
        conversation_id=conv.id,
        sender_id=keys[0],
        sender_role=role,
        body=req.body
    )
    db.add(msg)
    db.commit()
    
    # Send Notifications
    for pid, prole in recipients:
        rid = resolve_notification_recipient(db, pid, prole)
        if rid is None:
            continue
        NotificationService.send_notification(
            db=db,
            recipient_user_id=rid,
            recipient_role=prole,
            type="announcement",
            title="📣 اطلاعیه کلاسی جدید",
            body=req.body[:50]
        )
        
    return {"message": "پیام گروهی با موفقیت ارسال شد"}


# --- 7. Pin / Unpin Conversation (personal view preference, per user+role) ---
class PinToggleRequest(BaseModel):
    pinned: bool

@router.post("/messages/conversations/{id}/pin")
def toggle_conversation_pin(
    id: int,
    req: PinToggleRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    role: str = Depends(require_permission("messages.read"))
):
    session = db.query(models.UserSession).filter(models.UserSession.token == authorization.split()[1]).first()
    keys = resolve_participant_keys(db, session, role)
    if not keys:
        raise HTTPException(status_code=401, detail="نشست معتبر نیست؛ لطفاً دوباره وارد شوید")
    conv = db.query(Conversation).filter(Conversation.id == id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="گفتگو یافت نشد")
    # Safety Check: Verify user is participant (IDOR, same as history/send)
    is_part = db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id == id, ConversationParticipant.user_id.in_(keys), ConversationParticipant.role == role).first()
    if not is_part:
        raise HTTPException(status_code=403, detail="شما مجاز به تغییر وضعیت این گفتگو نیستید (IDOR)")
    # FIX (H2/pin): per-user/role key set in CSV — pin is personal, not global.
    cur = set(filter(None, (conv.pinned_by or "").split(",")))
    key = f"{keys[0]}_{role}"
    if req.pinned:
        cur.add(key)
    else:
        cur.discard(key)
    conv.pinned_by = ",".join(sorted(cur)) or None
    db.commit()
    return {"is_pinned": key in cur}
