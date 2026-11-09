# ممیزی routeهای `audit`

> The route ledger below is the current generated audit snapshot and supersedes any older status/count matrix above.

این جدول از `docs/app-map/server-routes.csv` تولید شده است. هر claim تستی باید به نام تست و `file:line` ارجاع دهد.

| route | چه کاری می‌کند | تعداد تست | دسته‌های پوشش | نتیجه | باگ |
|---|---|---:|---|---|---|
| `GET /audit/suspicious_patterns` | handler `routers.audit.get_suspicious_patterns`؛ منبع `Kharazmi_Server/routers/audit.py:87` | 6 | empty/read-only + exact keys، night/delay، rapid-delete <1h only (exactly 1h excluded; >30d ignored)، perfect attendance last-10 (older absence excluded, recent absence suppresses) | 6 passed؛ باگ باز تأیید نشد | — |

<!-- GENERATED ROUTE LEDGER START -->
## Route ledger — map input + current isolated probes

Generated from `docs/app-map/server-routes.csv`; branch `arena/01a10aa8-kharazmiapp`. Static DB columns and response keys are the supplied map's AST/OpenAPI summary, not runtime proof. ‘Probe actor’ is the role intentionally selected by the sweep; it is not a substitute for a complete authorization contract.

| Route | One-sentence purpose / handler | Probe actor + observed result | Current Android caller / screen | Inputs → response values | Static DB reads → writes | Side effects | Audit evidence/status |
|---|---|---|---|---|---|---|---|
| `GET /audit/suspicious_patterns` | Runs `get suspicious patterns` for `GET /audit/suspicious_patterns`. Source: `Kharazmi_Server/routers/audit.py:87`. | admin / 200 list;<br> invalid=200 | `AuditApi.getSuspiciousPatterns` — `ApiInterfaces.kt`:146 | Input: header:authorization:{'anyOf': [{'type': 'string'},<br>{'type': 'null'}],<br>'title': 'Authorization'}:optional<br>Server response: List[AuditAlert];<br> static_return_keys=نامشخص<br>Android model: `List<AuditAlert>` (type:json=type:String;<br>severity:json=severity:String;<br>title:json=title:String;<br>description:json=description:String;<br>entityId:json=entity_id:Int;<br>entityName:json=entity_name:String;<br>detectedAt:json=detected_at:String) | Read: ActivityLog;<br>Attendance;<br>Course;<br>SessionLog;<br>Transaction<br>Write: نامشخص | نامشخص | Targeted request reference(s): `tests/route_audit/test_audit_audit.py:66` (`test_audit_seed_response_has_exact_alert_shape_and_is_read_only`),<br>`tests/route_audit/test_audit_audit.py:89` (`test_audit_pattern_a_reports_night_and_delayed_sessions_with_frozen_time`),<br>`tests/route_audit/test_audit_audit.py:153` (`test_audit_pattern_b_flags_only_recent_rapid_deleted_transaction`),<br>`tests/route_audit/test_audit_audit.py:200` (`test_audit_pattern_b_ignores_deleted_rows_with_logs_older_than_thirty_days`),<br>`tests/route_audit/test_audit_audit.py:243` (`test_audit_pattern_c_uses_ten_latest_sessions_and_detects_new_absence`);<br> assertion depth is per linked test,<br>not inferred here. Map note: استخراج خودکار از app.openapi()+AST؛ موارد نامشخص در ستون مربوطه. |

**Interpretation:** a 2xx/4xx smoke result only records the observed response for this isolated seed. It does not prove the listed static DB effect or business invariant. Direct test references are navigation aids, not a claim that every requested edge case is covered.
<!-- GENERATED ROUTE LEDGER END -->
