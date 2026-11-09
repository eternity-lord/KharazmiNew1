# Analysis (read-only): H2 leftovers — MessageRead + pin (2026-09-13)

## Server state
- `pinned_by` (models.py:630, Conversation): CSV of `{user_id}_{role}`. READ ONLY in
  messages.py:78-79 (`get_my_conversations`), served as `is_pinned`, sorted pinned-first (:89).
  NEVER WRITTEN — no pin/unpin endpoint; grep shows zero writers project-wide.
- `MessageRead` (models.py:650-656, table message_reads): defined + imported in 3 files
  (dependencies.py:6, admin.py:15, messages.py:12) but ZERO reads/writes/calls.
  History endpoint (:144-173) neither records reads nor returns read state. Fully dead.
- messages.py endpoints: list / create / history / send / delete / broadcast. No pin, no mark-read.
- Dev DB (read-only copy): conversations/participants/messages/message_reads all 0 rows;
  non-null pinned_by = 0. (Production state unknown from this DB.)

## Consumer audit (step 1)
- PIN — display consumer EXISTS, action UI ABSENT:
  - App shows pin icon: item_conversation.xml `imgPinned` ← MessageActivity :266/:280-284
    (`if (item.is_pinned) VISIBLE else GONE`). No toggle: adapter has only onClick→details,
    no long-press/menu/button. Since server never writes pinned_by, icon never shows in practice.
  - Parent portal (parent.py): no messaging UI at all. No FA pin strings in app (only «اسپینر» false+).
- READ RECEIPTS — NO consumer at all (QR/H18-class): MessageHistoryItem has no read fields,
  loadChatHistory renders only, no seen indicators, no mark-read call; server returns no read
  state. «خوانده» hits in 5 app files are all comments/other systems (notification center, etc.).

## Recommendation (step 2)
- PIN → BUILD (1 endpoint away; display path already live on both sides):
  `POST /messages/conversations/{id}/pin` {pinned: bool}, minimal per project patterns:
  require_permission("messages.read") + resolve_participant_keys + same IDOR participant check
  as history/send + 404 on missing conv; CSV add/discard `f"{keys[0]}_{role}"`, commit,
  return {"is_pinned": ...}. Caveat: CSV read-modify-write can clobber under concurrent
  toggles — acceptable for a view preference. App follow-up needed: long-press toggle → call.
- MessageRead → REMOVE (true dead code): delete model class + drop the name from the 3 import
  lines. Existing DBs keep the empty table harmlessly; fresh DBs won't create it; no migration
  needed (zero references). Alternative (not recommended): keep + document as future-ready —
  invites confusion, zero demand (no unread-count/seen UI anywhere).

## NOT done (awaiting user decision): no code changed, no deletions.
