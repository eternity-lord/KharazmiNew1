#!/usr/bin/env python3
"""گیتِ warningهای کامپایلرِ Kotlin — «بدتر نشود»، نه «صفر شود».

چرا این اسکریپت لازم است
--------------------------
`app/build.gradle.kts` هیچ `allWarningsAsErrors` ندارد و تا امروز هیچ workflow ای خروجیِ
کامپایلر را نمی‌خواند؛ یعنی شمارِ warningها **ناشناخته** بود. warningهای کامپایلر با
warningهای lint فرق دارند: lint سبک و بهترین‌روش را می‌سنجد، ولی کامپایلر چیزهایی را
اعلام می‌کند که می‌توانند **باگِ واقعی** باشند — «Name shadowed»، «Casting will throw
ClassCastException»، «Unreachable code»، «Elvis operator always returns the left operand»،
«Variable is never used». صفرکردنِ یک‌بارهٔ همه‌شان ریفکتور نیست و با رفتارمحافظ بودنِ این
کار در تضاد است، پس همان الگویِ `lint_gate.py`: **baseline را ثبت کن و فقط جلویِ بدتر شدن
را بگیر.**

دو تفاوتِ ماهوی با `lint_gate.py`
---------------------------------
۱) **warningهای Kotlin شناسهٔ پایدار ندارند.** خروجیِ lint یک `id` دارد
(`HardcodedText`) ولی کامپایلر فقط متنِ پیام می‌دهد (`Variable 'userName' is never used`).
پس شناسه را خودمان از **قالبِ پیام** می‌سازیم: نام‌های داخلِ نقل‌قول و backtick با `'*'`
و اعداد با `N` جایگزین می‌شوند ⇒ `Variable '*' is never used`. این کار دانه‌بندی را
پایدار و baseline را فشرده می‌کند (چند ده شناسه، نه چند هزار موقعیت).

ولی نقل‌قول به‌تنهایی کافی نیست: Kotlin در خانواده‌هایی نام یا نوع را **بی‌نقل‌قول**
می‌گذارد (`Name shadowed: item`، `Type mismatch: inferred type is String but Int was
expected`). بدونِ نرمال‌سازی‌شان به ازایِ هر نامِ متغیر یک شناسهٔ تازه ساخته می‌شد؛ یعنی
هم baseline منفجر می‌شد و هم **تغییرِ نامِ یک متغیر در یک ریفکتورِ بی‌خطر، گیت را با
«قالبِ جدید» به‌دروغ می‌شکست**. پس آن خانواده‌ها در `_BARE_HOLE_RULES` صریح فهرست
شده‌اند و یک قاعدهٔ عمومیِ پشتیبان، خانواده‌هایِ ناشناخته را می‌گیرد. خانواده‌هایی که
قالبشان بیش از یک کلمهٔ کلیدی دارد دست‌نخورده می‌مانند (`Variable '*' is never used` در
برابرِ `Parameter '*' is never used`)، پس بیش‌ازحد یکی‌کردن هم رخ نمی‌دهد.

۲) **لاگِ Gradle باید خودش را ثابت کند.** گزارشِ lint یک XMLِ ساخت‌یافته است که یا هست
یا نیست؛ ولی لاگِ کامپایل یک فایلِ متنی است که اگر build زود شکسته باشد **کوتاه** است و
کمتر warning دارد — و شمردنِ آن به‌معنایِ «بهبود» اشتباه می‌شود. پس نبودنِ شاهدِ اجرایِ
taskِ کامپایل خطایِ exit=2 است، نه «صفر warning». این همان قاعدهٔ «خواندنِ ناموفق هرگز
صفر گزارش نشود» است.

محدودیتِ صادقانهٔ این دانه‌بندی
--------------------------------
اگر در یک قالب یک warning **رفع** شود و هم‌زمان یک warning **جدید** از همان قالب اضافه
شود، شمارِ کل تغییر نمی‌کند و گیت آن را نمی‌بیند (netting-out) — همان بهایِ فشرده‌بودنِ
baseline که در `lint_gate.py` هم مستند است. دو چیز ریسک را کم می‌کند: هر **قالبِ جدید**
حتی با یک مورد هم شکست است، و baseline توزیعِ فایل‌ها را هم نگه می‌دارد تا تغییرِ شکلِ
پراکندگی دستِ‌کم برای بازبینِ انسانی ثبت شود.

قاعدهٔ تصمیم
-------------
pass  ⟺  هیچ قالبِ جدیدی نباشد **و** شمارِ هیچ قالبی از baseline بیشتر نشود **و** مجموع
از مجموعِ baseline بیشتر نشود. بهبود (کاهش) مجاز و گزارش‌شدنی است؛ در آن صورت baseline
باید با `--write-baseline` تازه شود تا دستاورد قفل بماند و بعداً بی‌صدا پس نرود.

کدهای خروج
-----------
۰ = پاس · ۱ = گیت رد شد · ۲ = ورودی ناخوانا/ناقص (لاگ نیست، خالی است، `BUILD FAILED`
دارد، یا شاهدِ اجرایِ taskِ کامپایل در آن پیدا نشد).

کانالِ انتقالِ baseline
-----------------------
artifact از CI قابلِ دانلود نیست و `output.summary` از API خالی برمی‌گردد؛ تنها کانالِ
قابلِ اتکا **annotation** است که از `api.github.com` خوانده می‌شود. پس `--emit-baseline`
خودِ JSON را در annotationِ قطعه‌بندی‌شده (سقفِ ۳۹۰۰ کاراکتر، چون GitHub فیلدِ `message`
را روی ۴۰۹۶ می‌بُرد) چاپ می‌کند تا بدونِ بازنویسیِ دستی به ریپو برسد.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

DEFAULT_LOG = "/tmp/gradle-assemble.log"
DEFAULT_BASELINE = "kotlin-warnings-baseline.json"
ANDROID_ROOT_MARKER = "KharazmiAdmin"

# سقفِ واقعیِ کانالِ annotation؛ همان عددی که در اجرای CI شمارهٔ 43042529340 اندازه‌گیری شد.
MAX_ANNOTATION = 3900
MAX_PARTS = 8

# شاهدِ اینکه taskِ کامپایلِ Kotlin واقعاً دویده است. اگر هیچ‌کدام در لاگ نباشد، لاگ
# «کوتاه» است نه «پاک» — و ما هرگز کوتاهی را صفر گزارش نمی‌کنیم.
COMPILE_TASK_RE = re.compile(r":app:compile\w*Kotlin\b")
BUILD_SUCCESSFUL = "BUILD SUCCESSFUL"
BUILD_FAILED = "BUILD FAILED"

# `w: file:///abs/path/Foo.kt:12:34 message` (قالبِ Kotlin 2.x) و
# `w: /abs/path/Foo.kt:12:34 message` (قالبِ قدیمی‌تر) و حالتِ بدونِ ستون.
# `.+?` غیرحریص است تا نخستین `:رقم` پایانِ مسیر باشد، نه بخشی از خودِ مسیر.
WARNING_RE = re.compile(r"^\s*w:\s+(?P<loc>.+?):(?P<line>\d+)(?::(?P<col>\d+))?\s+(?P<msg>\S.*)$")

# ساختِ شناسه از قالبِ پیام
_QUOTED_RE = re.compile(r"'[^']*'|\"[^\"]*\"|`[^`]*`")
_NUMBER_RE = re.compile(r"\b\d+\b")
_SPACE_RE = re.compile(r"\s+")
MAX_KIND_LEN = 80

# سوراخ‌هایِ **بی‌نقل‌قول**. Kotlin در بعضی خانواده‌ها نام یا نوع را بدونِ نقل‌قول در پیام
# می‌گذارد (`Name shadowed: item`، `Type mismatch: inferred type is String but Int was
# expected`). اگر این‌ها نرمال نشوند، به ازایِ هر نامِ متغیر یک شناسهٔ تازه ساخته می‌شود:
# هم baseline منفجر می‌شود (چند صد شناسه در یک annotationِ ۴KB نمی‌جاود) هم **تغییرِ نامِ
# یک متغیر در یک ریفکتورِ بی‌خطر، گیت را با «قالبِ جدید» به‌دروغ می‌شکند**. پس این
# خانواده‌ها صریح فهرست شده‌اند؛ ترتیب معنادار است و نخستین قاعدهٔ مطابق اعمال می‌شود.
_BARE_HOLE_RULES: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"^(Type mismatch:\s*inferred type is\s+).+?(\s+but\s+).+(\s+was expected)$"), r"\1*\2*\3"),
    (re.compile(r"^(Name shadowed:\s*).+$"), r"\1*"),
    (re.compile(r"(expected type\s+)\S+"), r"\1*"),
    (re.compile(r"(is not a subtype of\s+)\S+"), r"\1*"),
    (re.compile(r"(Inferred type for the parameter\s+)\S+"), r"\1*"),
)
# قاعدهٔ عمومیِ پشتیبان: اگر کلِ پیام به «سرآغاز: یک شناسه» ختم شود، آن شناسه سوراخ است و
# خانواده‌هایِ ناشناخته را پوشش می‌دهد. ریسکِ باقی‌مانده این است که دو پیامِ واقعاً متفاوت
# با یک دنبالهٔ تک‌شناسه یکی شوند؛ چون **قالبِ جدید شکست است**، خانوادهٔ پوشش‌داده‌نشده
# خودش را با شکستِ پرسروصدا نشان می‌دهد نه با سبزیِ بی‌صدا.
_TRAILING_IDENT_RE = re.compile(r"^([A-Za-z][^:]{2,60}:\s*)[A-Za-z_][\w.]{0,60}$")


class LogUnavailable(RuntimeError):
    """لاگِ Gradle ناخوانا یا ناقص است ⇒ هرگز «صفر warning» تلقی نمی‌شود."""


def escape(text: str) -> str:
    """فرارِ workflow command: درصد، CR و LF باید percent-encode شوند.

    چرا حیاتی است: GitHub متنِ annotation را تا **نخستین LF خام** نگه می‌دارد و بقیه را
    بی‌صدا دور می‌ریزد. این در اجرایِ CI شمارهٔ ۴۳۲۶۴۹۷۷۴۲۳ اندازه‌گیری شد: نسخهٔ اولِ
    این اسکریپت newline خام چاپ می‌کرد و در نتیجه `--emit-baseline` فقط «{» (یک کاراکتر،
    `message_len=1`) و `--table` فقط خطِ نخستِ جدول (۵۵ کاراکتر) را به ریپو رساند، با
    `raw_message` تهی. چون annotation **تنها** کانالِ بیرون‌کشیدنِ baseline از CI است
    (artifact بسته است و `output.summary` از API خالی برمی‌گردد)، این برش بی‌صدا کلِ
    مرحلهٔ enforcing را غیرممکن می‌کرد — و locally هیچ تستی نمی‌دید چون خروجیِ چاپ‌شده
    رویِ ترمینال سالم به نظر می‌رسید. `lint_gate.py` همین را با `escape()` حل کرده بود.
    """
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def emit_annotation(level: str, title: str, text: str) -> int:
    """متن را در یک یا چند annotationِ زیرِ سقفِ ۴KB منتشر می‌کند؛ تعدادِ قطعه‌ها را برمی‌گرداند.

    قطعه‌ها روی مرزِ خط می‌شکنند و `(part i/n)` می‌خورند، پس بازچسباندنِ‌شان دقیق است.
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
    total = len(parts)
    if total > MAX_PARTS:
        print(f"::warning title={safe_title} - truncated for the annotation channel::"
              f"{total} parts needed but only {MAX_PARTS} are published")
        parts = parts[:MAX_PARTS]
        total = len(parts)
    shown = len(parts)
    for i, part in enumerate(parts, start=1):
        # شمارهٔ قطعه در **عنوان** می‌آید نه در پیام: پیام نباید LF خام داشته باشد و
        # عنوانِ جدا، بازچسباندنِ قطعه‌ها را بی‌ابهام می‌کند (همان قراردادِ lint_gate.py).
        t = safe_title if shown == 1 else f"{safe_title} (part {i}/{shown})"
        print(f"::{level} title={t}::{escape(part)}")
    return shown


def normalize_path(raw: str, marker: str = ANDROID_ROOT_MARKER) -> str:
    """مسیرِ مطلقِ ماشینِ CI را به مسیرِ نسبیِ ریپو تبدیل می‌کند تا baseline قابلِ حمل باشد.

    `file:///home/runner/work/X/Y/KharazmiAdmin/app/src/Foo.kt` ⇒ `KharazmiAdmin/app/src/Foo.kt`.
    اگر نشانهٔ ریشهٔ اندروید در مسیر نبود، سه جزءِ آخر نگه داشته می‌شود تا دستِ‌کم فایل
    قابلِ تشخیص بماند (به‌جایِ دور ریختنِ اطلاعات).
    """
    p = raw.strip()
    if p.startswith("file://"):
        p = p[len("file://"):]
    p = p.replace("\\", "/")
    parts = [x for x in p.split("/") if x]
    if marker in parts:
        return "/".join(parts[parts.index(marker):])
    return "/".join(parts[-3:]) if len(parts) >= 3 else p


def kind_of(message: str) -> str:
    """قالبِ پیام را به شناسهٔ پایدار تبدیل می‌کند.

    `Variable 'userName' is never used` ⇒ `Variable '*' is never used`
    `Name shadowed: item` ⇒ `Name shadowed: *`  (نامِ بی‌نقل‌قول هم سوراخ است)
    """
    t = _QUOTED_RE.sub("'*'", message)
    t = _NUMBER_RE.sub("N", t)
    for rx, repl in _BARE_HOLE_RULES:
        collapsed = rx.sub(repl, t)
        if collapsed != t:
            t = collapsed
            break
    t = _TRAILING_IDENT_RE.sub(r"\1*", t)
    t = _SPACE_RE.sub(" ", t).strip().rstrip(".")
    return t[:MAX_KIND_LEN] or message.strip()[:MAX_KIND_LEN] or "unknown"


def read_log(path: str) -> str:
    """لاگ را می‌خواند و **شاهدِ اجرایِ کامپایل** را می‌خواهد؛ در غیر این صورت LogUnavailable."""
    p = Path(path)
    if not p.exists():
        raise LogUnavailable(f"compile log not found: {path}")
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise LogUnavailable(f"compile log unreadable: {path} ({exc})") from exc
    if not text.strip():
        raise LogUnavailable(f"compile log is empty: {path}")
    if BUILD_FAILED in text:
        raise LogUnavailable(
            f"compile log contains {BUILD_FAILED!r}; the build broke so the warning "
            "inventory is partial and must not be compared against the baseline"
        )
    if not COMPILE_TASK_RE.search(text) and BUILD_SUCCESSFUL not in text:
        raise LogUnavailable(
            "compile log has no witness that a Kotlin compile task ran "
            f"(looked for :app:compile*Kotlin or {BUILD_SUCCESSFUL!r}); refusing to report "
            "zero warnings from a truncated log"
        )
    return text


def parse_log(text: str) -> list[dict]:
    """خطوطِ `w:` را به رکوردِ warning تبدیل می‌کند؛ تکراری‌هایِ دقیق حذف می‌شوند.

    چرا حذفِ تکرار: اگر روزی بیش از یک variant کامپایل شود (`assembleDebug` +
    `assembleRelease`) همان warning دو بار چاپ می‌شود و شمارِ baseline دو برابر می‌پرد.
    معیارِ یکتایی (فایل، خط، ستون، پیام) است نه فقط پیام، تا دو warningِ هم‌متن در دو
    جایِ متفاوت هر دو شمرده شوند.
    """
    out: list[dict] = []
    seen: set[tuple[str, int, int, str]] = set()
    for line in text.splitlines():
        m = WARNING_RE.match(line)
        if not m:
            continue
        loc = normalize_path(m.group("loc"))
        ln = int(m.group("line"))
        col = int(m.group("col")) if m.group("col") else 0
        msg = m.group("msg").strip()
        key = (loc, ln, col, msg)
        if key in seen:
            continue
        seen.add(key)
        out.append({"file": loc, "line": ln, "col": col, "message": msg, "kind": kind_of(msg)})
    return out


def build_stats(warnings: list[dict], log_path: str) -> dict:
    by_kind = Counter(w["kind"] for w in warnings)
    by_file = Counter(w["file"] for w in warnings)
    return {
        "total": len(warnings),
        "distinct_kinds": len(by_kind),
        "by_kind": dict(by_kind.most_common()),
        "files_with_warnings": len(by_file),
        "top_files": dict(by_file.most_common(10)),
        "log": log_path,
        "warnings": warnings,
    }


def compact_table(stats: dict) -> str:
    lines = [
        f"Kotlin compiler warnings: {stats['total']} in {stats['distinct_kinds']} kinds "
        f"across {stats['files_with_warnings']} files",
        "",
    ]
    for kind, n in stats["by_kind"].items():
        lines.append(f"{n:5d}  {kind}")
    lines.append("")
    lines.append("top files:")
    for f, n in stats["top_files"].items():
        lines.append(f"{n:5d}  {f}")
    return "\n".join(lines)


def baseline_payload(stats: dict, note: str) -> dict:
    return {
        "_comment": [
            "baseline گیتِ warningهای کامپایلرِ Kotlin — ساختهٔ KharazmiAdmin/kotlin_warning_gate.py.",
            "دانه‌بندی عمداً «شمارِ warning به تفکیکِ قالبِ پیام» است؛ علت و محدودیتِ صادقانهٔ آن",
            "(netting-out) در docstring همان اسکریپت آمده: artifact از CI قابلِ دانلود نیست و",
            "output.summary از API خالی برمی‌گردد، پس تنها کانالِ انتقالِ baseline همان annotation است.",
            "شناسه‌ها قالبِ پیام‌اند، نه id پایدارِ ابزار: نام‌های نقل‌قولی '*' و اعداد N شده‌اند.",
        ],
        "total": stats["total"],
        "distinct_kinds": stats["distinct_kinds"],
        "by_kind": stats["by_kind"],
        "files_with_warnings": stats["files_with_warnings"],
        "top_files": stats["top_files"],
        "log": stats["log"],
        "source": note,
    }


def check_against_baseline(stats: dict, baseline_path: str) -> int:
    p = Path(baseline_path)
    if not p.exists():
        # نبودنِ baseline یعنی وضعیت **ناشناخته** است، نه «پاس». همان قاعدهٔ fail-closed.
        print(f"::error title=kotlin warning gate::baseline not found: {baseline_path}. "
              "Run with --emit-baseline in CI and commit the JSON, or --write-baseline locally. "
              "Until then the warning inventory is unknown and the gate cannot pass.")
        return 1
    try:
        base = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"::error title=kotlin warning gate::baseline unreadable: {baseline_path} ({exc})")
        return 1

    base_kinds: dict = base.get("by_kind") or {}
    now_kinds: dict = stats["by_kind"]
    base_total = int(base.get("total") or 0)
    problems: list[str] = []

    new_kinds = sorted(k for k in now_kinds if k not in base_kinds)
    if new_kinds:
        problems.append("new warning kinds (not present in the baseline): "
                        + "; ".join(f"{k} x{now_kinds[k]}" for k in new_kinds))
    regressed = sorted(
        (k for k in now_kinds if k in base_kinds and now_kinds[k] > int(base_kinds[k])),
        key=lambda k: -(now_kinds[k] - int(base_kinds[k])),
    )
    if regressed:
        problems.append("warning counts increased: "
                        + "; ".join(f"{k} {base_kinds[k]}->{now_kinds[k]}" for k in regressed))
    if stats["total"] > base_total:
        problems.append(f"total warnings increased: {base_total} -> {stats['total']}")

    improved = sorted(
        (k for k in base_kinds if now_kinds.get(k, 0) < int(base_kinds[k])),
        key=lambda k: -(int(base_kinds[k]) - now_kinds.get(k, 0)),
    )
    gone = [k for k in base_kinds if now_kinds.get(k, 0) == 0]
    summary = (f"Kotlin compiler warnings: now {stats['total']} in {stats['distinct_kinds']} kinds "
               f"| baseline {base_total} in {len(base_kinds)} kinds "
               f"| delta {stats['total'] - base_total:+d}")

    if problems:
        for item in problems:
            print(f"::error title=kotlin warning gate::{item}")
        print(summary)
        return 1

    print(summary)
    if improved:
        detail = "; ".join(f"{k} {base_kinds[k]}->{now_kinds.get(k, 0)}" for k in improved)
        text = f"{summary}\nbaseline can be refreshed (improvements must be locked in):\n{detail}"
        if gone:
            text += "\nkinds fully resolved: " + ", ".join(gone)
        text += "\nRun --write-baseline and commit the result."
        emit_annotation("notice", "kotlin warning baseline can be refreshed", text)
    else:
        print("no change against the baseline")
    return 0


def collect_locations(stats: dict, wanted: set[str] | None, max_per_kind: int) -> str:
    lines: list[str] = []
    listed = 0
    matched_kinds: set[str] = set()
    for kind, n in stats["by_kind"].items():
        if wanted and not any(w.lower() in kind.lower() for w in wanted):
            continue
        matched_kinds.add(kind)
        lines.append(f"{kind}  (x{n})")
        shown = 0
        for w in stats["warnings"]:
            if w["kind"] != kind:
                continue
            if shown >= max_per_kind:
                lines.append(f"    ... {n - shown} more")
                break
            lines.append(f"    {w['file']}:{w['line']}:{w['col']}  {w['message']}")
            shown += 1
            listed += 1
        lines.append("")
    if wanted:
        missing = sorted(w for w in wanted if not any(w.lower() in k.lower() for k in matched_kinds))
        if missing:
            lines.append("kinds requested but not present in this log: " + ", ".join(missing))
    lines.append(f"locations listed: {listed}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", default=DEFAULT_LOG, help="لاگِ Gradle (پیش‌فرض: /tmp/gradle-assemble.log)")
    ap.add_argument("--baseline", default=DEFAULT_BASELINE, help="مسیرِ baseline JSON")
    ap.add_argument("--source", default=None, help="برچسبِ مبدأ برای baseline (مثلاً شمارهٔ اجرای CI)")
    ap.add_argument("--check", action="store_true", help="لاگِ فعلی را با baseline مقایسه کن (حالتِ گیت)")
    ap.add_argument("--write-baseline", action="store_true", help="baseline را از لاگِ فعلی بساز/بازنویسی کن")
    ap.add_argument("--table", action="store_true", help="جدولِ فشردهٔ موجودی را چاپ/منتشر کن")
    ap.add_argument("--emit-baseline", action="store_true",
                    help="خودِ JSONِ baseline را در annotation منتشر کن تا از CI به ریپو برسد")
    ap.add_argument("--locations", action="store_true", help="مکانِ file:line هر warning را منتشر کن")
    ap.add_argument("--kinds", default="",
                    help="فهرستِ قالب‌ها با کاما؛ هر جزء به‌عنوانِ زیررشته مقایسه می‌شود؛ خالی = همه")
    ap.add_argument("--max-per-kind", type=int, default=20, help="سقفِ تعدادِ مکانِ چاپ‌شده برای هر قالب")
    args = ap.parse_args(argv)

    if not (args.check or args.write_baseline or args.table or args.emit_baseline or args.locations):
        ap.error("one of --check / --write-baseline / --table / --emit-baseline / --locations is required")

    try:
        text = read_log(args.log)
    except LogUnavailable as exc:
        # نبودنِ لاگ هرگز «صفر warning» نیست: یک buildِ خراب بی‌صدا گیت را رد می‌کرد.
        print(f"::error title=kotlin warning log unavailable::{exc}")
        return 2

    warnings = parse_log(text)
    stats = build_stats(warnings, args.log)

    if args.locations:
        wanted = {x.strip() for x in args.kinds.split(",") if x.strip()} or None
        body = collect_locations(stats, wanted, args.max_per_kind)
        label = args.kinds.strip() or "all kinds"
        emit_annotation("notice", ("kotlin warning locations for " + label)[:60], body)
        print(body)
    if args.table:
        emit_annotation("notice",
                        f"Kotlin compiler warnings - {stats['total']} in {stats['distinct_kinds']} kinds",
                        compact_table(stats))
        print(compact_table(stats))
    if args.emit_baseline:
        payload = baseline_payload(stats, args.source or "local gradle log")
        body = json.dumps(payload, ensure_ascii=False, indent=2)
        emit_annotation("notice",
                        "kotlin warning baseline JSON - commit as KharazmiAdmin/" + DEFAULT_BASELINE,
                        body)
        print(body)
    if args.write_baseline:
        payload = baseline_payload(stats, args.source or f"written from {args.log}")
        out = Path(args.baseline)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"baseline written: {out} ({payload['total']} warnings in {payload['distinct_kinds']} kinds)")
        return 0
    if args.check:
        return check_against_baseline(stats, args.baseline)
    return 0


if __name__ == "__main__":
    sys.exit(main())
