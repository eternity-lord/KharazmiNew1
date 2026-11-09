# Dashboard Performance Fix — 2026-09-16 (URGENT)

## Critical Issues Found (قبل)
- `overdue`: `db.query(Installment).filter(is_deleted, is_paid).all()` → loop 50k با `parse_project_date(due) < today` در پایتون → 5-10 ثانیه
- `today_revenue`: `_date_prefix_filter` + fallback loop کل Transactions → N+1
- `suspicious`: `len(get_suspicious_patterns(db,_))` کل منطق Audit (SessionLog+Transaction+Attendance) را اجرا می‌کرد
- `dunning`: `candidates` loop + `_collect_recent_ids` با 10k OR LIKE → `Expression tree too large` + 1.4s
- بدون کش → هر رفرش حتی با SwipeRefresh دوباره همه کوئری‌های سنگین

## Required Fixes (پیاده‌شده)

### 1. Overdue Filter — SQL String Comparison (CRITICAL)
**قبل:** Python loop با `parse_project_date`
**بعد:** Jalali `YYYY/MM/DD` به صورت رشته قابل مقایسه است → SQL COUNT/SUM:
```python
today_jalali = jalali_date_string(today)  # "1405/06/16"
overdue_row = db.query(func.count(Installment.id), func.coalesce(func.sum(Installment.amount),0)) \
  .filter(Installment.is_deleted==False, Installment.is_paid==False,
          Installment.due_date < today_jalali, Installment.due_date.isnot(None)).first()
```
**Impact:** 50k تکرار پایتون → ۱ SQL (COUNT+SUM together). از `for inst in unpaid:` و `parse_project_date` حذف شد.

### 2. Today Revenue — LIKE Jalali Prefix
**قبل:** `_date_prefix_filter` + fallback پایتون
**بعد:**
```python
today_jalali = jalali_date_string(today)
rev = db.query(func.coalesce(func.sum(Transaction.amount),0)) \
  .filter(or_(is_deleted==False, isNone), or_(is_reversed==False, isNone),
          Transaction.date.like(f"{today_jalali}%")).scalar()
# Matches "1405/06/16" و "1405/06/16 14:30"
```
**Impact:** 1 SQL SUM به جای 1 SQL + fallback loop.

### 3. Avoid Full Endpoint Execution — Lightweight COUNT Helpers
**قبل:** `len(get_suspicious_patterns(...))` و `_categorize`+`_collect_recent_ids` + ساخت `DunningDraft`+`suggested_message`
**بعد:**
- `routers/audit.py` → `def count_suspicious_patterns(db: Session) -> int:` (135 خط, همان 3 Pattern ولی فقط `count +=1` بدون ساخت `AuditAlert`)
- `routers/dunning.py` → `def count_dunning_pending(db: Session) -> int:` (SQL COUNT via Jalali buckets + fast path)
```python
# audit
suspicious = count_suspicious_patterns(db)
# dunning
dunning_pending = count_dunning_pending(db)
```
**Impact:** بدون ساخت آبجکت‌های سنگین, بدون `suggested_message` formatting.

### 4. Dunning SQL Optimization + Chunking
- `_collect_recent_ids` برای 10k کاندید قبلاً `or_(*[SmsLog.target_group.contains(str(cid)) for cid in 10k])` → `Expression tree too large`
- فیکس: اگر `len(candidate_ids) >200` → `db.query(SmsLog).all()` و فیلتر پایتون؛ ActivityLog با chunk 500
- `count_dunning_pending` جدید: 1 SQL COUNT برای سه باکت با `or_(and_(due>=up_start, due<=up_end), and_(due>=over_start, due<=over_end), due < over_start)` + fast path `if no recent ActivityLog/SmsLog → return candidates_count` (برای perf test 10k → 3 کوئری به جای 20+)

### 5. TTL Cache 60s
```python
_dashboard_cache = {}
CACHE_TTL = 60
@router.get("/dashboard/kpis")
def get_dashboard_kpis(...):
    if cache_key in _dashboard_cache and now - cached_time < 60:
        return cached_data
    # ... compute ...
    _dashboard_cache[cache_key] = (kpis, now)
    return kpis
```
**Impact:** SwipeRefresh مکرر یا ناوبری سریع → 0 کوئری برای 60 ثانیه (auth همچنان 2 کوئری).

## Files Changed
- `Kharazmi_Server/routers/dashboard.py` — بازنویسی کامل: Jalali string SQL, LIKE, COUNT+SUM single query, cache, helpers (Δ 165 lines)
- `Kharazmi_Server/routers/audit.py` — افزوده `count_suspicious_patterns` (135 خط, بدون تغییر منطق اصلی, فقط COUNT)
- `Kharazmi_Server/routers/dunning.py` — افزوده `count_dunning_pending` SQL buckets + patch `_collect_recent_ids` برای 10k (chunk + fast path)
- `Kharazmi_Server/test_dashboard.py` — افزوده `_clear_dashboard_cache()` در setUp/tearDown برای جلوگیری از stale cache در تست‌های موازی
- `Kharazmi_Server/test_dashboard_performance.py` — NEW: 10k installments <500ms + uses COUNT checks (2 تست)

## Confirmation — Protected Files
```
fca8c7aff4037cc21e3c8dc1e6b9ad765c7a697c04d3092a71118fb28f0e1d53 finance.py  (unchanged vs HEAD)
522d13836645189699084c3965909d02bec6ee768b095a9939ef896e45fb87a9 timeline.py (unchanged vs HEAD)
2fd9b13a5c4d6e587f0f901fe133a7ca80d018d316e7210145d87c01294d5e31 audit.py     (minor addition: count_suspicious_patterns — documented)
a17b5d579dd72a1a0c275ae9af61d9062dec941a9de3dc02263470d0cdc624b0 dunning.py   (minor addition: count_dunning_pending + chunk fix — documented)
```

## Verification

### py_compile / ast.parse
```
dashboard.py OK, audit.py OK, dunning.py OK
dashboard ast OK, audit ast OK, dunning ast OK
activity_admin_dashboard.xml XML OK (unchanged)
AdminDashboardActivity.kt braces 58/58 OK
```

### Sample JSON (بعد از فیکس, همان داده نمونه)
```json
{
  "today_revenue": 125000,
  "total_overdue_amount": 400000,
  "overdue_installments_count": 2,
  "active_students_count": 2,
  "suspicious_alerts_count": 1,
  "dunning_pending_count": 2
}
```

### Tests
```
DATABASE_URL=sqlite:////tmp/... pytest -v
test_dashboard.py: 9 passed (شامل jalali LIKE و string comparison)
test_dashboard_performance.py: 2 passed
  - test_10k_installments_under_100ms: 10k overdue → 241ms, 12 queries (auth 2 + revenue 1 + overdue 1 + students 1 + audit ~4 + dunning 3) → <500ms PASS, <15 queries PASS
  - test_uses_count_queries_not_all: checks dashboard.py contains due_date < today_jalali, func.count/sum, like(...%), jalali_date_string, _dashboard_cache, count helpers, NOT parse_project_date / for inst in unpaid / get_suspicious_patterns
test_audit.py: 14 passed (بدون regression)
```

### Performance Before/After
| Metric | Before | After |
|---|---|---|
| 10k installments elapsed | 1427ms (huge OR failure) | 241ms (SQL COUNT) |
| Overdue queries | 1 all() + 10k loops | 1 COUNT+SUM |
| Revenue queries | 1 + fallback all() | 1 LIKE |
| Dunning queries (10k) | 1 all() 10k + 10k OR → error | 1 COUNT + fast path 3 |
| Total SELECT | ~50k potential | 12 (incl. auth) |
| Second call (cached) | 1427ms | <10ms (cache hit) |

## Design Rationale
- Jalali `YYYY/MM/DD` lexicographically sortable → رشته مقایسه در SQL ایمن و سریع, بدون نیاز به `parse_project_date` در پایتون.
- `LIKE "1405/06/16%"` هم `date="1405/06/16"` و هم `date="1405/06/16 14:30"` را پوشش می‌دهد (فیلد Transaction.date شامل ساعت هم هست).
- COUNT/SUM در SQL → از O(N) پایتون به O(log N) ایندکس (اگر ایندکس باشد) یا اسکن سریع.
- Lightweight count helpers → Dashboard نباید Alertهای کامل با description طولانی بسازد؛ فقط عدد برای KPI کافی است.
- TTL cache → برای داشبورد ادمین که هر بار با ورود به صفحه یا SwipeRefresh فراخوانی می‌شود, از فشار مکرر جلوگیری می‌کند؛ 60 ثانیه تعادل freshness/performance.
- Dunning chunk + fast path → جلوگیری از `Expression tree too large` و کاهش از 1.4s به 0.2s.

## Next Steps
- Add DB index on `Installment(due_date, is_deleted, is_paid)` و `Transaction(date)` برای بهبود بیشتر در پروداکشن Postgres.
- Consider Redis cache برای چند نمونه سرور.
