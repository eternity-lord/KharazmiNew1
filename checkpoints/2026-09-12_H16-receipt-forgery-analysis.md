# Checkpoint — H16 receipt-forgery analysis (READ-ONLY, no code changed)

Date: 2026-09-12. Q: receipt printed from editable fields, not server truth?

## Step 1 — dialog IS modal; post-submit field-tampering NOT practically possible
- showRemittanceSuccessDialog (InvoiceActivity.kt:530): AlertDialog.Builder +
  setView + setCancelable(false) (:547-549) + create(); no
  setCanceledOnTouchOutside override, no window flags, no custom touch
  listeners; single show() at end. Stock Android: dialog window blocks ALL
  touches to behind Activity; BACK + outside-tap dismissal disabled.
- After dismiss, both buttons clear fields (etAmount/etDesc setText("") :592,608).
- Rotation edge: plain AlertDialog (not DialogFragment) dies with Activity;
  post-submit MODE≠REPRINT so no re-show; resubmit creates a NEW server txn —
  UX quirk, not forgery. REPRINT+rotation re-shows from same intent — fine.

## Step 2 — REPRINT fully traced (internal-only forgery chain, REAL)
- InvoiceActivity :104-119: ST/CL/AMOUNT/DATE/DESC/RECEIPT_ID/IS_MODIFIED from
  Intent extras → editable fields + auto-show dialog. Print handlers (:556-558,
  :569-572) read etAmount/etDesc/tvStName/tvStClass/tvDate + receiptId param.
  printReceiptClientSide (:616+) builds HTML from params ONLY (+fresh institute
  settings); no transaction re-fetch. Any crafted in-app intent ⇒
  official-looking forged receipt (arbitrary amount + tracking number).
- Site 1 — TransactionManageActivity:187 (row btnPrint): extras from
  TransactionFullItem (AppModels.kt:257: id/student/course/amount/date/desc/
  remittance). List = FRESH api.getTransactions (GET admin/transactions/list,
  :28-30,112-116), NO CacheManager — but TOCTOU-stale at print tap + passes
  through editable fields. IS_MODIFIED=false.
- Site 2 — TransactionManageActivity:250 (post-PUT auto-print): extras = ECHO
  of just-PUT values (server 200 confirmed, not re-read) + IS_MODIFIED=true
  (prints «اصلاح شده» stamp).

## Step 3 — exported=false (manifest:87-88). External vector CLOSED
- InvoiceActivity android:exported="false", no intent-filters → no other app can
  fire the intent (non-root). Threat = in-app paths only (today: the 2 sites).

## Step 4 — server receipt endpoints EXIST (and are id-only/DB-truthful)
- GET /finance/receipt/{transaction_id} (finance.py:1665-1697): auth +
  verify_financial_idor + 404 for missing/reversed/deleted. Returns
  transaction_id/remittance_number/student_name/national/amount/payment_method/
  tracking_code/date/description/target_wallet/type/is_reversed. Covers print
  needs EXCEPT course_name (add via enrollment→course; null-safe fallback).
  Bonus: rebuilding via it auto-blocks printing reversed/deleted txns (404).
- POST /finance/receipt/print + /pdf (:433-516): id-only, DB-truthful — BUT
  (i) Retrofit stubs declared (InvoiceActivity.kt:54-58) NEVER called (dialog
  uses client-side renderers); (ii) both are STUBS (fake print_job/pdf_url,
  "در اینجا منطق... اجرا می‌شود"); (iii) ADJACENT: unlike GET receipt, they
  LACK IDOR (any logged-in role can pull any txn by id) — C1-class, list-only.
- App NEVER calls GET receipt today (grep empty).

## Step 5 — proposal
- (a) REPRINT: pass ONLY receipt_id; on open GET /finance/receipt/{id} and render
  dialog/print from response (drop AMOUNT/DESC/etc extras). Server: add
  course_name to GET response. Site-2 keeps IS_MODIFIED stamp (display bool,
  safe) — values come from re-GET (same result, truthful). Client-only except
  one server field.
- (b) exported: ALREADY false — no change; keep (no legit external caller).
- (c) Post-submit: NO vuln (modality proven) — but harden by UNIFYING: same
  loadAndShowReceipt(receiptId) loader for post-submit (res.receipt_id) and
  REPRINT. Rationale: FinanceResponse has NO amount echo (AppModels :315-320;
  server :415-421) so "read from res" is impossible without server change;
  GET-rebuild needs none. Snapshot-fields-into-locals adds nothing (fields
  frozen while modal). Footnote: split ("both") payments create MULTIPLE txns
  (receipt_ids) but dialog prints primary only — separate product UX question.
