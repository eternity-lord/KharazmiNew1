"""شاهدِ گیتِ warningهای کامپایلرِ Kotlin (`KharazmiAdmin/kotlin_warning_gate.py`).

چرا این تست‌ها این‌جا هستند و نه در CI
---------------------------------------
خودِ warningها فقط با JVM/Gradle تولید می‌شوند و در محیطِ کاریِ ما هیچ‌کدام نیست، پس
**موجودیِ واقعی** را فقط CI می‌دهد. ولی منطقِ گیت — تجزیهٔ خطوطِ `w:`، ساختِ شناسه از
قالبِ پیام، مقایسه با baseline، و مهم‌تر از همه **fail-closed بودن** — کاملاً محلی و
قطعی قابلِ آزمودن است. این تست‌ها همان کاری را می‌کنند که برای `lint_gate.py` لازم بود:
قفل کردنِ معنا پیش از آنکه CI عددِ واقعی را بدهد.

مهم‌ترین گروه، گروهِ fail-closed است. لاگِ Gradle یک فایلِ متنی است و اگر build زود
بشکند **کوتاه** است؛ شمردنِ آن به‌معنایِ «بهبود» اشتباه می‌شود. یک گیتِ warning که
لاگِ ناقص را صفر بخواند، بدتر از نبودنِ گیت است: به دروغ سبز می‌شود.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from KharazmiAdmin.kotlin_warning_gate import (
    MAX_ANNOTATION,
    LogUnavailable,
    build_stats,
    collect_locations,
    compact_table,
    emit_annotation,
    escape,
    kind_of,
    main,
    normalize_path,
    parse_log,
    read_log,
)

ROOT = "KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin"
CI = "file:///home/runner/work/KharazmiNew1/KharazmiNew1/" + ROOT

REALISTIC_LOG = f"""
> Configure project :app
> Task :app:preBuild UP-TO-DATE
> Task :app:compileDebugKotlin
w: {CI}/MainActivity.kt:45:13 Variable 'userName' is never used
w: {CI}/MainActivity.kt:120:9 Name shadowed: item
w: {CI}/InvoiceActivity.kt:310:22 Casting 'response' to 'List<Student>' will throw ClassCastException
w: /home/dev/KharazmiNew1/{ROOT}/AppModels.kt:88:5 The integer literal does not conform to the expected type Long
w: {CI}/MainActivity.kt:45:13 Variable 'userName' is never used
e: {CI}/Broken.kt:9:1 Unresolved reference: nope
> Task :app:mergeDebugResources
Deprecated Gradle features were used in this build
BUILD SUCCESSFUL in 1m 42s
47 actionable tasks: 20 executed 27 up-to-date
""".strip()


def _stats(log: str, path: str = "/tmp/gradle-assemble.log") -> dict:
    return build_stats(parse_log(log), path)


def _write(tmp_path, name: str, text: str) -> str:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


# ── ۱) تجزیه: کنترلِ مثبت ────────────────────────────────────────────────────
def test_parser_sees_every_warning_form_in_a_realistic_log():
    """اگر روزی regex بشکند، این تست باید قرمز شود — نه اینکه بی‌صدا «۰ warning» بدهد."""
    warnings = parse_log(REALISTIC_LOG)
    assert len(warnings) == 4, [w["message"] for w in warnings]

    # قالبِ file:/// و قالبِ مسیرِ مطلقِ ساده هر دو گرفته می‌شوند و به مسیرِ نسبیِ ریپو
    # نرمال می‌شوند تا baseline بینِ CI و ماشینِ محلی قابلِ حمل بماند.
    assert warnings[0]["file"] == f"{ROOT}/MainActivity.kt"
    assert warnings[0]["line"] == 45 and warnings[0]["col"] == 13
    assert warnings[3]["file"] == f"{ROOT}/AppModels.kt"

    # تکرارِ دقیق (همان فایل/خط/ستون/پیام) شمرده نمی‌شود، وگرنه کامپایلِ دو variant
    # شمارِ baseline را دو برابر می‌کرد.
    assert sum(1 for w in warnings if w["file"].endswith("MainActivity.kt")) == 2

    # خطایِ `e:` و نویزِ Gradle هرگز warning شمرده نمی‌شوند.
    assert all(w["message"] != "Unresolved reference: nope" for w in warnings)
    assert not any("BUILD SUCCESSFUL" in w["message"] for w in warnings)


def test_kind_of_normalizes_identifiers_numbers_and_paths():
    assert kind_of("Variable 'userName' is never used") == "Variable '*' is never used"
    # `Name shadowed: item` عمداً نرمال می‌شود (شناسهٔ بی‌نقل‌قول است)؛ شاهدِ دقیقِ آن
    # test_kind_of_collapses_bare_identifier_holes_so_renames_do_not_churn_the_gate است.
    assert kind_of("Name shadowed: item") == "Name shadowed: *"
    assert kind_of("Casting 'response' to 'List<Student>' will throw ClassCastException") \
        == "Casting '*' to '*' will throw ClassCastException"
    assert kind_of("Parameter 'a' is never used") == "Parameter '*' is never used"
    # عدد نرمال می‌شود تا «deprecated since API 34» و «since API 33» یک قالب بمانند
    assert kind_of("This operation has been deprecated since API 34") \
        == kind_of("This operation has been deprecated since API 33")
    # قالب‌های متفاوت نباید در هم بریزند
    assert kind_of("Variable 'x' is never used") != kind_of("Parameter 'x' is never used")


def test_kind_of_collapses_bare_identifier_holes_so_renames_do_not_churn_the_gate():
    """خانواده‌هایی که نام/نوع را بی‌نقل‌قول می‌گذارند باید یک قالب بمانند.

    اگر این نرمال‌سازی برداشته شود، هر تغییرِ نامِ متغیر در یک ریفکتورِ بی‌خطر یک
    «قالبِ جدید» می‌سازد و گیت را به‌دروغ می‌شکند — و چون baselineِ فشرده باید در یک
    annotationِ ۴KB جا شود، انفجارِ شناسه‌ها کانالِ انتقال را هم می‌بندد.
    """
    assert kind_of("Name shadowed: item") == "Name shadowed: *"
    assert kind_of("Name shadowed: item") == kind_of("Name shadowed: row")
    assert kind_of("Type mismatch: inferred type is String but Int was expected") \
        == "Type mismatch: inferred type is * but * was expected"
    assert kind_of("Type mismatch: inferred type is Foo? but Bar was expected") \
        == kind_of("Type mismatch: inferred type is String but Int was expected")
    assert kind_of("The integer literal does not conform to the expected type Long") \
        == "The integer literal does not conform to the expected type *"
    # بیش‌ازحد یکی‌کردن هم ممنوع: خانواده‌هایِ متفاوت باید متفاوت بمانند
    assert kind_of("Variable 'x' is never used") != kind_of("Parameter 'x' is never used")
    assert kind_of("Unreachable code") == "Unreachable code"
    assert kind_of("Name shadowed: item") != kind_of("Variable 'item' is never used")


def test_normalize_path_handles_url_and_windows_and_foreign_roots():
    assert normalize_path(f"{CI}/Foo.kt").startswith("KharazmiAdmin/")
    assert normalize_path("file:///a/b/KharazmiAdmin/app/Foo.kt") == "KharazmiAdmin/app/Foo.kt"
    assert normalize_path("C:\\proj\\KharazmiAdmin\\app\\Foo.kt") == "KharazmiAdmin/app/Foo.kt"
    # بدونِ نشانهٔ ریشه، سه جزءِ آخر می‌ماند تا فایل قابلِ تشخیص باشد
    assert normalize_path("/tmp/whatever/deep/Foo.kt") == "whatever/deep/Foo.kt"


def test_stats_and_table_are_consistent_and_non_empty():
    stats = _stats(REALISTIC_LOG)
    assert stats["total"] == 4
    assert stats["distinct_kinds"] == 4
    assert sum(stats["by_kind"].values()) == stats["total"]
    assert stats["files_with_warnings"] == 3
    table = compact_table(stats)
    assert "4 in 4 kinds" in table and "top files:" in table
    locs = collect_locations(stats, {"never used"}, 5)
    assert f"{ROOT}/MainActivity.kt:45:13" in locs
    assert "locations listed: 1" in locs
    absent = collect_locations(stats, {"totally-absent-kind"}, 5)
    assert "kinds requested but not present in this log: totally-absent-kind" in absent


# ── ۲) fail-closed: لاگِ ناقص هرگز «صفر warning» نیست ───────────────────────
def test_missing_log_exits_2_and_never_reports_zero(tmp_path):
    rc = main(["--log", str(tmp_path / "nope.log"), "--table"])
    assert rc == 2


def test_empty_log_exits_2(tmp_path):
    rc = main(["--log", _write(tmp_path, "empty.log", "   \n\n"), "--table"])
    assert rc == 2


def test_log_without_a_compile_witness_exits_2(tmp_path):
    """لاگی که taskِ کامپایل در آن ندویده، **کوتاه** است نه **پاک**."""
    log = f"w: {CI}/Foo.kt:1:1 Variable 'x' is never used\nSome unrelated output\n"
    with pytest.raises(LogUnavailable) as exc:
        read_log(_write(tmp_path, "nowitness.log", log))
    assert "no witness" in str(exc.value)
    assert main(["--log", _write(tmp_path, "nowitness2.log", log), "--table"]) == 2


def test_build_failed_log_exits_2_because_the_inventory_is_partial(tmp_path):
    log = ("> Task :app:compileDebugKotlin\n"
           f"w: {CI}/Foo.kt:1:1 Variable 'x' is never used\n"
           "e: compilation failed\nBUILD FAILED in 12s\n")
    with pytest.raises(LogUnavailable) as exc:
        read_log(_write(tmp_path, "failed.log", log))
    assert "partial" in str(exc.value)
    assert main(["--log", _write(tmp_path, "failed2.log", log), "--check",
                 "--baseline", str(tmp_path / "b.json")]) == 2


def test_check_without_a_baseline_fails_instead_of_passing(tmp_path, capsys):
    """نبودنِ baseline یعنی وضعیت **ناشناخته** است؛ گیتِ بی‌داده سبز نمی‌شود."""
    log = _write(tmp_path, "ok.log", REALISTIC_LOG)
    rc = main(["--log", log, "--check", "--baseline", str(tmp_path / "absent.json")])
    assert rc == 1
    assert "baseline not found" in capsys.readouterr().out


# ── ۳) معنایِ گیت ────────────────────────────────────────────────────────────
def _baseline(tmp_path, payload: dict) -> str:
    p = tmp_path / "kotlin-warnings-baseline.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(p)


def _full_baseline(stats: dict) -> dict:
    return {"total": stats["total"], "distinct_kinds": stats["distinct_kinds"],
            "by_kind": dict(stats["by_kind"]), "files_with_warnings": stats["files_with_warnings"],
            "top_files": stats["top_files"], "log": "x", "source": "test"}


def test_gate_passes_when_the_log_matches_the_baseline_exactly(tmp_path, capsys):
    stats = _stats(REALISTIC_LOG)
    rc = main(["--log", _write(tmp_path, "ok.log", REALISTIC_LOG), "--check",
               "--baseline", _baseline(tmp_path, _full_baseline(stats))])
    assert rc == 0
    assert "delta +0" in capsys.readouterr().out


def test_gate_fails_on_a_brand_new_kind_even_with_a_single_occurrence(tmp_path, capsys):
    stats = _stats(REALISTIC_LOG)
    log = REALISTIC_LOG.replace(
        "BUILD SUCCESSFUL in 1m 42s",
        f"w: {CI}/NewFile.kt:7:3 Elvis operator (?:) always returns the left operand of non-null type\n"
        "BUILD SUCCESSFUL in 1m 42s")
    rc = main(["--log", _write(tmp_path, "new.log", log), "--check",
               "--baseline", _baseline(tmp_path, _full_baseline(stats))])
    assert rc == 1
    out = capsys.readouterr().out
    assert "new warning kinds" in out and "Elvis operator" in out


def test_gate_fails_when_an_existing_kind_grows(tmp_path, capsys):
    stats = _stats(REALISTIC_LOG)
    log = REALISTIC_LOG.replace(
        "BUILD SUCCESSFUL in 1m 42s",
        f"w: {CI}/Other.kt:9:9 Name shadowed: row\nBUILD SUCCESSFUL in 1m 42s")
    rc = main(["--log", _write(tmp_path, "grown.log", log), "--check",
               "--baseline", _baseline(tmp_path, _full_baseline(stats))])
    assert rc == 1
    out = capsys.readouterr().out
    # `Name shadowed: row` و `Name shadowed: item` **یک قالب‌اند** (شناسهٔ بی‌نقل‌قول
    # نرمال می‌شود)، پس این رشدِ واقعیِ یک قالبِ موجود است نه «قالبِ جدید».
    assert "new warning kinds" not in out
    assert "warning counts increased" in out and "Name shadowed: * 1->2" in out
    assert "total warnings increased: 4 -> 5" in out


def test_gate_passes_on_improvement_and_asks_for_the_baseline_to_be_tightened(tmp_path, capsys):
    stats = _stats(REALISTIC_LOG)
    shorter = "\n".join(line for line in REALISTIC_LOG.splitlines()
                         if "Name shadowed" not in line)
    rc = main(["--log", _write(tmp_path, "better.log", shorter), "--check",
               "--baseline", _baseline(tmp_path, _full_baseline(stats))])
    assert rc == 0
    out = capsys.readouterr().out
    assert "delta -1" in out
    assert "baseline can be refreshed" in out and "kinds fully resolved" in out


def test_write_baseline_then_check_round_trips(tmp_path, capsys):
    log = _write(tmp_path, "ok.log", REALISTIC_LOG)
    out_path = str(tmp_path / "written.json")
    assert main(["--log", log, "--write-baseline", "--baseline", out_path,
                 "--source", "test run"]) == 0
    payload = json.loads(Path(out_path).read_text(encoding="utf-8"))
    assert payload["total"] == 4 and payload["source"] == "test run"
    assert payload["by_kind"]["Variable '*' is never used"] == 1
    assert "_comment" in payload and len(payload["_comment"]) >= 4
    # همان baseline باید بی‌درنگ گیت را پاس کند
    assert main(["--log", log, "--check", "--baseline", out_path]) == 0
    assert "delta +0" in capsys.readouterr().out


# ── ۴) کانالِ annotation ────────────────────────────────────────────────────
def test_multiline_messages_are_percent_encoded_so_github_keeps_them(capsys):
    """باگی که فقط CI لو داد: GitHub پیامِ annotation را تا نخستین LF خام نگه می‌دارد.

    اندازه‌گیری در اجرایِ ۴۳۲۶۴۹۷۷۴۲۳: نسخهٔ اول newline خام چاپ می‌کرد، پس
    `--emit-baseline` فقط «{» را رساند (`message_len=1`، `raw_message` تهی) و `--table`
    فقط خطِ نخستِ جدول را. چون annotation تنها کانالِ بیرون‌کشیدنِ baseline از CI است،
    این باگ بی‌صدا مرحلهٔ enforcing را غیرممکن می‌کرد — و محلی دیده نمی‌شد چون خروجیِ
    چاپ‌شده رویِ ترمینال سالم به نظر می‌رسید.
    """
    body = "line one\nline two\nline three"
    assert emit_annotation("notice", "multi line body", body) == 1
    out = capsys.readouterr().out
    published = [ln for ln in out.splitlines() if ln.startswith("::notice")]
    assert len(published) == 1, "یک پیامِ چندخطی باید دقیقاً یک خطِ فیزیکی منتشر شود"
    assert "\n" not in published[0]
    assert "%0A" in published[0]
    # محتوایِ رمزگشایی‌شده باید عینِ ورودی باشد — یعنی چیزی دور ریخته نشده
    decoded = published[0].split("::", 2)[2].replace("%0A", "\n").replace("%25", "%")
    assert decoded == body


def test_escape_handles_percent_cr_and_lf():
    assert escape("a\nb") == "a%0Ab"
    assert escape("a\rb") == "a%0Db"
    # درصد نخست فرار می‌شود وگرنه %0Aهایِ خودِ متن با فرارِ ما قاطی می‌شوند
    assert escape("100% \n done") == "100%25 %0A done"
    # متنی که از قبل «%0A» دارد با فرارِ درصد دوپهلو نمی‌شود (درصد نخست فرار می‌شود)
    assert escape("%0A") == "%250A"


def test_annotations_chunk_below_the_measured_4kb_ceiling(capsys):
    body = "\n".join("x" * 200 for _ in range(60))          # ~12KB
    parts = emit_annotation("notice", "kotlin warning baseline JSON - commit as KharazmiAdmin", body)
    out = capsys.readouterr().out
    assert parts > 1
    physical = [ln for ln in out.splitlines() if ln.startswith("::notice")]
    assert len(physical) == parts, "هر قطعه باید دقیقاً یک خطِ فیزیکیِ بی‌LF باشد"
    for line in physical:
        assert len(line) <= MAX_ANNOTATION + 200, len(line)
        assert "\n" not in line
    # شمارهٔ قطعه در عنوان است، نه در پیام
    assert f"title=kotlin warning baseline JSON - commit as KharazmiAdmin (part 1/{parts})" in out
    assert f"(part {parts}/{parts})" in out
    # بازچسباندنِ قطعه‌ها باید عینِ ورودی را بدهد
    rejoined = "\n".join(ln.split("::", 2)[2].replace("%0A", "\n") for ln in physical)
    assert rejoined == body


def test_annotation_titles_never_contain_a_comma(capsys):
    """کاما جداکنندهٔ propertyها در workflow command است و عنوان را بی‌صدا کوتاه می‌کند."""
    emit_annotation("notice", "Kotlin warnings, 12 kinds, from CI", "body")
    title = capsys.readouterr().out.splitlines()[0]
    assert title.startswith("::notice title=")
    assert title.split("::", 2)[1].count(",") == 0


def test_short_annotation_is_a_single_part_without_numbering(capsys):
    assert emit_annotation("notice", "small", "one line") == 1
    out = capsys.readouterr().out
    assert "(part" not in out
