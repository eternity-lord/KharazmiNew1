"""ابزارِ ریفکتور: انتقالِ بدنهٔ یک handler به لایهٔ سرویس و ساختنِ «پوستهٔ HTTP».

این اسکریپت همان کاری را می‌کند که فاز P3b با آن انجام شد و **تضمین‌هایش مکانیکی است**،
نه دستی:

  * decoratorها + امضای handler **بایت‌به‌بایت** در پوسته کپی می‌شوند ⇒ OpenAPI عوض نمی‌شود؛
  * docstringِ handler در پوسته می‌ماند (FastAPI آن را `description` منتشر می‌کند)؛
  * کامنت‌های بینِ امضا و اولین عبارت، همراهِ بدنه منتقل می‌شوند؛
  * بدنهٔ منتقل‌شده بایت‌به‌بایت همان کدِ قبلی است (راستی‌آزمایی‌اش با
    `refactor_verify_move.py` است)؛
  * `import X as Y` دقیقاً با همان alias بازتولید می‌شود — درسِ P3a: گم‌شدنِ یک alias
    یک NameErrorِ نهفته می‌سازد که تستِ سبز هم نمی‌گیردش؛
  * اگر نامِ آزادی به تابع/ثابتِ **داخلِ همان روتر** اشاره کند، انتقال متوقف می‌شود
    (چون سرویس مجبور می‌شد از روتر import کند = چرخه). اول باید آن نام منتقل شود.

چرا handler حذف نمی‌شود و فقط واگذار می‌کند؟ چون امضایش قراردادِ OpenAPI است و ده‌ها تست
و `scripts/run_financial_audit.py` این توابع را مستقیم — گاهی با آرگومان پوزیشنال — از
`routers.*` صدا می‌زنند. قراردادِ کامل در `services/__init__.py` مستند شده.

استفاده:
    # تحلیلِ بدون تغییر (چه importهایی لازم است، چه نام‌هایی مانع‌اند)
    python Kharazmi_Server/scripts/refactor_move_body.py \
        --router routers/finance.py --handler refund_transaction \
        --service services/payments.py --dry-run

    # اجرای انتقال
    python Kharazmi_Server/scripts/refactor_move_body.py \
        --router routers/finance.py --handler refund_transaction \
        --service services/payments.py --module-doc /tmp/doc.txt

بعد از هر انتقال، این گیت‌ها اجباری‌اند (درسِ دو باگِ واقعیِ P3a و P3b):
    ruff check . --select F821          # باید همان تعدادِ بیس‌لاین بماند
    ruff check . --statistics           # مقایسهٔ rule-by-rule با بیس‌لاین
    python Kharazmi_Server/scripts/refactor_verify_move.py --base HEAD ...
و بعد اوراکل OpenAPI + هر دو سوئیت تست (دو پروسسِ جدا) + گارد md5 دیتابیس واقعی.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import collections
import pathlib
import sys

SERVER = pathlib.Path(__file__).resolve().parents[1]
BUILTINS = set(dir(builtins))

STDLIB = {
    "base64", "calendar", "collections", "copy", "csv", "datetime", "decimal", "functools",
    "hashlib", "html", "io", "itertools", "json", "logging", "math", "os", "pathlib",
    "random", "re", "secrets", "shutil", "tempfile", "textwrap", "time", "typing", "uuid",
}
THIRD_PARTY = {
    "apscheduler", "bcrypt", "fastapi", "httpx", "jose", "jwt", "limits", "openpyxl",
    "passlib", "pydantic", "reportlab", "requests", "slowapi", "sqlalchemy", "starlette",
}


def _bucket(module: str | None) -> str:
    root = (module or "").split(".")[0]
    if root in STDLIB:
        return "std"
    if root in THIRD_PARTY:
        return "third"
    return "first"


def module_table(tree: ast.AST) -> dict[str, tuple[str, str | None, str | None, str | None]]:
    """نام‌های سطحِ ماژول → («from»/«import»/«local»/«const», ماژول, نام اصلی, alias)."""
    table: dict[str, tuple[str, str | None, str | None, str | None]] = {}

    def visit(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    table[alias.asname or alias.name] = ("from", node.module, alias.name, alias.asname)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    key = (alias.asname or alias.name).split(".")[0]
                    table[key] = ("import", alias.name, None, alias.asname)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                table[node.name] = ("local", node.name, None, None)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        table[target.id] = ("const", target.id, None, None)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                table[node.target.id] = ("const", node.target.id, None, None)
            elif isinstance(node, (ast.If, ast.Try, ast.With, ast.For)):
                for attr in ("body", "orelse", "finalbody", "handlers"):
                    visit(getattr(node, attr, None) or [])

    visit(tree.body)  # type: ignore[arg-type]
    return table


def free_names(fn: ast.AST) -> collections.Counter[str]:
    """نام‌های آزادی که بدنهٔ `fn` مصرف می‌کند (بدونِ bindingهای محلی و builtins)."""
    local: set[str] = set()
    for node in ast.walk(fn):
        # def/class تودرتو نامِ خودش را در دامنهٔ بیرونی bind می‌کند ⇒ با بدنه منتقل می‌شود
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node is not fn:
            local.add(node.name)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            args = node.args
            local |= {a.arg for a in args.posonlyargs + args.args + args.kwonlyargs}
            if args.vararg:
                local.add(args.vararg.arg)
            if args.kwarg:
                local.add(args.kwarg.arg)
        elif isinstance(node, ast.comprehension):
            for target in ast.walk(node.target):
                if isinstance(target, ast.Name):
                    local.add(target.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            local.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            local.add(node.id)
        elif isinstance(node, ast.arg):
            local.add(node.arg)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                local.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local.add((alias.asname or alias.name).split(".")[0])

    used: collections.Counter[str] = collections.Counter()
    for node in ast.walk(fn):
        if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                and node.id not in local and node.id not in BUILTINS):
            used[node.id] += 1
        elif (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id not in local and node.value.id not in BUILTINS):
            used[node.value.id] += 1
    return used


def sig_end_index(lines: list[str], fn: ast.AST) -> int:
    """شمارهٔ (۱-مبنا) خطی که امضا را می‌بندد: اولین `:` در عمقِ صفر."""
    depth = 0
    start = getattr(fn, "lineno", 1)
    end = getattr(fn, "end_lineno", start)
    for i in range(start - 1, end):
        depth += lines[i].count("(") + lines[i].count("[") + lines[i].count("{")
        depth -= lines[i].count(")") + lines[i].count("]") + lines[i].count("}")
        if depth <= 0 and lines[i].rstrip().endswith(":"):
            return i + 1
    raise AssertionError(f"signature end not found for {getattr(fn, 'name', '?')}")


def _split_parts(lines: list[str], fn: ast.AST, src: str) -> dict[str, object]:
    doc = None
    body = getattr(fn, "body", None)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        doc = body[0]
    sig_end = sig_end_index(lines, fn)
    signature = "".join(lines[fn.lineno - 1:sig_end])
    docstring = "".join(lines[doc.lineno - 1:doc.end_lineno]) if doc else ""
    if doc:
        # کامنت‌های بینِ امضا و docstring همراهِ بدنه می‌روند؛ خودِ docstring در پوسته می‌ماند
        body_text = "".join(lines[sig_end:doc.lineno - 1]) + "".join(lines[doc.end_lineno:fn.end_lineno])
    else:
        body_text = "".join(lines[sig_end:fn.end_lineno])
    decorators = [ast.get_source_segment(src, d) for d in getattr(fn, "decorator_list", [])]
    args = getattr(fn, "args", None)
    params = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs] if args else []
    return {
        "signature": signature, "docstring": docstring, "body": body_text,
        "body_span": (sig_end + 1, fn.end_lineno), "fn_span": (fn.lineno, fn.end_lineno),
        "sig_end": sig_end, "decorators": decorators, "params": params,
        "src": "".join(lines[fn.lineno - 1:fn.end_lineno]), "start": fn.lineno,
        "is_async": isinstance(fn, ast.AsyncFunctionDef),
        "dec_start": min([d.lineno for d in getattr(fn, "decorator_list", [])] + [fn.lineno]),
    }


def _find_node(rel_path: str, name: str) -> tuple[pathlib.Path, list[str], ast.AST, str]:
    path = SERVER / rel_path
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            return path, lines, node, src
    raise StopIteration(f"{name} not found at module level in {rel_path}")


def find_assign_text(src: str, name: str) -> tuple[None, None, ast.stmt]:
    """گزارهٔ Assign/AnnAssignِ سطحِ ماژول (حتی داخل if/try) برای `name`، روی متنِ داده‌شده."""
    tree = ast.parse(src)
    found = [
        node for node in ast.walk(tree)
        if (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets))
        or (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name)
    ]
    if len(found) != 1:
        raise AssertionError(f"{name}: {len(found)} assignments found")
    return None, None, found[0]


def find_assign(rel_path: str, name: str) -> tuple[pathlib.Path, list[str], ast.stmt]:
    """همان `find_assign_text` ولی روی فایلی از روترها."""
    path = SERVER / rel_path
    src = path.read_text(encoding="utf-8")
    _unused, _also_unused, node = find_assign_text(src, name)
    return path, src.splitlines(keepends=True), node


def analyse(rel_router: str, name: str) -> dict[str, object]:
    """تحلیلِ یک نامِ سطحِ ماژول برای انتقال: امضا، بدنه، importهای لازم، و موانع."""
    path, lines, fn, src = _find_node(rel_router, name)
    parts = _split_parts(lines, fn, src)
    if not str(parts["body"]).strip() and isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise AssertionError(f"empty body for {name}")
    table = module_table(ast.parse(src))

    saved = getattr(fn, "decorator_list", [])
    fn.decorator_list = []          # `router`/`limiter` فقط در decoratorاند و در پوسته می‌مانند
    used = free_names(fn)
    fn.decorator_list = saved
    params = set(parts["params"])   # type: ignore[arg-type]
    args = getattr(fn, "args", None)
    if args is not None:
        if args.vararg:
            params.add(args.vararg.arg)
        if args.kwarg:
            params.add(args.kwarg.arg)

    needed: dict[str, tuple[str, str | None, str | None, str | None]] = {}
    unresolved: list[str] = []
    cyclic: list[str] = []
    for free in sorted(k for k in used if k not in params):
        entry = table.get(free)
        if entry is None:
            unresolved.append(free)
        elif entry[0] in ("local", "const"):
            cyclic.append(free)
        else:
            needed[free] = entry
    parts.update({
        "path": path, "lines": lines, "fn": fn, "src": src, "needed": needed,
        "unresolved": unresolved, "cyclic": cyclic,
    })
    return parts


def imports_block(needed: collections.abc.Mapping[str, tuple]) -> str:
    """ساختِ بلوکِ import از نام‌های لازم (isort بعداً مرتب/ادغام می‌کند)."""
    groups: dict[str, list[str]] = {"std": [], "third": [], "first": []}
    froms: dict[str | None, list[tuple[str, str | None]]] = collections.defaultdict(list)
    plains: dict[str, str | None] = {}
    for entry in needed.values():
        kind, module, orig, asname = entry[:4]
        if kind == "provided":
            continue                      # در ماژولِ مقصد از قبل تعریف شده
        if kind == "import":
            plains[module] = asname
        elif kind == "from":
            froms[module].append((orig, asname))
    for module, names in froms.items():
        unique = sorted(set(names))
        rendered = ", ".join(f"{o} as {a}" if a and a != o else o for o, a in unique)
        if len(rendered) + len(module or "") > 76:
            inner = "".join(f"    {o} as {a},\n" if a and a != o else f"    {o},\n" for o, a in unique)
            stmt = f"from {module} import (\n{inner})"
        else:
            stmt = f"from {module} import {rendered}"
        groups[_bucket(module)].append(stmt)
    for module, asname in plains.items():
        stmt = f"import {module} as {asname}" if asname and asname != module else f"import {module}"
        groups[_bucket(module)].append(stmt)
    out: list[str] = []
    for key in ("std", "third", "first"):
        if groups[key]:
            out.extend(sorted(groups[key]))
            out.append("")
    while out and out[-1] == "":
        out.pop()
    return ("\n".join(out) + "\n") if out else ""


def merge_imports(text: str, needed: collections.abc.Mapping[str, tuple]) -> str:
    """هر importِ غایب را اضافه می‌کند؛ `ruff --select I001 --fix` مرتب و ادغام می‌کند."""
    tree = ast.parse(text)
    have: set[str] = set()
    last = 0
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            have |= {alias.asname or alias.name for alias in node.names}
            last = max(last, node.end_lineno)
        elif isinstance(node, ast.Import):
            have |= {(alias.asname or alias.name).split(".")[0] for alias in node.names}
            last = max(last, node.end_lineno)
    missing = {k: v for k, v in needed.items() if k not in have and v[0] != "provided"}
    if not missing:
        return text
    lines = text.splitlines(keepends=True)
    lines.insert(last, "\n" + imports_block(missing))
    out = "".join(lines)
    ast.parse(out)
    return out


def shell_text(info: dict[str, object], service_attr: str, note: str) -> str:
    """ساختِ پوستهٔ HTTP: decorator + امضا + docstring (همگی بایت‌به‌بایت) + یک return."""
    fn = info["fn"]
    assert isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
    await_ = "await " if info["is_async"] else ""
    args = fn.args
    params = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]
    if args.vararg:
        params.append("*" + args.vararg.arg)
    if args.kwarg:
        params.append("**" + args.kwarg.arg)
    decorators = "".join(f"@{d}\n" for d in info["decorators"])   # type: ignore[union-attr]
    docstring = info["docstring"] if str(info["docstring"]).strip() else ""
    note_block = "".join(f"    # {line}\n" if line.strip() else "    #\n" for line in note.split("\n"))
    return (f"{decorators}{info['signature']}{docstring}{note_block}"
            f"    return {await_}{service_attr}({', '.join(params)})\n")


def apply_move(info: dict[str, object], service_rel: str, service_attr: str, note: str,
               svc_docstring: str | None = None, module_doc: str = "") -> bool:
    """انتقالِ بدنه به ماژولِ سرویس و جایگزینیِ handler با پوسته. True یعنی الحاق به فایلِ موجود."""
    svc_path = SERVER / service_rel
    header = str(info["signature"])
    if svc_docstring:
        header += '    """' + svc_docstring + '"""\n'
    block = header + str(info["body"])
    if not block.endswith("\n"):
        block += "\n"
    if svc_path.exists():
        current = svc_path.read_text(encoding="utf-8")
        sep = "\n\n\n" if current.rstrip("\n").count("\n") else "\n\n"
        svc_path.write_text(merge_imports(current.rstrip("\n") + sep + block,
                                         info["needed"]),  # type: ignore[arg-type]
                            encoding="utf-8")
        merged = True
    else:
        svc_path.parent.mkdir(parents=True, exist_ok=True)
        svc_path.write_text(module_doc + imports_block(info["needed"]) + "\n\n" + block,  # type: ignore[arg-type]
                            encoding="utf-8")
        merged = False
    lines = info["lines"]
    assert isinstance(lines, list)
    fn = info["fn"]
    assert isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
    start = int(info["dec_start"]) - 1                          # type: ignore[call-overload]
    new_lines = [*lines[:start], shell_text(info, service_attr, note), *lines[fn.end_lineno:]]
    path = info["path"]
    assert isinstance(path, pathlib.Path)
    path.write_text("".join(new_lines), encoding="utf-8")
    return merged


def _leading_comment(lines: list[str], index: int) -> tuple[int, str]:
    """بلوکِ کامنتِ چسبیده به خطِ `index` (۰-مبنا) را هم برمی‌دارد تا با کدش برود."""
    start = index
    while start > 0 and lines[start - 1].lstrip().startswith("#"):
        start -= 1
    return start, "".join(lines[start:index])


def move_plain(rel_router: str, name: str, target_rel: str, module_doc: str = "") -> int:
    """انتقالِ **بایت‌به‌بایت** یک تابع/کلاس (بدون route)؛ بدونِ پوسته. تعداد ارجاعِ باقی‌مانده را برمی‌گرداند."""
    info = analyse(rel_router, name)
    fn = info["fn"]
    assert isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    lines = info["lines"]
    assert isinstance(lines, list)
    start, comment = _leading_comment(lines, fn.lineno - 1)
    block = comment + "".join(lines[fn.lineno - 1:fn.end_lineno])
    target = SERVER / target_rel
    if target.exists():
        current = target.read_text(encoding="utf-8")
        sep = "\n\n\n" if current.rstrip("\n").count("\n") else "\n\n"
        target.write_text(merge_imports(current.rstrip("\n") + sep + block,
                                       info["needed"]),  # type: ignore[arg-type]
                          encoding="utf-8")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(module_doc + imports_block(info["needed"]) + "\n\n" + block,  # type: ignore[arg-type]
                          encoding="utf-8")
    end = fn.end_lineno
    while end < len(lines) and lines[end].strip() == "":
        end += 1                                    # جداکنندهٔ خالیِ همان تابع هم می‌رود
    path = info["path"]
    assert isinstance(path, pathlib.Path)
    remaining = lines[:start] + lines[end:]
    path.write_text("".join(remaining), encoding="utf-8")
    left = sum(1 for line in remaining if name in line)
    print(f"  moved {name}: {fn.end_lineno - fn.lineno + 1} LOC (+{len(comment.splitlines())} comment) "
          f"-> {target_rel}; refs left in {rel_router}: {left}")
    return left


def move_constant(rel_router: str, name: str, target_rel: str, extra_imports: dict | None = None) -> int:
    """انتقالِ بایت‌به‌بایتِ یک ثابتِ سطحِ ماژول (با کامنتِ چسبیده‌اش)."""
    path, lines, node = find_assign(rel_router, name)
    start, comment = _leading_comment(lines, node.lineno - 1)
    block = comment + "".join(lines[node.lineno - 1:node.end_lineno])
    target = SERVER / target_rel
    current = target.read_text(encoding="utf-8") if target.exists() else ""
    sep = "\n\n\n" if current.rstrip("\n").count("\n") else "\n\n"
    text = (current.rstrip("\n") + sep + block) if current else block
    if extra_imports:
        text = merge_imports(text, extra_imports)
    target.write_text(text, encoding="utf-8")
    end = node.end_lineno
    while end < len(lines) and lines[end].strip() == "":
        end += 1
    remaining = lines[:start] + lines[end:]
    path.write_text("".join(remaining), encoding="utf-8")
    left = sum(1 for line in remaining if name in line)
    print(f"  moved const {name} -> {target_rel}; refs left in {rel_router}: {left}")
    return left


def add_import_from(rel_router: str, module: str, names: list[str]) -> None:
    """`names` را به `from <module> import ...` همان روتر اضافه (یا آن گزاره را ایجاد) می‌کند."""
    path = SERVER / rel_router
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    unique = list(dict.fromkeys(names))
    node = next((n for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == module), None)
    lines = src.splitlines(keepends=True)
    if node is not None:
        merged = sorted({(alias.name, alias.asname) for alias in node.names} | {(n, None) for n in unique})
        rendered = ", ".join(f"{o} as {a}" if a and a != o else o for o, a in merged)
        if len(rendered) + len(module) > 76:
            inner = "".join(f"    {o} as {a},\n" if a and a != o else f"    {o},\n" for o, a in merged)
            stmt = f"from {module} import (\n{inner})\n"
        else:
            stmt = f"from {module} import {rendered}\n"
        lines[node.lineno - 1:node.end_lineno] = [stmt]
    else:
        last = max((n.end_lineno for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))), default=0)
        lines.insert(last, f"from {module} import {', '.join(unique)}\n")
    path.write_text("".join(lines), encoding="utf-8")
    ast.parse(path.read_text(encoding="utf-8"))
    print(f"  {rel_router}: `from {module} import {', '.join(unique)}` ensured")


def ensure_service_import(rel_router: str, module_name: str) -> None:
    """`from services import <module_name>` را در روتر تضمین می‌کند."""
    add_import_from(rel_router, "services", [module_name])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--router", required=True, help="مسیرِ نسبیِ روتر، مثلاً routers/finance.py")
    parser.add_argument("--handler", required=True, help="نامِ تابع/کلاس/ثابت")
    parser.add_argument("--service", required=True, help="ماژولِ مقصد، مثلاً services/payments.py")
    parser.add_argument("--attr", help="پیشوندِ فراخوانی در پوسته (پیش‌فرض: نامِ ماژولِ مقصد)")
    parser.add_argument("--note", default="REFAC: بدنهٔ دامنه به لایهٔ سرویس رفت؛ این پوسته فقط لایهٔ HTTP است.",
                        help="کامنتِ داخلِ پوسته")
    parser.add_argument("--module-doc", help="فایلِ docstringِ ماژولِ تازه (فقط وقتی مقصد وجود ندارد)")
    parser.add_argument("--plain", action="store_true",
                        help="انتقالِ کاملِ بدونِ پوسته (برای هلپر/اسکیما/ثابت، نه route)")
    parser.add_argument("--dry-run", action="store_true", help="فقط تحلیل، بدونِ نوشتن")
    args = parser.parse_args(argv)

    try:
        info = analyse(args.router, args.handler)
    except StopIteration:
        _path, _lines, node = find_assign(args.router, args.handler)
        print(f"{args.handler}: constant at line {node.lineno}")
        if args.dry_run or args.plain:
            return 0
        move_constant(args.router, args.handler, args.service, {"os": ("import", "os", None, None)})
        return 0

    fn = info["fn"]
    assert isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    span = info["body_span"]
    assert isinstance(span, tuple)
    print(f"{args.handler}: def {info['fn_span']}, body {span[0]}-{span[1]} ({span[1] - span[0] + 1} lines), "
          f"async={info['is_async']}, docstring={'yes' if str(info['docstring']).strip() else 'no'}")
    print("decorators:", info["decorators"])
    print("imports needed:\n" + (imports_block(info["needed"]) or "   (none)"))
    if info["unresolved"]:
        print("!! UNRESOLVED (not in the router's import table):", info["unresolved"])
    if info["cyclic"]:
        print("!! ROUTER-LOCAL (move these first, else the service would import a router):", info["cyclic"])
    if args.dry_run:
        return 0
    if info["unresolved"] or info["cyclic"]:
        print("refusing to move: resolve the names above first")
        return 1

    module_doc = ""
    if args.module_doc and not (SERVER / args.service).exists():
        module_doc = pathlib.Path(args.module_doc).read_text(encoding="utf-8")
    if args.plain:
        move_plain(args.router, args.handler, args.service, module_doc)
        return 0
    attr = args.attr or pathlib.Path(args.service).stem
    merged = apply_move(info, args.service, f"{attr}.{args.handler}", args.note,
                        svc_docstring=f"بدنهٔ دامنه‌ایِ `{args.handler}`؛ توضیحِ HTTP در پوستهٔ روتر است.",
                        module_doc=module_doc)
    ensure_service_import(args.router, attr)
    print(f"  {args.router}::{args.handler} -> {args.service} ({'appended' if merged else 'created'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
