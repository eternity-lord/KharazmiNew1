#!/usr/bin/env python3
"""branch_id backfill for legacy NULL rows — REPORT by default, --apply writes.

Scope: Student.branch_id and Course.branch_id ONLY.
Never touches enrollments, transactions, or any financial data.
Never blind-sets every row to branch 1 — only unambiguous rows are changed.

Decision sources (reliability order, per row):
  Students:
    - branches of ACTIVE enrollments -> course.branch_id (active branches only)
    - exactly 1 distinct valid branch  -> CANDIDATE
    - >1 distinct branches            -> AMBIGUOUS «دانش‌آموز با کلاس‌های فعال در چند شعبه‌ی متفاوت»
    - 0 reliable enrollments/branches -> AMBIGUOUS «دانش‌آموز بدون enrollment قابل اتکا»
    - resolved branch inactive        -> INVALID «branch نامعتبر یا حذف‌شده»
  Courses:
    - teacher exists and teacher.branch_id is a valid active branch, AND the
      teacher's other courses do not span multiple branches (معلم چندشعبه‌ای) -> CANDIDATE
    - teacher unknown/deleted/branchless -> fall back to active-enrollment
      student.branch_id values (exactly 1 valid -> CANDIDATE, else AMBIGUOUS)

Usage (DO NOT run --apply without reviewing the report first):
  cd Kharazmi_Server && python3 backfill_branch_ids.py            # report only
  cd Kharazmi_Server && python3 backfill_branch_ids.py --apply    # report + write
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except Exception:
    pass

import models
from models import Branch, Course, Enrollment, SessionLocal, Student


def _active_branch_map(db):
    """{branch_id: branch} برای شعبه‌های فعال."""
    return {b.id: b for b in db.query(Branch).filter(Branch.active == True).all()}


def student_branch_candidates(db, active):
    """For each NULL-branch student: (student, decision, branch_id_or_None, reason)."""
    result = []
    for st in db.query(Student).filter(Student.branch_id == None).all():  # noqa: E711
        enrollments = (
            db.query(Enrollment)
            .filter(Enrollment.student_id == st.id, Enrollment.is_deleted == False)  # noqa: E712
            .all()
        )
        branches = set()
        for en in enrollments:
            course = db.query(Course).filter(Course.id == en.course_id).first()
            if course and course.branch_id in active:
                branches.add(course.branch_id)
        if len(branches) == 1:
            result.append((st, "candidate", next(iter(branches)), "یک‌شعبه‌ی معتبر از enrollmentهای فعال"))
        elif len(branches) > 1:
            result.append((st, "ambiguous", None, f"کلاس‌های فعال در چند شعبه‌ی متفاوت: {sorted(branches)}"))
        else:
            result.append((st, "ambiguous", None, "بدون enrollment فعال قابل اتکا"))
    return result


def course_branch_candidates(db, active):
    """For each NULL-branch course: (course, decision, branch_id_or_None, reason)."""
    result = []
    for course in db.query(Course).filter(Course.branch_id == None).all():  # noqa: E711
        teacher = (
            db.query(models.Teacher).filter(models.Teacher.id == course.teacher_id).first()
            if course.teacher_id is not None
            else None
        )
        if teacher is None or teacher.is_deleted:
            # معلم نامشخص — از branch دانش‌آموزهای فعال استفاده می‌کنیم
            branches = _branches_from_enrolled_students(db, course, active)
            if len(branches) == 1:
                result.append((course, "candidate", next(iter(branches)), "branch یکپارچه از دانش‌آموزان فعال (بدون معلم معتبر)"))
            elif len(branches) > 1:
                result.append((course, "ambiguous", None, f"معلم نامشخص و دانش‌آموزان در چند شعبه: {sorted(branches)}"))
            else:
                result.append((course, "ambiguous", None, "معلم نامشخص و بدون منبع قابل اتکا"))
            continue

        if teacher.branch_id not in active:
            # teacher موجود ولی branch نامعتبر/حذف‌شده یا خالی
            if teacher.branch_id is None:
                branches = _branches_from_enrolled_students(db, course, active)
                if len(branches) == 1:
                    result.append((course, "candidate", next(iter(branches)), "branch یکپارچه از دانش‌آموزان فعال (branch معلم خالی)"))
                elif len(branches) > 1:
                    result.append((course, "ambiguous", None, f"branch معلم خالی و دانش‌آموزان در چند شعبه: {sorted(branches)}"))
                else:
                    result.append((course, "ambiguous", None, "branch معلم خالی و بدون منبع قابل اتکا"))
            else:
                result.append((course, "ambiguous", None, f"branch معلم نامعتبر یا حذف‌شده: {teacher.branch_id}"))
            continue

        # teacher با branch معتبر — اما اگر معلم چندشعبه‌ای باشد، branch او قابل اتکا نیست
        other_branches = {
            c.branch_id
            for c in db.query(Course)
            .filter(models.Course.teacher_id == teacher.id, Course.id != course.id,
                    Course.branch_id != None)  # noqa: E711
            .all()
            if c.branch_id in active
        }
        if len(other_branches) > 1:
            result.append((course, "ambiguous", None, f"معلم چندشعبه‌ای: {sorted(other_branches | {teacher.branch_id})}"))
        elif len(other_branches) == 1 and other_branches.pop() != teacher.branch_id:
            result.append((course, "ambiguous", None, f"تضاد branch معلم ({teacher.branch_id}) با کلاس‌هایش"))
        else:
            result.append((course, "candidate", teacher.branch_id, "branch معتبر معلم"))
    return result


def _branches_from_enrolled_students(db, course, active):
    enrollments = (
        db.query(Enrollment)
        .filter(Enrollment.course_id == course.id, Enrollment.is_deleted == False)  # noqa: E712
        .all()
    )
    branches = set()
    for en in enrollments:
        st = db.query(Student).filter(Student.id == en.student_id).first()
        if st and st.branch_id in active:
            branches.add(st.branch_id)
    return branches


def collect_plan(db):
    """Build the full backfill plan (read-only)."""
    active = _active_branch_map(db)
    return {
        "students": student_branch_candidates(db, active),
        "courses": course_branch_candidates(db, active),
    }


def apply_plan(db, plan):
    """Apply ONLY candidate rows. Returns (students_updated, courses_updated)."""
    students_updated = 0
    for st, decision, branch_id, _reason in plan["students"]:
        if decision == "candidate":
            st.branch_id = branch_id
            students_updated += 1
    courses_updated = 0
    for course, decision, branch_id, _reason in plan["courses"]:
        if decision == "candidate":
            course.branch_id = branch_id
            courses_updated += 1
    if students_updated or courses_updated:
        db.commit()
    return students_updated, courses_updated


def _fmt_student(st):
    return f"student #{st.id} (code={st.student_code}, {st.first_name or ''} {st.last_name or ''})".strip()


def _fmt_course(course):
    return f"course #{course.id} (code={course.code}, {course.title or ''})".strip()


def print_report(db, plan, applied=None):
    active = _active_branch_map(db)
    students_null = db.query(Student).filter(Student.branch_id == None).count()  # noqa: E711
    courses_null = db.query(Course).filter(Course.branch_id == None).count()  # noqa: E711

    lines = []
    lines.append("=" * 78)
    lines.append("branch_id backfill report — Student.branch_id / Course.branch_id ONLY")
    lines.append("=" * 78)
    lines.append(f"active branches: {[(b.id, b.name) for b in active.values()] or 'NONE'}")
    lines.append(f"students with NULL branch: {students_null}")
    lines.append(f"courses  with NULL branch: {courses_null}")
    lines.append("")

    cand_s = [r for r in plan["students"] if r[1] == "candidate"]
    amb_s = [r for r in plan["students"] if r[1] != "candidate"]
    lines.append(f"STUDENTS — candidates: {len(cand_s)}, ambiguous: {len(amb_s)}")
    for st, decision, branch_id, reason in plan["students"]:
        mark = "APPLY" if decision == "candidate" else "SKIP "
        bname = active.get(branch_id, Branch()).name if branch_id else "-"
        lines.append(f"  [{mark}] {_fmt_student(st)} -> branch {branch_id} ({bname}) — {reason}")
    lines.append("")

    cand_c = [r for r in plan["courses"] if r[1] == "candidate"]
    amb_c = [r for r in plan["courses"] if r[1] != "candidate"]
    lines.append(f"COURSES — candidates: {len(cand_c)}, ambiguous: {len(amb_c)}")
    for course, decision, branch_id, reason in plan["courses"]:
        mark = "APPLY" if decision == "candidate" else "SKIP "
        bname = active.get(branch_id, Branch()).name if branch_id else "-"
        lines.append(f"  [{mark}] {_fmt_course(course)} -> branch {branch_id} ({bname}) — {reason}")
    lines.append("")

    if applied is not None:
        s_upd, c_upd = applied
        students_after = db.query(Student).filter(Student.branch_id == None).count()  # noqa: E711
        courses_after = db.query(Course).filter(Course.branch_id == None).count()  # noqa: E711
        lines.append("APPLIED:")
        lines.append(f"  students updated: {s_upd}  (NULL remaining: {students_null} -> {students_after})")
        lines.append(f"  courses  updated: {c_upd}  (NULL remaining: {courses_null} -> {courses_after})")
    else:
        lines.append("REPORT ONLY — nothing was changed. Re-run with --apply after review.")

    report = "\n".join(lines)
    print(report)
    return report


def main():
    APPLY = "--apply" in sys.argv
    db = SessionLocal()
    try:
        plan = collect_plan(db)
        applied = None
        if APPLY:
            applied = apply_plan(db, plan)
        report = print_report(db, plan, applied=applied)
        report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "branch_backfill_report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        print(f"\nFull report written to: {report_path}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
