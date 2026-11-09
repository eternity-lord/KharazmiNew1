# ممیزی routeهای `timeline`

> The route ledger below is the current generated audit snapshot and supersedes any older status/count matrix above.

این جدول از `docs/app-map/server-routes.csv` تولید شده است. هر claim تستی باید به نام تست و `file:line` ارجاع دهد.

| route | چه کاری می‌کند | تعداد تست | دسته‌های پوشش | نتیجه | باگ |
|---|---|---:|---|---|---|
| `GET /students/{student_id}/timeline` | رویدادهای پرداخت، غیبت، نمره و قسط را برای دانش‌آموز مجاز در feed فقط‌خواندنی، نزولی بر اساس زمان ادغام می‌کند. | 9 | four exact event types/fields/order, Persian/Gregorian timestamps, empty/full, per-source 20/global 50, filters, role/IDOR, deleted/suspended states, DB no-write, Kotlin/Gson/display | 9 passed؛ xfail ندارد؛ رفتار مبهم Q-032..Q-034 | — |

<!-- GENERATED ROUTE LEDGER START -->
## Route ledger — map input + current isolated probes

Generated from `docs/app-map/server-routes.csv`; branch `arena/01a10aa8-kharazmiapp`. Static DB columns and response keys are the supplied map's AST/OpenAPI summary, not runtime proof. ‘Probe actor’ is the role intentionally selected by the sweep; it is not a substitute for a complete authorization contract.

| Route | One-sentence purpose / handler | Probe actor + observed result | Current Android caller / screen | Inputs → response values | Static DB reads → writes | Side effects | Audit evidence/status |
|---|---|---|---|---|---|---|---|
| `GET /students/{student_id}/timeline` | Runs `get student timeline` for `GET /students/{student_id}/timeline`. Source: `Kharazmi_Server/routers/timeline.py:85`. | student / 200 list;<br> invalid=422 | `TimelineApi.getTimeline` — `ApiInterfaces.kt`:154 | Input: path:student_id:integer:required<br>header:authorization:{'anyOf': [{'type': 'string'},<br>{'type': 'null'}],<br>'title': 'Authorization'}:optional<br>Server response: List[TimelineEvent];<br> static_return_keys=نامشخص<br>Android model: `List<TimelineEvent>` (timestamp:json=timestamp:String;<br>type:json=type:String;<br>title:json=title:String;<br>subtitle:json=subtitle:String;<br>iconName:json=icon_name:String;<br>colorHex:json=color_hex:String) | Read: Attendance;<br>Course;<br>Grade;<br>Installment;<br>Student;<br>Transaction<br>Write: نامشخص | نامشخص | Targeted request reference(s): `tests/route_audit/test_audit_timeline.py:126` (`test_timeline_empty_and_all_event_values_are_ordered_read_only_and_gson_compatible`),<br>`tests/route_audit/test_audit_timeline.py:327` (`test_timeline_role_scope_missing_deleted_and_suspended_students_are_observed_read_only`),<br>`tests/route_audit/test_audit_timeline.py:441` (`test_timeline_per_source_limit_filters_transactions_and_orders_latest_twenty`),<br>`tests/route_audit/test_audit_timeline.py:514` (`test_timeline_each_remaining_source_caps_at_twenty_and_orders_descending`),<br>`tests/route_audit/test_audit_timeline.py:620` (`test_timeline_combined_feed_keeps_fifty_newest_after_per_type_limits`);<br> assertion depth is per linked test,<br>not inferred here. Map note: استخراج خودکار از app.openapi()+AST؛ موارد نامشخص در ستون مربوطه. |

**Interpretation:** a 2xx/4xx smoke result only records the observed response for this isolated seed. It does not prove the listed static DB effect or business invariant. Direct test references are navigation aids, not a claim that every requested edge case is covered.
<!-- GENERATED ROUTE LEDGER END -->
