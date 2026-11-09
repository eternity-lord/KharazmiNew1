# Checkpoint — H16 implementation (server-truthful receipt loader)

Date: 2026-09-12. 9 ops (2 server + 7 app), anchors asserted + visual read-back.
No compile/run (standing Android rule).

## Step 1 — server: course_name in GET /finance/receipt/{id}
- finance.py: lookup block after student_national (~:1683-1695): enrollment→course
  first, trans.course_id fallback, "---" default. NO is_deleted filters (receipt
  = historical document; matches "archived must retain valid course reference").
- Response field added (~:1705) after description. App never called this endpoint
  → zero regression surface. (Enrollment/Course already imported in finance.py.)

## Step 2 — IDOR adjacent: REAL exposure, NO change (awaiting order)
- POST /finance/receipt/print (:433) + /pdf (:473): check_user_login only, NO
  verify_financial_idor, and neither even TAKES authorization param. Any
  authenticated role (student/teacher/parent) can enumerate ids → other users'
  names, national codes, amounts. receipt_data is REAL DB data (only
  print_job/pdf_url are stubbed). App declares-but-never-calls them; parent web
  portal doesn't reference them → needs direct API call to exploit. MEDIUM.
- Recommended fix (not applied): add `authorization` Header + one-line
  verify_financial_idor(trans.student_id, authorization, db) in each, mirroring
  GET receipt.

## Step 3 — loader (InvoiceActivity.kt)
- Imports: GET/Path/HttpException (:31-33). File-local ReceiptDetailsResponse
  (all-nullable, remittance_number: Any? — server mixes int/"---") +
  ReceiptDetailsApi GET (~:60-82).
- loadAndShowReceipt(receiptId, message, isModified=false) :546-580: guards
  id<=0 → GET → populates VIEWS from server (same Main block, atomic vs input;
  modality proven) → dialog. 404 → clear Toast (deleted/reversed); other errors
  → generic Toast. Bug-19 cancellation pattern kept.

## Step 4 — both paths converted to id-only
- REPRINT block :129-134: reads only RECEIPT_ID (+IS_MODIFIED stamp) → loader.
- TransactionManage :184-191 (row print) and :245-251 (post-edit): only
  RECEIPT_ID (+stamp) passed — TOCTOU + PUT-echo gone. Stale extras grep: EMPTY.

## Step 5 — post-submit unified, intact
- sendData :530: res.receipt_id → loader (same dialog UX after a LAN-fast fetch;
  accepted: no progress UI for the gap). Dialog now has exactly ONE caller (the
  loader); both old direct calls converted. res.receipt_id==0 edge → clean
  invalid-id Toast (was: dialog with id "0" — clearer now).
- Display parity kept: tracking shows transaction id as before (no switch to
  remittance_number — unasked behavior change avoided). Split-payment footnote
  unchanged: primary txn printed (same as before).
