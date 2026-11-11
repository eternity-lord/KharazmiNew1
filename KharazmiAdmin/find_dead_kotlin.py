#!/usr/bin/env python3
"""یافتنِ کدِ مردهٔ Kotlin در اپ اندروید — در سطحِ **نمادِ سطحِ بالا**.

چرا سنجهٔ ساده غلط است
----------------------
«declarationی که در *فایلِ دیگری* ارجاع نشده» برای این اپ بی‌اعتبار است: اینترفیس‌های
Retrofit و data classهای Gson داخلِ **همان فایلِ خودشان** مصرف می‌شوند
(`retrofit.create(XApi::class.java)`، `suspend fun list(): List<Foo>`). با آن سنجه ۲۰۴ مورد
«مرده» به دست می‌آمد که تقریباً همه زنده بودند. سنجهٔ درست: تعدادِ ارجاع در **کلِ پیکره**
منهای خودِ محل‌های تعریف.

چه چیزی بررسی می‌شود و چه چیزی نه
--------------------------------
فقط **نمادهای سطحِ بالا** (class/object/interface/fun/val/var در ستونِ صفر). اعضای کلاس‌ها
عمداً بیرون از دامنه‌اند، چون:
  • propertyهای data class را Gson با **reflection** پر می‌کند ⇒ حتی اگر هیچ‌جا متنًا خوانده
    نشوند، زنده‌اند و حذفشان بی‌صدا قراردادِ JSON را می‌شکند؛
  • `override fun`ها (۲۸۶ مورد در این اپ) توسط framework صدا زده می‌شوند، نه توسط کدِ اپ؛
  • وقتی یک `object` مرده است، حذفِ کلِ فایل، اعضای مرده‌اش را هم می‌برد
    (مثالِ واقعی: `GoldAnimations` با ۱۳ تابع که هیچ‌کدام ارجاع نداشتند).

بردارهایی که یک اسکنِ صرفاً Kotlin هرگز نمی‌بیند و این‌جا پوشش داده شده‌اند
--------------------------------------------------------------------------
۱) **custom View در layout**: `<com.example.kharazmiadmin.GoldButton …/>`. AAPT2 نامِ کلاس را
   اعتبارسنجی **نمی‌کند** ⇒ حذفِ چنین کلاسی build را سبز نگه می‌دارد و در زمانِ اجرا
   inflate را می‌ترکاند. پس همهٔ XMLهای `res/` و `AndroidManifest.xml` هم جزوِ پیکرهٔ
   ارجاع‌اند (هم به شکلِ FQCN و هم نامِ ساده).
۲) **Manifest**: Activity/Service/Receiver/Provider/Application با `android:name=".X"` از
   طریقِ reflection ساخته می‌شوند ⇒ هیچ ارجاعِ متنیِ دیگری ندارند.
۳) هر سه source set: `main`، `test` و `androidTest` (چیزی که فقط تست مصرفش می‌کند مرده نیست).
۴) `android:onClick` — در این اپ **صفر** مورد است، ولی اگر روزی اضافه شود این ابزار
   آن را به‌عنوانِ ارجاع می‌شمارد چون XML در پیکره هست.
۵) reflection با نامِ رشته‌ای (`Class.forName`, `getDeclaredMethod`) — در این اپ صفر مورد؛
   اگر پیدا شود با صدای بلند گزارش می‌شود چون آن‌گاه تحلیلِ نام‌محور بی‌اعتبار است.

پشتوانهٔ نهایی
---------------
حکمِ نهایی با CI است: `.github/workflows/android.yml` → `:app:assembleDebug`
(کامپایلرِ Kotlin هر ارجاعِ جامانده را با نام و شمارهٔ خط گزارش می‌کند) و
`:app:testDebugUnitTest`.

کاربرد:
    python3 KharazmiAdmin/find_dead_kotlin.py            # گزارشِ خوانا
    python3 KharazmiAdmin/find_dead_kotlin.py --json     # خروجیِ ماشین‌خوان
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
APP_SRC = os.path.join(HERE, "app", "src")
SOURCE_SETS = ("main", "test", "androidTest")
TEST_SOURCE_SETS = ("test", "androidTest")
PACKAGE = "com.example.kharazmiadmin"

# ── الگوهای تعریفِ سطحِ بالا (ستونِ صفر) ────────────────────────────────
_MODS = r"(?:(?:public|internal|private|abstract|open|sealed|data|enum|value|annotation|expect|actual|fun|inline|external|suspend|tailrec|operator|infix|const|lateinit)\s+)*"
DECL_TYPE = re.compile(rf"^{_MODS}(class|object|interface)\s+([A-Z]\w*)", re.M)
DECL_FUN = re.compile(rf"^{_MODS}fun\s+(?:<[^>]*>\s*)?(?:[\w.<>?\[\]]+\.)?([A-Za-z_]\w*)\s*\(", re.M)
DECL_PROP = re.compile(rf"^{_MODS}(val|var)\s+([A-Za-z_]\w*)\b", re.M)
# نام‌هایی که هرگز پیشنهادِ حذف نمی‌گیرند
NEVER = {"main"}


def _iter_files(_mode: str = "all"):
    kt, xml = [], []
    for sset in SOURCE_SETS:
        base = os.path.join(APP_SRC, sset)
        if not os.path.isdir(base):
            continue
        # کلاس‌های تست را به‌عنوانِ «تعریف» جمع نمی‌کنیم: JUnit/AndroidJUnit4 آن‌ها را با
        # reflection نمونه می‌سازد و هیچ ارجاعِ متنی ندارند، پس سنجهٔ «تعدادِ ارجاع» دربارهٔ
        # آن‌ها بی‌معناست. (فایل‌های تست همچنان جزوِ **پیکرهٔ ارجاع** هستند تا چیزی که فقط
        # تست مصرفش می‌کند مرده شمرده نشود.)
        if sset in TEST_SOURCE_SETS and _mode == "decls":
            continue
        for root_dir, _dirs, files in os.walk(base):
            for name in sorted(files):
                path = os.path.join(root_dir, name)
                if name.endswith((".kt", ".java")):
                    kt.append(path)
                elif name.endswith(".xml"):
                    xml.append(path)
    manifest = os.path.join(APP_SRC, "main", "AndroidManifest.xml")
    if os.path.exists(manifest):
        xml.append(manifest)
    return kt, xml


def _strip_comments(text: str) -> str:
    """کامنت‌ها را خالی می‌کند ولی **تعدادِ خطوط را دقیقاً حفظ می‌کند**.

    چرا مهم است: بازهٔ هر تعریف از `text[:match.start()].count("\n")` به دست می‌آید، پس اگر
    حذفِ کامنت حتی یک خط را جابه‌جا کند، همهٔ بازه‌ها غلط می‌شوند و حذف‌کننده خطِ اشتباهی را
    می‌بُرد. الگوی قبلی `^\s*//.*$` بود و `\s` newline را هم می‌خورد ⇒ یک خطِ خالیِ قبلِ
    کامنت حذف می‌شد. حالا فقط space/tab خورده می‌شود و خودِ newline دست‌نخورده می‌ماند.
    """
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return re.sub(r"^[ \t]*//[^\n]*", "", text, flags=re.M)


def _word_count(name: str, text: str) -> int:
    return len(re.findall(r"(?<![\w.])" + re.escape(name) + r"(?![\w])", text))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--min-lines", type=int, default=0,
                        help="فقط نمادهایی که تعریفشان دستِ‌کم این‌قدر خط دارد")
    args = parser.parse_args()

    kt_files, xml_files = _iter_files("decls")
    kt_raw = {p: open(p, encoding="utf-8", errors="replace").read() for p in kt_files}
    kt_code = {p: _strip_comments(t) for p, t in kt_raw.items()}
    # XML با کامنت پاک نمی‌شود: `<!-- <com.x.Y/> -->` هم برای ما «ارجاع» است (محافظه‌کارانه)
    xml_text = {p: open(p, encoding="utf-8", errors="replace").read() for p in xml_files}

    manifest_text = xml_text.get(os.path.join(APP_SRC, "main", "AndroidManifest.xml"), "")
    in_manifest = set(re.findall(r'android:name="\.?([\w.]+)"', manifest_text))
    in_manifest |= {n.rsplit(".", 1)[-1] for n in in_manifest}

    reflection = []
    for p, t in kt_code.items():
        for pat in (r"Class\.forName\s*\(", r"getDeclaredMethod\s*\(", r"getMethod\s*\(",
                    r"getIdentifier\s*\("):
            for m in re.finditer(pat, t):
                line = t[: m.start()].count("\n") + 1
                reflection.append(f"{os.path.relpath(p, HERE)}:{line}  {pat.rstrip(chr(92)+'s*(')}")

    # ── جمع‌آوریِ تعریف‌های سطحِ بالا ─────────────────────────────────
    # name -> {"kind":…, "decls": [file…], "decl_sites": int, "start": line, "end": line}
    decls: dict[str, dict] = defaultdict(lambda: {"kind": set(), "decl_sites": 0, "files": set(),
                                                  "spans": []})
    for path, code in kt_code.items():
        lines = code.splitlines()
        # DECL_FUN تنها یک گروهِ capture دارد (نام)، بقیه دو تا (نوع، نام)
        for pattern, kind, name_group in ((DECL_TYPE, "type", 2), (DECL_FUN, "fun", 1),
                                          (DECL_PROP, "prop", 2)):
            for m in pattern.finditer(code):
                name = m.group(name_group)
                if name in NEVER:
                    continue
                lineno = code[: m.start()].count("\n")
                # انتهای تعریف: تا خطِ بعدی که در ستونِ صفر یک تعریفِ دیگر یا `}` تنهاست
                # هم پرانتزِ primary constructor و هم براکتِ بدنه شمرده می‌شوند
                end = lineno
                depth, opened = 0, False
                for i in range(lineno, len(lines)):
                    stripped = lines[i]
                    depth += (stripped.count("(") - stripped.count(")")
                              + stripped.count("{") - stripped.count("}"))
                    if depth > 0:
                        opened = True
                    if depth <= 0 and (opened or i > lineno or ")" in stripped or "{" not in stripped):
                        end = i
                        break
                    end = i
                d = decls[name]
                d["kind"].add(kind)
                d["decl_sites"] += 1
                d["files"].add(os.path.relpath(path, HERE))
                d["spans"].append((os.path.relpath(path, HERE), lineno + 1, end + 1))

    # ── شمارشِ ارجاع در کلِ پیکره ────────────────────────────────────
    total = defaultdict(int)
    where = defaultdict(set)
    for name in decls:
        pat = re.compile(r"(?<![\w.])" + re.escape(name) + r"(?![\w])")
        fqcn = f"{PACKAGE}.{name}"
        for p, t in kt_code.items():
            n = len(pat.findall(t))
            if n:
                total[name] += n
                where[name].add(os.path.relpath(p, HERE))
        for p, t in xml_text.items():
            n = len(pat.findall(t)) + len(re.findall(re.escape(fqcn), t))
            if n:
                total[name] += n
                where[name].add(os.path.relpath(p, HERE) + " [XML]")

    dead = []
    for name, d in sorted(decls.items()):
        refs = total[name] - d["decl_sites"]
        if refs > 0:
            continue
        if name in in_manifest:
            continue
        span_lines = max(e - s + 1 for _f, s, e in d["spans"])
        if span_lines < args.min_lines:
            continue
        dead.append({
            "name": name,
            "kind": "/".join(sorted(d["kind"])),
            "lines": span_lines,
            "defined_in": sorted(d["files"]),
            "spans": d["spans"],
        })
    dead.sort(key=lambda r: (-r["lines"], r["name"]))

    payload = {
        "kotlin_files": len(kt_files),
        "xml_files": len(xml_files),
        "top_level_declarations": len(decls),
        "reflection_sites": reflection,
        "manifest_declared": sorted(in_manifest),
        "dead_total": len(dead),
        "dead_lines_total": sum(d["lines"] for d in dead),
        "dead": dead,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        return 0

    print(f"فایل‌های Kotlin/Java : {payload['kotlin_files']}")
    print(f"فایل‌های XML (res + manifest) : {payload['xml_files']}")
    print(f"نمادهای سطحِ بالا : {payload['top_level_declarations']}")
    print(f"سایت‌های reflection/پویشِ پویا : {len(reflection)}")
    for site in reflection:
        print(f"    ⚠️  {site}   ← تحلیلِ نام‌محور برای نمادهای مرتبط با این سایت ناامن است")
    print(f"نام‌های اعلام‌شده در Manifest (هرگز مرده شمرده نمی‌شوند): {len(payload['manifest_declared'])}")
    print()
    print(f"مرده: {payload['dead_total']} نماد، {payload['dead_lines_total']} خط")
    for d in dead:
        spans = ", ".join(f"{f}:{s}-{e}" for f, s, e in d["spans"])
        print(f"  [{d['kind']:<12}] {d['name']:<38} {d['lines']:>5} خط   {spans}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
