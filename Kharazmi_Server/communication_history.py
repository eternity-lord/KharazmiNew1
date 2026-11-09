"""Read-only aggregation of SMS and internal messenger history for profiles."""

import datetime
import re
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from sqlalchemy.orm import Session

from models import (
    Conversation,
    ConversationParticipant,
    Enrollment,
    Installment,
    Message,
    Payment,
    SmsLog,
    Student,
    Teacher,
    User,
)
from today_summary import parse_project_date


Identity = Tuple[str, int]


def _role(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _summary(value: Optional[str], limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip())
    if not text:
        return "پیام بدون متن"
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _sms_summary(log: SmsLog) -> str:
    group = (log.target_group or "").lower()
    # OTP values must not be exposed from a profile-wide aggregate view.
    if "otp" in group:
        return "پیامک کد یک‌بارمصرف ارسال شد"
    return _summary(log.message_text)


def _sms_datetime(value: Optional[str]) -> datetime.datetime:
    date_value = parse_project_date(value)
    if not date_value:
        return datetime.datetime.min
    normalized = (value or "").translate(
        str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    )
    match = re.search(r"(?:^|\s)([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?", normalized)
    if not match:
        return datetime.datetime.combine(date_value, datetime.time.min)
    hour, minute, second = (int(part or 0) for part in match.groups())
    return datetime.datetime.combine(date_value, datetime.time(hour, minute, second))


def _linked_teacher_user_ids(db: Session, teacher: Teacher) -> Set[int]:
    ids = {teacher.id}
    if teacher.mobile:
        users = (
            db.query(User)
            .filter(User.username == teacher.mobile)
            .all()
        )
        ids.update(user.id for user in users)
    return ids


class _IdentityNames:
    def __init__(self, db: Session):
        self.db = db
        self.cache: Dict[Identity, str] = {}

    def get(self, role: Optional[str], user_id: int) -> str:
        normalized_role = _role(role)
        key = (normalized_role, user_id)
        if key in self.cache:
            return self.cache[key]

        name = "کاربر نامشخص"
        if normalized_role == "student":
            student = self.db.query(Student).filter(Student.id == user_id).first()
            if student:
                name = f"{student.first_name or ''} {student.last_name or ''}".strip()
        elif normalized_role == "parent":
            student = self.db.query(Student).filter(Student.id == user_id).first()
            if student:
                student_name = f"{student.first_name or ''} {student.last_name or ''}".strip()
                name = f"ولی {student_name}".strip()
        elif normalized_role == "teacher":
            # Messenger rows historically used either Teacher.id or the linked User.id.
            user = (
                self.db.query(User)
                .filter(User.id == user_id)
                .first()
            )
            teacher = None
            if user and (_role(user.role) == "teacher" or _role(user.sub_role) == "teacher"):
                teacher = (
                    self.db.query(Teacher)
                    .filter(Teacher.mobile == user.username)
                    .first()
                )
                name = user.full_name or user.username or name
            if not teacher:
                teacher = self.db.query(Teacher).filter(Teacher.id == user_id).first()
            if teacher:
                name = f"{teacher.first_name or ''} {teacher.last_name or ''}".strip()
        else:
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                name = user.full_name or user.username or name

        self.cache[key] = name or "کاربر نامشخص"
        return self.cache[key]


def _internal_message_items(
    db: Session,
    target_identities: Set[Identity],
    target_display_name: str,
    required_participant_identities: Optional[Set[Identity]] = None,
) -> List[Dict]:
    target_parts = (
        db.query(ConversationParticipant)
        .filter(
            ConversationParticipant.user_id.in_([identity[1] for identity in target_identities]),
            ConversationParticipant.role.in_([identity[0] for identity in target_identities]),
        )
        .all()
    )
    conversation_ids = {
        part.conversation_id
        for part in target_parts
        if (_role(part.role), part.user_id) in target_identities
    }

    if required_participant_identities and conversation_ids:
        required_parts = (
            db.query(ConversationParticipant)
            .filter(
                ConversationParticipant.conversation_id.in_(conversation_ids),
                ConversationParticipant.user_id.in_(
                    [identity[1] for identity in required_participant_identities]
                ),
                ConversationParticipant.role.in_(
                    [identity[0] for identity in required_participant_identities]
                ),
            )
            .all()
        )
        required_conversations = {
            part.conversation_id
            for part in required_parts
            if (_role(part.role), part.user_id) in required_participant_identities
        }
        conversation_ids &= required_conversations

    if not conversation_ids:
        return []

    conversations = {
        conversation.id: conversation
        for conversation in (
            db.query(Conversation)
            .filter(Conversation.id.in_(conversation_ids))
            .all()
        )
    }
    participants_by_conversation: Dict[int, List[ConversationParticipant]] = defaultdict(list)
    participants = (
        db.query(ConversationParticipant)
        .filter(ConversationParticipant.conversation_id.in_(conversation_ids))
        .all()
    )
    for participant in participants:
        participants_by_conversation[participant.conversation_id].append(participant)

    messages = (
        db.query(Message)
        .filter(
            Message.conversation_id.in_(conversation_ids),
            Message.is_deleted == False,
        )
        .all()
    )
    names = _IdentityNames(db)
    items: List[Dict] = []
    for message in messages:
        sender_identity = (_role(message.sender_role), message.sender_id)
        is_target_sender = sender_identity in target_identities
        sender_name = names.get(message.sender_role, message.sender_id)

        if is_target_sender:
            other_names: List[str] = []
            for participant in participants_by_conversation[message.conversation_id]:
                identity = (_role(participant.role), participant.user_id)
                if identity in target_identities:
                    continue
                resolved = names.get(participant.role, participant.user_id)
                if resolved not in other_names:
                    other_names.append(resolved)
            if not other_names:
                conversation = conversations.get(message.conversation_id)
                recipient_name = (
                    conversation.title
                    if conversation and conversation.title
                    else "اعضای گفتگو"
                )
            elif len(other_names) <= 2:
                recipient_name = "، ".join(other_names)
            else:
                recipient_name = f"{other_names[0]}، {other_names[1]} و {len(other_names) - 2} نفر دیگر"
        else:
            target_participants = [
                participant
                for participant in participants_by_conversation[message.conversation_id]
                if (_role(participant.role), participant.user_id) in target_identities
            ]
            if target_participants:
                recipient_name = names.get(
                    target_participants[0].role,
                    target_participants[0].user_id,
                )
            else:
                recipient_name = target_display_name

        created_at = message.created_at or datetime.datetime.min
        items.append(
            {
                "source_id": message.id,
                "type": "internal_message",
                "type_label": "پیام داخلی",
                "summary": _summary(
                    message.body
                    or ("پیوست پیام" if message.attachment else "پیام بدون متن")
                ),
                "date": (
                    created_at.strftime("%Y/%m/%d %H:%M")
                    if created_at != datetime.datetime.min
                    else "---"
                ),
                "sender": sender_name,
                "recipient": recipient_name,
                "direction": "outgoing" if is_target_sender else "incoming",
                "conversation_id": message.conversation_id,
                "_sort_at": created_at,
            }
        )
    return items


def _student_sms_recipients(db: Session, student: Student) -> Dict[str, str]:
    student_name = f"{student.first_name or ''} {student.last_name or ''}".strip()
    parent_name = f"ولی {student_name}".strip()
    recipients: Dict[str, str] = {
        "all_students": student_name,
        f"student_{student.id}": student_name,
        f"online_reg_{student.id}": student_name,
        f"portal_link_{student.id}": parent_name,
        f"notif_student_{student.id}": student_name,
        f"notif_parent_{student.id}": parent_name,
        f"parent_{student.id}": parent_name,
    }
    if (student.wallet_teacher or 0) < 0 or (student.wallet_institute or 0) < 0:
        # SmsLog stores only the cohort name for legacy bulk debtor sends; the
        # current debt flag is the safest available association for those rows.
        recipients["debtors"] = student_name
    if student.student_mobile:
        recipients[f"student_otp_{student.student_mobile.strip()}"] = student_name
    if student.parent_mobile:
        recipients[f"otp_{student.parent_mobile.strip()}"] = parent_name

    enrollment_ids = [
        row[0]
        for row in (
            db.query(Enrollment.id)
            .filter(Enrollment.student_id == student.id)
            .all()
        )
    ]
    if enrollment_ids:
        installment_ids = [
            row[0]
            for row in (
                db.query(Installment.id)
                .filter(Installment.enrollment_id.in_(enrollment_ids))
                .all()
            )
        ]
        for installment_id in installment_ids:
            recipients[f"installment_{installment_id}"] = parent_name
            recipients[f"overdue_{installment_id}"] = parent_name
            recipients[f"manual_remind_{installment_id}"] = parent_name

    payment_ids = [
        row[0]
        for row in (
            db.query(Payment.id)
            .filter(Payment.student_id == student.id)
            .all()
        )
    ]
    for payment_id in payment_ids:
        recipients[f"online_pay_{payment_id}"] = parent_name
    return recipients


def _sms_items(db: Session, recipients: Dict[str, str]) -> List[Dict]:
    if not recipients:
        return []
    logs = (
        db.query(SmsLog)
        .filter(SmsLog.target_group.in_(list(recipients.keys())))
        .all()
    )
    items: List[Dict] = []
    for log in logs:
        sort_at = _sms_datetime(log.date)
        items.append(
            {
                "source_id": log.id,
                "type": "sms",
                "type_label": "پیامک",
                "summary": _sms_summary(log),
                "date": log.date or "---",
                "sender": "آموزشگاه",
                "recipient": recipients.get(log.target_group, "مخاطب"),
                "direction": "incoming",
                "conversation_id": None,
                "_sort_at": sort_at,
            }
        )
    return items


def _sorted_public_items(items: Iterable[Dict]) -> List[Dict]:
    sorted_items = sorted(
        items,
        key=lambda item: (item["_sort_at"], item["source_id"]),
        reverse=True,
    )
    for item in sorted_items:
        item.pop("_sort_at", None)
    return sorted_items


def build_student_communication_history(
    db: Session,
    student: Student,
    viewer_teacher: Optional[Teacher] = None,
    include_sms: bool = True,
) -> List[Dict]:
    student_name = f"{student.first_name or ''} {student.last_name or ''}".strip()
    target_identities: Set[Identity] = {
        ("student", student.id),
        ("parent", student.id),
    }
    required_identities = None
    if viewer_teacher:
        required_identities = {
            ("teacher", identity_id)
            for identity_id in _linked_teacher_user_ids(db, viewer_teacher)
        }

    items = _internal_message_items(
        db=db,
        target_identities=target_identities,
        target_display_name=student_name,
        required_participant_identities=required_identities,
    )
    if include_sms:
        items.extend(_sms_items(db, _student_sms_recipients(db, student)))
    return _sorted_public_items(items)


def build_teacher_communication_history(
    db: Session,
    teacher: Teacher,
) -> List[Dict]:
    teacher_name = f"{teacher.first_name or ''} {teacher.last_name or ''}".strip()
    teacher_ids = _linked_teacher_user_ids(db, teacher)
    target_identities = {("teacher", identity_id) for identity_id in teacher_ids}
    items = _internal_message_items(
        db=db,
        target_identities=target_identities,
        target_display_name=teacher_name,
    )

    recipients = {
        "all_teachers": teacher_name,
        f"teacher_{teacher.id}": teacher_name,
        f"notif_teacher_{teacher.id}": teacher_name,
    }
    if teacher.mobile:
        recipients[f"teacher_otp_{teacher.mobile.strip()}"] = teacher_name
        recipients[f"otp_{teacher.mobile.strip()}"] = teacher_name
    items.extend(_sms_items(db, recipients))
    return _sorted_public_items(items)
