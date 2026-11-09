"""Isolated boundary fixture used to prove the audit seed covers edge values.

This deliberately lives beside, rather than inside, the canonical seed: the
normal 30/300-student fixture remains unchanged and all writes target a temp
SQLite database.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..seed import seed_database


BOUNDARY_TRANSACTION_ID = 99
BOUNDARY_EXAM_ID = 99
BOUNDARY_HOMEWORK_ID = 99
BOUNDARY_AMOUNT = 2**31 + 1


def seed_boundary_database(path: str | Path) -> dict[str, Any]:
    manifest = seed_database(path)
    import models  # loaded after seed_database selects the temporary DATABASE_URL

    db = models.SessionLocal()
    try:
        db.add(models.Transaction(
            id=BOUNDARY_TRANSACTION_ID,
            student_id=1,
            enrollment_id=None,
            course_id=None,
            amount=BOUNDARY_AMOUNT,
            payment_method="کارت",
            tracking_code="BOUNDARY-INT32",
            date="",
            receiver="آموزشگاه",
            description=None,
            type="deposit",
            share_teacher=0,
            share_institute=BOUNDARY_AMOUNT,
            target_wallet="institute",
            is_deleted=False,
            is_reversed=False,
        ))
        db.add(models.Exam(
            id=BOUNDARY_EXAM_ID,
            title="آزمون مرزی اعشاری",
            course_id=1,
            teacher_id=1,
            date="1405/08/01",
            duration=1,
            max_score=12.5,
            status="published",
        ))
        db.add(models.Homework(
            id=BOUNDARY_HOMEWORK_ID,
            course_id=1,
            teacher_id=1,
            title="تکلیف مرزی",
            description=None,
            due_date="",
            max_score=20.0,
            status="pending",
        ))
        db.commit()
    finally:
        db.close()
    manifest["boundary"] = {
        "decimal_max_score": 12.5,
        "large_amount": BOUNDARY_AMOUNT,
        "null_optional_fields": ["transactions.description", "homeworks.description"],
        "empty_strings": ["transactions.date", "homeworks.due_date"],
        "empty_lists": ["TeacherClassItem.students_preview"],
    }
    return manifest


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(seed_boundary_database(args.output), ensure_ascii=False, indent=2))
