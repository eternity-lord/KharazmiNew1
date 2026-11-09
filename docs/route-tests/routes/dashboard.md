# ممیزی routeهای `dashboard`

> The route ledger below is the current generated audit snapshot and supersedes any older status/count matrix above.

این جدول از `docs/app-map/server-routes.csv` تولید شده است. هر claim تستی باید به نام تست و `file:line` ارجاع دهد.

| route | چه کاری می‌کند | تعداد تست | دسته‌های پوشش | نتیجه | باگ |
|---|---|---:|---|---|---|
| `GET /dashboard/kpis` | handler `routers.dashboard.get_dashboard_kpis`؛ منبع `Kharazmi_Server/routers/dashboard.py:56` | 0 | inventory/fixture | مسدود: تست رفتاری این route در نوبت router آن نوشته می‌شود | — |
| `GET /dashboard/push_status` | handler `routers.dashboard.get_push_status`؛ منبع `Kharazmi_Server/routers/dashboard.py:157` | 0 | inventory/fixture | مسدود: تست رفتاری این route در نوبت router آن نوشته می‌شود | — |

<!-- GENERATED ROUTE LEDGER START -->
## Route ledger — map input + current isolated probes

Generated from `docs/app-map/server-routes.csv`; branch `arena/01a10aa8-kharazmiapp`. Static DB columns and response keys are the supplied map's AST/OpenAPI summary, not runtime proof. ‘Probe actor’ is the role intentionally selected by the sweep; it is not a substitute for a complete authorization contract.

| Route | One-sentence purpose / handler | Probe actor + observed result | Current Android caller / screen | Inputs → response values | Static DB reads → writes | Side effects | Audit evidence/status |
|---|---|---|---|---|---|---|---|
| `GET /dashboard/kpis` | Runs `get dashboard kpis` for `GET /dashboard/kpis`. Source: `Kharazmi_Server/routers/dashboard.py:56`. | admin / 200 object;<br> invalid=200 | `DashboardApi.getKPIs` — `ApiInterfaces.kt`:173 | Input: header:authorization:{'anyOf': [{'type': 'string'},<br>{'type': 'null'}],<br>'title': 'Authorization'}:optional<br>Server response: DashboardKPIs;<br> static_return_keys=نامشخص<br>Android model: `DashboardKPIs` (todayRevenue:json=today_revenue:Long;<br>totalOverdueAmount:json=total_overdue_amount:Long;<br>overdueInstallmentsCount:json=overdue_installments_count:Int;<br>activeStudentsCount:json=active_students_count:Int;<br>suspiciousAlertsCount:json=suspicious_alerts_count:Int;<br>dunningPendingCount:json=dunning_pending_count:Int) | Read: نامشخص<br>Write: نامشخص | نامشخص | Targeted request reference(s): `tests/route_audit/test_audit_dashboard.py:19` (`test_dashboard_kpis_have_independent_seed_values_and_push_is_local`);<br> assertion depth is per linked test,<br>not inferred here. Map note: استخراج خودکار از app.openapi()+AST؛ موارد نامشخص در ستون مربوطه. |
| `GET /dashboard/push_status` | Runs `get push status` for `GET /dashboard/push_status`. Source: `Kharazmi_Server/routers/dashboard.py:157`. | admin / 200 object;<br> invalid=200 | No static Retrofit caller in current overlay;<br> server-only/deferred screen attribution. | Input: header:authorization:{'anyOf': [{'type': 'string'},<br>{'type': 'null'}],<br>'title': 'Authorization'}:optional<br>Server response: PushStatus;<br> static_return_keys=نامشخص | Read: نامشخص<br>Write: نامشخص | PushStatus | Targeted request reference(s): `tests/route_audit/test_audit_dashboard.py:29` (`test_dashboard_kpis_have_independent_seed_values_and_push_is_local`);<br> assertion depth is per linked test,<br>not inferred here. Map note: استخراج خودکار از app.openapi()+AST؛ موارد نامشخص در ستون مربوطه. |

**Interpretation:** a 2xx/4xx smoke result only records the observed response for this isolated seed. It does not prove the listed static DB effect or business invariant. Direct test references are navigation aids, not a claim that every requested edge case is covered.
<!-- GENERATED ROUTE LEDGER END -->
