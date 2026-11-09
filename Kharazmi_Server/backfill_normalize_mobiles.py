#!/usr/bin/env python3
"""H20 batch-3: backfill mobile normalization — REPORT by default, --apply writes.

Scope: Teacher.mobile, Student.student_mobile, Student.parent_mobile,
       User.username (role='teacher' ONLY — never admin/other names), Lead.mobile.

Policy (per H20 design):
  - empty-after-strip -> SKIP silently (established-legit, e.g. parent_mobile="").
  - normalize OK + differs from stored -> CANDIDATE (updated only with --apply,
    unless blocked by a conflict).
  - normalize None (non-empty) -> INVALID list for manual review; NEVER touched.
  - two different rows -> same canonical within a UNIQUE scope
    (Teacher.mobile, Student.student_mobile, User.username) -> CONFLICT:
    all involved rows listed, all left untouched (NO auto-merge).
  - parent_mobile / Lead.mobile are non-unique -> normalized without conflict check.
  - same canonical across DIFFERENT scopes -> INFORMATIONAL section only.
  - teacher username==mobile pairs still divergent after final values -> REVIEW.

Usage (DO NOT run without reviewing the conflict report first):
  cd Kharazmi_Server && python3 backfill_normalize_mobiles.py            # report only
  cd Kharazmi_Server && python3 backfill_normalize_mobiles.py --apply    # report + write
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except Exception:
    pass

try:
    from dependencies import normalize_mobile
    from models import Lead, SessionLocal, Student, Teacher, User
except RuntimeError as e:
    print(f"FATAL: {e}")
    sys.exit(2)

APPLY = "--apply" in sys.argv
REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mobile_backfill_report.txt")
PRINT_CAP = 200  # rows printed per section on stdout; full lists go to the report file

# (scope_name, unique_scope?)
SCOPES = [
    ("Teacher.mobile", True),
    ("Student.student_mobile", True),
    ("Student.parent_mobile", False),
    ("User.username[teacher]", True),
    ("Lead.mobile", False),
]


def collect(db):
    """Return per-scope rows: {scope: [(id, raw), ...]}."""
    teachers = [(t.id, t.mobile) for t in db.query(Teacher).all()]
    students_sm = [(s.id, s.student_mobile) for s in db.query(Student).all()]
    students_pm = [(s.id, s.parent_mobile) for s in db.query(Student).all()]
    shadows = [(u.id, u.username) for u in db.query(User).filter(User.role == "teacher").all()]
    leads = [(l.id, l.mobile) for l in db.query(Lead).all()]
    return {
        "Teacher.mobile": teachers,
        "Student.student_mobile": students_sm,
        "Student.parent_mobile": students_pm,
        "User.username[teacher]": shadows,
        "Lead.mobile": leads,
    }


def analyze(rows_by_scope):
    """Classify every row. Returns dict with invalid/candidates/conflicts/cross/pairs."""
    invalid = []  # (scope, id, raw)
    candidates = []  # (scope, id, raw, canonical)
    finals = {}  # scope -> {id: final_value or None}
    for scope, rows in rows_by_scope.items():
        finals[scope] = {}
        for rid, raw in rows:
            s = (raw or "").strip()
            if not s:
                continue  # established-legit empty; leave alone, don't list
            norm = normalize_mobile(s)
            if norm is None:
                invalid.append((scope, rid, raw))
                continue
            finals[scope][rid] = norm
            if norm != s:
                candidates.append((scope, rid, raw, norm))
    # conflicts: same canonical, different ids, within one UNIQUE scope
    # (already-canonical rows count too — they occupy the value).
    conflicts = []  # (scope, canonical, [ids])
    blocked = set()  # (scope, id) candidates to skip
    for scope, unique in SCOPES:
        if not unique:
            continue
        by_value = {}
        for rid, val in finals[scope].items():
            by_value.setdefault(val, []).append(rid)
        for val, ids in sorted(by_value.items()):
            if len(set(ids)) > 1:
                conflicts.append((scope, val, sorted(set(ids))))
                for i in set(ids):
                    blocked.add((scope, i))
    # cross-scope informational: same canonical in 2+ scopes
    cross = {}
    for scope, idmap in finals.items():
        for rid, val in idmap.items():
            cross.setdefault(val, []).append((scope, rid))
    cross = {v: locs for v, locs in sorted(cross.items()) if len({s for s, _ in locs}) > 1}
    return {
        "invalid": invalid,
        "candidates": candidates,
        "conflicts": conflicts,
        "blocked": blocked,
        "cross": cross,
        "finals": finals,
    }


def pair_review(db, finals):
    """Teacher username==mobile pairs divergent after final values -> review list."""
    review = []
    no_shadow = []
    teachers = {t.id: (t.mobile or "").strip() for t in db.query(Teacher).all()}
    shadows = {(u.username or "").strip(): u.id for u in db.query(User).filter(User.role == "teacher").all()}
    for tid, raw_mob in teachers.items():
        if not raw_mob:
            continue
        sid = shadows.get(raw_mob)
        if sid is None:
            no_shadow.append(tid)
            continue
        fin_mob = finals["Teacher.mobile"].get(tid)
        fin_user = finals["User.username[teacher]"].get(sid)
        if fin_mob is not None and fin_user is not None and fin_mob != fin_user:
            review.append((tid, sid, raw_mob))
    return review, no_shadow


def fmt_rows(rows, limit=PRINT_CAP):
    lines = [f"  {r}" for r in rows[:limit]]
    if len(rows) > limit:
        lines.append(f"  ... and {len(rows) - limit} more (see report file)")
    return lines


def build_report(analysis, review, no_shadow):
    out = []
    inv, cand, conf, blocked = (
        analysis["invalid"],
        analysis["candidates"],
        analysis["conflicts"],
        analysis["blocked"],
    )
    applyable = [c for c in cand if (c[0], c[1]) not in blocked]
    out.append(f"mode: {'APPLY (writes!)' if APPLY else 'DRY-RUN (report only)'}")
    out.append(f"candidates (would update): {len(cand)}; applyable: {len(applyable)}; "
               f"blocked by conflict: {len(cand) - len(applyable)}")
    out.append(f"invalid (manual review, never touched): {len(inv)}")
    out.append(f"conflicts (manual review, no auto-merge): {len(conf)}")
    out.append("")
    out.append("== INVALID (scope, id, raw) ==")
    out += fmt_rows([f"{s} id={i} raw={r!r}" for s, i, r in inv], limit=10**9)
    out.append("")
    out.append("== CONFLICTS (scope, canonical, ids) ==")
    out += fmt_rows([f"{s} {v} ids={ids}" for s, v, ids in conf], limit=10**9)
    out.append("")
    out.append("== DIVERGENT PAIRS (teacher_id, shadow_id, raw_mobile) ==")
    out += fmt_rows([f"teacher={t} shadow={u} raw={m!r}" for t, u, m in review], limit=10**9)
    out.append("")
    out.append(f"teachers with mobile but no teacher-role shadow: {len(no_shadow)} "
               f"(login recreates; first ids: {no_shadow[:20]})")
    out.append("")
    out.append("== CROSS-SCOPE same canonical (informational) ==")
    for val, locs in list(analysis["cross"].items())[:500]:
        out.append(f"  {val}: {locs}")
    if len(analysis["cross"]) > 500:
        out.append(f"  ... and {len(analysis['cross']) - 500} more")
    out.append("")
    out.append("== CANDIDATES (scope, id, raw -> canonical) ==")
    out += fmt_rows(
        [f"{s} id={i} {r!r} -> {c!r}{' BLOCKED' if (s, i) in blocked else ''}" for s, i, r, c in cand],
        limit=10**9,
    )
    return "\n".join(out) + "\n"


def apply_updates(db, analysis):
    cand = [c for c in analysis["candidates"] if (c[0], c[1]) not in analysis["blocked"]]
    by_scope = {}
    for scope, rid, _raw, canon in cand:
        by_scope.setdefault(scope, []).append((rid, canon))
    n = 0
    for scope, pairs in by_scope.items():
        if scope == "Teacher.mobile":
            for rid, canon in pairs:
                db.query(Teacher).filter(Teacher.id == rid).update({"mobile": canon}, synchronize_session=False)
                n += 1
        elif scope == "Student.student_mobile":
            for rid, canon in pairs:
                db.query(Student).filter(Student.id == rid).update({"student_mobile": canon}, synchronize_session=False)
                n += 1
        elif scope == "Student.parent_mobile":
            for rid, canon in pairs:
                db.query(Student).filter(Student.id == rid).update({"parent_mobile": canon}, synchronize_session=False)
                n += 1
        elif scope == "User.username[teacher]":
            for rid, canon in pairs:
                db.query(User).filter(User.id == rid).update({"username": canon}, synchronize_session=False)
                n += 1
        elif scope == "Lead.mobile":
            for rid, canon in pairs:
                db.query(Lead).filter(Lead.id == rid).update({"mobile": canon}, synchronize_session=False)
                n += 1
    db.commit()
    return n


def main():
    db = SessionLocal()
    try:
        rows = collect(db)
        total = sum(len(v) for v in rows.values())
        print(f"scanned rows: {total}")
        analysis = analyze(rows)
        review, no_shadow = pair_review(db, analysis["finals"])
        report = build_report(analysis, review, no_shadow)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"report written: {REPORT_PATH}")
        if APPLY:
            n = apply_updates(db, analysis)
            print(f"APPLIED: {n} rows updated (conflicts/invalid untouched)")
        else:
            print("DRY-RUN: no writes. Review the report, then re-run with --apply.")
            head = "\n".join(report.split("\n")[:12])
            print("---- head ----")
            print(head)
    finally:
        db.close()


if __name__ == "__main__":
    main()
