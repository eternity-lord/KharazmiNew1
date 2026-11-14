#!/usr/bin/env python3
"""گیتِ «بدتر-نشود» برایِ کیفیتِ کدِ پایتون — ruff و mypy در برابرِ baselineِ commit‌شده.

چرا این اسکریپت لازم است
--------------------------
تا امروز دو ابزارِ سنجشِ کد در این ریپو **نصب و اجرا می‌شدند ولی هیچ‌جا گیت نمی‌شدند**:
`Kharazmi_Server/requirements-dev.txt` نسخه‌های `ruff==0.17.4` و `mypy==2.4.1` را pin
کرده (دقیقاً به این دلیل که «قواعد lint باید بین توسعه‌دهنده و CI یکسان بماند»)، ولی
هیچ workflow ای آن‌ها را نصب نمی‌کرد و هیچ گیتی شمارِ خطاها را نمی‌خواند. نتیجه: عددِ
۲۵۰ خطایِ ruff و ۷۲۵ خطایِ mypy فقط در حافظهٔ دستیِ توسعه‌دهنده‌ها زنده بود و یک
commit می‌توانست بی‌صدا ۳۰ خطایِ تازه اضافه کند — همان کلاسی از پوسیدگی که
`lint_gate.py` (برایِ lint اندروید) و `kotlin_warning_gate.py` (برایِ warningهای
کامپایلرِ Kotlin) جلویش را گرفته‌اند.

صفرکردنِ ۲۵۰ + ۷۲۵ خطا ریفکتور نیست: بخشِ بزرگی از آن‌ها سلیقه‌ای‌اند
(`E701` چند دستور در یک خط، `C408` فراخوانیِ بی‌ضرورتِ dict/list، `B905` زیپ بدونِ
strict) و اصلاحِ یکجایشان بدونِ تستِ رفتار، خطرِ ساختنِ باگِ واقعی دارد. پس همان الگوی
دو گیتِ قبلی: **baseline را ثبت کن و فقط جلویِ بدتر شدن را بگیر.**

سه تفاوتِ ماهوی با `kotlin_warning_gate.py`
-------------------------------------------
۱) **ابزارها محلی در دسترس‌اند.** آن گیت به لاگِ Gradle نیاز داشت چون در محیطِ کاریِ ما
   JVM/Gradle نیست و baseline تنها از annotationِ CI به ریپو می‌رسید. اینجا ruff و mypy
   خالص‌پایتون‌اند، پس `--write-baseline` محلی معنادار است و CI نقشِ **راستی‌آزماییِ
   مستقل** را دارد (نه تنها کانالِ تولیدِ baseline). مسیرِ annotation برایِ روزی که
   شمارِ CI با محلی تفاوت کند همچنان باز است.

۲) **شناسه‌ها پایدارند، پس قالب‌سازیِ پیام لازم نیست.** خروجیِ کامپایلرِ Kotlin فقط متنِ
   پیام دارد و آن گیت مجبور بود از پیام «شناسه» بسازد (نام‌ها `'*'`، اعداد `N`، و برایِ
   قالب‌هایِ بلند پسوندِ `#sha1`). اینجا هر دو ابزار **خودشان** شناسه می‌دهند: ruff یک
   `code` (مثل `F841`) و mypy یک error-code (مثل `arg-type`). پس دانه‌بندیِ baseline
   «شمار به تفکیکِ شناسهٔ ابزار» است و هیچ نرمال‌سازیِ دست‌سازی در کار نیست — که هم
   ساده‌تر است و هم دقیق‌تر.

۳) **ورودی باید خودش را ثابت کند.** سه شاهدِ fail-loud:
   - **نسخهٔ ابزار** باید با نسخهٔ pin‌شده در baseline یکی باشد. ruff بین نسخه‌ها قواعد
     تازه اضافه می‌کند؛ اگر CI با ruffِ دیگری اجرا شود، صدها «خطایِ جدید» می‌بیند که
     باگ نیستند و گیت بی‌معنا می‌شود. اختلافِ نسخه ⇒ `exit 2` (وضعیتِ ناشناخته)، نه پاس
     و نه شکست.
   - **خطِ خلاصهٔ mypy** (`Found 725 errors in 44 files (checked 55 source files)`) با
     شمارِ پارس‌شده مقایسه می‌شود. اگر mypy نتواند فایلی را بخواند، خروجی‌اش **کوتاه**
     می‌شود و شمردنِ آن به‌معنایِ «بهبود» اشتباه است.
   - **`errors prevented further checking`** (یا هر exit code بزرگ‌تر از ۱) یعنی موجودی
     ناقص است ⇒ `exit 2`. این دقیقاً همان امضایی است که در محیطِ کاریِ ما وقتی لایهٔ
     فایل‌سیستم قطع‌و‌صل می‌شود دیده شد: mypy می‌گوید «Cannot read file» و یک شمارِ
     بی‌معنا می‌دهد. بدونِ این شاهد، آن وضعیت «بهبودِ بزرگ» خوانده می‌شد و baseline
     رویِ عددِ غلط قفل می‌شد.

قاعدهٔ کلیِ همهٔ گیت‌هایِ این ریپو اینجا هم برقرار است: **خواندنِ ناموفق هرگز «صفر خطا»
گزارش نمی‌شود.**

معنایِ مقایسه (مثلِ دو گیتِ دیگر)
----------------------------------
شکست (`exit 1`) فقط در سه حالت: شناسهٔ **تازه**، شناسهٔ **رشدکرده**، یا **افزایشِ
جمع**. بهبود (`delta -N`) شکست نیست — ولی بی‌اثر هم نمی‌ماند: خودِ گیت JSONِ آمادهٔ
commit را در یک `notice` منتشر می‌کند تا بهبود **قفل** شود. بدونِ این قفل، حذفِ یک خطا
هیچ اثرِ پایداری ندارد و بازگشتش بی‌صدا می‌ماند (درسِ عملیِ PR #27).

محدودیتِ صادقانهٔ این دانه‌بندی
--------------------------------
**netting-out**: اگر یک خطا از شناسهٔ `F841` رفع شود و هم‌زمان یک `F841` تازه اضافه
شود، هم `by_code` و هم `total` بی‌تغییر می‌مانند و گیت ساکت است. راهِ رفعش مقایسهٔ
موقعیت‌به‌موقعیت است که baseline را از چند ده شناسه به چند هزار موقعیت منفجر می‌کند و
از کانالِ ۴KBِ annotation بیرون نمی‌رود. همان مصالحهٔ دو گیتِ دیگر، با همان دلیل.

خروجی‌ها: `0` پاس · `1` گیت شکست خورد · `2` ورودی در دسترس/قابلِ اعتماد نیست.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE = str(ROOT / "scripts" / "python-quality-baseline.json")
BASELINE_REL = "scripts/python-quality-baseline.json"

# سقف‌های کانالِ annotation: GitHub متن را در ۴۰۹۶ بایت می‌بُرد، پس قطعه‌ها زیرِ آن
# نگه داشته می‌شوند و `(part i/n)` در **عنوان** می‌آید نه در پیام (پیام نباید LF خام
# داشته باشد). همان عددِ اندازه‌گیری‌شده در دو گیتِ دیگر.
MAX_ANNOTATION = 3900
MAX_PARTS = 8

RUFF_TARGET = "."
MYPY_SUMMARY_RE = re.compile(
    r"^Found (?P<errors>\d+) errors? in (?P<files>\d+) files? \(checked (?P<checked>\d+) source files?\)")
MYPY_SUCCESS_RE = re.compile(r"^Success: no issues found in (?P<checked>\d+) source files?")
MYPY_LINE_RE = re.compile(
    r"^(?P<path>[^:]+):(?P<line>\d+):(?:(?P<col>\d+):)?\s+"
    r"(?P<sev>error|warning|note):\s+(?P<msg>.*?)(?:\s+\[(?P<code>[a-z0-9-]+)\])?$")
# اگر mypy نتواند فایلی را بخواند، موجودی ناقص است و شمردنش «بهبود» می‌شود.
MYPY_PARTIAL_MARKERS = ("errors prevented further checking", "Cannot read file")
TOP_FILES_LIMIT = 10
NO_CODE = "<no-code>"


class ToolUnavailable(RuntimeError):
    """ابزار نیست، یا خروجی‌اش قابلِ اعتماد نیست. هرگز «صفر خطا» نیست."""


class ToolRun:
    """نتیجهٔ یک فراخوانیِ ابزار (ساختارِ ساده تا در تست قابلِ جعل باشد)."""

    def __init__(self, rc: int, stdout: str, stderr: str) -> None:
        self.rc = rc
        self.stdout = stdout
        self.stderr = stderr


def escape(text: str) -> str:
    """فرارِ workflow command: درصد، CR و LF باید percent-encode شوند.

    GitHub متنِ annotation را تا **نخستین LF خام** نگه می‌دارد و بقیه را بی‌صدا دور
    می‌ریزد (اندازه‌گیری‌شده در اجرایِ CI شمارهٔ ۴۳۲۶۴۹۷۷۴۲۳: `message_len=1`). چون
    annotation تنها کانالِ بیرون‌کشیدنِ baseline از CI است، این یک تزئین نیست.
    """
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def emit_annotation(level: str, title: str, text: str) -> int:
    """متن را در یک یا چند annotationِ زیرِ سقفِ ۴KB منتشر می‌کند؛ تعدادِ قطعه‌ها را برمی‌گرداند.

    قطعه‌ها روی مرزِ خط می‌شکنند و `(part i/n)` می‌خورند، پس بازچسباندن‌شان دقیق است.
    عنوان نباید کاما داشته باشد: کاما جداکنندهٔ propertyها در workflow command است و
    عنوان را بی‌صدا کوتاه می‌کند.
    """
    safe_title = title.replace(",", " ").replace(":", "-")
    parts: list[str] = []
    cur = ""
    for line in text.split("\n"):
        if cur and len(cur) + 1 + len(line) > MAX_ANNOTATION:
            parts.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        parts.append(cur)
    shown = len(parts)
    if shown > MAX_PARTS:
        print(f"::warning title={safe_title} - truncated for the annotation channel::"
              f"{shown} parts needed but only {MAX_PARTS} are published")
        parts = parts[:MAX_PARTS]
        shown = len(parts)
    for i, part in enumerate(parts, start=1):
        t = safe_title if shown == 1 else f"{safe_title} (part {i}/{shown})"
        print(f"::{level} title={t}::{escape(part)}")
    return shown


def default_runner(cmd: list[str], cwd: Path) -> ToolRun:
    """اجرایِ واقعیِ ابزار. `runner` در `collect()` تزریق‌پذیر است تا تست‌ها ابزارِ واقعی
    را اجرا نکنند (کند و وابسته به محیط است) و بتوانند ورودیِ خراب را هم بسنجند."""
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
    return ToolRun(proc.returncode, proc.stdout, proc.stderr)


def find_ruff(interpreter: str | None = None) -> str:
    """ruff یک باینریِ Rust است، پس `python -m mypy` برایش معادل ندارد؛ کنارِ همان
    interpreterِ در حالِ اجرا دنبالش می‌گردیم و اگر نبود از PATH. نبودنش ⇒ وضعیتِ ناشناخته."""
    exe = sys.executable if interpreter is None else interpreter
    beside = Path(exe).parent / "ruff"
    if beside.exists():
        return str(beside)
    found = shutil.which("ruff")
    if not found:
        raise ToolUnavailable("ruff executable not found (looked beside "
                              f"{exe} and on PATH) — cannot measure lint inventory")
    return found


def _version_token(run: ToolRun, tool: str) -> str:
    """`ruff 0.17.4` ⇒ `0.17.4` و `mypy 2.4.1 (compiled: yes)` ⇒ `2.4.1`."""
    if run.rc != 0:
        raise ToolUnavailable(f"{tool} --version failed (exit {run.rc}): "
                              f"{(run.stderr or run.stdout).strip()[:200]}")
    bits = (run.stdout or "").split()
    if len(bits) < 2:
        raise ToolUnavailable(f"{tool} --version printed nothing parseable: {run.stdout!r}")
    return bits[1].strip()


def relativize(path: str, root: Path) -> str:
    """مسیرِ ماشینِ اجرا را به مسیرِ نسبیِ ریپو تبدیل می‌کند تا baseline قابلِ حمل باشد
    (وگرنه baselineِ ساخته‌شده در CI با مسیرِ `/home/runner/work/…` بی‌فایده است).

    دو شکلِ ورودی وجود دارد و هر دو واقعی‌اند: ruff در JSON **مسیرِ مطلق** می‌دهد، ولی
    mypy مسیرها را **نسبی به پوشهٔ اجرا** چاپ می‌کند. مسیرِ نسبی باید به `root` گره بخورد
    نه به cwdِ فرایند — در اجرایِ عادی این دو یکی‌اند، ولی اگر یکی نباشد (اجرایِ گیت از
    پوشه‌ای دیگر، یا `--root` صریح) مسیرِ نسبی به cwd گره می‌خورد و baseline را با
    مسیرِ بی‌معنا پر می‌کند. این ریپو یک سوئیتِ کاملِ «مستقل‌بودن از پوشهٔ اجرا» دارد،
    پس همین‌جا هم همان قاعده برقرار است.
    """
    p = Path(path)
    if not p.is_absolute():
        p = root / p
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return Path(path).as_posix()


def parse_ruff_json(text: str) -> list[dict]:
    """خروجیِ `ruff check --output-format json` یک آرایه است؛ هر چیزی جز آن یعنی ورودیِ
    بی‌اعتبار، نه «صفر خطا»."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ToolUnavailable(f"ruff JSON output is not parseable ({exc}); "
                              f"first 200 chars: {text[:200]!r}") from exc
    if not isinstance(data, list):
        raise ToolUnavailable(f"ruff JSON output is not a list but {type(data).__name__}")
    items: list[dict] = []
    for raw in data:
        if not isinstance(raw, dict):
            raise ToolUnavailable(f"ruff JSON item is not an object: {raw!r}")
        items.append({
            # `code` در ruff برایِ خطاهایِ نحوی می‌تواند تهی باشد؛ بی‌شناسه رهایش
            # نمی‌کنیم چون یک خطایِ بی‌شناسه در مقایسهٔ بعدی «شناسهٔ تازه» نمی‌شود.
            "code": raw.get("code") or NO_CODE,
            "message": raw.get("message") or "",
            "path": raw.get("filename") or "",
            "line": int((raw.get("location") or {}).get("row") or 0),
            "col": int((raw.get("location") or {}).get("column") or 0),
        })
    return items


def parse_mypy_output(text: str) -> tuple[list[dict], dict | None]:
    """خطایِ mypy را پارس می‌کند و خطِ خلاصه را هم برمی‌گرداند تا با شمارِ پارس‌شده
    مقایسه شود. `note`ها شمرده نمی‌شوند: کد ندارند و خطا نیستند (۶۳ note در برابرِ
    ۷۲۵ خطا اندازه‌گیری شد)."""
    for marker in MYPY_PARTIAL_MARKERS:
        if marker in text:
            raise ToolUnavailable(f"mypy inventory is partial ({marker!r} present) — "
                                  "counting it would look like an improvement")
    errors: list[dict] = []
    summary: dict | None = None
    for line in text.splitlines():
        m = MYPY_SUMMARY_RE.match(line.strip())
        if m:
            summary = {k: int(v) for k, v in m.groupdict().items()}
            continue
        ok = MYPY_SUCCESS_RE.match(line.strip())
        if ok:
            summary = {"errors": 0, "files": 0, "checked": int(ok.group("checked"))}
            continue
        hit = MYPY_LINE_RE.match(line)
        if hit and hit.group("sev") == "error":
            errors.append({
                "code": hit.group("code") or NO_CODE,
                "message": hit.group("msg") or "",
                "path": hit.group("path"),
                "line": int(hit.group("line")),
                "col": int(hit.group("col") or 0),
            })
    if summary is None:
        raise ToolUnavailable("mypy printed no summary line "
                              "(neither 'Found N errors…' nor 'Success: …') — inventory untrustworthy")
    return errors, summary


def _section(items: list[dict], root: Path, version: str, extra: dict | None = None) -> dict:
    by_code: dict[str, int] = {}
    by_file: dict[str, int] = {}
    for it in items:
        by_code[it["code"]] = by_code.get(it["code"], 0) + 1
        rel = relativize(it["path"], root)
        by_file[rel] = by_file.get(rel, 0) + 1
    top = dict(sorted(by_file.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_FILES_LIMIT])
    out = {
        "version": version,
        "total": len(items),
        "distinct_codes": len(by_code),
        "by_code": dict(sorted(by_code.items(), key=lambda kv: (-kv[1], kv[0]))),
        "files_with_issues": len(by_file),
        "top_files": top,
        "items": items,
    }
    if extra:
        out.update(extra)
    return out


def collect(root: Path | None = None, runner=None) -> dict:
    """هر دو ابزار را اجرا می‌کند و موجودیِ تجمیعی را می‌سازد.

    `runner` برایِ تست تزریق‌پذیر است. کدهایِ خروجِ ruff و mypy با هم فرق دارند: ruff
    وقتی خطا پیدا کند `1` می‌دهد (معمولی) و وقتی خودش خراب باشد `2`؛ mypy هم `1` یعنی
    خطا دارد و `2` یعنی خطایِ مهلک. پس «غیرصفر» به‌تنهایی معنایِ شکست ندارد.
    """
    base = root or ROOT
    run = runner or default_runner
    ruff_exe = find_ruff()

    rv = run([ruff_exe, "--version"], base)
    ruff_version = _version_token(rv, "ruff")
    rr = run([ruff_exe, "check", "--output-format", "json", RUFF_TARGET], base)
    if rr.rc not in (0, 1):
        raise ToolUnavailable(f"ruff failed to run (exit {rr.rc}): "
                              f"{(rr.stderr or rr.stdout).strip()[:300]}")
    ruff_items = parse_ruff_json(rr.stdout)

    mv = run([sys.executable, "-m", "mypy", "--version"], base)
    mypy_version = _version_token(mv, "mypy")
    mr = run([sys.executable, "-m", "mypy"], base)
    if mr.rc not in (0, 1):
        raise ToolUnavailable(f"mypy failed to run (exit {mr.rc}): "
                              f"{(mr.stderr or mr.stdout).strip()[:300]}")
    mypy_items, summary = parse_mypy_output(mr.stdout)

    # شاهدِ درونیِ mypy: شمارِ پارس‌شده باید با خطِ خلاصهٔ خودِ ابزار یکی باشد.
    assert summary is not None
    if summary["errors"] != len(mypy_items):
        raise ToolUnavailable(f"mypy summary says {summary['errors']} errors but "
                              f"{len(mypy_items)} were parsed — inventory untrustworthy")
    mypy_files = {relativize(i["path"], base) for i in mypy_items}
    if summary["files"] != len(mypy_files):
        raise ToolUnavailable(f"mypy summary says {summary['files']} files with errors but "
                              f"{len(mypy_files)} were parsed — inventory untrustworthy")

    return {
        "root": str(base),
        "ruff": _section(ruff_items, base, ruff_version),
        "mypy": _section(mypy_items, base, mypy_version,
                         extra={"checked_files": summary["checked"],
                                "files_with_errors": len(mypy_files)}),
    }


def compact_table(stats: dict) -> str:
    """جدولِ فشردهٔ موجودی — همان چیزی که در annotation و ترمینال چاپ می‌شود."""
    out: list[str] = []
    for tool in ("ruff", "mypy"):
        s = stats[tool]
        out.append(f"{tool} {s['version']}: {s['total']} issues "
                   f"in {s['distinct_codes']} codes across {s['files_with_issues']} files")
        for code, n in s["by_code"].items():
            out.append(f"   {n:>4}  {code}")
        out.append("   top files:")
        for path, n in s["top_files"].items():
            out.append(f"   {n:>4}  {path}")
        if tool == "mypy" and "checked_files" in s:
            out.append(f"   checked source files: {s['checked_files']}")
        out.append("")
    return "\n".join(out).rstrip("\n")


def baseline_payload(stats: dict, note: str) -> dict:
    """فقط فیلدهایِ مقایسه‌پذیر در baseline می‌آیند — نه خودِ موقعیت‌ها (چند هزار مورد
    می‌شود و از کانالِ annotation بیرون نمی‌رود)."""
    def slim(tool: str) -> dict:
        s = stats[tool]
        keep = {k: s[k] for k in ("version", "total", "distinct_codes", "by_code",
                                  "files_with_issues", "top_files") if k in s}
        if tool == "mypy":
            keep["checked_files"] = s.get("checked_files")
        return keep

    return {
        "_comment": [
            "baseline گیتِ کیفیتِ کدِ پایتون — ساختهٔ scripts/python_quality_gate.py.",
            "دانه‌بندی «شمارِ خطا به تفکیکِ شناسهٔ خودِ ابزار» است: ruff یک code می‌دهد",
            "(مثل F841) و mypy یک error-code (مثل arg-type)، پس برخلافِ گیتِ warningهای",
            "Kotlin هیچ قالب‌سازیِ دست‌سازی از متنِ پیام لازم نیست.",
            "نسخهٔ ابزارها بخشی از baseline است: ruff/mypy بین نسخه‌ها قواعد تازه اضافه",
            "می‌کنند، پس شمارِ نسخهٔ دیگر قابلِ مقایسه نیست و گیت exit 2 می‌دهد (ناشناخته)،",
            "نه پاس و نه شکست. نسخه‌های pin‌شده در Kharazmi_Server/requirements-dev.txt‌اند.",
            "محدودیتِ صادقانه: netting-out — رفعِ یک خطا و افزودنِ یک خطایِ هم‌شناسه",
            "نه total را تغییر می‌دهد نه by_code را، پس گیت ساکت می‌ماند.",
        ],
        "ruff": slim("ruff"),
        "mypy": slim("mypy"),
        "totals": {
            "combined": stats["ruff"]["total"] + stats["mypy"]["total"],
            "distinct_codes": stats["ruff"]["distinct_codes"] + stats["mypy"]["distinct_codes"],
        },
        "source": note,
    }


def _compare_tool(tool: str, now: dict, base: dict) -> tuple[list[str], list[str], list[str], str, set[str]]:
    """مقایسهٔ یک ابزار.

    خروجی: (مشکل‌ها، بهبودها، شناسه‌هایِ کاملاً رفع‌شده، خلاصه، شناسه‌هایِ مقصر).
    شناسه‌هایِ مقصر عمداً **همین‌جا** جمع می‌شوند و نه با پارسِ رشتهٔ مشکل‌ها: نسخهٔ اولِ
    این اسکریپت متنِ مشکل را با `split(": ")` می‌شکست تا شناسه را بیابد و در عمل کلمهٔ
    «new» از «new codes (not in the baseline): B006 x1» بیرون می‌آمد — یعنی شکستِ گیت
    بدونِ مکانِ قابلِ عمل منتشر می‌شد. هر چیزی که برایِ پیام ساخته شده نباید ورودیِ
    منطق باشد.
    """
    now_codes: dict = now["by_code"]
    base_codes: dict = base.get("by_code") or {}
    base_total = int(base.get("total") or 0)
    problems: list[str] = []
    offending: set[str] = set()

    new_codes = sorted(c for c in now_codes if c not in base_codes)
    if new_codes:
        problems.append(f"{tool}: new codes (not in the baseline): "
                        + "; ".join(f"{c} x{now_codes[c]}" for c in new_codes))
        offending.update(new_codes)
    regressed = sorted(
        (c for c in now_codes if c in base_codes and now_codes[c] > int(base_codes[c])),
        key=lambda c: -(now_codes[c] - int(base_codes[c])))
    if regressed:
        problems.append(f"{tool}: counts increased: "
                        + "; ".join(f"{c} {base_codes[c]}->{now_codes[c]}" for c in regressed))
        offending.update(regressed)
    if now["total"] > base_total:
        problems.append(f"{tool}: total increased: {base_total} -> {now['total']}")

    improved = sorted(
        (c for c in base_codes if now_codes.get(c, 0) < int(base_codes[c])),
        key=lambda c: -(int(base_codes[c]) - now_codes.get(c, 0)))
    gone = [c for c in base_codes if now_codes.get(c, 0) == 0]
    summary = (f"{tool} {now['version']}: now {now['total']} in {now['distinct_codes']} codes "
               f"| baseline {base_total} in {len(base_codes)} codes "
               f"| delta {now['total'] - base_total:+d}")
    return problems, improved, gone, summary, offending


def _check_versions(stats: dict, base: dict) -> list[str]:
    """اختلافِ نسخه ⇒ وضعیتِ ناشناخته. شمارِ ruffِ دیگر با baselineِ این ruff مقایسه‌شدنی
    نیست، پس نه می‌شود پاس داد نه شکست."""
    out: list[str] = []
    for tool in ("ruff", "mypy"):
        want = str((base.get(tool) or {}).get("version") or "")
        got = str(stats[tool]["version"])
        if want and want != got:
            out.append(f"{tool} version mismatch: baseline was built with {want} "
                       f"but this run used {got} — counts are not comparable "
                       "(versions are pinned in Kharazmi_Server/requirements-dev.txt)")
    return out


def check_against_baseline(stats: dict, baseline_path: str) -> int:
    p = Path(baseline_path)
    if not p.exists():
        # نبودنِ baseline یعنی وضعیت **ناشناخته** است، نه «پاس». همان قاعدهٔ fail-closed.
        print(f"::error title=python quality gate::baseline not found: {baseline_path}. "
              f"Run with --write-baseline locally or --emit-baseline in CI and commit the JSON "
              f"as {BASELINE_REL}. Until then the inventory is unknown and the gate cannot pass.")
        return 1
    try:
        base = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"::error title=python quality gate::baseline unreadable: {baseline_path} ({exc})")
        return 1

    version_problems = _check_versions(stats, base)
    if version_problems:
        for item in version_problems:
            print(f"::error title=python quality gate::{item}")
        return 2

    problems: list[str] = []
    improved_all: list[str] = []
    gone_all: list[str] = []
    summaries: list[str] = []
    offending_all: set[str] = set()
    for tool in ("ruff", "mypy"):
        prob, imp, gone, summ, offending = _compare_tool(tool, stats[tool], base.get(tool) or {})
        problems.extend(prob)
        offending_all |= offending
        improved_all.extend(f"{tool}:{c} {int((base[tool]['by_code'])[c])}->{stats[tool]['by_code'].get(c, 0)}"
                            for c in imp)
        gone_all.extend(f"{tool}:{c}" for c in gone)
        summaries.append(summ)

    combined_now = stats["ruff"]["total"] + stats["mypy"]["total"]
    base_combined = int((base.get("totals") or {}).get("combined") or 0)
    headline = ("python quality gate: ruff "
                f"{stats['ruff']['total']}/{stats['ruff']['distinct_codes']} codes + mypy "
                f"{stats['mypy']['total']}/{stats['mypy']['distinct_codes']} codes "
                f"= {combined_now} | baseline {base_combined} | delta {combined_now - base_combined:+d}")

    if problems:
        for item in problems:
            print(f"::error title=python quality gate::{item}")
        print(headline)
        for s in summaries:
            print(s)
        # شکست باید **قابلِ عمل** باشد: مکانِ همان شناسه‌هایی که باعثِ شکست شدند منتشر
        # می‌شود تا بدونِ یک دورِ دیگرِ CI قابلِ رفع باشد. شناسه‌ها را `_compare_tool`
        # برمی‌گرداند؛ هرگز از متنِ پیام بازپارس نمی‌شوند (به docstring همان تابع).
        detail = collect_locations(stats, offending_all or None, max_per_code=10)
        if detail.strip():
            emit_annotation("notice", "python quality gate - locations of the failing codes", detail)
        return 1

    print(headline)
    for s in summaries:
        print(s)
    if improved_all:
        text = headline + "\nbaseline can be refreshed (improvements must be locked in):\n"
        text += "; ".join(improved_all)
        if gone_all:
            text += "\ncodes fully resolved: " + ", ".join(gone_all)
        text += "\nThe commit-ready JSON follows as a separate annotation."
        emit_annotation("notice", "python quality baseline can be refreshed", text)
        # انتشارِ متنِ **دقیقِ** فایلِ تازه، فقط در مسیرِ موفق و فقط هنگامِ بهبود: وقتی گیت
        # شکست خورده، برکت‌دادنِ baselineِ جدید یعنی بی‌اثرکردنِ همان گیت.
        refreshed = json.dumps(baseline_payload(stats, note="refreshed by python_quality_gate.py --check"),
                               ensure_ascii=False, indent=2)
        emit_annotation("notice", f"python quality baseline refreshed - commit as {BASELINE_REL}", refreshed)
    else:
        print("no change against the baseline")
    return 0


def locations_for_codes(stats: dict, codes: set[str], max_per_code: int = 20) -> str:
    """مکانِ `file:line:col` + پیامِ کامل برایِ شناسه‌هایِ داده‌شده."""
    out: list[str] = []
    for tool in ("ruff", "mypy"):
        for code in sorted(codes):
            hits = [i for i in stats[tool]["items"] if i["code"] == code]
            if not hits:
                continue
            out.append(f"[{tool}] {code} (x{len(hits)})")
            for h in sorted(hits, key=lambda x: (x["path"], x["line"]))[:max_per_code]:
                rel = relativize(h["path"], Path(stats["root"]))
                loc = f"{rel}:{h['line']}" + (f":{h['col']}" if h["col"] else "")
                out.append(f"    {loc}  {h['message']}")
            if len(hits) > max_per_code:
                out.append(f"    … and {len(hits) - max_per_code} more")
    return "\n".join(out)


def collect_locations(stats: dict, wanted: set[str] | None, max_per_code: int) -> str:
    if wanted is None:
        wanted = {c for tool in ("ruff", "mypy") for c in stats[tool]["by_code"]}
    body = locations_for_codes(stats, wanted, max_per_code)
    return body or f"no locations for the requested codes: {sorted(wanted)}"


def fingerprint(payload: dict) -> str:
    """اثرِ انگشتِ کوتاهِ محتوا (بدونِ فیلدِ source) تا در commit بتوان ثابت کرد
    baselineِ برداشت‌شده از CI با نسخهٔ محلی هم‌محتواست."""
    slim = {k: v for k, v in payload.items() if k != "source"}
    blob = json.dumps(slim, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:10]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baseline", default=DEFAULT_BASELINE,
                    help=f"مسیرِ baseline JSON (پیش‌فرض: {BASELINE_REL} نسبت به ریشهٔ ریپو)")
    ap.add_argument("--source", default=None, help="برچسبِ مبدأ برای baseline (مثلاً شمارهٔ اجرای CI)")
    ap.add_argument("--root", default=None, help="ریشهٔ ریپو (پیش‌فرض: والدِ پوشهٔ همین اسکریپت)")
    ap.add_argument("--check", action="store_true", help="موجودیِ فعلی را با baseline مقایسه کن (حالتِ گیت)")
    ap.add_argument("--write-baseline", action="store_true", help="baseline را از موجودیِ فعلی بساز/بازنویسی کن")
    ap.add_argument("--table", action="store_true", help="جدولِ فشردهٔ موجودی را چاپ/منتشر کن")
    ap.add_argument("--emit-baseline", action="store_true",
                    help="خودِ JSONِ baseline را در annotation منتشر کن تا از CI به ریپو برسد")
    ap.add_argument("--locations", action="store_true", help="مکانِ file:line هر خطا را منتشر کن")
    ap.add_argument("--codes", default="",
                    help="فهرستِ شناسه‌ها با کاما (ruff code یا mypy error-code)؛ خالی = همه")
    ap.add_argument("--max-per-code", type=int, default=20, help="سقفِ تعدادِ مکانِ چاپ‌شده برای هر شناسه")
    args = ap.parse_args(argv)

    modes = [args.check, args.write_baseline, args.table, args.emit_baseline, args.locations]
    if not any(modes):
        ap.error("one of --check / --write-baseline / --table / --emit-baseline / --locations is required")

    root = Path(args.root).resolve() if args.root else ROOT
    try:
        stats = collect(root)
    except ToolUnavailable as exc:
        # نبودن/خرابیِ ابزار هرگز «صفر خطا» نیست: یک اجرایِ خراب بی‌صدا گیت را رد می‌کرد.
        print(f"::error title=python quality inventory unavailable::{exc}")
        return 2

    if args.locations:
        wanted = {x.strip() for x in args.codes.split(",") if x.strip()} or None
        body = collect_locations(stats, wanted, args.max_per_code)
        label = args.codes.strip() or "all codes"
        emit_annotation("notice", ("python quality locations for " + label)[:60], body)
        print(body)
    if args.table:
        table = compact_table(stats)
        emit_annotation("notice",
                        f"Python quality - ruff {stats['ruff']['total']} + mypy {stats['mypy']['total']}",
                        table)
        print(table)
    if args.emit_baseline:
        payload = baseline_payload(stats, args.source or "local run")
        body = json.dumps(payload, ensure_ascii=False, indent=2)
        emit_annotation("notice", f"python quality baseline JSON - commit as {BASELINE_REL}", body)
        print(body)
    if args.write_baseline:
        payload = baseline_payload(stats, args.source or "written from a local run")
        out = Path(args.baseline)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"baseline written: {out} (ruff {payload['ruff']['total']} + "
              f"mypy {payload['mypy']['total']} = {payload['totals']['combined']}, "
              f"fingerprint {fingerprint(payload)})")
        return 0
    if args.check:
        return check_against_baseline(stats, args.baseline)
    return 0


if __name__ == "__main__":
    sys.exit(main())
