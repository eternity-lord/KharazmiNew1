# Checkpoint — H20 analysis: mobile normalization (read-only)

Date: 2026-09-12. No normalize_mobile exists (grep-confirmed). No code changed.

## Step 1 — sweep (all direct, unnormalized)
Teacher.mobile ==: auth.py:67 login_user, :331 get_me, :582/:603/:611
change_mobile, admin.py:1573 update_teacher_credentials, classes.py:934
request_class_deletion, reports.py:403 get_logged_in_teacher, teachers.py:41
register_teacher, :415 update_teacher. Plain: auth.py:257 change_password
(!=), admin.py:1572/1581 (!= change-detect).
Student.student_mobile ==: auth.py:374 request_student_otp, :469 student_login,
crm.py:155 convert_lead, :210 public_online_registration, students.py:40
register_student, auth.py:583 change_mobile.
Student.parent_mobile ==: parent.py:31 request_parent_otp, :141 parent_login;
plain IDOR compare parent.py:202 select_child (!=).
ParentOTP.mobile ==: parent.py:38/42/50/:109, auth.py:385/393/:444.
LoginAttempt.mobile ==: auth.py:31/49/113 (H14 throttle key!).
User.username (mobile-form): auth.py:37/:83/:86 (shadow lookup+create),
:269/:280 change_password, :581/:592/:597-598 change_mobile,
admin.py:~1582/:~1587 shadow lookup+write.

## Step 2 — entries sanitize strip-only or NOTHING
strip-only: register_student :39 (student_mobile; parent_mobile via dict()
fully RAW), register_teacher :40, update_student :452-469 (strip-store, NO
uniqueness check!), update_teacher :411-417+loop, OTP request vars
(parent.py:27, auth.py:371), H14 throttle key (auth.pySans? stripped).
isdigit+len-reject, no normalize (H1): change_mobile :577, update_teacher
:413, update_student :454/459, admin creds :~1565.
FULLY RAW (no strip): register_and_enroll :83-84, crm lead intake :73,
convert copy :167-168, public register :210/:226-227, login lookups
auth.py:37/:67 (req.mobile raw), all mobile WRITES store request bytes.
Legacy data: mixed formats near-certain → H4/C3-style backfill question.
Student shadows NOT affected (namespaced usernames, deps:464); teacher
shadows ARE (username=mobile, auth.py:86).

## Step 3 — normalize_mobile design (proposed, not written)
dependencies.py: translate FA/AR digits→ASCII, drop spaces/dashes/parens,
strip +/0098/12-digit-98, 10-digit-9→11-digit-0, accept only ^09\d{9}$,
else None (caller→400; never return invalid string). Supersedes H1's
10-or-11 dual form (which today stores two canonical forms!).

## Step 4 — fix categories
WRITES (normalize-or-400 before store): all register/update/change/creds/
crm/lead/OTP/attempt/shadow-teacher sites above. Fix adjacent: add missing
mobile clash-check to update_student.
READS (normalize input before compare): all logins, OTP verifies, identity
resolvers (:331/:934/:403), clash checks, select_child :202 (normalize BOTH
sides — temp-JWT + stored).
BACKFILL: YES for Teacher.mobile, Student.student_mobile/parent_mobile,
User.username WHERE role=teacher (never touch admin/non-mobile names),
Lead.mobile. Report same-normalized conflicts + un-normalizables for manual
review; no auto-merge. ParentOTP/LoginAttempt ephemeral → no backfill.
Impact if reads-only without backfill: legacy-row lockouts. Live impacts
today: cross-format login/OTP failure, duplicate-registration bypass, H14
throttle bypass + OTP rate-limit bypass via format rotation, select_child
false-403.
