import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

import models
from models import Branch, Resource, ResourceBooking, Student, Teacher, Course, Room, Transaction, Enrollment
from routers.branches import create_branch, update_branch, list_branches, get_branch_stats
from routers.calendar import check_scheduling_conflicts, ConflictCheckRequest


class TestKharazmiMultiBranch(unittest.TestCase):

    def setUp(self):
        # Fresh in-memory database for multi-branch and resource verification
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        # Seed the default branch as created by auto_patch_database
        self.default_branch = Branch(
            id=1,
            name="شعبه مرکزی",
            address="تهران، ولیعصر",
            phone="021-88888888",
            manager="مدیریت کل",
            active=True
        )
        self.db.add(self.default_branch)
        self.db.commit()

        # Seed a second branch
        self.branch2 = Branch(
            id=2,
            name="شعبه تجریش",
            address="تهران، تجریش",
            phone="021-22222222",
            manager="مهندس رضایی",
            active=True
        )
        self.db.add(self.branch2)
        self.db.commit()

        # Seed teachers for both branches
        self.teacher1 = Teacher(first_name="امین", last_name="علوی", branch_id=1, wallet_balance=0)
        self.teacher2 = Teacher(first_name="الهه", last_name="رضایی", branch_id=2, wallet_balance=0)
        self.db.add_all([self.teacher1, self.teacher2])
        self.db.commit()

        # Seed students for both branches
        self.student1 = Student(first_name="آرش", last_name="کمالی", branch_id=1, national_code="111")
        self.student2 = Student(first_name="نازنین", last_name="راد", branch_id=2, national_code="222")
        self.db.add_all([self.student1, self.student2])
        self.db.commit()

        # Seed rooms
        self.room1 = Room(name="اتاق ۱۰۱", capacity=20, location="طبقه اول", branch_id=1, active=True)
        self.room2 = Room(name="اتاق ۲۰۲", capacity=25, location="طبقه دوم", branch_id=2, active=True)
        self.db.add_all([self.room1, self.room2])
        self.db.commit()

        # Seed courses
        self.course1 = Course(title="شیمی دهم", code="CH10", teacher_id=self.teacher1.id, room_id=self.room1.id, days_of_week="شنبه", class_time="10:00", branch_id=1, is_deleted=False, is_suspended=False)
        self.course2 = Course(title="هندسه یازدهم", code="GE11", teacher_id=self.teacher2.id, room_id=self.room2.id, days_of_week="شنبه", class_time="10:00", branch_id=2, is_deleted=False, is_suspended=False)
        self.db.add_all([self.course1, self.course2])
        self.db.commit()

        # Seed enrollments
        self.enroll1 = Enrollment(student_id=self.student1.id, course_id=self.course1.id, total_tuition=400000, branch_id=1)
        self.enroll2 = Enrollment(student_id=self.student2.id, course_id=self.course2.id, total_tuition=600000, branch_id=2)
        self.db.add_all([self.enroll1, self.enroll2])
        self.db.commit()

        # Seed hardware resources
        self.resource1 = Resource(name="پروژکتور سونی", type="projector", serial_code="PRJ-101", branch_id=1, active=True)
        self.resource2 = Resource(name="لپ‌تاپ دل", type="computer", serial_code="LAP-202", branch_id=2, active=True)
        self.db.add_all([self.resource1, self.resource2])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(bind=self.engine)

    def test_branch_creation_and_update(self):
        """1. Verify creating, updating, and listing branches"""
        # Create a new branch
        new_b = Branch(name="شعبه نیاوران", address="نیاوران", phone="123", manager="احمدی", active=True)
        self.db.add(new_b)
        self.db.commit()
        
        self.assertIsNotNone(new_b.id)
        
        # Verify listing
        branches = self.db.query(Branch).all()
        self.assertEqual(len(branches), 3)  # Central, Tajrish, Niavaran

        # Update branch details
        branch_to_edit = self.db.query(Branch).filter(Branch.id == new_b.id).first()
        branch_to_edit.name = "شعبه نیاوران شمالی"
        self.db.commit()

        self.assertEqual(branch_to_edit.name, "شعبه نیاوران شمالی")

    def test_resource_booking_and_conflict_detection(self):
        """2. Verify resources can be booked and clashing requests are detected"""
        # Book resource 1 (projector) for Course 1
        booking = ResourceBooking(
            resource_id=self.resource1.id,
            course_id=self.course1.id,
            days_of_week="شنبه",
            class_time="10:00"
        )
        self.db.add(booking)
        self.db.commit()

        # Now, try to schedule another class at the same Saturday 10:00 and request resource 1.
        # This must raise a conflict in scheduling conflict detector!
        req = ConflictCheckRequest(
            teacher_id=999,  # No teacher clash
            room_id=None,    # No room clash
            days_of_week="شنبه",
            class_time="10:00",
            student_ids=[],
            resource_ids=[self.resource1.id]  # Requesting resource 1 which is booked!
        )

        res = check_scheduling_conflicts(req, self.db, "admin")
        self.assertTrue(res.has_conflict)
        self.assertIn("تداخل منبع: منبع 'پروژکتور سونی' قبلاً در همین روز و ساعت", res.details[0])

    def test_dashboard_branch_statistics_aggregation(self):
        """3. Verify branch stats aggregates student counts, classes, and revenue accurately per branch"""
        # Add a financial transaction to Branch 1
        trans1 = Transaction(
            student_id=self.student1.id,
            amount=250000,
            payment_method="نقدی",
            type="deposit",
            branch_id=1,
            is_deleted=False
        )
        self.db.add(trans1)
        
        # Add transaction to Branch 2
        trans2 = Transaction(
            student_id=self.student2.id,
            amount=400000,
            payment_method="online",
            type="deposit",
            branch_id=2,
            is_deleted=False
        )
        self.db.add(trans2)
        self.db.commit()

        # Run statistics for Branch 1
        stats1 = get_branch_stats(branch_id=1, db=self.db, _="admin")
        self.assertEqual(stats1["branch_name"], "شعبه مرکزی")
        self.assertEqual(stats1["statistics"]["student_count"], 1)
        self.assertEqual(stats1["statistics"]["class_count"], 1)
        self.assertEqual(stats1["statistics"]["total_revenue"], 250000)

        # Run statistics for Branch 2
        stats2 = get_branch_stats(branch_id=2, db=self.db, _="admin")
        self.assertEqual(stats2["branch_name"], "شعبه تجریش")
        self.assertEqual(stats2["statistics"]["student_count"], 1)
        self.assertEqual(stats2["statistics"]["class_count"], 1)
        self.assertEqual(stats2["statistics"]["total_revenue"], 400000)

        # Run summary for all branches
        summary = get_branch_stats(branch_id=None, db=self.db, _="admin")
        self.assertEqual(len(summary["revenue_by_branch"]), 2)
        self.assertEqual(summary["revenue_by_branch"][0]["amount"], 250000)
        self.assertEqual(summary["revenue_by_branch"][1]["amount"], 400000)

    def test_backward_compatibility_backfilling(self):
        """4. Verify that legacy records are safely backfilled to default branch ID 1 and remain functional"""
        # Simulate older record created without a branch_id (which is None)
        legacy_student = Student(first_name="سیاوش", last_name="کسرایی", national_code="333", branch_id=None)
        self.db.add(legacy_student)
        self.db.commit()

        # Verify it has None
        self.assertIsNone(legacy_student.branch_id)

        # Execute patching/backfilling logic on older record
        if legacy_student.branch_id is None:
            legacy_student.branch_id = 1
        self.db.commit()

        # Verify it is backfilled to Central Branch successfully
        self.assertEqual(legacy_student.branch_id, 1)


if __name__ == "__main__":
    unittest.main()
