# ممیزی routeهای `exports`

> The route ledger below is the current generated audit snapshot and supersedes any older status/count matrix above.

این جدول از `docs/app-map/server-routes.csv` تولید شده است. هر claim تستی باید به نام تست و `file:line` ارجاع دهد.

| route | چه کاری می‌کند | تعداد تست | دسته‌های پوشش | نتیجه | باگ |
|---|---|---:|---|---|---|
| `GET /exports/audit_alerts` | handler `routers.exports.export_audit_alerts`؛ منبع `Kharazmi_Server/routers/exports.py:228` | 0 | inventory/fixture | مسدود: تست رفتاری این route در نوبت router آن نوشته می‌شود | — |
| `GET /exports/debtors` | handler `routers.exports.export_debtors`؛ منبع `Kharazmi_Server/routers/exports.py:99` | 0 | inventory/fixture | مسدود: تست رفتاری این route در نوبت router آن نوشته می‌شود | — |
| `GET /exports/overdue_installments` | handler `routers.exports.export_overdue_installments`؛ منبع `Kharazmi_Server/routers/exports.py:192` | 0 | inventory/fixture | مسدود: تست رفتاری این route در نوبت router آن نوشته می‌شود | — |

<!-- GENERATED ROUTE LEDGER START -->
## Route ledger — map input + current isolated probes

Generated from `docs/app-map/server-routes.csv`; branch `arena/01a10aa8-kharazmiapp`. Static DB columns and response keys are the supplied map's AST/OpenAPI summary, not runtime proof. ‘Probe actor’ is the role intentionally selected by the sweep; it is not a substitute for a complete authorization contract.

| Route | One-sentence purpose / handler | Probe actor + observed result | Current Android caller / screen | Inputs → response values | Static DB reads → writes | Side effects | Audit evidence/status |
|---|---|---|---|---|---|---|---|
| `GET /exports/audit_alerts` | Runs `export audit alerts` for `GET /exports/audit_alerts`. Source: `Kharazmi_Server/routers/exports.py:228`. | admin / 200 non-json;<br> invalid=200 | `ExportApi.exportAuditAlerts` — `ApiInterfaces.kt`:192 | Input: header:authorization:{'anyOf': [{'type': 'string'},<br>{'type': 'null'}],<br>'title': 'Authorization'}:optional<br>Server response: نامشخص;<br> static_return_keys=نامشخص<br>Android model: `Response<ResponseBody>` () | Read: نامشخص<br>Write: نامشخص | نامشخص | Targeted request reference(s): `tests/route_audit/test_audit_exports.py:23` (`test_export_csv_headers_rows_and_role_guard`);<br> assertion depth is per linked test,<br>not inferred here. Map note: استخراج خودکار از app.openapi()+AST؛ موارد نامشخص در ستون مربوطه. |
| `GET /exports/debtors` | Runs `export debtors` for `GET /exports/debtors`. Source: `Kharazmi_Server/routers/exports.py:99`. | admin / 200 non-json;<br> invalid=200 | `ExportApi.exportDebtors` — `ApiInterfaces.kt`:184 | Input: query:branch_id:{'anyOf': [{'type': 'integer'},<br>{'type': 'null'}],<br>'title': 'Branch Id'}:optional<br>header:authorization:{'anyOf': [{'type': 'string'},<br>{'type': 'null'}],<br>'title': 'Authorization'}:optional<br>Server response: نامشخص;<br> static_return_keys=نامشخص<br>Android model: `Response<ResponseBody>` () | Read: Branch<br>Write: نامشخص | نامشخص | Targeted request reference(s): `tests/route_audit/test_audit_exports.py:21` (`test_export_csv_headers_rows_and_role_guard`);<br> assertion depth is per linked test,<br>not inferred here. Map note: استخراج خودکار از app.openapi()+AST؛ موارد نامشخص در ستون مربوطه. |
| `GET /exports/overdue_installments` | Runs `export overdue installments` for `GET /exports/overdue_installments`. Source: `Kharazmi_Server/routers/exports.py:192`. | admin / 200 non-json;<br> invalid=200 | `ExportApi.exportOverdueInstallments` — `ApiInterfaces.kt`:188 | Input: header:authorization:{'anyOf': [{'type': 'string'},<br>{'type': 'null'}],<br>'title': 'Authorization'}:optional<br>Server response: نامشخص;<br> static_return_keys=نامشخص<br>Android model: `Response<ResponseBody>` () | Read: نامشخص<br>Write: نامشخص | نامشخص | Targeted request reference(s): `tests/route_audit/test_audit_exports.py:22` (`test_export_csv_headers_rows_and_role_guard`);<br> assertion depth is per linked test,<br>not inferred here. Map note: استخراج خودکار از app.openapi()+AST؛ موارد نامشخص در ستون مربوطه. |

**Interpretation:** a 2xx/4xx smoke result only records the observed response for this isolated seed. It does not prove the listed static DB effect or business invariant. Direct test references are navigation aids, not a claim that every requested edge case is covered.
<!-- GENERATED ROUTE LEDGER END -->
