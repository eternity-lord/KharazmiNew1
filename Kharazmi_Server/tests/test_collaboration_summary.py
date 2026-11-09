import datetime
import unittest
import time

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models import Base, Branch, Course, LiveSession, Settlement, Teacher, User, UserSession
from collaboration_summary import build_teacher_collaboration_summary
from routers.teachers import get_teacher_collaboration_summary, get_teacher_full_profile
from dependencies import check_admin_access


class TestCollaborationSummary(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        self.db.add(Branch(id=1, name="مرکزی", active=True))
        admin = User(
            username="admin",
            password="x",
            full_name="مدیر",
            role="admin",
            sub_role="admin",
            branch_id=1,
        )
        secretary = User(
            username="sec",
            password="x",
            full_name="منشی",
            role="admin",
            sub_role="secretary",
            branch_id=1,
        )
        teacher_user = User(
            username="09120000001",
            password="x",
            full_name="معلم",
            role="teacher",
            sub_role="teacher",
        )
        self.db.add_all([admin, secretary, teacher_user])
        self.db.flush()
        self.db.add_all(
            [
                UserSession(
                    token="admin-token",
                    user_id=admin.id,
                    sub_role="admin",
                    created_at=datetime.datetime.now(),
                ),
                UserSession(
                    token="secretary-token",
                    user_id=secretary.id,
                    sub_role="secretary",
                    created_at=datetime.datetime.now(),
                ),
                UserSession(
                    token="teacher-token",
                    user_id=teacher_user.id,
                    sub_role="teacher",
                    created_at=datetime.datetime.now(),
                ),
            ]
        )

        self.teacher = Teacher(
            first_name="مریم",
            last_name="معلم",
            mobile="09120000001",
            national_code="0012345678",
            teacher_code=101,
            is_approved=True,
        )
        self.db.add(self.teacher)
        self.db.flush()

        course1 = Course(
            title="ریاضی",
            code="C-101",
            teacher_id=self.teacher.id,
            is_admin_approved=True,
            is_deleted=False,
            is_suspended=False,
            class_time="16:00-17:30",
            days_of_week="شنبه",
        )
        course2 = Course(
            title="فیزیک",
            code="C-102",
            teacher_id=self.teacher.id,
            is_admin_approved=True,
            is_deleted=False,
            is_suspended=False,
            class_time="08:00",
            days_of_week="یکشنبه",
        )
        self.db.add_all([course1, course2])
        self.db.flush()

        now = datetime.datetime.now()
        # Live sessions within last 30 days
        # Scheduled 16:00, actual 16:10 => 10 min delay
        self.db.add(
            LiveSession(
                course_id=course1.id,
                teacher_id=self.teacher.id,
                status="ENDED",
                start_time=(now - datetime.timedelta(days=2)).strftime("%Y-%m-%d 16:10"),
                started_at_ts=int((now - datetime.timedelta(days=2)).timestamp()),
                ended_automatically=False,
            )
        )
        # Scheduled 08:00, actual 08:25 => 25 min delay, auto ended
        self.db.add(
            LiveSession(
                course_id=course2.id,
                teacher_id=self.teacher.id,
                status="ENDED",
                start_time=(now - datetime.timedelta(days=5)).strftime("%Y-%m-%d 08:25"),
                started_at_ts=int((now - datetime.timedelta(days=5)).timestamp()),
                ended_automatically=True,
            )
        )
        # Outside 30 days, should not affect delay average, but should count for total auto-ended
        self.db.add(
            LiveSession(
                course_id=course1.id,
                teacher_id=self.teacher.id,
                status="ENDED",
                start_time=(now - datetime.timedelta(days=40)).strftime("%Y-%m-%d 16:00"),
                started_at_ts=int((now - datetime.timedelta(days=40)).timestamp()),
                ended_automatically=True,
            )
        )
        # Early start: scheduled 16:00, actual 15:50 => should be 0 delay
        self.db.add(
            LiveSession(
                course_id=course1.id,
                teacher_id=self.teacher.id,
                status="ENDED",
                start_time=(now - datetime.timedelta(days=1)).strftime("%Y-%m-%d 15:50"),
                started_at_ts=int((now - datetime.timedelta(days=1)).timestamp()),
                ended_automatically=False,
            )
        )

        self.db.add_all(
            [
                Settlement(
                    teacher_id=self.teacher.id,
                    total_amount=500000,
                    session_count=2,
                    settled_at=now - datetime.timedelta(days=10),
                    settled_by_user_id=admin.id,
                ),
                Settlement(
                    teacher_id=self.teacher.id,
                    total_amount=300000,
                    session_count=1,
                    settled_at=now - datetime.timedelta(days=1),
                    settled_by_user_id=admin.id,
                ),
            ]
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_average_delay_and_counts(self):
        summary = build_teacher_collaboration_summary(self.db, self.teacher.id, period_days=30)
        # Delays: 10, 25, 0 => avg = 35/3 = 11.666... rounded 11.7
        self.assertEqual(summary["delay_samples_count"], 3)
        self.assertAlmostEqual(summary["average_delay_minutes"], 11.7, places=1)
        self.assertEqual(summary["live_sessions_last_30_days"], 3)
        self.assertEqual(summary["total_settlements_count"], 2)
        self.assertEqual(summary["total_settled_amount"], 800000)
        self.assertEqual(summary["auto_ended_sessions_count"], 2)
        self.assertEqual(summary["auto_ended_last_30_days_count"], 1)

    def test_admin_only_endpoint(self):
        # admin can access
        result = get_teacher_collaboration_summary(
            teacher_id=self.teacher.id,
            authorization="Bearer admin-token",
            db=self.db,
            _="admin",
        )
        self.assertEqual(result["total_settlements_count"], 2)

        # secretary should be blocked by check_admin_access
        with self.assertRaises(HTTPException) as err:
            check_admin_access("Bearer secretary-token", self.db)
        self.assertEqual(err.exception.status_code, 403)

        # Direct endpoint with secretary token also fails
        with self.assertRaises(HTTPException) as err2:
            get_teacher_collaboration_summary(
                teacher_id=self.teacher.id,
                authorization="Bearer secretary-token",
                db=self.db,
                _=check_admin_access("Bearer secretary-token", self.db),
            )
        self.assertEqual(err2.exception.status_code, 403)

    def test_full_profile_includes_collaboration_for_admin(self):
        # admin full profile should include collaboration_summary
        full = get_teacher_full_profile(
            id=self.teacher.id,
            authorization="Bearer admin-token",
            db=self.db,
            sub_role="admin",
        )
        self.assertIsNotNone(full.collaboration_summary)
        self.assertEqual(full.collaboration_summary.total_settlements_count, 2)

        # teacher own profile should NOT include collaboration_summary (None)
        full_teacher = get_teacher_full_profile(
            id=self.teacher.id,
            authorization="Bearer teacher-token",
            db=self.db,
            sub_role="teacher",
        )
        self.assertIsNone(full_teacher.collaboration_summary)

    def test_empty_teacher(self):
        # teacher with no live sessions / settlements
        empty_teacher = Teacher(
            first_name="خالی",
            last_name="معلم",
            mobile="09120000099",
            national_code="0012345699",
            teacher_code=102,
            is_approved=True,
        )
        self.db.add(empty_teacher)
        self.db.commit()
        summary = build_teacher_collaboration_summary(self.db, empty_teacher.id)
        self.assertEqual(summary["average_delay_minutes"], 0.0)
        self.assertEqual(summary["total_settlements_count"], 0)
        self.assertEqual(summary["auto_ended_sessions_count"], 0)


if __name__ == "__main__":
    unittest.main()
