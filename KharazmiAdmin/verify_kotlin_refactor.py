#!/usr/bin/env python3
"""راستی‌آزمایِ ریفکتورِ Kotlin — بدونِ JVM/Gradle/kotlinc.

این اسکریپت جای «کامپایلرِ محلی» را نمی‌گیرد؛ جای «حدس زدن» را می‌گیرد. هر بررسی
fail-closed است: اگر نتواند مطمئن شود، شکست می‌دهد. اثباتِ نهاییِ کامپایل همچنان CI است
(`:app:compileDebugKotlin`).

چرا لازم است: تست‌های این ریپو **متنِ سورسِ Kotlin** را پین می‌کنند، و هیچ کامپایلری هم
محلی در دسترس نیست؛ پس هر جابه‌جایی/استخراج باید با اوراکل‌های مکانیکی اثبات شود.

بررسی‌ها:
  --pins     نقشهٔ پینِ سراسری: کدام لیترال/regexِ asserted در تست‌ها به کدام فایلِ .kt
             قفل شده. معیارِ «پینِ سخت» = حذفِ آن بلوک باعث شود لیترال دیگر در آن فایل
             پیدا نشود (یعنی دقیقاً همان چیزی که تست مشاهده می‌کند). assertNotIn هرگز
             پین نیست چون بیرون بردنِ متن فقط به آن کمک می‌کند.
  --types    اوراکلِ حلِ نوع: هر شناسهٔ با حرفِ بزرگ باید در scope همان فایل حل شود
             (import — با بازکردنِ star import — / نامِ top-levelِ هم‌بسته / اعلامِ محلی /
             builtin). رشته‌ها ارجاعِ نوع نیستند و نادیده گرفته می‌شوند.
  --diff     حالتِ تفاضلیِ --types در برابرِ HEAD: یک فایل فقط می‌تواند توکنِ حل‌نشده
             **کم** کند، هرگز اضافه.
  --arity    شمارِ آرگومانِ هر نقطهٔ فراخوانی در برابرِ `required ≤ n ≤ total`ِ اعلام.
             «فراموش شدنِ یک context» را می‌گیرد.
  --members  یکتاییِ امضایِ اعضا در هر فایل. «اعلامِ تکراری» (Duplicate JVM class method)
             را می‌گیرد — چیزی که --arity نمی‌بیند چون نقطهٔ فراخوانی را می‌سنجد.
  --names    نام‌های top-levelِ کلِ ریپو در برابرِ HEAD: هیچ‌کدام نباید گم یا تکراری شود
             و هر نامِ تازه باید در فهرستِ مجاز باشد.
  --spans    بازهٔ دقیقِ هر عضوِ کلاس/object (رشته‌آگاه و کامنت‌آگاه) — برای استخراجِ
             کلمه‌به‌کلمهٔ بدنه‌ها.

فقط کتابخانهٔ استاندارد. خروجی فارسی، مثلِ بقیهٔ ابزارهای این پوشه.
"""
from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import importlib.util
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP_SRC = ROOT / "KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin"
TEST_DIRS = [ROOT / "KHarazmi_Server/tests", ROOT / "tests"]
ANALYZER = ROOT / "KharazmiAdmin/find_dead_kotlin.py"

# بسته‌های star: چه نام‌هایی فراهم می‌کنند. بدونِ این، `import retrofit2.http.*` به
# یک شناسهٔ بی‌معنیِ «*» تجزیه می‌شود و اوراکل، فایلِ سالم را خراب گزارش می‌دهد.
STAR_PROVIDES = {
    "retrofit2.http": set(
        "GET POST PUT DELETE PATCH HEAD OPTIONS Streaming Body Path Query QueryMap Url "
        "FormUrlEncoded Field FieldMap Multipart Part PartMap Header HeaderMap Headers Tag".split()
    ),
    "kotlinx.coroutines": set(
        "Deferred Flow StateFlow SharedFlow Job CoroutineScope SupervisorJob SupervisorScope "
        "Mutex Channel CoroutineExceptionHandler NonCancellable MainScope Dispatchers".split()
    ),
    "kotlinx.coroutines.sync": {"withLock", "Mutex"},
    "android.widget": set(
        "TextView Button ImageView EditText Toast ListView ProgressBar Spinner CheckBox "
        "RadioButton ScrollView LinearLayout FrameLayout RelativeLayout AdapterView PopupMenu "
        "Switch SeekBar ImageButton".split()
    ),
}

# نام‌هایی که در Kotlin/Java بدونِ import حل می‌شوند.
# `IntArray`/`Regex` و… builtinِ stdlibِ Kotlin‌اند و `RESULT_OK` ثابتِ به‌ارث‌رسیدهٔ
# `Activity` است؛ نبودشان در این مجموعه اوراکلِ نوع را وادار به «توضیحِ زبانی» می‌کرد.
BUILTIN = set(
    """Int String Boolean Long Double Float Short Byte Char Any Unit Nothing List Map Set
    Collection Iterable Pair Triple Array ArrayList HashMap HashSet LinkedHashMap MutableList
    MutableMap MutableSet Number Comparable Throwable Exception Error Runnable Void Object
    CharSequence ByteArray IntRange LongRange ClosedRange Sequence Override Deprecated Suppress
    Companion StringBuilder Charsets System Math
    IntArray LongArray ShortArray DoubleArray FloatArray BooleanArray CharArray ArrayDeque
    Regex MatchResult Result Lazy Comparator MutableCollection MutableIterable UInt ULong
    RESULT_OK RESULT_CANCELED""".split()
)

COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
DECL_ANY = re.compile(
    r"\b(?:class|interface|object|enum class|data class|sealed class|sealed interface"
    r"|annotation class|typealias|fun|val|var)\s+(\w+)"
)
TOP_LEVEL = re.compile(
    r"^(?:interface|class|object|enum class|data class|sealed class|sealed interface"
    r"|annotation class|typealias)\s+(\w+)",
    re.M,
)
STRING = re.compile(r'"(?:\\.|[^"\\])*"')
KW_NOT_CALL = {
    "if", "when", "for", "while", "catch", "return", "fun", "val", "var", "object",
    "class", "try", "else", "do", "is", "in", "super", "constructor", "package", "import",
}


# ───────────────────────────────── پیمایشِ رشته‌آگاه ─────────────────────────────────
def code_only(line: str) -> str:
    """محتوای رشته‌ها، کاراکترها و کامنت‌ها را با فاصله جایگزین می‌کند (طول حفظ می‌شود)."""
    out, i, n = [], 0, len(line)
    while i < n:
        c = line[i]
        if c in ('"', "'"):
            quote = c
            i += 1
            while i < n:
                if line[i] == "\\":
                    i += 2
                    continue
                if line[i] == quote:
                    i += 1
                    break
                i += 1
            out.append(" ")
            continue
        if c == "/" and i + 1 < n and line[i + 1] == "/":
            break
        if c == "/" and i + 1 < n and line[i + 1] == "*":
            j = line.find("*/", i + 2)
            i = (j + 2) if j >= 0 else n
            out.append(" ")
            continue
        out.append(c)
        i += 1
    return "".join(out)


def brace_delta(line: str) -> int:
    c = code_only(line)
    return c.count("{") - c.count("}")


def strip_comments(text: str) -> str:
    """کامنت‌ها را خالی می‌کند؛ شمارِ خطوط حفظ می‌شود (شرطِ لازم برای شمارهٔ خطِ درست)."""
    out = COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    assert out.count("\n") == text.count("\n"), "strip_comments must preserve line count"
    return out


def make_spans(text: str, indent: int = 4):
    """بازهٔ اعضای یک کلاس/object.

    یک عضو از خطِ اعلامش (به‌همراهِ کامنتِ چسبیدهٔ بالایش) تا نخستین خطی ادامه دارد که
    هم‌تورفتگیِ عضو باشد و عمقِ براکت صفر — یا تورفتگیِ کمتر (پایانِ خودِ کلاس/object).
    براکت‌های داخلِ رشته/تمپلیت شمرده نمی‌شوند، وگرنه `"x_${y}.csv"` بازه را می‌شکند.
    """
    lines = text.splitlines(True)
    pad, member, outer = " " * indent, re.compile(rf"^ {{{indent}}}\S"), re.compile(r"^\S")

    def decl_index(name: str) -> int:
        pat = re.compile(
            rf"^ {{{indent}}}(?:private |internal |public |protected )?(?:override |open |suspend )*fun {re.escape(name)}\("
        )
        for i, line in enumerate(lines):
            if pat.match(line):
                return i
        raise KeyError(name)

    def span(name: str) -> tuple[int, int]:
        i = decl_index(name)
        k = i
        while k > 0 and lines[k - 1].strip().startswith(("//", "/**", "*", "/*")):
            k -= 1
        depth, j = 0, i
        while True:
            depth += brace_delta(lines[j])
            j += 1
            if j >= len(lines):
                break
            if depth <= 0 and (member.match(lines[j]) or outer.match(lines[j])):
                break
        while j > i + 1 and lines[j - 1].strip() == "":
            j -= 1
        return k, j

    def text_of(name: str) -> str:
        a, b = span(name)
        return "".join(lines[a:b])

    def members() -> list[str]:
        pat = re.compile(
            rf"^ {{{indent}}}(?:private |internal |public |protected )?(?:override |open |suspend |inline )*fun (\w+)\(",
            re.M,
        )
        # بدونِ re.M الگویِ ^ فقط آغازِ رشته را می‌دید و فهرستِ تهی می‌داد؛ آن تهی بودن
        # با except KeyError بی‌صدا بلعیده می‌شد. اینجا صریح اثبات می‌کنیم عضو پیدا شده است.
        names = [m.group(1) for m in pat.finditer(text)]
        return names

    return span, text_of, members, lines


# ───────────────────────────────── نام‌های هم‌بسته ─────────────────────────────────
def same_package_names() -> set[str]:
    """نام‌های top-levelِ هم‌بسته که بدونِ import حل می‌شوند (از خودِ analyzer ریپو)."""
    spec = importlib.util.spec_from_file_location("_dk", ANALYZER)
    dk = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(dk)
    files, _ = dk._iter_files("decls")
    names: set[str] = set()
    for path in files:
        code = dk._strip_comments(pathlib.Path(path).read_text(encoding="utf-8", errors="replace"))
        for pattern, group in ((dk.DECL_TYPE, 2), (dk.DECL_FUN, 1), (dk.DECL_PROP, 2)):
            for m in pattern.finditer(code):
                names.add(m.group(group))
    return names


def imported_names(text: str) -> set[str]:
    names: set[str] = set()
    for fq, alias in re.findall(r"^import (\S+?)(?:\s+as\s+(\w+))?$", text, flags=re.M):
        if alias:
            names.add(alias)
        elif fq.endswith(".*"):
            names |= STAR_PROVIDES.get(fq[:-2], set())
        else:
            names.add(fq.rsplit(".", 1)[-1])
    return names


def unresolved_tokens(text: str, extra_ok: set[str] | None = None) -> set[str]:
    """شناسه‌های با حرفِ بزرگ که در scope این فایل حل نمی‌شوند."""
    body = re.sub(r"^import .+$|^package .+$", "", text, flags=re.M)
    body = strip_comments(body)
    body = STRING.sub('""', body)  # رشته‌ها ارجاعِ نوع نیستند
    ok = imported_names(text) | BUILTIN | set(DECL_ANY.findall(body)) | extra_ok or set()
    ok |= {chr(c) for c in range(65, 91)}  # پارامترهای جنریک: T، E، K، V
    return {
        m.group(1)
        for m in re.finditer(r"(?<![\w.])([A-Z]\w*)(?![\w])", body)
        if m.group(1) not in ok
    }


# ───────────────────────────────── اوراکلِ arity ─────────────────────────────────
def params_of(decl: str) -> tuple[int, int]:
    """(required, total) از فهرستِ پارامترهایِ یک اعلام."""
    i = decl.index("(")
    depth, j = 0, i
    while j < len(decl):
        if decl[j] == "(":
            depth += 1
        elif decl[j] == ")":
            depth -= 1
            if depth == 0:
                break
        j += 1
    inner = decl[i + 1 : j]
    if not inner.strip():
        return 0, 0
    parts, depth, cur = [], 0, ""
    for ch in inner:
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return sum(0 if "=" in p else 1 for p in parts), len(parts)


def count_args(text: str, start: int) -> int:
    """start = جایِ «(»؛ شمارِ آرگومان‌ها با عبورِ رشته‌آگاه از ()/[]/{} و `.`ها."""
    depth, j, args = 0, start, 1
    while j < len(text):
        c = text[j]
        if c == '"':
            j += 1
            while j < len(text):
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == '"':
                    break
                j += 1
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                break
        elif c == "," and depth == 1:
            args += 1
        j += 1
    return 0 if not text[start + 1 : j].strip() else args


def signature_table(text: str, scope: str, indent: int = 4) -> dict[tuple[str, str], tuple[int, int]]:
    table = {}
    for m in re.finditer(
        rf"^ {{{indent}}}(?:private |internal |public |protected )?(?:override |open )?(suspend )?fun (\w+)\(",
        text,
        flags=re.M,
    ):
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_end = text.find("\n", m.start())
        table[(scope, m.group(2))] = params_of(text[line_start:line_end])
    return table


# ───────────────────────────────── نقشهٔ پین ─────────────────────────────────
HELPER = re.compile(r"^(assert\w+|kt|_kotlin_\w+|read_text|open|get)$")
NEGATIVE = {"assertNotIn", "assertNotRegex", "notin"}


# فایل‌های تستی که حتماً باید در کورپس باشند. اگر readdirِ فایل‌سیستم لحظه‌ای بلنگد
# (اتفاقِ مشاهده‌شده در این sandbox: `ls DIR` شکست خورد ولی `find DIR` و Python سالم بودند)،
# یک کورپسِ ناقص بی‌صدا گزارش می‌دهد «پینی نیست» و مجوزِ شکستنِ تست‌ها می‌شود.
# پس فهرست از indexِ git خوانده می‌شود (معتبر، بدونِ وابستگی به readdir) و کامل بودنش
# با assert اثبات می‌شود.
REQUIRED_TESTS = {"test_android_resources_static.py"}
MIN_TEST_FILES = 100


def test_files() -> list[pathlib.Path]:
    listed = git("ls-files", "--", "*/test_*.py", "test_*.py").split()
    out, missing = [], []
    for f in listed:
        p = ROOT / f
        (out if p.exists() else missing).append(p)
    if missing:
        raise SystemExit(f"ABORT: {len(missing)} فایلِ تستِ tracked روی دیسک نیست: {[str(m)[:60] for m in missing[:3]]}")
    names = {p.name for p in out}
    absent = REQUIRED_TESTS - names
    if absent:
        raise SystemExit(f"ABORT: کورپسِ تست ناقص است، اینها نیستند: {sorted(absent)}")
    if len(out) < MIN_TEST_FILES:
        raise SystemExit(f"ABORT: کورپسِ تست فقط {len(out)} فایل دارد (< {MIN_TEST_FILES}) — قابلِ اعتماد نیست")
    return sorted(out)


def collect_pins(path: pathlib.Path):
    """-> (فایل‌های .ktِ مرجع‌شده، [(لیترال, نوع)]) برای یک فایلِ تست."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    kts: set[str] = set()
    lits: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.endswith(".kt"):
            kts.add(node.value)
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "") or ""
            if HELPER.match(name):
                for a in list(node.args) + [k.value for k in node.keywords]:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        kind = "not" if name in NEGATIVE else ("regex" if "Regex" in name else "lit")
                        lits.append((a.value, kind))
        if isinstance(node, ast.Compare) and any(isinstance(o, (ast.In, ast.NotIn)) for o in node.ops):
            neg = all(isinstance(o, ast.NotIn) for o in node.ops)
            for side in [node.left] + node.comparators:
                if isinstance(side, ast.Constant) and isinstance(side.value, str):
                    lits.append((side.value, "not" if neg else "lit"))
    return kts, lits


def matches(literal: str, kind: str, text: str) -> bool:
    if kind == "not":
        return False
    if kind == "regex":
        try:
            return re.search(literal, text) is not None
        except re.error:
            return literal in text
    return len(literal) >= 3 and literal in text


def member_blocks(text: str, indent: int = 4) -> list[tuple[str, str]]:
    """بلوکِ هر عضوِ تابع (با کامنتِ چسبیدهٔ بالایش) — دانه‌بندیِ درست برای استخراجِ تابع."""
    out = []
    span, text_of, members, _ = make_spans(text, indent)
    seen = members()
    for name in seen:
        try:
            out.append((name, text_of(name)))
        except KeyError:
            continue
    if seen and not out:
        raise SystemExit(f"ABORT: {len(seen)} عضو پیدا شد ولی هیچ بازه‌ای ساخته نشد — الگویِ decl_index را ببین")
    return out


def pin_map(corpus, kt_path: pathlib.Path, granularity: str = "member") -> tuple[list, list, list]:
    """برای یک فایلِ Kotlin: (پین‌های سخت، پین‌های نرم، پین‌های منفی).

    پینِ سخت = لیترالی که امروز در فایل match می‌شود ولی پس از حذفِ آن بلوک دیگر نمی‌شود —
    یعنی دقیقاً همان چیزی که تست مشاهده می‌کند.

    دانه‌بندی مهم است: با `top` بلوکِ یک کلاس یعنی **کلِ فایل**، پس هر لیترالی «سخت»
    می‌شود و ابزار بی‌فایده مثبتِ کاذب می‌دهد. برای استخراجِ تابع، دانه‌بندیِ `member`
    (هر تابعِ عضو) درست است.

    پینِ منفی (`assertNotIn`) هرگز مانعِ جابه‌جایی نیست — بیرون بردنِ متن فقط کمکش می‌کند —
    ولی **قیدِ چه‌چیزی-نباید-اضافه-شود** است، پس همیشه گزارش می‌شود.
    """
    full = kt_path.read_text(encoding="utf-8")
    name = kt_path.name
    hard, soft, negative = [], [], []
    blocks = member_blocks(full) if granularity == "member" else []
    for m in re.finditer(r"^(interface|class|object|enum class|data class|sealed class)\s+(\w+)", full, flags=re.M):
        if granularity == "member":
            continue
        i = full.find("{", m.end())
        if i < 0:
            continue
        depth, j = 0, i
        while j < len(full):
            if full[j] == "{":
                depth += 1
            elif full[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        blocks.append((m.group(2), full[m.start() : j + 1]))
    for test_path, (kts, lits) in corpus.items():
        if name not in kts:
            continue
        for lit, kind in lits:
            if kind == "not":
                # assertNotIn: همیشه گزارش شود؛ «حضور دارد» یعنی تست همین حالا هم شکست
                negative.append((test_path.name, lit, lit in full))
                continue
            if not matches(lit, kind, full):
                continue
            for block_name, block in blocks:
                remaining = full.replace(block, "", 1)
                if not matches(lit, kind, remaining):
                    hard.append((test_path.name, kind, lit, block_name))
                elif matches(lit, kind, block):
                    soft.append((test_path.name, kind, lit, block_name))
    return hard, soft, negative


# ───────────────────────────────── git ─────────────────────────────────
def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def tracked_files(*globs: str) -> list[str]:
    out: list[str] = []
    for g in globs:
        out += subprocess.run(
            ["git", "ls-files", g], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.split()
    return out


def status_split() -> tuple[list[str], list[str]]:
    lines = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    modified = [l[3:] for l in lines if l.startswith(" M") and l.endswith(".kt")]
    untracked = [l[3:] for l in lines if l.startswith("??") and l.endswith(".kt")]
    return modified, untracked


# ───────────────────────────────── بررسی‌ها ─────────────────────────────────
def check_types(paths: list[pathlib.Path], differential: bool, allow: set[str]) -> list[str]:
    extra = allow | same_package_names()
    fails = []
    for p in paths:
        text = p.read_text(encoding="utf-8")
        bad = unresolved_tokens(text, extra)
        rel = p.relative_to(ROOT) if p.is_absolute() else p
        if differential:
            try:
                old = git("show", f"HEAD:{rel}")
            except subprocess.CalledProcessError:
                print(f"  [types] {rel.name}: فایلِ تازه — {len(bad)} توکنِ حل‌نشده {sorted(bad)[:6]}")
                if bad:
                    fails.append(f"{rel.name}: {sorted(bad)}")
                continue
            gained = bad - unresolved_tokens(old, extra)
            tag = "OK" if not gained else "REGRESSION"
            print(f"  [types] {rel.name}: حل‌نشده={len(bad)} تازه-دربرابر-HEAD={len(gained)} {tag}")
            if gained:
                fails.append(f"{rel.name}: توکن‌های تازهٔ حل‌نشده {sorted(gained)}")
        else:
            print(f"  [types] {rel.name}: {len(bad)} توکنِ حل‌نشده {sorted(bad)[:6] or ''}")
            if bad:
                fails.append(f"{rel.name}: {sorted(bad)}")
    return fails


def check_arity(paths: list[pathlib.Path], scopes: dict[str, str]) -> list[str]:
    tables: dict[tuple[str, str], tuple[int, int]] = {}
    for p in paths:
        tables |= signature_table(p.read_text(encoding="utf-8"), scopes.get(p.name, p.stem))
    fails, checked = [], 0
    for p in paths:
        scope = scopes.get(p.name, p.stem)
        text = p.read_text(encoding="utf-8")
        for m in re.finditer(r"(?<![\w.])(\w+)\(", text):
            name = m.group(1)
            if name in KW_NOT_CALL:
                continue
            line_start = text.rfind("\n", 0, m.start()) + 1
            if re.match(r"\s*(?:private |internal |public |protected )?(?:override |open )?(?:suspend )?fun ",
                        text[line_start : m.start() + 4]):
                continue  # خودِ اعلام است، نه فراخوانی
            prefix = text[max(0, m.start() - 28) : m.start()]
            q = re.search(r"([A-Z]\w*|repository|api)\.$", prefix)
            target = scopes.get(q.group(1) + ".kt", q.group(1)) if q else scope
            if (target, name) not in tables:
                continue
            n = count_args(text, m.end() - 1)
            req, total = tables[(target, name)]
            checked += 1
            if not (req <= n <= total):
                line = text[: m.start()].count("\n") + 1
                fails.append(f"{p.name}:{line} {name}({n}) ولی اعلام req={req} total={total}")
    print(f"  [arity] {checked} نقطهٔ فراخوانی سنجیده شد، {len(fails)} ناهمخوانی")
    for f in fails[:10]:
        print(f"      !! {f}")
    return fails


def check_members(paths: list[pathlib.Path]) -> list[str]:
    fails = []
    for p in paths:
        text = p.read_text(encoding="utf-8")
        sigs = collections.Counter()
        for m in re.finditer(
            r"^    (?:private |internal |public |protected )?(?:override |open )?(?:suspend )?fun (\w+)\(([^)]*)\)",
            text,
            flags=re.M,
        ):
            sigs[(m.group(1), len([x for x in m.group(2).split(",") if x.strip()]))] += 1
        dup = [k for k, c in sigs.items() if c > 1]
        print(f"  [members] {p.name}: {sum(sigs.values())} عضو، {len(sigs)} امضایِ متمایز، تکراری={dup or 'none'}")
        if dup:
            fails.append(f"{p.name}: امضایِ تکراری {dup}")
    return fails


def check_names(allow_born: set[str]) -> list[str]:
    def tops(text: str) -> set[str]:
        return set(TOP_LEVEL.findall(strip_comments(text)))

    head: set[str] = set()
    for f in tracked_files("*.kt"):
        head |= tops(git("show", f"HEAD:{f}"))
    now: set[str] = set()
    counter: collections.Counter = collections.Counter()
    for p in sorted((ROOT / "KharazmiAdmin").rglob("*.kt")):
        for n in tops(p.read_text(encoding="utf-8")):
            now.add(n)
            counter[n] += 1
    born, gone = now - head, head - now
    dupes = [n for n, c in counter.items() if c > 1]
    print(f"  [names] HEAD={len(head)} now={len(now)} born={sorted(born)} gone={sorted(gone) or 'none'} dup={dupes or 'none'}")
    fails = []
    if gone:
        fails.append(f"نام‌های top-level گم‌شده: {sorted(gone)}")
    if dupes:
        fails.append(f"نامِ top-level تکراری (Duplicate JVM class name): {dupes}")
    unexpected = born - allow_born
    if unexpected:
        fails.append(f"نامِ تازهٔ خارج از فهرستِ مجاز: {sorted(unexpected)}")
    return fails


def check_pins(only: str | None, granularity: str) -> list[str]:
    corpus: dict[pathlib.Path, tuple[set[str], list]] = {}
    for t in test_files():
        try:
            kts, lits = collect_pins(t)
        except SyntaxError:
            continue
        if kts:
            corpus[t] = (kts, lits)
    kt_total = len({k for kts, _ in corpus.values() for k in kts})
    print(f"  [pins] کورپس: {len(corpus)} فایلِ تست و {kt_total} فایلِ .ktِ مرجع")
    fails: list[str] = []
    targets = [APP_SRC / only] if only else sorted(APP_SRC.glob("*Activity.kt"))
    for kt in targets:
        if not kt.exists():
            fails.append(f"فایلِ هدف نیست: {kt}")
            continue
        hard, soft, negative = pin_map(corpus, kt, granularity)
        head = (f"  [pins] {kt.name} (granularity={granularity}): "
                f"سخت={len(hard)} نرم={len(soft)} منفی={len(negative)}")
        print(head)
        for t, kind, lit, block in dict.fromkeys(hard):
            print(f"      سخت  {t} [{kind}] {lit[:70]!r} ← بلوکِ {block}")
        for t, lit, present in dict.fromkeys(negative):
            state = "الآن هست (پس حق ندارم جابه‌جایش کنم)" if present else "الآن نیست (پس حق ندارم اضافه‌اش کنم)"
            print(f"      منفی {t} {lit[:60]!r} ← {state}")
        if not hard and not negative and not soft:
            print("      هیچ پینی ندارد")
    return fails

def norm_body(text: str) -> str:
    """بدنه را برای مقایسه نرمال می‌کند: کامنت/تورفتگی/فضای اضافی حذف می‌شود.

    پیش از هر یکسان‌سازیِ تابع‌های هم‌نام باید این مقایسه انجام شود؛ درسِ بک‌اند
    (`_now_str_with_seconds` با %H:%M:%S در برابرِ `_now_str` با %H:%M) می‌گوید
    دو هم‌نام با منطقِ متفاوت هرگز نباید یکی شوند.
    """
    out = []
    for line in strip_comments(text).splitlines():
        c = code_only(line).strip()
        if c:
            out.append(re.sub(r"\s+", " ", c))
    return "\n".join(out)


def check_duplicates(names: list[str]) -> list[str]:
    """همهٔ تعریف‌های هم‌نام در پکیجِ اپ را می‌یابد و بدنه‌ها را گروه‌بندی می‌کند."""
    found: dict[str, list] = {n: [] for n in names}
    for f in sorted(APP_SRC.rglob("*.kt")):
        src = f.read_text(encoding="utf-8")
        for name, block in member_blocks(src):
            short = name.split(".").pop()
            if short in found:
                sig = block.strip().splitlines()[0] if block.strip() else ""
                found[short].append((f, sig, block))
    fails: list[str] = []
    for n in names:
        hits = found[n]
        print(f"  [dup] {n}: {len(hits)} تعریف")
        if len(hits) < 2:
            for f, sig, _ in hits:
                print(f"      تنها: {f.name} :: {sig.strip()[:84]}")
            continue
        groups: dict[str, list] = {}
        for f, sig, block in hits:
            idx = block.find("{")           # خطِ امضا از مقایسه بیرون می‌ماند
            groups.setdefault(norm_body(block[idx + 1:] if idx >= 0 else block), []).append((f, sig, block))
        for i, (body, members) in enumerate(groups.items(), 1):
            print(f"      گروه {i}: {len(members)} عضو، {len(body.splitlines())} خطِ نرمال — "
                  + "، ".join(f"{f.name}" for f, _, _ in members))
            for f, sig, _ in members:
                print(f"          {f.name} :: {sig.strip()[:88]}")
        if len(groups) == 1:
            print(f"      ⇒ بدنه‌ها یکسان‌اند: یکسان‌سازیِ {n} امن است")
        else:
            print(f"      ⇒ {len(groups)} بدنهٔ متفاوت: {n} را یکی نکن")
            fails.append(f"{n}: {len(groups)} بدنهٔ متفاوت — یکسان‌سازی ممنوع")
        print()
    return fails


def check_spans(paths: list[pathlib.Path], want: list[str]) -> list[str]:
    """بازهٔ دقیقِ اعضا را چاپ می‌کند — ورودیِ استخراجِ کلمه‌به‌کلمه."""
    fails = []
    for p in paths:
        text = p.read_text(encoding="utf-8")
        span, text_of, members, lines = make_spans(text)
        names = want or members()
        print(f"  [spans] {p.name}: {len(members())} عضو")
        for n in names:
            try:
                a, b = span(n)
            except KeyError:
                print(f"      !! عضو پیدا نشد: {n}")
                fails.append(f"{p.name}: {n} پیدا نشد")
                continue
            body = text_of(n)
            balanced = sum(brace_delta(l) for l in lines[a:b])
            flag = "" if balanced == 0 else f"  !! ترازِ براکت={balanced}"
            if balanced:
                fails.append(f"{p.name}: {n} ترازِ براکت ندارد")
            print(f"      {n:28s} خطوط {a + 1}..{b} ({b - a} خط){flag}")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="فایل‌های Kotlin موردِ بررسی (مسیر یا نام در پوشهٔ اپ)")
    ap.add_argument("--spans", nargs="*", default=None, metavar="MEMBER",
                    help="چاپِ بازهٔ دقیقِ اعضا (بی‌نام = همهٔ اعضا)")
    ap.add_argument("--types", action="store_true", help="اوراکلِ حلِ نوع")
    ap.add_argument("--diff", action="store_true", help="حلِ نوعِ تفاضلی در برابرِ HEAD")
    ap.add_argument("--arity", action="store_true", help="اوراکلِ شمارِ آرگومان‌ها")
    ap.add_argument("--members", action="store_true", help="یکتاییِ امضایِ اعضا")
    ap.add_argument("--names", action="store_true", help="نام‌های top-level در برابرِ HEAD")
    ap.add_argument("--pins", action="store_true", help="نقشهٔ پینِ سراسری")
    ap.add_argument("--allow-born", default="", help="نام‌های تازهٔ مجاز، با کاما")
    ap.add_argument("--scopes", default="", help="نگاشتِ «فایل=scope» با کاما، برای --arity")
    ap.add_argument("--duplicates", default="", help="نام‌های هم‌نام، با کاما، برای مقایسهٔ بدنه بین فایل‌ها")
    ap.add_argument("--changed", action="store_true", help="خودکار: فایل‌های .ktِ تغییریافته + تازه")
    ap.add_argument("--granularity", choices=("member", "top"), default="member",
                    help="دانه‌بندیِ بلوک برای --pins: member=هر تابع (پیش‌فرض)، top=بلوکِ سطحِ بالا")
    args = ap.parse_args()

    if not any([args.types, args.diff, args.arity, args.members, args.names, args.pins,
                args.duplicates]) and args.spans is None:
        ap.error("دستِ کم یکی از --types/--diff/--arity/--members/--names/--pins/--duplicates لازم است")

    paths: list[pathlib.Path] = []
    for f in args.files:
        p = pathlib.Path(f)
        if not p.exists():
            p = APP_SRC / f
        if not p.exists():
            print(f"  !! فایل پیدا نشد: {f}")
            return 2
        paths.append(p)
    if args.changed:
        mod, new = status_split()
        paths += [ROOT / f for f in mod + new if (ROOT / f) not in paths]

    scopes = {}
    for pair in filter(None, (s.strip() for s in args.scopes.split(","))):
        if "=" in pair:
            fname, scope = pair.split("=", 1)
            scopes[fname] = scope
    allow = {n.strip() for n in args.allow_born.split(",") if n.strip()}

    fails: list[str] = []
    if args.spans is not None and paths:
        fails += check_spans(paths, args.spans)
    if args.pins:
        fails += check_pins(args.files[0] if len(args.files) == 1 and args.files[0].endswith(".kt") else None,
                          args.granularity)
    if paths and (args.types or args.diff):
        fails += check_types(paths, differential=args.diff, allow=allow)
    if paths and args.arity:
        fails += check_arity(paths, scopes)
    if paths and args.members:
        fails += check_members(paths)
    if args.duplicates:
        fails += check_duplicates([x.strip() for x in args.duplicates.split(",") if x.strip()])
    if args.names:
        fails += check_names(allow)

    print()
    if fails:
        print("شکست:")
        for f in fails:
            print("  -", f)
        return 1
    print("همهٔ بررسی‌های خواسته‌شده سبز")
    return 0


if __name__ == "__main__":
    sys.exit(main())
