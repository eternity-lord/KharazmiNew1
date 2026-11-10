#!/usr/bin/env python3
"""یافتنِ منابعِ مردهٔ اپ اندروید: «تعریف شده ولی هیچ‌جا ارجاع نشده».

چرا این ابزار لازم است
-----------------------
تستِ `Kharazmi_Server/tests/test_android_resources_static.py` جهتِ
«ارجاع‌شده ⇒ تعریف‌شده» را می‌سنجد (منبعِ گم‌شده ⇒ خطای build). این اسکریپت جهتِ
**عکس** را می‌سنجد: منبعی که تعریف شده و کسی ارجاعش نمی‌کند، یعنی وزنِ مرده. این دو
مکمل‌اند و هیچ‌کدام دیگری را پوشش نمی‌دهد.

چرا قابلِ اعتماد است
-------------------
۱) منابع را از هر سه جایی که ممکن است ارجاع شوند جمع می‌کند: Kotlin/Java (`R.type.name`)،
   همهٔ XMLهای `res/` (شاملِ selector/layer-list/style که به منابعِ دیگر ارجاع می‌دهند)،
   و `AndroidManifest.xml`.
۲) شکل‌های ارجاعی را می‌شناسد که یک اسکنِ سادهٔ `@type/name` **از دست می‌دهد** و اگر
   ندیده گرفته شوند مثبتِ کاذب می‌سازند:
     • `?attr/foo` و `?foo` (ارجاع از طریق attributeِ تم)
     • `parent="GajOutlineBoxStyle"` در `<style>` — ارجاعِ **بدونِ `@`** به یک styleِ خودی
     • styleهای نقطه‌دار: در XML `@style/Theme.Kharazmi` ولی در Kotlin
       `R.style.Theme_Kharazmi` ⇒ هر دو شکل بررسی می‌شوند
     • `string-array`/`integer-array` هر دو در `R.array` و `@array` دیده می‌شوند
     • namespaceهای `tools:` و `app:` هم ارجاع شمرده می‌شوند (محافظه‌کارانه: `tools:` در
       runtime مصرف نمی‌شود ولی build به آن نیاز دارد، پس حذفش build را می‌شکند)
۳) منبعِ نوعِ `id` را **هرگز** پیشنهادِ حذف نمی‌دهد: تنها سایتِ `getIdentifier` در کلِ اپ
   (`ShareConfigActivity.kt`) نامِ `et1…et15` را به‌صورتِ پویا از روی رشته می‌سازد و
   `resources.getIdentifier(name, "id", packageName)` صدا می‌کند. تحلیلِ نام‌محور برای
   `id` بی‌معناست. برای بقیهٔ نوع‌ها همان سایت بررسی و گزارش می‌شود تا اگر روزی
   `getIdentifier` برای نوعِ دیگری اضافه شد، این ابزار با صدای بلند هشدار بدهد.
۴) همهٔ پوشه‌های `values*` (شاملِ `values-night` و `values-v31`) را با هم می‌بیند، پس
   تعریفِ یک نام در چند variant فقط یک منبع شمرده می‌شود و برای حذف باید **همهٔ**
   variantها با هم بروند.

پشتوانهٔ نهایی
---------------
این اسکریپت «پیشنهاد» می‌دهد، حکم نمی‌کند. حکمِ نهایی با دو گیتِ واقعی است:
  • `.github/workflows/android.yml` → `:app:assembleDebug` یعنی لینکِ منابع با AAPT2؛
    اگر منبعِ هنوز‌ارجاع‌شده‌ای حذف شود، build با نامِ دقیقِ همان منبع می‌شکند.
  • سوئیتِ Python → هر `R.<type>.<name>` استفاده‌شده در Kotlin باید منبع داشته باشد.

کاربرد:
    python3 KharazmiAdmin/find_dead_resources.py            # گزارش
    python3 KharazmiAdmin/find_dead_resources.py --json     # خروجیِ ماشین‌خوان
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

APP_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "src")
MAIN = os.path.join(APP_ROOT, "main")
RES = os.path.join(MAIN, "res")
CODE_DIRS = [os.path.join(APP_ROOT, name, "java") for name in ("main", "test", "androidTest")]
MANIFEST = os.path.join(MAIN, "AndroidManifest.xml")

# پوشه‌های res که نامِ فایل در آن‌ها = نامِ منبع
FILE_TYPES = {
    "layout", "drawable", "mipmap", "anim", "animator", "font", "menu", "xml", "raw", "color",
}
# تگ‌های داخل values/*.xml که یک منبعِ نام‌دار تعریف می‌کنند
VALUE_TAGS = {
    "string", "color", "dimen", "plurals", "integer", "bool", "attr", "id",
    "string-array", "integer-array", "array", "declare-styleable", "style", "item", "eat-comment",
}
# نوع‌هایی که حذفشان پیشنهاد نمی‌شود
NEVER_SUGGEST = {"id", "declare-styleable"}
# نرمال‌سازیِ نامِ نوع: تعریف و ارجاع باید به یک کلید برسند
TYPE_ALIAS = {"string-array": "array", "integer-array": "array"}
RESOURCE_FILE_EXT = re.compile(
    r"\.(xml|png|jpg|jpeg|webp|gif|ttf|otf|mp3|wav|ogg|json|9\.png)$", re.IGNORECASE
)


def _read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _rel(path: str) -> str:
    return os.path.relpath(path, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _strip_kotlin_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), source, flags=re.S)
    return re.sub(r"^\s*//.*$", "", source, flags=re.M)


# ───────────────────────────── تعریف‌ها ─────────────────────────────
def collect_definitions():
    """(type, name) -> sorted list of files that define it."""
    defs: dict[tuple[str, str], set[str]] = defaultdict(set)
    for folder in sorted(os.listdir(RES)):
        folder_path = os.path.join(RES, folder)
        if not os.path.isdir(folder_path):
            continue
        base = folder.split("-")[0]          # values-night -> values, drawable-hdpi -> drawable
        if base in FILE_TYPES:
            for name in sorted(os.listdir(folder_path)):
                if name.startswith("."):
                    continue
                stem = RESOURCE_FILE_EXT.sub("", name)
                stem = re.sub(r"\.(png|webp|jpg|jpeg)$", "", stem, flags=re.I)   # foo.9.png
                defs[(base, stem)].add(f"res/{folder}/{name}")
        elif base == "values":
            for vfile in sorted(os.listdir(folder_path)):
                if not vfile.endswith(".xml"):
                    continue
                try:
                    root = ET.parse(os.path.join(folder_path, vfile)).getroot()
                except ET.ParseError as exc:
                    print(f"  !! cannot parse res/{folder}/{vfile}: {exc}", file=sys.stderr)
                    continue
                for el in root:
                    if el.tag not in VALUE_TAGS:
                        continue
                    name = el.get("name")
                    if not name:
                        continue
                    if el.tag == "item":
                        rtype = TYPE_ALIAS.get(el.get("type", "id"), el.get("type", "id"))
                    else:
                        rtype = TYPE_ALIAS.get(el.tag, el.tag)
                    defs[(rtype, name)].add(f"res/{folder}/{vfile}")
    return defs


# ───────────────────────────── ارجاع‌ها ─────────────────────────────
# سینتکسِ ارجاعِ منبع در اندروید **اسلش** دارد نه دونقطه:
#   @color/foo   @+id/foo   @android:color/foo   @*android:color/foo   ?attr/foo   ?foo
# (یک اسکنِ `@type:name` هیچ ارجاعِ XML را نمی‌گیرد و صدها مثبتِ کاذب می‌سازد — خودِ این
#  ابزار پیش از commit با همین اشتباه `app_name` و `ic_launcher` را «مرده» می‌گفت.)
XML_REF = re.compile(r"[@?]\+?(?:\*?(\w+):)?(\w+)/([A-Za-z_][\w.]*)")
# R.type.name در Kotlin/Java
R_REF = re.compile(r"\bR\.(\w+)\.([A-Za-z_]\w*)")
# <style parent="..."> — ارجاعِ بدونِ @ به یک styleِ خودی
STYLE_PARENT = re.compile(r'parent\s*=\s*"([^"]+)"')


def collect_references():
    """(type, name) -> set of files referencing it, plus the dynamic-lookup report."""
    refs: dict[tuple[str, str], set[str]] = defaultdict(set)
    dynamic: list[str] = []

    code_files = []
    for code_dir in CODE_DIRS:
        if not os.path.isdir(code_dir):
            continue
        for root_dir, _dirs, files in os.walk(code_dir):
            code_files += [os.path.join(root_dir, f) for f in sorted(files) if f.endswith((".kt", ".java"))]

    for path in code_files:
        text = _strip_kotlin_comments(_read(path))
        where = _rel(path)
        for match in R_REF.finditer(text):
            rtype, name = match.group(1), match.group(2)
            refs[(rtype, name)].add(where)
            # styleهای نقطه‌دار در Kotlin با `_` نوشته می‌شوند: R.style.Theme_Kharazmi
            if rtype == "style" and "_" in name:
                refs[("style", name.replace("_", "."))].add(where)
        for match in re.finditer(r"getIdentifier\s*\(", text):
            line = text[: match.start()].count("\n") + 1
            tail = text[match.end(): match.end() + 90].split("\n", 1)[0]
            dynamic.append(f"{where}:{line}  getIdentifier({tail.strip()})")

    xml_files = []
    for root_dir, _dirs, files in os.walk(RES):
        xml_files += [os.path.join(root_dir, f) for f in sorted(files) if f.endswith(".xml")]
    if os.path.exists(MANIFEST):
        xml_files.append(MANIFEST)

    for path in xml_files:
        text = _read(path)
        where = _rel(path)
        for match in XML_REF.finditer(text):
            namespace, rtype, name = match.group(1), match.group(2), match.group(3)
            if namespace == "android":
                continue                      # منابعِ framework، مالِ ما نیستند
            refs[(rtype, name)].add(where)
            if rtype == "style":
                refs[("style", name.replace(".", "_"))].add(where)
        for match in STYLE_PARENT.finditer(text):
            parent = match.group(1).strip()
            refs[("style", parent)].add(where)
            refs[("style", parent.replace(".", "_"))].add(where)
        # قاعدهٔ ارثِ ضمنیِ اندروید: یک styleِ نقطه‌دار **بدونِ** `parent` صریح، از prefixِ
        # خودش ارث می‌برد (`A.B.C` ⇒ والدِ ضمنی `A.B`). اگر این قاعده دیده نشود، والدِ
        # ضمنی «مرده» به نظر می‌رسد در حالی که حذفش build را می‌شکند. (در حال حاضر در این اپ
        # صفر مورد است — همهٔ styleهای نقطه‌دار `parent` صریح دارند — ولی قاعده باید درست باشد.)
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            root = None
        if root is not None:
            for el in root:
                if el.tag != "style" or el.get("parent") is not None:
                    continue
                sname = el.get("name") or ""
                while "." in sname:
                    sname = sname.rsplit(".", 1)[0]
                    refs[("style", sname)].add(where + " (implicit dotted parent)")
        # `<item name="...">` داخلِ style یک ارجاع به attr نیست، ولی nameهای attrِ خودی
        # که بدونِ `?attr/` در item می‌آیند را هم پوشش بده
        for match in re.finditer(r'<item\s+name="([A-Za-z_][\w.]*)"', text):
            refs[("attr", match.group(1))].add(where)

    return refs, dynamic


def is_referenced(key, refs) -> bool:
    rtype, name = key
    if (rtype, name) in refs:
        return True
    if rtype == "style":
        # هر دو نگارشِ نقطه‌دار و زیرخطی
        return ("style", name.replace(".", "_")) in refs or ("style", name.replace("_", ".")) in refs
    if rtype == "array":
        return ("string-array", name) in refs or ("integer-array", name) in refs
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="خروجیِ ماشین‌خوان")
    parser.add_argument("--type", action="append", default=None, help="فقط این نوع‌ها (قابلِ تکرار)")
    args = parser.parse_args()

    defs = collect_definitions()
    refs, dynamic = collect_references()

    dead = defaultdict(list)
    for key, files in sorted(defs.items()):
        rtype = key[0]
        if rtype in NEVER_SUGGEST:
            continue
        if args.type and rtype not in args.type:
            continue
        if is_referenced(key, refs):
            continue
        dead[rtype].append({"name": key[1], "defined_in": sorted(files)})

    payload = {
        "definitions": len(defs),
        "distinct_references": len(refs),
        "dynamic_getidentifier_sites": dynamic,
        "dead_total": sum(len(v) for v in dead.values()),
        "dead_by_type": {k: v for k, v in sorted(dead.items())},
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        return 0

    print(f"تعریف‌های منبع : {payload['definitions']}")
    print(f"ارجاع‌های متمایز: {payload['distinct_references']}")
    print(f"سایت‌های getIdentifier (پویشِ پویا): {len(dynamic)}")
    for site in dynamic:
        kind = "id" if '"id"' in site else "⚠️ نوعِ غیرِ id — تحلیلِ نام‌محور برای آن نوع ناامن است"
        print(f"    {site}\n      → {kind}")
    print()
    for rtype in sorted(dead, key=lambda t: -len(dead[t])):
        items = dead[rtype]
        print(f"### {rtype}: {len(items)}")
        for item in items:
            where = ", ".join(os.path.basename(f) for f in item["defined_in"])
            print(f"    {item['name']:<48} {where}")
        print()
    print(f"جمعِ منابعِ مرده: {payload['dead_total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
