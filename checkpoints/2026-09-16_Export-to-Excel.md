# Export to Excel/CSV — 2026-09-16 (FEATURE)

## درخواست
سه گزارش کلیدی برای ادمین به‌صورت **CSV سازگار با Excel** با پشتیبانی کامل فارسی،
بدون هیچ تغییری در `finance.py` / `timeline.py` / `audit.py` / `dunning.py` / `dashboard.py`،
به‌صورت **استریم** (10k+ ردیف) و **فقط-ادمین**.

## قیود رعایت‌شده
- جداسازی کامل: تنها فایل جدید سرور `routers/exports.py` است (هیچ منطقی به روترهای موجود اضافه نشد).
- ۵ فایل ممنوعه **بایت‌به‌بایت** دست‌نخورده: مقایسه‌ی sha256 با نسخه‌ی HEAD در بخش Verification.
- مسیرها بدون prefix در `main.py` (خود روتر `/exports/...` دارد) → مسیر کامل اپ هم `exports/debtors` می‌شود.

## سرور — `routers/exports.py` (جدید، ۲۴۹ خط)

سه اندپوینت، همه با `Depends(check_admin_access)` (≠ `admin_or_secretary` که debtors_list قدیمی دارد — اینجا فقط ادمین):

| مسیر | منبع داده | ستون‌ها (سرستون فارسی داخل فایل) |
|---|---|---|
| `GET /exports/debtors` | کپی منطق کوئری `finance.get_debtors_list:2299` (بدون فراخوانی اندپوینت) | شناسه، نام دانش‌آموز، کد ملی، موبایل ولی، بدهی معلم، بدهی آموزشگاه، بدهی کل، کلاس‌های فعال |
| `GET /exports/overdue_installments` | `Installment` با `is_paid==False and is_deleted==False and due_date < today_jalali` | شناسه قسط، نام دانش‌آموز، موبایل ولی، عنوان کلاس، مبلغ، سررسید، روزهای تأخیر، وضعیت |
| `GET /exports/audit_alerts` | فراخوانی مستقیم `get_suspicious_patterns(db)` از `routers/audit.py` | نوع، شدت، عنوان، توضیحات، شناسه موجودیت، نام موجودیت، زمان تشخیص |

### هلپرهای CSV
```python
def _csv_stream(header, rows):      # yield '\ufeff' → csv.writer(io.StringIO) با truncate/seek بعد از هر ردیف
def _safe_cell(value):              # مهار CSV/formula injection: '= + - @' ابتدای سلول متنی → quote با '
def _csv_response(filename, ...):   # StreamingResponse + media_type='text/csv; charset=utf-8'
                                    # + Content-Disposition: attachment; filename=debtors.csv
```
- `_iter_debtor_rows`: wallet منفی → `debt_teacher`/`debt_institute`، `total_debt = calculate_student_debt`،
  skip `total_debt <= 0`، فیلتر شعبه با lazy import `from routers.finance import get_user_branch_filter` (فایل finance دست نمی‌خورد).
- `_iter_overdue_rows`: fast-path SQL (`due_date < today_jalali OR NOT like("14__/__/__")`) سپس re-check پایتون با
  `parse_project_date` (ردیف‌های میلادی legacy/نامعتبر)، `days_overdue = (today - due).days`،
  وضعیت «بحرانی» برای ≥۷ روز و «معوق» برای بقیه (هم‌راستا با باکت‌بندی Dunning)، `yield_per(500)` + `joinedload(enrollment.student/course)`.
- `main.py`: `exports` به import روت‌ها + `app.include_router(exports.router)` (بدون prefix).

## اندروید (بدون کامپایل — فقط بررسی استاتیک)

| فایل | تغییر |
|---|---|
| `ApiInterfaces.kt` | `interface ExportApi` با ۳ متد `@Streaming @GET suspend fun ...(): Response<ResponseBody>` + importهای `retrofit2.Response`/`retrofit2.http.Streaming`/`okhttp3.ResponseBody` |
| `AdminDashboardActivity.kt` | `exportApi`، ۳ دکمه، `downloadExport(fileName, fetch: suspend () -> Response<ResponseBody>)` + `exportErrorMessage(code)` + `openSavedExport()` + `setExportButtonsEnabled()` + فلگ `isExporting` (ضد دابل‌کلیک) |
| `res/layout/activity_admin_dashboard.xml` | کارت «خروجی اکسل گزارش‌ها» با ۳ `MaterialButton` (`btnExportDebtors`/`btnExportOverdue`/`btnExportAlerts`) |
| `res/values/strings.xml` | ۱۳ رشته‌ی جدید `export_*` (عنوان کارت، برچسب دکمه‌ها، شروع، ذخیره‌شده، خطا، 403/401، open-failed، share-title، server-code) |

### انحراف آگاهانه از اسپک (مستند)
اسپک «ذخیره در **Downloads عمومی** + `ACTION_VIEW`» گفته بود؛ پیاده‌سازی روی **`getExternalFilesDir(null)` + FileProvider**
(مانند `ReportExporter` موجود) انجام شد، به سه دلیل:
1. `targetSdk=34` ⇒ Scoped Storage: `WRITE_EXTERNAL_STORAGE` روی API 29+ بی‌اثر است و نوشتن مستقیم در Downloads عمومی شکست می‌خورد.
2. `provider_paths.xml` فعلاً فقط `<external-files-path path=".">` را پوشش می‌دهد ⇒ Uri عمومی از FileProvider قابل ساخت نیست.
3. `Uri.fromFile` روی API 24+ استثنای `FileUriExposedException` می‌دهد.
⇒ در نتیجه **نیازی به مجوز رانتایم نیست** (مجوزهای READ/WRITE_EXTERNAL در مانیفست از قبل هستند و دست‌نخورده ماندند)؛
فایل ذخیره می‌شود و با یک تپ در Excel/Sheets باز یا از طریق chooser اشتراک‌گذاری می‌شود
(`FileProvider.getUriForFile(this, "$packageName.provider", file)`).
- خطاها: چون امضا `Response<ResponseBody>` است، کد وضعیت بدون استثنا در دسترس است →
  `if (!response.isSuccessful || body == null)` → `exportErrorMessage(code)`: 403 «فقط مدیر سیستم»، 401 «نشست منقضی»، سایر «خطای سرور N»
  (شاخه‌ی `HttpException` هم برای سایر لایه‌ها نگه داشته شد؛ خطای شبکه/IO → پیام اریجینال).
- استریم تدریجی بافر ۴KB با `coroutineContext.ensureActive()` (لغوپذیری در سفر به بک‌گراند).

## تست — `test_exports.py` (جدید، ۳۲۸ خط، ۱۲ تست)
`TestExportsCSV` (۱۰) + `TestExportSessionLifecycle` (۲): 401 بدون توکن، 403 برای secretary و teacher، 200 ادمین،
BOM (`EF BB BF`)، سرستون/مقادیر فارسی، حذف بدهی صفر، مهار injection، سناریوهای قسط
(پرداخت‌شده / آینده / حذف‌شده / سررسیدِ امروز / میلادی legacy / نامعتبر)، استریم ۳۰۰۳ ردیف < ۱۵s،
alerts خالی و شبانه، read-only (count و wallet قبل/بعد)، و assert نبود `db.commit/add/delete` در فایل روتر.

### 🔎 کشف مهم حین اجرا — وابستگی تست‌ها به cwd
- اجرا از **ریشه‌ی ریپو**: `PYTHONPATH=Kharazmi_Server python3 -m pytest Kharazmi_Server` → **305 passed / 0 failed**
- اجرا از **داخل `Kharazmi_Server/`**: ۴ تست قدیمی fail می‌شوند:
  `test_audit.py::test_joinedload_used_for_nplus1`، `test_audit.py::test_no_silent_except_pass`،
  `test_dashboard.py::test_dashboard_isolated_no_finance_touch`،
  `test_dashboard_performance.py::test_uses_count_queries_not_all`
  — چون این تست‌ها سورس را با مسیر نسبیِ **ریشه‌ی ریپو** (`"Kharazmi_Server/routers/..."`) باز می‌کنند. **قبلاً هم همین‌طور بوده** (ایراد جدید نیست).
- تست ایزولاسیون خودم هم در اولین اجرا همین اشکال را داشت؛ اصلاح شد به مسیر مستقل از cwd:
  `os.path.join(os.path.dirname(os.path.abspath(__file__)), "routers", "exports.py")` → الان **۱۲/۱۲ در هر دو cwd**.
- **روش کانونیکال اجرای سوئیت کامل: از ریشه‌ی ریپو با `PYTHONPATH=Kharazmi_Server`.**

## Verification (همه واقعی، روی کپی — نه DB پروداکشن)
```
1) ast.parse(exports.py, main.py, test_exports.py)                     → OK
2) test_exports.py از داخل Kharazmi_Server                             → 12 passed
   test_exports.py از ریشه‌ی ریپو (PYTHONPATH)                          → 12 passed
   سوئیت کامل از ریشه‌ی ریپو                                            → 305 passed, 0 failed
3) ۵ فایل ممنوعه — sha256(current) vs sha256(HEAD):
   finance   fca8c7aff403   UNCHANGED
   timeline  522d13836645   UNCHANGED
   audit     2fd9b13a5c4d   UNCHANGED
   dunning   a17b5d579dd7   UNCHANGED
   dashboard 3e338f15b5b6   UNCHANGED
4) DB پروداکشن: sha256 = f0e55fe7c5130ec17e39e73036e2291794c3c335f67d852c37599a6c0f99ec79 (بدون تغییر)
5) نمونه‌ی زنده (کپی /tmp/export_samples.db + uvicorn :8021 + توکن ادمین):
   /tmp/debtors.csv  → BOM ✓، ۸ ستون، «1,الارا صیامی,0001000012,,50000,0,50000,ریاضی کنکور»
   /tmp/overdue.csv  → BOM ✓، ۸ ستون، «2,…,750000,1405/06/10,15,بحرانی» و «1,…,500000,1405/06/21,4,معوق»
   /tmp/alerts.csv   → BOM ✓، ۷ ستون، هشدار suspicious_attendance/high (جلسه 02:30)
   بدون توکن → 401
6) اندروید — بررسی استاتیک: امضای `Response<ResponseBody>` در ۳/۳ متد ExportApi و در `downloadExport`؛
   هیچ import بی‌استفاده/گمشده‌ای نیست (بررسی خودکار)؛ XML هر ۳ فایل parse شد؛ همه‌ی ۱۳ رشته‌ی `export_*` (۸ در کد + ۵ در layout) تعریف شده؛
   هر ۳ `btnExport*` در layout موجود؛ همه‌ی ۳۳ `R.id` و ۲۰ `R.string` ارجاع‌شده تعریف دارند؛
   تمام `@style`/`@color`/`@drawable` کارت جدید resolve شدند (باگ `@color/gold_text_secondary`ِ ناموجود
   با `@color/gold_primary_light` جایگزین شد)؛ brace-balance دو فایل Kotlin OK.
```

## فایل‌های تغییر‌یافته
```
M  KharazmiAdmin/.../AdminDashboardActivity.kt
M  KharazmiAdmin/.../ApiInterfaces.kt
M  KharazmiAdmin/app/src/main/res/layout/activity_admin_dashboard.xml
M  KharazmiAdmin/app/src/main/res/values/strings.xml
M  Kharazmi_Server/main.py                    (۲ خط: import + include_router)
?? Kharazmi_Server/routers/exports.py
?? Kharazmi_Server/test_exports.py
```

## نکته‌ی محیطی
بدون `Kharazmi_Server/.env` (شامل `JWT_SECRET_KEY`) هیچ `import main`/pytest اجرا نمی‌شود
(`dependencies.py:20` → `RuntimeError`). فایل `.env` ساخته شد و gitignore است.
