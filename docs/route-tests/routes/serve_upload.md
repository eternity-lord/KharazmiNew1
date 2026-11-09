# ممیزی routeهای `serve_upload`

> The route ledger below is the current generated audit snapshot and supersedes any older status/count matrix above.

این جدول از `docs/app-map/server-routes.csv` تولید شده است. هر claim تستی باید به نام تست و `file:line` ارجاع دهد.

| route | چه کاری می‌کند | تعداد تست | دسته‌های پوشش | نتیجه | باگ |
|---|---|---:|---|---|---|
| `GET /uploads/{filename}` | فایل profile/logo را پس از احراز هویت به صورت FileResponse از پوشهٔ `profiles` می‌فرستد. | 11 | authorized bytes/MIME/length و پنج نقش، 401، missing=404، filename path/hidden validation=400، exact DB no-write، Android Glide/Auth header source | 11 passed؛ xfail ندارد | — |

<!-- GENERATED ROUTE LEDGER START -->
## Route ledger — map input + current isolated probes

Generated from `docs/app-map/server-routes.csv`; branch `arena/01a10aa8-kharazmiapp`. Static DB columns and response keys are the supplied map's AST/OpenAPI summary, not runtime proof. ‘Probe actor’ is the role intentionally selected by the sweep; it is not a substitute for a complete authorization contract.

| Route | One-sentence purpose / handler | Probe actor + observed result | Current Android caller / screen | Inputs → response values | Static DB reads → writes | Side effects | Audit evidence/status |
|---|---|---|---|---|---|---|---|
| `GET /uploads/{filename}` | Runs `serve upload` for `GET /uploads/{filename}`. Source: `Kharazmi_Server/main.py:94`. | admin / 404 object;<br> invalid=404 | Glide authenticated image loads — `StudentProfileActivity.kt:344` (`profile_image`);<br> `TeacherProfileActivity.kt:291` (`profile_image`);<br> `InstituteSettingsActivity.kt:109` (`logo_path`). | Input: path:filename:string:required<br>header:authorization:{'anyOf': [{'type': 'string'},<br>{'type': 'null'}],<br>'title': 'Authorization'}:optional<br>Server response: نامشخص;<br> static_return_keys=نامشخص<br>Android display: `FileResponse` bytes displayed by Glide `ImageView`;<br> request uses `Authorization: Bearer <SecureLoginStore token>`. No Retrofit DTO. | Read: نامشخص<br>Write: نامشخص | FileResponse | Targeted request reference(s): `tests/route_audit/test_audit_serve_upload.py:78` (`test_serve_upload_returns_exact_temp_file_for_each_authenticated_role`),<br>`tests/route_audit/test_audit_serve_upload.py:98` (`test_serve_upload_requires_authentication_before_resolving_file`),<br>`tests/route_audit/test_audit_serve_upload.py:116` (`test_serve_upload_missing_file_is_404_and_read_only`);<br> assertion depth is per linked test,<br>not inferred here. Map note: استخراج خودکار از app.openapi()+AST؛ موارد نامشخص در ستون مربوطه. |

**Interpretation:** a 2xx/4xx smoke result only records the observed response for this isolated seed. It does not prove the listed static DB effect or business invariant. Direct test references are navigation aids, not a claim that every requested edge case is covered.
<!-- GENERATED ROUTE LEDGER END -->
