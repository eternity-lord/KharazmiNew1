# ممیزی routeهای `ai`

> The route ledger below is the current generated audit snapshot and supersedes any older status/count matrix above.

این جدول از `docs/app-map/server-routes.csv` تولید شده است. هر claim تستی باید به نام تست و `file:line` ارجاع دهد.

| route | چه کاری می‌کند | تعداد تست | دسته‌های پوشش | نتیجه | باگ |
|---|---|---:|---|---|---|
| `POST /ai/chat` | handler `routers.ai.chat_with_ai_assistant`؛ منبع `Kharazmi_Server/routers/ai.py:153` | 0 | inventory/fixture | مسدود: تست رفتاری این route در نوبت router آن نوشته می‌شود | — |

<!-- GENERATED ROUTE LEDGER START -->
## Route ledger — map input + current isolated probes

Generated from `docs/app-map/server-routes.csv`; branch `arena/01a10aa8-kharazmiapp`. Static DB columns and response keys are the supplied map's AST/OpenAPI summary, not runtime proof. ‘Probe actor’ is the role intentionally selected by the sweep; it is not a substitute for a complete authorization contract.

| Route | One-sentence purpose / handler | Probe actor + observed result | Current Android caller / screen | Inputs → response values | Static DB reads → writes | Side effects | Audit evidence/status |
|---|---|---|---|---|---|---|---|
| `POST /ai/chat` | Runs `chat with ai assistant` for `POST /ai/chat`. Source: `Kharazmi_Server/routers/ai.py:153`. | admin / 200 object;<br> invalid=422 | No static Retrofit caller in current overlay;<br> server-only/deferred screen attribution. | Input: header:authorization:{'anyOf': [{'type': 'string'},<br>{'type': 'null'}],<br>'title': 'Authorization'}:optional<br>body:AIChatRequest:required<br>Server response: نامشخص;<br> static_return_keys=status,<br>response,<br>role,<br>suggested_action | Read: Attendance;<br>Course;<br>Student;<br>models.UserSession<br>Write: نامشخص | نامشخص | Targeted request reference(s): `tests/route_audit/test_audit_ai.py:63` (`test_ai_admin_revenue_response_uses_seeded_financial_values_without_writes`),<br>`tests/route_audit/test_audit_ai.py:118` (`test_ai_role_tool_values_are_passed_to_provider_without_database_side_effects`),<br>`tests/route_audit/test_audit_ai.py:148` (`test_ai_invalid_request_does_not_call_provider_or_mutate_history`),<br>`tests/route_audit/test_audit_ai.py:163` (`test_ai_conversation_history_stays_bounded_to_fifteen_messages`);<br> assertion depth is per linked test,<br>not inferred here. Map note: استخراج خودکار از app.openapi()+AST؛ موارد نامشخص در ستون مربوطه. |

**Interpretation:** a 2xx/4xx smoke result only records the observed response for this isolated seed. It does not prove the listed static DB effect or business invariant. Direct test references are navigation aids, not a claim that every requested edge case is covered.
<!-- GENERATED ROUTE LEDGER END -->
