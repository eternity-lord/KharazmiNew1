import datetime
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from communication_history import (
    build_student_communication_history,
    build_teacher_communication_history,
)
from models import (
    Base,
    Conversation,
    ConversationParticipant,
    Course,
    Enrollment,
    Installment,
    Message,
    Payment,
    SmsLog,
    Student,
    Teacher,
    User,
    UserSession,
)
from routers.students import get_student_communication_history
from routers.teachers import get_teacher_communication_history


class TestCommunicationHistory(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        self.admin_user = User(
            username="admin",
            password="x",
            full_name="مدیر آموزشگاه",
            role="admin",
            sub_role="admin",
        )
        self.teacher_user = User(
            username="09120000001",
            password="x",
            full_name="حساب کاربری معلم",
            role="teacher",
            sub_role="teacher",
        )
        self.other_teacher_user = User(
            username="09120000002",
            password="x",
            full_name="معلم دوم",
            role="teacher",
            sub_role="teacher",
        )
        self.teacher = Teacher(
            first_name="مریم",
            last_name="معلم",
            mobile="09120000001",
            national_code="0012345678",
        )
        self.other_teacher = Teacher(
            first_name="سارا",
            last_name="دیگر",
            mobile="09120000002",
            national_code="0012345679",
        )
        self.student = Student(
            first_name="علی",
            last_name="دانش‌آموز",
            national_code="0012345680",
            student_mobile="09121111111",
            parent_mobile="09122222222",
            wallet_teacher=-100,
            wallet_institute=0,
        )
        self.unrelated_student = Student(
            first_name="رضا",
            last_name="نامرتبط",
            national_code="0012345681",
            student_mobile="09123333333",
            parent_mobile="09124444444",
        )
        self.db.add_all(
            [
                self.admin_user,
                self.teacher_user,
                self.other_teacher_user,
                self.teacher,
                self.other_teacher,
                self.student,
                self.unrelated_student,
            ]
        )
        self.db.flush()

        self.db.add_all(
            [
                UserSession(
                    token="teacher-token",
                    user_id=self.teacher_user.id,
                    sub_role="teacher",
                    created_at=datetime.datetime.now(),
                ),
                UserSession(
                    token="other-teacher-token",
                    user_id=self.other_teacher_user.id,
                    sub_role="teacher",
                    created_at=datetime.datetime.now(),
                ),
            ]
        )

        course = Course(
            title="ریاضی",
            code="C-1",
            teacher_id=self.teacher.id,
            is_admin_approved=True,
            is_deleted=False,
            is_suspended=False,
        )
        self.db.add(course)
        self.db.flush()
        enrollment = Enrollment(
            student_id=self.student.id,
            course_id=course.id,
            register_date="1405/06/02",
            shift="عصر",
        )
        self.db.add(enrollment)
        self.db.flush()
        installment = Installment(
            enrollment_id=enrollment.id,
            amount=500000,
            due_date="1405/06/01",
            is_paid=False,
        )
        payment = Payment(
            internal_transaction_id="PAY-1",
            amount=500000,
            student_id=self.student.id,
        )
        self.db.add_all([installment, payment])
        self.db.flush()

        admin_conversation = Conversation(title="گفتگو با مدیریت", type="private")
        teacher_conversation = Conversation(title="گفتگو با معلم", type="private")
        parent_conversation = Conversation(title="گفتگو با ولی", type="private")
        unrelated_conversation = Conversation(title="نامرتبط", type="private")
        self.db.add_all(
            [
                admin_conversation,
                teacher_conversation,
                parent_conversation,
                unrelated_conversation,
            ]
        )
        self.db.flush()

        self.db.add_all(
            [
                ConversationParticipant(
                    conversation_id=admin_conversation.id,
                    user_id=self.student.id,
                    role="student",
                ),
                ConversationParticipant(
                    conversation_id=admin_conversation.id,
                    user_id=self.admin_user.id,
                    role="admin",
                ),
                ConversationParticipant(
                    conversation_id=teacher_conversation.id,
                    user_id=self.student.id,
                    role="student",
                ),
                # Historical messenger data can use Teacher.id as participant...
                ConversationParticipant(
                    conversation_id=teacher_conversation.id,
                    user_id=self.teacher.id,
                    role="teacher",
                ),
                ConversationParticipant(
                    conversation_id=parent_conversation.id,
                    user_id=self.student.id,
                    role="parent",
                ),
                ConversationParticipant(
                    conversation_id=parent_conversation.id,
                    user_id=self.admin_user.id,
                    role="admin",
                ),
                ConversationParticipant(
                    conversation_id=unrelated_conversation.id,
                    user_id=self.unrelated_student.id,
                    role="student",
                ),
                ConversationParticipant(
                    conversation_id=unrelated_conversation.id,
                    user_id=self.admin_user.id,
                    role="admin",
                ),
            ]
        )
        self.db.add_all(
            [
                Message(
                    conversation_id=admin_conversation.id,
                    sender_id=self.admin_user.id,
                    sender_role="admin",
                    body="پیام مدیریت برای دانش‌آموز",
                    created_at=datetime.datetime(2026, 8, 24, 9, 0),
                    is_deleted=False,
                ),
                Message(
                    conversation_id=teacher_conversation.id,
                    # ...while a teacher-sent message uses linked User.id.
                    sender_id=self.teacher_user.id,
                    sender_role="teacher",
                    body="پیام مرتبط معلم",
                    created_at=datetime.datetime(2026, 8, 24, 11, 0),
                    is_deleted=False,
                ),
                Message(
                    conversation_id=parent_conversation.id,
                    sender_id=self.student.id,
                    sender_role="parent",
                    body="پیام ولی دانش‌آموز",
                    created_at=datetime.datetime(2026, 8, 24, 10, 0),
                    is_deleted=False,
                ),
                Message(
                    conversation_id=unrelated_conversation.id,
                    sender_id=self.admin_user.id,
                    sender_role="admin",
                    body="نباید نمایش داده شود",
                    created_at=datetime.datetime(2026, 8, 24, 13, 0),
                    is_deleted=False,
                ),
                Message(
                    conversation_id=admin_conversation.id,
                    sender_id=self.admin_user.id,
                    sender_role="admin",
                    body="پیام حذف‌شده",
                    created_at=datetime.datetime(2026, 8, 24, 14, 0),
                    is_deleted=True,
                ),
            ]
        )
        self.db.add_all(
            [
                SmsLog(
                    target_group=f"student_{self.student.id}",
                    message_text="یادآوری اختصاصی دانش‌آموز",
                    sent_count=1,
                    date="2026/08/24 12:00",
                ),
                SmsLog(
                    target_group=f"otp_{self.student.parent_mobile}",
                    message_text="کد تایید ورود: 12345",
                    sent_count=1,
                    date="2026/08/24 08:00",
                ),
                SmsLog(
                    target_group=f"installment_{installment.id}",
                    message_text="یادآوری قسط برای ولی",
                    sent_count=1,
                    date="1405/06/01 07:00",
                ),
                SmsLog(
                    target_group=f"online_pay_{payment.id}",
                    message_text="پرداخت آنلاین ثبت شد",
                    sent_count=1,
                    date="2026/08/23 15:00",
                ),
                SmsLog(
                    target_group="all_students",
                    message_text="اطلاعیه همه دانش‌آموزان",
                    sent_count=100,
                    date="2026/08/22 12:00",
                ),
                SmsLog(
                    target_group="debtors",
                    message_text="اطلاعیه گروه بدهکاران",
                    sent_count=10,
                    date="2026/08/22 11:00",
                ),
                SmsLog(
                    target_group=f"student_{self.unrelated_student.id}",
                    message_text="پیامک نامرتبط",
                    sent_count=1,
                    date="2026/08/24 15:00",
                ),
                SmsLog(
                    target_group="all_teachers",
                    message_text="اطلاعیه معلمان",
                    sent_count=20,
                    date="2026/08/24 12:30",
                ),
                SmsLog(
                    target_group=f"notif_teacher_{self.teacher.id}",
                    message_text="پیامک اختصاصی معلم",
                    sent_count=1,
                    date="2026/08/24 12:15",
                ),
            ]
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_student_combines_sms_parent_and_internal_messages_newest_first(self):
        history = build_student_communication_history(self.db, self.student)
        summaries = [item["summary"] for item in history]

        self.assertEqual(history[0]["summary"], "یادآوری اختصاصی دانش‌آموز")
        self.assertEqual(history[0]["type"], "sms")
        self.assertIn("پیام مرتبط معلم", summaries)
        self.assertIn("پیام مدیریت برای دانش‌آموز", summaries)
        self.assertIn("پیام ولی دانش‌آموز", summaries)
        self.assertIn("یادآوری قسط برای ولی", summaries)
        self.assertIn("پرداخت آنلاین ثبت شد", summaries)
        self.assertIn("اطلاعیه همه دانش‌آموزان", summaries)
        self.assertIn("اطلاعیه گروه بدهکاران", summaries)
        self.assertNotIn("پیامک نامرتبط", summaries)
        self.assertNotIn("نباید نمایش داده شود", summaries)
        self.assertNotIn("پیام حذف‌شده", summaries)

        otp = next(item for item in history if item["date"] == "2026/08/24 08:00")
        self.assertEqual(otp["summary"], "پیامک کد یک‌بارمصرف ارسال شد")
        self.assertNotIn("12345", otp["summary"])

    def test_teacher_history_supports_teacher_and_linked_user_ids(self):
        history = build_teacher_communication_history(self.db, self.teacher)
        summaries = [item["summary"] for item in history]
        self.assertIn("پیام مرتبط معلم", summaries)
        self.assertIn("اطلاعیه معلمان", summaries)
        self.assertIn("پیامک اختصاصی معلم", summaries)
        internal = next(item for item in history if item["summary"] == "پیام مرتبط معلم")
        self.assertEqual(internal["direction"], "outgoing")
        self.assertEqual(internal["sender"], "مریم معلم")

    def test_teacher_student_view_is_related_and_does_not_expose_sms(self):
        history = get_student_communication_history(
            student_id=self.student.id,
            authorization="Bearer teacher-token",
            db=self.db,
            role="teacher",
        )
        self.assertEqual([item["summary"] for item in history], ["پیام مرتبط معلم"])
        self.assertTrue(all(item["type"] == "internal_message" for item in history))

        with self.assertRaises(HTTPException) as error:
            get_student_communication_history(
                student_id=self.unrelated_student.id,
                authorization="Bearer teacher-token",
                db=self.db,
                role="teacher",
            )
        self.assertEqual(error.exception.status_code, 403)

    def test_teacher_can_only_open_own_teacher_history(self):
        own = get_teacher_communication_history(
            teacher_id=self.teacher.id,
            authorization="Bearer teacher-token",
            db=self.db,
            sub_role="teacher",
        )
        self.assertTrue(own)

        with self.assertRaises(HTTPException) as error:
            get_teacher_communication_history(
                teacher_id=self.teacher.id,
                authorization="Bearer other-teacher-token",
                db=self.db,
                sub_role="teacher",
            )
        self.assertEqual(error.exception.status_code, 403)

    def test_admin_secretary_allowed_and_other_roles_denied(self):
        secretary_history = get_student_communication_history(
            student_id=self.student.id,
            authorization=None,
            db=self.db,
            role="secretary",
        )
        self.assertGreater(len(secretary_history), 1)

        with self.assertRaises(HTTPException) as error:
            get_student_communication_history(
                student_id=self.student.id,
                authorization=None,
                db=self.db,
                role="student",
            )
        self.assertEqual(error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
