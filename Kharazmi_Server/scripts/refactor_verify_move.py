"""راستی‌آزمایِ «انتقالِ بایت‌به‌بایت» — گیتِ اجباریِ بعد از هر ریفکتورِ جابه‌جاییِ کد.

این اسکریپت ادعایِ «بدنهٔ دامنه بدونِ تغییر منتقل شد» را **اثبات** می‌کند، نه فرض:

  ۱. بدنهٔ هر handlerِ منتقل‌شده در ماژولِ سرویس، بایت‌به‌بایت با همان تابع در
     `git show <base>:<router>` مقایسه می‌شود؛
  ۲. پوستهٔ باقی‌مانده در روتر باید decoratorها، امضا و docstring را بایت‌به‌بایت حفظ کرده
     باشد (این‌ها قراردادِ OpenAPI و مستنداتِ endpointاند) و **همهٔ** پارامترها را به‌ترتیب
     به تابعِ سرویس پاس بدهد؛
  ۳. هر انتقالِ مستقیم (هلپر/کلاس/اسکیما/ثابت) باید با بلوکِ کامنتِ چسبیده‌اش بایت‌به‌بایت
     منتقل شده باشد، و اگر نامش هنوز در روتر مصرف دارد، روتر باید بتواند resolveاش کند.

چرا لازم است: «تست‌ها سبز شدند» برای این کلاس از باگ کافی نیست. در P3a یک aliasِ گم‌شده
(`import time` به‌جای `import time as time_module`) یک NameErrorِ نهفته ساخت که **هیچ** تستی
نمی‌گرفتش، چون تنها فراخوانی‌اش پشتِ یک short-circuit بود؛ در P3b هم ثابتِ
`PAYMENT_GATEWAY_ENABLED` بدونِ بازصادرت ماند و مسیرش فقط وقتی فلگ روشن باشد اجرا می‌شد.
هر دو را فقط مقایسهٔ مکانیکی با `git` و `ruff --select F821` می‌گرفتند.

استفاده:
    python Kharazmi_Server/scripts/refactor_verify_move.py --base HEAD \
        --handler routers/finance.py:payment_callback:services/payments.py \
        --plain   routers/finance.py:_jalali_now_str:services/jalali_time.py:resolve
کدِ خروج ۰ یعنی همه‌چیز بایت‌به‌بایت یکسان است؛ ۱ یعنی حداقل یک مشکل.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import refactor_move_body as cutter  # بعد از bootstrapِ sys.path (E402 در این ریپو ignore است)

REPO = cutter.SERVER.parent


def head_source(rel_path: str, base: str) -> str:
    result = subprocess.run(["git", "show", f"{base}:Kharazmi_Server/{rel_path}"],
                            cwd=REPO, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f"cannot read {base}:Kharazmi_Server/{rel_path}: {result.stderr.strip()}")
    return result.stdout


def parts_from(src: str, name: str) -> dict[str, object]:
    """همان تجزیه‌ای که ابزارِ انتقال انجام می‌دهد، ولی روی متنِ دلخواه."""
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    node = next((n for n in tree.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == name),
                None)
    if node is None:
        _path, _lines, assign = cutter.find_assign_text(src, name)
        return {"sig": "", "doc": "", "body": "", "span": (assign.lineno, assign.end_lineno),
                "decs": [], "params": [], "start": assign.lineno,
                "src": "".join(lines[assign.lineno - 1:assign.end_lineno])}
    info = cutter._split_parts(lines, node, src)
    return {
        "sig": info["signature"], "doc": info["docstring"], "body": info["body"],
        "span": info["body_span"], "decs": info["decorators"], "params": info["params"],
        "start": node.lineno, "src": info["src"],
    }


def _first_diff(old: str, new: str) -> str:
    old_lines = old.splitlines(True)
    new_lines = new.splitlines(True)
    for index, (a, b) in enumerate(zip(old_lines, new_lines, strict=False)):
        if a != b:
            return f"first difference at line {index + 1}:\n     BASE: {a!r}\n     NOW : {b!r}"
    return f"length differs: {len(old_lines)} -> {len(new_lines)} lines"


def check_handler(router_rel: str, handler: str, service_rel: str, base: str) -> list[str]:
    old = parts_from(head_source(router_rel, base), handler)
    shell = parts_from((cutter.SERVER / router_rel).read_text(encoding="utf-8"), handler)
    moved = parts_from((cutter.SERVER / service_rel).read_text(encoding="utf-8"), handler)
    problems: list[str] = []
    if moved["body"] != old["body"]:
        problems.append("BODY is not byte-identical: " + _first_diff(str(old["body"]), str(moved["body"])))
    if shell["sig"] != old["sig"]:
        problems.append(f"shell SIGNATURE changed:\n     BASE: {old['sig']!r}\n     NOW : {shell['sig']!r}")
    if shell["doc"] != old["doc"]:
        problems.append("shell DOCSTRING changed (FastAPI publishes it as the endpoint description)")
    if shell["decs"] != old["decs"]:
        problems.append(f"shell DECORATORS changed: {old['decs']} -> {shell['decs']}")
    if moved["params"] != old["params"]:
        problems.append(f"service PARAMS changed: {old['params']} -> {moved['params']}")

    lines = (cutter.SERVER / router_rel).read_text(encoding="utf-8").splitlines()
    span = shell["span"]
    assert isinstance(span, tuple)
    segment = lines[span[0] - 1:span[1]]
    index = next((i for i, line in enumerate(segment) if line.strip().startswith("return ")), None)
    if index is None:
        problems.append("shell has no forwarding `return` inside the analysed span")
    else:
        call = " ".join(part.strip() for part in segment[index:])
        forwarded = [x.strip() for x in call[call.index("(") + 1:call.rindex(")")].split(",") if x.strip()]
        if forwarded != old["params"]:
            problems.append(f"shell forwards {forwarded} but the signature is {old['params']}")
    return problems


def check_plain(router_rel: str, name: str, target_rel: str, must_resolve: bool, base: str) -> list[str]:
    base_src = head_source(router_rel, base)
    old = parts_from(base_src, name)
    target_text = (cutter.SERVER / target_rel).read_text(encoding="utf-8")
    new = parts_from(target_text, name)
    problems: list[str] = []
    if new["src"] != old["src"]:
        problems.append("source is not byte-identical: " + _first_diff(str(old["src"]), str(new["src"])))
    base_lines = base_src.splitlines(True)
    start = int(old["start"]) - 1
    probe = start
    while probe > 0 and base_lines[probe - 1].lstrip().startswith("#"):
        probe -= 1
    comment = "".join(base_lines[probe:start])
    if comment and (comment + str(old["src"])) not in target_text:
        problems.append(f"the {len(comment.splitlines())}-line comment block above it was not moved along")
    if must_resolve and name not in (cutter.SERVER / router_rel).read_text(encoding="utf-8"):
        problems.append(f"`{router_rel}` can no longer resolve `{name}` (a consumer is still there)")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="HEAD", help="git ref برای مقایسه (پیش‌فرض HEAD)")
    parser.add_argument("--handler", action="append", default=[], metavar="ROUTER:NAME:SERVICE",
                        help="handlerِ پوسته‌شده؛ قابلِ تکرار")
    parser.add_argument("--plain", action="append", default=[], metavar="ROUTER:NAME:TARGET[:resolve]",
                        help="انتقالِ مستقیمِ هلپر/کلاس/ثابت؛ قابلِ تکرار")
    args = parser.parse_args(argv)
    if not args.handler and not args.plain:
        parser.error("nothing to verify: pass --handler and/or --plain")

    failures = 0
    if args.handler:
        print(f"=== handler bodies + shells vs {args.base} ===")
    for spec in args.handler:
        router_rel, handler, service_rel = spec.split(":")
        problems = check_handler(router_rel, handler, service_rel, args.base)
        old = parts_from(head_source(router_rel, args.base), handler)
        print(f"[{'OK ' if not problems else 'FAIL'}] {router_rel}::{handler} -> {service_rel} "
              f"(body {len(str(old['body']).splitlines())} lines, {len(old['params'])} params, "
              f"{len(old['decs'])} decorators)")
        for problem in problems:
            print("      " + problem)
            failures += 1

    if args.plain:
        print(f"\n=== direct moves (verbatim) vs {args.base} ===")
    for spec in args.plain:
        bits = spec.split(":")
        router_rel, name, target_rel = bits[0], bits[1], bits[2]
        must_resolve = len(bits) > 3 and bits[3] == "resolve"
        problems = check_plain(router_rel, name, target_rel, must_resolve, args.base)
        old = parts_from(head_source(router_rel, args.base), name)
        print(f"[{'OK ' if not problems else 'FAIL'}] {router_rel}::{name} -> {target_rel} "
              f"({len(str(old['src']).splitlines())} LOC, router-still-resolves="
              f"{name in (cutter.SERVER / router_rel).read_text(encoding='utf-8')})")
        for problem in problems:
            print("      " + problem)
            failures += 1

    total = len(args.handler) + len(args.plain)
    print("\nRESULT:", f"{total}/{total} byte-identical to {args.base}" if not failures
          else f"{failures} PROBLEM(S) in {total} checked move(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
