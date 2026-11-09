# فاز A — فهرست routeهای سرور

## روش و دامنه

- نقطهٔ ثبت routeها `Kharazmi_Server/main.py:692-715` است؛ routerهای `routers/*.py` در این بازه با `app.include_router` ثبت می‌شوند.
- route مستقیم فایل عکس در `Kharazmi_Server/main.py:94` ثبت شده است.
- CSV دستی/قابل جست‌وجو: [`server-routes.csv`](server-routes.csv)
- خروجی خام استخراج‌شده از runtime/OpenAPI: [`server-routes-extracted.csv`](server-routes-extracted.csv)
- extractor: [`Kharazmi_Server/scripts/extract_server_routes.py`](../../Kharazmi_Server/scripts/extract_server_routes.py)

اجرای بازتولیدپذیر باید با copy دیتابیس انجام شود؛ import `main` در startup، `models.Base.metadata.create_all` و patchهای idempotent را اجرا می‌کند (`Kharazmi_Server/main.py:111-146` و ادامهٔ تابع `auto_patch_database`). نمونهٔ اجرا در docstring خود اسکریپت آمده است.

## اعداد

| مورد | مقدار | مرجع |
|---|---:|---|
| routeهای ثبت‌شده در OpenAPI/runtime | 221 | خروجی `server-routes-extracted.csv`؛ extractor: `extract_server_routes.py:134-190` |
| GET | 109 | شمارش ستون `method` در CSV |
| POST | 87 | شمارش ستون `method` در CSV |
| PUT | 14 | شمارش ستون `method` در CSV |
| DELETE | 11 | شمارش ستون `method` در CSV |

## معنای ستون‌های CSV

- `method`, `path کامل`, `handler`, `file:line`: از `app.routes`/`app.openapi()` و `inspect` گرفته شده‌اند.
- `input`: پارامترهای `path/query/header/body` و نام schema که OpenAPI برای operation ثبت کرده است.
- `response keys/schema`: نام response schema از OpenAPI و کلیدهای literal موجود در `return {…}` handler؛ اگر handler response model یا dict literal قابل استخراج نداشته باشد، `نامشخص` نگه داشته شده است.
- `DB tables read (static)`, `DB tables/columns written (static)`, `columns referenced`, `side effects`: خروجی scan محدود AST روی منبع handler است، نه حدس runtime. `نامشخص` یعنی از خود handler قابل اثبات literal نبوده است؛ برای جست‌وجوی دستی، `file:line` مرجع اصلی است.
- این فاز عمداً هیچ route یا منطق سرور را تغییر نداده است.

## جدول prefix

| ثبت در app | prefix صریح |
|---|---|
| `auth.router`, `students.router`, `admin.router`, `teachers.router`, `classes.router`, `finance.router`, `reports.router`, `attendance.router`, `parent.router`, `homework.router`, `calendar.router`, `messages.router`, `exams.router`, `crm.router`, `branches.router`, `automation.router`, `analytics.router`, `ai.router`, `timeline.router`, `dunning.router`, `exports.router`, `audit_trail.router` | بدون prefix اضافه در `main.py:692-709,711-715`؛ prefix داخل decorator/روتر ثبت شده و در path کامل CSV منعکس است |
| `audit.router` | `/audit` در `main.py:710` |
| `dashboard.router` | `/dashboard` در `main.py:713` |

## نکتهٔ نامشخص

- برای responseهایی که handler آن‌ها از helper/import خارجی یا `response_model` غیر-inline استفاده می‌کند، استخراج خودکار همهٔ کلیدهای تو در تو را اثبات نمی‌کند؛ CSV آن را با `نامشخص` علامت می‌زند و schema/handler/file:line را نگه می‌دارد. این مورد در فاز D به‌عنوان mismatch تلقی نشده مگر اینکه مقایسهٔ Kotlin و کد handler اختلاف مشخص نشان دهد.
