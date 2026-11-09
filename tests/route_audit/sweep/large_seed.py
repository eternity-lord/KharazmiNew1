"""Scale fixture for list limit/order/filter checks (temporary DB only)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..seed import seed_database


def seed_large_list_database(path: str | Path) -> dict[str, Any]:
    manifest = seed_database(path, large=True)
    import models

    db = models.SessionLocal()
    try:
        # Give the transaction and settlement/read lists enough rows to expose
        # accidental first-page truncation and unstable ordering.
        for index, student_id in enumerate(range(1, 301), start=100):
            db.add(models.Transaction(
                id=index,
                student_id=student_id,
                enrollment_id=None,
                course_id=1,
                amount=100_000 + index,
                payment_method="کارت",
                tracking_code=f"LARGE-{index}",
                date="1405/07/01",
                receiver="آموزشگاه",
                description=f"تراکنش حجیم {index}",
                type="deposit",
                share_teacher=0,
                share_institute=100_000 + index,
                target_wallet="institute",
                is_deleted=False,
                is_reversed=False,
            ))
        for index in range(100, 400):
            db.add(models.SessionLog(
                id=index,
                session_code=6000 + index,
                course_id=1,
                date=f"1405/07/{index:03d}",
                time="16:00",
                final_teacher_cost=1_000,
                final_institute_share=0,
                cost_per_student=1_000,
                attendee_count=1,
                status="Finished",
                start_time="16:00",
                end_time="17:00",
                is_deleted=False,
            ))
            db.add(models.Attendance(
                session_id=index,
                student_id=1,
                status="Present",
                is_billed=False,
                excused=False,
                is_deleted=False,
            ))
        db.commit()
    finally:
        db.close()
    return manifest
