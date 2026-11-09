# L5 — Final Summary (all 6 batches, 2026-09-13, no Android compile)

## Totals
- Replacements (→ getString): B1 164 + B2 134 + B3 128 + B4 183 + B5 313 + B6 247 = **1169**
- FA `"..."` matches: 1204 (69 files, baseline) → **102 left** (all classified below) = **1102 eliminated**
  (1169 > 1102 because replacements also covered 40+ emoji-only literals and `"""`-block lines
  that were never in the FA baseline; 1 FA literal removed by grade-289 null-fix, not a resource.)
- strings.xml: 200 → **1127** (+927: B1 35, B2 109, B3 124, B4 141, B5 305, B6 213)
- R.string refs project-wide: 954 — resolve check: NONE missing. XML validated.
- aapt hardening (B6): 77 strings with boundary `\n`/whitespace wrapped in `"..."` (documented
  preservation mechanism); all literal newlines normalized to `\n` escapes (CRLF-proof).

## Zeroed files (main dir: 51 of 69 fully zero FA+emoji+triples)
Attendance B2*, Main B2, Invoice B3*, StudentProfile B3, ParentPortal B4, StudentPortal B4,
TeacherDash B4, TeacherProfile B4, + B4 registers*, ClassDetail B5*, ClassSetup B5*, DeletionRequests B5,
Calendar B5*, Exam B5*, Homework B5*, TransactionManage B5*, Chart B5, EditStudent B5, CrmLeads B5,
PersonList B5, Report B6, Settings B6, ClassManagement B6*, InstituteSettings B6, TeacherCredentials B6,
LiveRoster B6, LiveClass B6, NotificationCenter B6, SessionHistory B6, EditTeacher B6, PendingClasses B6,
LiveClasses B6, Message B6, CachedApiCall B6, PendingClassDetail B6, RetrofitClient B6, BaseActivity B6,
PendingTeachers B6, ReportExporter B6, ClassDashboard B6, ShareConfig B6, CommunicationHistory B6,
NumberAnimator B6, Login, + all other untouched-by-L5 files that had no Persian.
(* = zero except listed set-asides/comments/separators below. ui/: MainRepository + MainUseCase zero;
MainViewModel comment-only; MainActivityRefactored = skeleton set-aside.)

## B6 replacements (247): Report 15, Settings 17, ClassMgmt 18, InstSet 16, TCred 16, LiveRoster 13,
LiveClass 11, Notif 12, Sms 4, SessHist 10, EditTeacher 10, PendClasses 9, LiveClasses 8, Message 7,
ParentContacts 6, SubmitGrade 6, CachedApiCall 5, PendClassDet 6, RetrofitClient 4, Base 3, PendTeachers 5,
ReportExporter 4, ClassDash 2, ShareConfig 3, CommHist 3, NumberAnimator 1, ClassDetail 6, ClassSetup 1,
CrmLeads 2, DelReq 1, EditStudent 1, Login 1, ParentPortal 4, StudentPortal 3, StudentProfile 7,
StudentRegister 1, Txn 1, Invoice 1, TeacherDash 1, Attendance 1, PersonList 1.

## SET-ASIDE REGISTRY (complete, with future-migration guidance)
Line numbers = current (post-L5).

### A. API/logic-mapped (need code-map refactor, NOT blind move)
A1. Discount-trio unit — display⟷API when-maps (`درصدی→percentage`, `مبلغ ثابت→fixed`):
  ClassSetup :197/:200/:211-212/:275-276; StudentRegister :169/:171/:177-178/:327-328/:381-382.
  Future: parallel code arrays + migrate display only.
A2. Genders `آقا/خانم` (API-sent): StudentRegister :156/:158; TeacherRegister :147/:149.
A3. Study-status ×4 (`در حال تحصیل/فارغ‌التحصیل/انصرافی/سایر`): StudentRegister :163/:166.
A4. Marital ×3 (`مجرد/متاهل/مطلقه`): TeacherRegister :151/:153.
A5. Employment ×3 (`رسمی/پیمانی/آزاد`): TeacherRegister :155/:157.
A6. Address request default `ثبت نشده`: StudentRegister :420.
A7. AddClass: grades array :68-71, eduTypes :74, request literals :144-146 (`مختلط/نامشخص`) —
  sent as grade_level/education_type/etc.
A8. Calendar days array + default :249/:251 — sent as days_of_week.
A9. Sms target trio — forward when-KEYS + reverse map: :69/:85-86/:151-153 (codes all_students/all_teachers/debtors).
A10. Invoice: :261 `کد: ` substring parser (producer = server strings); payMethod values
  :425-427/:431 (feed API payment_method + idempotency formSig); :430 Log line.
A11. ClassDetail :669 `status == "حاضر"` server-value compare (icons migrated, compare kept).

### B. Non-migratable without restructure
B1. ServerAddress :11/:15/:18/:20 — `require()` messages, object has no Context.
B2. ui/MainActivityRefactored :61-65 — Compose-skeleton labels, plain fun with no Context/`stringResource`
  (scaffolding; LazyGrid commented out). :108 + MainViewModel :35 are comments.
B3. JalaliUtils :17-18 — FA/Arabic digit constants (logic).

### C. Mock/demo data (migrate only if mocks go to resources)
C1. Homework :291-292; C2. DesignSystem :16-18 (avatar demo names).

### D. Punctuation separators (kept, locale-neutral)
D1. `، `: ClassSetup :133, Exam :375, ParentContacts :128. D2. `؛ `: Attendance :218.

### E. Code comments (out of L5 scope, never migrate)
E1. AppModels :307; E2. SubmitGrade :47; E3. TransactionManage :243; E4. ui comments (:108, VM :35).

### F. Server-side (explicitly OUT of L5 — Android strings.xml can't serve Python)
F1. `routers/parent.py` (~159 FA lines: API details + served HTML portal). Needs separate
  Python-constants/i18n decision. Same for any other server FA strings.

## Fixed during L5 (not set aside)
- grade-289: ClassDetail :289 hardcoded `دوازدهم` → null (app) + server `_VALID_GRADE_LEVELS`
  400-validation (routers/classes.py :1080-1091/:1116-1122). Checkpoint: 2026-09-13_grade289-fix.md.

## Standing traps for future migrators (from L5)
- Nested `"..."` inside `${}` need NO backslash (Exam :308, LiveClass :233).
- Precomposed vs decomposed Persian (B4 TREG أ) — byte-read on miss.
- Bare `%` after format args → `%%` in XML.
- `"""` blocks: pair delimiters; regex spans blocks (false positives).
- Never parallelize edits to the SAME file (grade-289 incident: lost edits).
