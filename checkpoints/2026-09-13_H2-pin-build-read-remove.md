# H2 leftovers implemented (decision ج) — 2026-09-13, no compile/run

## Step 1 — Server pin endpoint (routers/messages.py:316-350)
- :318 `PinToggleRequest(pinned: bool)`; :321 `POST /messages/conversations/{id}/pin`.
- Same auth pattern as history/send: require_permission("messages.read") + session/keys via
  resolve_participant_keys + 401/404/403 (IDOR participant check).
- CSV set add/discard of `f"{keys[0]}_{role}"`; empty → None (NULL, like never-pinned).
  Returns {"is_pinned": key in cur}. Sorted join for deterministic storage.

## Step 2 — App long-press toggle (MessageActivity.kt + strings.xml)
- :59-66 PinToggleRequest/PinToggleResponse; :83-84 `setPin` Retrofit POST.
- :105 `convAdapter` field; :180-185 adapter construction with onClick+onLongClick.
- :197-214 `togglePin()`: POST flipped value (Bug-19 pattern), on success
  `updatePin(id, res.is_pinned)` — single-item `copy()` + `notifyItemChanged`, NO full refresh.
  Error → Toast `msg_pin_error` (strings.xml:1130 «خطا در تغییر وضعیت پین»).
- Adapter :294 onLongClick param, :296 items MutableList, :299-305 updatePin(), :332 long-press
  listener, onBind/getItemCount switched list→items. ChatAdapter untouched.
- KNOWN: local toggle updates the icon only; pinned-first REORDER applies on next list load
  (server sorts; no client-side sort to honor "no full refresh").

## Step 3 — MessageRead removed
- models.py: class deleted (:650-656). Imports cleaned: messages.py:12, dependencies.py:6, admin.py:15.
- Project-wide grep: ZERO `MessageRead` matches (incl. tests). No migration needed:
  fresh DBs via `Base.metadata.create_all` (main.py:101/132/150) simply won't create
  `message_reads`; old DBs keep the orphan empty table, zero code references.

## Step 4 — Manual trace (per-user pin)
Conv C: A(5/student) + B(9/teacher), pinned_by=NULL.
A long-press → POST pin true → pinned_by="5_student" → A: icon on, list-top on reload.
B list: key "9_teacher" ∉ → is_pinned=false, normal. B pins → "5_student,9_teacher" → both pinned.
A unpins → "9_teacher" → A normal, B pinned. 401/403/404 paths mirror history/send.

## Verify: ast.parse (4 server files) + XML parse + grep line numbers. No execution.
## Incident: ChatAdapter shares `val item = list[position]` shape — adapter-edit anchor had to
## include `holder.title` line; first app script aborted pre-write, reran fixed.
