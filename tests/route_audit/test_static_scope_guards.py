"""قفلِ رگرسیون برایِ گاردهایِ مردهٔ `in locals()` — کلاسِ همان باگی که F821 لو داد.

ریشهٔ باگ: در `Kharazmi_Server/routers/exams.py:379` نوشته شده بود

    "attendance_percentage": round(attendance_percentage, 1) if 'attendance_percentage' in locals() else round(attendance_pct, 1),

`attendance_percentage` **هرگز** در آن تابع assign نمی‌شد. در Python محلی‌بودنِ نام در
زمانِ کامپایل تعیین می‌شود، پس آن نام global دیده می‌شد و `'…' in locals()` در frameِ
تابع **همیشه False** بود ⇒ شاخهٔ اول کدِ مرده بود. `NameError` هم نمی‌داد (اتفاقاً به
همان دلیل)، پس هیچ تستی گرفتارش نمی‌شد و تنها نشانه‌اش `ruff --select F821` بود.

این ماژول همان الگو را مکانیکی می‌بندد: هر گاردِ `<رشته> in locals()` که رشته‌اش در
همان scopeِ تابع assign نشده باشد، شکست است. فقط کتابخانهٔ استاندارد (`ast`)، بدونِ
وابستگی به ruff — چون در CI نصبِ ابزارِ اضافی تضمین‌شده نیست.

سه تست عمدی‌اند:
  ۱) شمارشِ فایل‌ها — «۰ یافته» هرگز نباید از «۰ فایلِ دیده» آمده باشد.
  ۲) خودِ آشکارساز رویِ یک نمونهٔ مصنوعی — اثباتِ **غیرِتهی** بودنِ بررسی.
  ۳) جارویِ کلِ سرور.
"""

import ast
import pathlib

SERVER = pathlib.Path(__file__).resolve().parents[2] / "Kharazmi_Server"


def _assigned_names(fn):
    """نام‌هایی که در *همان* scopeِ این تابع bind می‌شوند (نه در تابعِ تودرتو).

    چرا تودرتو نه: `locals()` در frameِ همان تابع ارزیابی می‌شود، پس assign در تابعِ
    داخلی هیچ تأثیری بر گاردِ تابعِ بیرونی ندارد. اگر تودرتو را هم می‌شمردیم، باگِ
    واقعی می‌توانست پشتِ یک هم‌نامیِ تصادفی پنهان بماند.
    """
    names = {a.arg for a in list(fn.args.posonlyargs) + list(fn.args.args)
             + list(fn.args.kwonlyargs)}
    if fn.args.vararg:
        names.add(fn.args.vararg.arg)
    if fn.args.kwarg:
        names.add(fn.args.kwarg.arg)

    class _Collector(ast.NodeVisitor):
        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Store):
                names.add(node.id)

        def visit_FunctionDef(self, node):
            return  # پایین‌تر نرو

        visit_AsyncFunctionDef = visit_FunctionDef
        visit_Lambda = visit_FunctionDef
        visit_ClassDef = visit_FunctionDef

    for stmt in fn.body:
        _Collector().visit(stmt)
    # `global`/`nonlocal` هم locals() را پر نمی‌کند، پس عمداً شمرده نمی‌شود
    return names


def _dead_locals_guards(tree):
    """هر `Compare` به‌شکلِ `<str-const> in locals()` که رشته‌اش local نیست."""
    offenders = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        scope = _assigned_names(fn)
        for node in ast.walk(fn):
            if not isinstance(node, ast.Compare) or len(node.ops) != 1:
                continue
            if not isinstance(node.ops[0], (ast.In, ast.NotIn)):
                continue
            left, comp = node.left, node.comparators[0]
            for name_node, str_node in ((left, comp), (comp, left)):
                if not (isinstance(name_node, ast.Call)
                        and isinstance(name_node.func, ast.Name)
                        and name_node.func.id == "locals"
                        and isinstance(str_node, ast.Constant)
                        and isinstance(str_node.value, str)):
                    continue
                guarded = str_node.value
                if guarded not in scope:
                    offenders.append((fn.name, getattr(fn, "lineno", 0),
                                      node.lineno, guarded))
    return offenders


def _server_python_files():
    return sorted(p for p in SERVER.rglob("*.py") if "__pycache__" not in p.parts)


def test_scan_actually_sees_the_server_tree():
    """«هیچ گاردِ مرده‌ای نیست» فقط وقتی معنا دارد که واقعاً فایل‌ها دیده شده باشند."""
    files = _server_python_files()
    assert SERVER.is_dir(), f"پوشهٔ سرور پیدا نشد: {SERVER}"
    assert len(files) >= 100, f"فقط {len(files)} فایلِ پایتون دیده شد — جارو ناقص است"
    assert any(p.name == "exams.py" and p.parent.name == "routers" for p in files), \
        "routers/exams.py در جارو نیست ⇒ مسیرها اشتباه‌اند"


def test_detector_is_not_vacuous():
    """آشکارساز باید الگو را رویِ نمونهٔ مصنوعی **پیدا کند**، وگرنه تستِ بعدی تهی است."""
    bad = ast.parse(
        "def f(a):\n"
        "    pct = 1\n"
        "    return round(ghost, 1) if 'ghost' in locals() else round(pct, 1)\n"
    )
    found = _dead_locals_guards(bad)
    assert len(found) == 1, f"آشکارساز نمونهٔ بد را نگرفت: {found}"
    assert found[0][3] == "ghost"

    good = ast.parse(
        "def f(a):\n"
        "    pct = 1\n"
        "    return round(pct, 1) if 'pct' in locals() else 0\n"
    )
    assert _dead_locals_guards(good) == [], "آشکارساز رویِ گاردِ سالم positiveِ کاذب داد"

    nested = ast.parse(
        "def outer():\n"
        "    def inner():\n"
        "        ghost = 1\n"
        "    return ghost if 'ghost' in locals() else 0\n"
    )
    assert len(_dead_locals_guards(nested)) == 1, \
        "assign در تابعِ تودرتو نباید گاردِ تابعِ بیرونی را معتبر کند"


def test_no_dead_locals_guard_in_server():
    """هیچ گاردِ `in locals()` نباید نامی را بپاید که در همان تابع bind نمی‌شود."""
    offenders = []
    for path in _server_python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            offenders.append((str(path.relative_to(SERVER.parent)), 0, 0,
                              f"SyntaxError: {exc.msg}"))
            continue
        for fn_name, _fn_line, line, guarded in _dead_locals_guards(tree):
            offenders.append((str(path.relative_to(SERVER.parent)), fn_name, line, guarded))
    assert not offenders, (
        "گاردِ مردهٔ `in locals()` پیدا شد — رشتهٔ پاییده‌شده در همان تابع assign "
        "نمی‌شود، پس گارد همیشه False است و آن شاخه کدِ مرده است:\n  "
        + "\n  ".join(f"{f}:{ln} در {fn}() → {g!r}" for f, fn, ln, g in offenders)
    )
