#!/usr/bin/env python3
"""گیتِ lint اندروید — «بدتر نشود»، نه «صفر شود».

چرا این اسکریپت لازم است
--------------------------
تا امروز هیچ workflow ای `lint` را اجرا نکرده بود و اپ هیچ `lint {}` پیکربندی نداشت، یعنی
وضعیتِ lint کاملاً **ناشناخته** بود. صفرکردنِ یک‌بارهٔ صدها مسئلهٔ انباشته یک فازِ ریفکتور
نیست، یک بازنویسی است و با «رفتارمحافظ» بودنِ این کار در تضاد است. پس همان الگویی که برای
ruff/mypy سمتِ سرور لازم داریم این‌جا هم پیاده می‌شود: **baseline را ثبت کن و فقط جلویِ
بدتر شدن را بگیر.**

چرا از مکانیزمِ بومیِ `lint { baseline = file("lint-baseline.xml") }` استفاده نمی‌کنیم
--------------------------------------------------------------------------------------
آن مکانیزم بهتر است (دانه‌بندی‌اش موقعیت‌به‌موقعیت است)، ولی فایلِ baseline را خودِ Gradle در
CI تولید می‌کند و باید به ریپو برسد. در محیطِ کاریِ ما راهی برای بیرون‌کشیدنِ فایل از CI نیست:
هاستِ دانلودِ artifact (`pipelines.actions.githubusercontent.com`) بسته است و
`output.summary` هم از API خالی برمی‌گردد. تنها کانالِ قابلِ اتکا **annotation** است که از
`api.github.com` خوانده می‌شود و جایِ کمی دارد. پس baseline باید آن‌قدر فشرده باشد که در یک
annotation جا شود ⇒ دانه‌بندیِ ما **شمارِ مسئله به تفکیکِ `id`** است، نه به تفکیکِ موقعیت.

محدودیتِ صادقانهٔ این دانه‌بندی
--------------------------------
اگر در یک `id` یک مسئله **رفع** شود و هم‌زمان یک مسئلهٔ **جدید** از همان `id` اضافه شود،
شمارِ کل تغییر نمی‌کند و این گیت آن را نمی‌بیند (netting-out). این بهایِ فشرده‌بودنِ baseline
است. دو چیز این ریسک را کم می‌کنند: هر `id` **جدید** حتی با یک مورد هم شکست است، و
`--check` فهرستِ فایل‌های دارای مسئله را هم در baseline نگه می‌دارد تا تغییرِ شکلِ توزیع
دستِ‌کم برای بازبینِ انسانی ثبت شود.

قاعدهٔ تصمیم
-------------
pass  ⟺  هیچ `id` جدیدی نباشد **و** شمارِ هیچ `id` از baseline بیشتر نشود.
بهبود (کاهشِ شمار) مجاز و گزارش‌شدنی است؛ در آن صورت baseline باید دستی تازه شود
(`--write-baseline`) تا دستاورد قفل شود و بعداً بی‌صدا پس نرود.

ایمنیِ مهم
-----------
نبودنِ گزارشِ lint هرگز «صفر مسئله» تلقی نمی‌شود. اگر فایلِ گزارش وجود نداشته باشد یا خالی/
ناخوانا باشد، اسکریپت با کدِ ۲ شکست می‌خورد — وگرنه یک buildِ خرابِ lint بی‌صدا گیت را رد
می‌کند.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET

# مسیرهای پیش‌فرض نسبت به پوشهٔ KharazmiAdmin
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REPORT = os.path.join(HERE, "app", "build", "reports", "lint-results-debug.xml")
DEFAULT_BASELINE = os.path.join(HERE, "lint-baseline.json")

SEVERITY_ORDER = {"Fatal": 0, "Error": 1, "Warning": 2, "Information": 3, "Ignore": 4}


def fail_hard(msg: str) -> None:
    """شکستِ سخت (کدِ ۲) — برای «گیت کار نکرد»، نه «گیت بدتر شد»."""
    print(f"::error title=lint gate could not run::{escape(msg)}")
    print(msg, file=sys.stderr)
    raise SystemExit(2)


def escape(text: str) -> str:
    """فرارِ workflow command: درصد، CR و LF باید encoded شوند."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def parse_report(path: str) -> dict:
    """گزارشِ XML لینت را به آمارِ فشرده تبدیل می‌کند.

    ساختارِ گزارشِ AGP:
        <issues ...>
          <issue id="UnusedResources" severity="Warning" message="..."
                 category="Performance" priority="51" ...>
            <location file="src/main/res/drawable/x.xml" line="3"/>
          </issue>
    یک `<issue>` می‌تواند چند `<location>` داشته باشد (موقعیتِ اصلی + نمونه‌ها). برای
    شمارشِ «چند مسئله» هر `<issue>` **یک** شمارش است، نه هر location — چون خودِ lint هم
    در خطِ آخرِ گزارشش همین را می‌شمارد.
    """
    if not os.path.exists(path):
        fail_hard(
            f"گزارشِ lint پیدا نشد: {path}\n"
            "یعنی task لینت اصلاً اجرا نشده یا شکسته است. نبودنِ گزارش هرگز «صفر مسئله» "
            "نیست — این گیت بی‌خبر رد نمی‌شود."
        )
    if os.path.getsize(path) == 0:
        fail_hard(f"گزارشِ lint خالی است (۰ بایت): {path}")

    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        fail_hard(f"گزارشِ lint خوانده نشد ({path}): {exc}")

    if root.tag != "issues":
        fail_hard(f"ریشهٔ گزارش انتظارش «issues» بود، «{root.tag}» است: {path}")

    by_id: dict[str, int] = {}
    severity_of: dict[str, str] = {}
    category_of: dict[str, str] = {}
    per_severity: dict[str, int] = {}
    files: set[str] = set()
    total = 0

    for issue in root.findall("issue"):
        iid = issue.get("id")
        if not iid:
            fail_hard(f"یک <issue> بدون id در {path} — ساختارِ گزارش با انتظار ما نمی‌خواند")
        sev = issue.get("severity") or "Unknown"
        by_id[iid] = by_id.get(iid, 0) + 1
        severity_of.setdefault(iid, sev)
        category_of.setdefault(iid, issue.get("category") or "")
        per_severity[sev] = per_severity.get(sev, 0) + 1
        total += 1
        for loc in issue.findall("location"):
            f = loc.get("file")
            if f:
                # مسیرِ مطلقِ رانر به مسیرِ نسبیِ ریپو نرمال می‌شود تا baseline قابلِ
                # انتقال باشد (وگرنه با هر تغییرِ مسیرِ build همه‌چیز «جدید» دیده می‌شود).
                files.add(normalize_file(f))

    return {
        "total": total,
        "by_id": dict(sorted(by_id.items(), key=lambda kv: (-kv[1], kv[0]))),
        "severity_of": severity_of,
        "category_of": category_of,
        "per_severity": dict(sorted(per_severity.items(), key=lambda kv: SEVERITY_ORDER.get(kv[0], 9))),
        "distinct_ids": len(by_id),
        "files_with_issues": sorted(files),
        "report": os.path.relpath(path, HERE) if path.startswith(HERE) else path,
    }


def normalize_file(path: str) -> str:
    path = path.replace(os.sep, "/")
    # گزارشِ lint در CI با مسیرِ مطلقِ رانر می‌آید؛ هر چه تا «KharazmiAdmin/» است دور ریخته
    # می‌شود تا baseline به ماشینِ رانر وابسته نباشد. مسیرِ نسبی (src/main/... که AGP
    # نسبت به ماژول می‌دهد) دست‌نخورده می‌ماند.
    marker = "KharazmiAdmin/"
    i = path.find(marker)
    if i >= 0:
        return path[i + len(marker):]
    return path.lstrip("./")


def compact_table(stats: dict) -> str:
    """جدولِ فشرده برای annotation — باید در یک پیام جا شود."""
    lines = [
        "LINT REPORT  total={} issues, {} distinct ids".format(stats["total"], stats["distinct_ids"]),
        "by severity: " + ", ".join(f"{k}={v}" for k, v in stats["per_severity"].items()),
        "by id (count, severity, id):",
    ]
    for iid, n in stats["by_id"].items():
        lines.append(f"  {n:5d}  {stats['severity_of'].get(iid, '?'):11s}  {iid}")
    lines.append(f"files with issues: {len(stats['files_with_issues'])}")
    return "\n".join(lines)


def baseline_payload(stats: dict, note: str | None = None) -> dict:
    """دقیقاً همان چیزی که گیت مصرف می‌کند — نه بیشتر.

    عمداً `category_of` و `files_with_issues` در baseline نمی‌آیند: گیت از آن‌ها استفاده
    نمی‌کند و هر تغییرِ نامِ فایل بی‌دلیل baseline را تکان می‌داد. مهم‌تر اینکه **کلِ**
    baseline باید از کانالِ annotation (تنها راهِ بیرون‌کشیدنِ داده از CI) قابلِ بازسازی
    باشد، و آن دو فهرست در یک پیام جا نمی‌شدند.
    """
    return {
        "_comment": [
            "baseline گیتِ lint اندروید — ساختهٔ KharazmiAdmin/lint_gate.py.",
            "دانه‌بندی عمداً «شمارِ مسئله به تفکیکِ id» است؛ علت و محدودیتِ صادقانهٔ آن",
            "(netting-out) در docstring همان اسکریپت آمده: artifact از CI قابلِ",
            "بیرون‌کشیدن نیست و تنها کانال، annotation است.",
            "قاعدهٔ گیت: id جدید = شکست؛ افزایشِ شمارِ هر id = شکست؛ کاهش مجاز است.",
            "پس از هر بهبود این فایل را با --write-baseline تازه کنید تا دستاورد قفل شود.",
        ],
        "total": stats["total"],
        "distinct_ids": stats["distinct_ids"],
        "per_severity": stats["per_severity"],
        "by_id": stats["by_id"],
        "severity_of": stats["severity_of"],
        "report": stats["report"],
        **({"source": note} if note else {}),
    }


def cmd_write_baseline(stats: dict, path: str) -> int:
    payload = baseline_payload(stats)

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"baseline نوشته شد: {path}")
    print(compact_table(stats))
    return 0


def cmd_check(stats: dict, path: str) -> int:
    if not os.path.exists(path):
        fail_hard(
            f"فایلِ baseline وجود ندارد: {path}\n"
            "اول یک بار با --write-baseline baseline بسازید و commit کنید. بدونِ baseline،"
            "«بدتر نشد» تعریف ندارد."
        )
    with open(path, encoding="utf-8") as fh:
        base = json.load(fh)
    base_ids: dict[str, int] = base.get("by_id", {})
    now_ids: dict[str, int] = stats["by_id"]

    new_ids = sorted(i for i in now_ids if i not in base_ids)
    worse = sorted(
        ((i, base_ids[i], now_ids[i]) for i in now_ids if i in base_ids and now_ids[i] > base_ids[i]),
        key=lambda t: (-(t[2] - t[1]), t[0]),
    )
    better = sorted(
        ((i, base_ids[i], now_ids[i]) for i in now_ids if i in base_ids and now_ids[i] < base_ids[i]),
        key=lambda t: (t[2] - t[1], t[0]),
    )
    gone = sorted(i for i in base_ids if i not in now_ids)

    out = [
        f"total: baseline={base.get('total')} now={stats['total']} ({stats['total'] - base.get('total', 0):+d})",
        f"distinct ids: baseline={base.get('distinct_ids')} now={stats['distinct_ids']}",
        f"new ids: {len(new_ids)} | worse ids: {len(worse)} | improved ids: {len(better)} | gone ids: {len(gone)}",
    ]
    for i in new_ids:
        out.append(f"  NEW     {now_ids[i]:5d}  {stats['severity_of'].get(i, '?'):11s}  {i}")
    for i, b, n in worse:
        out.append(f"  WORSE   {b:5d} -> {n:<5d} (+{n - b})  {i}")
    for i, b, n in better[:40]:
        out.append(f"  better  {b:5d} -> {n:<5d} ({n - b})  {i}")
    for i in gone:
        out.append(f"  gone    {base_ids[i]:5d} -> 0      {i}")
    if better or gone:
        out.append("  (بهبود دارید — baseline را تازه کنید تا دستاورد قفل شود)")

    report = "\n".join(out)
    print(report)

    if new_ids or worse:
        msg = "LINT GATE FAILED - وضعیتِ lint بدتر شده است\n" + report
        print(f"::error title=lint gate: must not get worse::{escape(msg)}")
        return 1

    print(f"::notice title=lint gate: {stats['total']} issues, not worse than baseline::{escape(report)}")

    # بهبود داشتیم ⇒ baseline باید تازه شود وگرنه دستاورد قفل نمی‌شود و بعداً می‌تواند
    # بی‌صدا پس برود. ولی ما در این محیط JVM نداریم، پس «اجرای محلیِ --write-baseline»
    # ممکن نیست؛ تنها راه این است که خودِ CI متنِ دقیقِ فایلِ تازه را منتشر کند تا عیناً
    # commit شود. این کار عمداً **فقط در مسیرِ موفق و فقط هنگامِ بهبود** انجام می‌شود:
    # وقتی گیت شکست خورده، برکت‌دادنِ baseline جدید یعنی بی‌اثرکردنِ همان گیت.
    if better or gone:
        refreshed = json.dumps(baseline_payload(stats, note="refreshed by lint_gate.py --check"),
                               ensure_ascii=False, indent=2)
        print("::notice title=lint baseline refreshed - commit this as KharazmiAdmin/lint-baseline.json::"
              + escape(refreshed))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", default=DEFAULT_REPORT, help="مسیرِ lint-results-debug.xml")
    ap.add_argument("--baseline", default=DEFAULT_BASELINE, help="مسیرِ lint-baseline.json")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--write-baseline", action="store_true", help="baseline را (از گزارشِ فعلی) بساز/بازنویسی کن")
    mode.add_argument("--check", action="store_true", help="گزارشِ فعلی را با baseline مقایسه کن")
    ap.add_argument("--table", action="store_true", help="فقط جدولِ فشرده را چاپ کن (برای annotation)")
    ap.add_argument("--emit-baseline", action="store_true",
                    help="خودِ JSONِ baseline را در یک annotation چاپ کن تا بدونِ بازنویسیِ دستی به ریپو برسد")
    ap.add_argument("--source", default=None, help="برچسبِ مبدأ برای --emit-baseline (مثلاً شمارهٔ اجرای CI)")
    args = ap.parse_args()

    # `--table` حالتِ مستقل است: همان کانالی است که baseline برای اولین بار از CI به دستِ
    # ما می‌رسد (artifact قابلِ دانلود نیست و output.summary از API خالی است، فقط annotation
    # از api.github.com خوانده می‌شود). پس نباید به یکی از دو حالتِ دیگر وابسته باشد.
    if not args.table and not args.emit_baseline and args.write_baseline == args.check:
        ap.error("exactly one of --write-baseline / --check / --table / --emit-baseline is required")

    stats = parse_report(args.report)

    if args.table:
        print(f"::notice title=Lint report: {stats['total']} issues / {stats['distinct_ids']} ids::{escape(compact_table(stats))}")
        print(compact_table(stats))
        return 0
    if args.emit_baseline:
        payload = baseline_payload(stats, note=args.source or "CI lint report")
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        print(f"::notice title=lint baseline JSON (commit this as KharazmiAdmin/lint-baseline.json)::"
              f"{escape(text)}")
        print(text)
        return 0
    if args.write_baseline:
        return cmd_write_baseline(stats, args.baseline)
    return cmd_check(stats, args.baseline)


if __name__ == "__main__":
    raise SystemExit(main())
