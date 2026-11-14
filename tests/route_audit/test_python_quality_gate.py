"""شاهدهایِ گیتِ کیفیتِ کدِ پایتون (`scripts/python_quality_gate.py`).

سه دسته پرسش اینجا پاسخ می‌گیرد:

۱) **پارس**: آیا خروجیِ واقعیِ ruff (JSON) و mypy (متنی با error-code) درست خوانده
   می‌شود، و — مهم‌تر — آیا ورودیِ ناقص/خراب به‌جایِ «صفر خطا» **رد** می‌شود؟ این
   همان قاعدهٔ سراسریِ گیت‌هایِ این ریپو است: خواندنِ ناموفق هرگز پاک گزارش نمی‌شود.
   mypy دو امضایِ خطرناک دارد: «errors prevented further checking» و «Cannot read
   file». هر دو خروجی را کوتاه می‌کنند و شمارشِ آن‌ها «بهبودِ بزرگ» به نظر می‌رسد.

۲) **معنایِ گیت**: چه چیزی شکست است (شناسهٔ تازه، شناسهٔ رشدکرده، افزایشِ جمع)، چه
   چیزی پاس ولی پیگیردار (بهبود ⇒ انتشارِ JSONِ آمادهٔ commit) و چه چیزی «ناشناخته»
   (اختلافِ نسخهٔ ابزار، نبودنِ baseline) ⇒ `exit 2`.

۳) **کانالِ annotation**: پیامِ چندخطی باید percent-encode و قطعه‌قطعه شود و عیناً
   بازچسبد، و عنوان کاما نداشته باشد — چون GitHub متن را تا نخستین LF خام نگه
   می‌دارد و کاما عنوان را بی‌صدا کوتاه می‌کند.

تست‌ها ابزارِ واقعی را اجرا نمی‌کنند (کند و وابسته به محیطِ نصب است)؛ `runner` تزریق
می‌شود. تنها دو تستِ آخر به فایل‌هایِ واقعیِ ریپو دست می‌زنند — baselineِ commit‌شده و
`Kharazmi_Server/requirements-dev.txt` — تا pinِ نسخه و baseline هیچ‌وقت بی‌صدا از هم
دور نیفتند (وگرنه گیت در CI با ruffِ دیگری اجرا می‌شود و صدها «خطایِ جدیدِ» بی‌معنا
می‌بیند).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.python_quality_gate import (
    MAX_ANNOTATION,
    MAX_PARTS,
    NO_CODE,
    ToolRun,
    ToolUnavailable,
    baseline_payload,
    check_against_baseline,
    collect,
    compact_table,
    emit_annotation,
    escape,
    fingerprint,
    locations_for_codes,
    main,
    parse_mypy_output,
    parse_ruff_json,
    relativize,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = REPO_ROOT / "scripts" / "python-quality-baseline.json"
DEV_REQUIREMENTS = REPO_ROOT / "Kharazmi_Server" / "requirements-dev.txt"

RUFF_VERSION_LINE = "ruff 0.17.4"
MYPY_VERSION_LINE = "mypy 2.4.1 (compiled: yes)"


# ── ۱) ابزارِ ساختِ ورودیِ جعلی ─────────────────────────────────


def ruff_item(root: Path, rel: str, code: str = "F841", line: int = 12, col: int = 5,
              msg: str = "local variable is assigned to but never used") -> dict:
    """یک آیتم به شکلِ **واقعیِ** `ruff check --output-format json` (همهٔ کلیدها)."""
    return {
        "cell": None,
        "code": code,
        "end_location": {"column": col + 1, "row": line},
        "filename": str(root / rel),
        "fix": None,
        "location": {"column": col, "row": line},
        "message": msg,
        "name": None,
        "noqa_row": None,
        "severity": "warning",
        "url": f"https://docs.astral.sh/ruff/rules/{code.lower()}",
    }


def mypy_text(errors: list[tuple[str, int, str]], checked: int = 9,
              notes: int = 0) -> str:
    """خروجیِ متنیِ mypy با جمع/مفردِ درست و با خطِ خلاصه‌ای که خودِ ابزار چاپ می‌کند."""
    lines: list[str] = []
    files = {rel for rel, _line, _code in errors}
    for i, (rel, line, code) in enumerate(errors):
        lines.append(f"{rel}:{line}: error: incompatible types in assignment  [{code}]")
        if i < notes:
            lines.append(f"{rel}:{line}: note: see the documentation")
    e_word = "error" if len(errors) == 1 else "errors"
    f_word = "file" if len(files) == 1 else "files"
    s_word = "source file" if checked == 1 else "source files"
    lines.append(f"Found {len(errors)} {e_word} in {len(files)} {f_word} (checked {checked} {s_word})")
    return "\n".join(lines)


def make_runner(ruff_items: list[dict] | None = None, mypy_out: str = "",
                ruff_rc: int = 1, mypy_rc: int = 1, version_rc: int = 0,
                ruff_version: str = RUFF_VERSION_LINE, mypy_version: str = MYPY_VERSION_LINE,
                ruff_raw: str | None = None):
    """runnerِ تزریقی با همان امضایِ `default_runner`: `(cmd, cwd) -> ToolRun`."""
    body = ruff_raw if ruff_raw is not None else json.dumps(ruff_items or [])

    def runner(cmd: list[str], cwd: Path) -> ToolRun:
        joined = " ".join(cmd)
        if "--version" in joined:
            if "mypy" in joined:
                return ToolRun(version_rc, mypy_version, "")
            return ToolRun(version_rc, ruff_version, "")
        if "mypy" in joined:
            return ToolRun(mypy_rc, mypy_out, "")
        return ToolRun(ruff_rc, body, "")

    return runner


def stats_for(root: Path, ruff_items: list[dict], mypy_errors: list[tuple[str, int, str]],
              **kwargs) -> dict:
    return collect(root, runner=make_runner(ruff_items, mypy_text(mypy_errors), **kwargs))


def write_baseline(path: Path, stats: dict, note: str = "test baseline") -> Path:
    path.write_text(json.dumps(baseline_payload(stats, note), ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path


TWO_ERRORS = [("pkg/models.py", 47, "valid-type"), ("pkg/routers/admin.py", 12, "arg-type")]


# ── ۲) پارسِ ruff ────────────────────────────────────────────────


def test_parse_ruff_json_reads_code_path_line_and_column(tmp_path):
    items = parse_ruff_json(json.dumps([ruff_item(tmp_path, "pkg/mod.py", "F841", 12, 5)]))
    assert len(items) == 1
    got = items[0]
    assert got["code"] == "F841"
    assert got["line"] == 12 and got["col"] == 5
    assert got["path"].endswith("pkg/mod.py")


def test_parse_ruff_json_rejects_output_that_is_not_json():
    with pytest.raises(ToolUnavailable, match="not parseable"):
        parse_ruff_json("error: unknown option --output-format\n")


def test_parse_ruff_json_rejects_a_json_value_that_is_not_a_list():
    with pytest.raises(ToolUnavailable, match="not a list"):
        parse_ruff_json(json.dumps({"violations": []}))


def test_parse_ruff_json_keeps_a_codeless_finding_visible(tmp_path):
    """ruff برایِ خطایِ نحوی `code` تهی می‌گذارد. رهایش نمی‌کنیم: یک خطایِ بی‌شناسه که
    بی‌صدا دور ریخته شود، در مقایسهٔ بعدی نه «شناسهٔ تازه» می‌شود نه «رشد» — یعنی
    گیت دقیقاً همان چیزی را نمی‌بیند که باید ببیند."""
    broken = ruff_item(tmp_path, "pkg/bad.py", "E999", 3, 1)
    broken["code"] = None
    items = parse_ruff_json(json.dumps([broken]))
    assert [i["code"] for i in items] == [NO_CODE]


# ── ۳) پارسِ mypy ────────────────────────────────────────────────


def test_parse_mypy_counts_only_errors_and_keeps_the_summary():
    text = mypy_text(TWO_ERRORS, checked=11, notes=2)
    errors, summary = parse_mypy_output(text)
    assert len(errors) == 2, "noteها خطا نیستند و نباید شمرده شوند"
    assert [e["code"] for e in errors] == ["valid-type", "arg-type"]
    assert summary == {"errors": 2, "files": 2, "checked": 11}
    assert all("note:" not in e["message"] for e in errors)


def test_parse_mypy_reads_optional_column_numbers():
    text = "pkg/mod.py:12:5: error: need type annotation  [var-annotated]\n" \
           "Found 1 error in 1 file (checked 4 source files)"
    errors, _summary = parse_mypy_output(text)
    assert errors[0]["line"] == 12 and errors[0]["col"] == 5


def test_parse_mypy_refuses_a_partial_inventory():
    """این امضایِ واقعیِ «موجودیِ ناقص» است؛ شمارشش «بهبود» به نظر می‌رسد."""
    text = ("pkg/mod.py:1: error: Cannot resolve  [misc]\n"
            "Found 1 error in 1 file (errors prevented further checking)")
    with pytest.raises(ToolUnavailable, match="partial"):
        parse_mypy_output(text)


def test_parse_mypy_refuses_a_cannot_read_file_inventory():
    text = "Kharazmi_Server: error: Cannot read file: No such file or directory\n"
    with pytest.raises(ToolUnavailable, match="partial"):
        parse_mypy_output(text)


def test_parse_mypy_refuses_output_without_a_summary_line():
    with pytest.raises(ToolUnavailable, match="no summary line"):
        parse_mypy_output("pkg/mod.py:12: error: boom  [misc]\n")


def test_parse_mypy_accepts_a_clean_run():
    errors, summary = parse_mypy_output("Success: no issues found in 55 source files")
    assert errors == []
    assert summary == {"errors": 0, "files": 0, "checked": 55}


# ── ۴) مسیرها ────────────────────────────────────────────────────


def test_relativize_makes_the_baseline_portable(tmp_path):
    """ruff مسیرِ مطلق می‌دهد و mypy مسیرِ نسبی به پوشهٔ اجرا. هر دو باید به یک
    مسیرِ نسبیِ یکسان برسند وگرنه baseline بینِ ماشینِ توسعه و CI قابلِ حمل نیست."""
    absolute = str(tmp_path / "pkg" / "mod.py")
    relative = "pkg/mod.py"
    assert relativize(absolute, tmp_path) == relative
    assert relativize(relative, tmp_path) == relative


def test_relativize_keeps_a_foreign_path_instead_of_dropping_it(tmp_path):
    other = tmp_path.parent / "elsewhere" / "x.py"
    assert relativize(str(other), tmp_path) == other.as_posix()


# ── ۵) collect: کدهایِ خروج و شاهدِ درونی ─────────────────────────


def test_collect_accepts_ruff_exit_1_because_findings_are_normal(tmp_path):
    stats = stats_for(tmp_path, [ruff_item(tmp_path, "a.py")], TWO_ERRORS)
    assert stats["ruff"]["total"] == 1 and stats["mypy"]["total"] == 2


def test_collect_refuses_ruff_exit_2(tmp_path):
    runner = make_runner([], mypy_text(TWO_ERRORS), ruff_rc=2)
    with pytest.raises(ToolUnavailable, match="ruff failed to run"):
        collect(tmp_path, runner=runner)


def test_collect_refuses_mypy_exit_2(tmp_path):
    runner = make_runner([ruff_item(tmp_path, "a.py")], "", mypy_rc=2)
    with pytest.raises(ToolUnavailable, match="mypy failed to run"):
        collect(tmp_path, runner=runner)


def test_collect_refuses_a_summary_that_disagrees_with_the_parsed_errors(tmp_path):
    """شاهدِ درونیِ mypy: اگر خطِ خلاصه بگوید ۵ خطا ولی ۲ خطا پارس شده باشد، موجودی
    ناقص است. بدونِ این شاهد، یک اجرایِ خراب «بهبودِ ۳ خطایی» خوانده می‌شد."""
    runner = make_runner([], "pkg/a.py:1: error: x  [misc]\npkg/b.py:2: error: y  [misc]\n"
                             "Found 5 errors in 2 files (checked 9 source files)")
    with pytest.raises(ToolUnavailable, match="summary says 5 errors"):
        collect(tmp_path, runner=runner)


def test_collect_refuses_a_summary_that_disagrees_on_the_file_count(tmp_path):
    runner = make_runner([], "pkg/a.py:1: error: x  [misc]\npkg/b.py:2: error: y  [misc]\n"
                             "Found 2 errors in 7 files (checked 9 source files)")
    with pytest.raises(ToolUnavailable, match="summary says 7 files"):
        collect(tmp_path, runner=runner)


def test_collect_refuses_a_broken_version_probe(tmp_path):
    runner = make_runner([], mypy_text(TWO_ERRORS), version_rc=1)
    with pytest.raises(ToolUnavailable, match="--version failed"):
        collect(tmp_path, runner=runner)


def test_collect_refuses_to_run_without_a_ruff_executable(tmp_path, monkeypatch):
    def boom(interpreter=None):
        raise ToolUnavailable("ruff executable not found")

    monkeypatch.setattr("scripts.python_quality_gate.find_ruff", boom)
    with pytest.raises(ToolUnavailable, match="not found"):
        collect(tmp_path, runner=make_runner([], mypy_text(TWO_ERRORS)))


def test_collect_counts_by_code_and_top_files_for_both_tools(tmp_path):
    items = [ruff_item(tmp_path, "a.py", "F841", 1), ruff_item(tmp_path, "a.py", "F841", 2),
             ruff_item(tmp_path, "b.py", "E701", 3)]
    stats = stats_for(tmp_path, items, TWO_ERRORS)
    ruff = stats["ruff"]
    assert ruff["total"] == 3 and ruff["distinct_codes"] == 2
    assert ruff["by_code"]["F841"] == 2 and ruff["by_code"]["E701"] == 1
    assert ruff["files_with_issues"] == 2
    assert next(iter(ruff["top_files"])) == "a.py", "ترتیب top_files باید نزولی باشد"
    mypy = stats["mypy"]
    assert mypy["by_code"] == {"valid-type": 1, "arg-type": 1}
    assert mypy["checked_files"] == 9


# ── ۶) معنایِ گیت ────────────────────────────────────────────────


def test_gate_passes_when_the_inventory_matches_the_baseline(tmp_path, capsys):
    stats = stats_for(tmp_path, [ruff_item(tmp_path, "a.py")], TWO_ERRORS)
    base = write_baseline(tmp_path / "b.json", stats)
    assert check_against_baseline(stats, str(base)) == 0
    out = capsys.readouterr().out
    assert "delta +0" in out and "no change against the baseline" in out
    assert "::error" not in out


def test_gate_fails_on_a_brand_new_code(tmp_path, capsys):
    before = stats_for(tmp_path, [ruff_item(tmp_path, "a.py")], TWO_ERRORS)
    base = write_baseline(tmp_path / "b.json", before)
    after = stats_for(tmp_path, [ruff_item(tmp_path, "a.py"), ruff_item(tmp_path, "c.py", "B006", 9)],
                      TWO_ERRORS)
    assert check_against_baseline(after, str(base)) == 1
    out = capsys.readouterr().out
    assert "ruff: new codes (not in the baseline): B006 x1" in out
    assert "::error title=python quality gate::" in out
    assert "B006" in out and "c.py:9" in out, "شکست باید مکانِ قابلِ عمل بدهد"


def test_gate_fails_when_an_existing_code_grows(tmp_path, capsys):
    before = stats_for(tmp_path, [ruff_item(tmp_path, "a.py")], TWO_ERRORS)
    base = write_baseline(tmp_path / "b.json", before)
    after = stats_for(tmp_path, [ruff_item(tmp_path, "a.py"), ruff_item(tmp_path, "b.py", "F841", 4)],
                      TWO_ERRORS)
    assert check_against_baseline(after, str(base)) == 1
    assert "ruff: counts increased: F841 1->2" in capsys.readouterr().out


def test_gate_fails_when_a_mypy_code_grows(tmp_path, capsys):
    before = stats_for(tmp_path, [], TWO_ERRORS)
    base = write_baseline(tmp_path / "b.json", before)
    after = stats_for(tmp_path, [], [*TWO_ERRORS, ("pkg/more.py", 5, "arg-type")])
    assert check_against_baseline(after, str(base)) == 1
    assert "mypy: counts increased: arg-type 1->2" in capsys.readouterr().out


def test_gate_passes_on_improvement_and_publishes_commit_ready_json(tmp_path, capsys):
    """بهبود شکست نیست — ولی بی‌اثر هم نمی‌ماند: JSONِ آمادهٔ commit منتشر می‌شود تا
    بهبود قفل شود. درسِ عملیِ PR #27: بدونِ این قفل، بازگشتِ همان خطا بی‌صدا می‌ماند."""
    before = stats_for(tmp_path, [ruff_item(tmp_path, "a.py"), ruff_item(tmp_path, "b.py", "E701", 3)],
                       TWO_ERRORS)
    base = write_baseline(tmp_path / "b.json", before)
    after = stats_for(tmp_path, [ruff_item(tmp_path, "a.py")], TWO_ERRORS)
    assert check_against_baseline(after, str(base)) == 0
    out = capsys.readouterr().out
    assert "baseline can be refreshed" in out
    assert "codes fully resolved: ruff:E701" in out
    assert "python quality baseline refreshed - commit as scripts/python-quality-baseline.json" in out


def test_the_published_json_then_passes_the_gate(tmp_path, capsys):
    """دورِ کامل: همان JSONِ منتشرشده در annotation باید بدونِ ویرایشِ دستی گیت را پاس کند."""
    before = stats_for(tmp_path, [ruff_item(tmp_path, "a.py"), ruff_item(tmp_path, "b.py", "E701", 3)],
                       TWO_ERRORS)
    base = write_baseline(tmp_path / "b.json", before)
    after = stats_for(tmp_path, [ruff_item(tmp_path, "a.py")], TWO_ERRORS)
    check_against_baseline(after, str(base))
    out = capsys.readouterr().out
    marker = "::notice title=python quality baseline refreshed"
    line = next(l for l in out.splitlines() if l.startswith(marker))
    decoded = line.split("::", 2)[2].replace("%0A", "\n").replace("%0D", "\r").replace("%25", "%")
    payload = json.loads(decoded[decoded.index("{"):decoded.rindex("}") + 1])
    refreshed = write_baseline(tmp_path / "r.json", payload, note=payload["source"])
    capsys.readouterr()
    assert check_against_baseline(after, str(refreshed)) == 0
    assert "delta +0" in capsys.readouterr().out


def test_gate_fails_closed_when_the_baseline_is_missing(tmp_path, capsys):
    stats = stats_for(tmp_path, [], TWO_ERRORS)
    missing = tmp_path / "nope.json"
    assert check_against_baseline(stats, str(missing)) == 1
    assert "baseline not found" in capsys.readouterr().out


def test_gate_fails_when_the_baseline_is_unreadable(tmp_path, capsys):
    broken = tmp_path / "b.json"
    broken.write_text("{ not json", encoding="utf-8")
    stats = stats_for(tmp_path, [], TWO_ERRORS)
    assert check_against_baseline(stats, str(broken)) == 1
    assert "baseline unreadable" in capsys.readouterr().out


def test_gate_reports_version_mismatch_as_unknown_not_as_pass(tmp_path, capsys):
    """ruff بین نسخه‌ها قواعدِ تازه اضافه می‌کند؛ شمارِ نسخهٔ دیگر با این baseline
    مقایسه‌شدنی نیست. پس نه پاس می‌دهیم نه شکست — `exit 2` یعنی «ناشناخته»."""
    stats = stats_for(tmp_path, [], TWO_ERRORS)
    base = write_baseline(tmp_path / "b.json", stats)
    drifted = stats_for(tmp_path, [], TWO_ERRORS, ruff_version="ruff 9.9.9")
    assert drifted["ruff"]["version"] == "9.9.9"
    assert check_against_baseline(drifted, str(base)) == 2
    out = capsys.readouterr().out
    assert "ruff version mismatch: baseline was built with 0.17.4 but this run used 9.9.9" in out
    assert "delta" not in out, "در وضعیتِ ناشناخته هیچ مقایسه‌ای چاپ نمی‌شود"


# ── ۷) کانالِ annotation ──────────────────────────────────────────


def test_escape_percent_encodes_percent_cr_and_lf():
    assert escape("a%b") == "a%25b"
    assert escape("a\nb") == "a%0Ab"
    assert escape("a\r\nb") == "a%0D%0Ab"
    assert escape(escape("a%b")) != escape("a%b"), "فرار باید درصدِ خودش را هم ببیند"


def test_multiline_payload_is_chunked_below_the_ceiling_and_rejoins_exactly(capsys):
    body = "\n".join("x" * 200 for _ in range(60))
    parts = emit_annotation("notice", "python quality baseline JSON - commit as scripts", body)
    out = capsys.readouterr().out
    assert parts > 1
    physical = [ln for ln in out.splitlines() if ln.startswith("::notice")]
    assert len(physical) == parts, "هر قطعه باید دقیقاً یک خطِ فیزیکیِ بی‌LF باشد"
    for line in physical:
        assert len(line) <= MAX_ANNOTATION + 200
        assert "\n" not in line
    assert "(part 1/" in out and f"(part {parts}/{parts})" in out
    rejoined = "\n".join(ln.split("::", 2)[2].replace("%0A", "\n") for ln in physical)
    assert rejoined == body


def test_annotation_titles_never_contain_a_comma(capsys):
    emit_annotation("notice", "Python quality, 27 codes, from CI", "body")
    title = capsys.readouterr().out.splitlines()[0]
    assert title.startswith("::notice title=")
    assert title.split("::", 2)[1].count(",") == 0


def test_short_annotation_is_a_single_part_without_numbering(capsys):
    assert emit_annotation("notice", "small", "one line") == 1
    assert "(part" not in capsys.readouterr().out


def test_too_many_parts_are_truncated_loudly_not_silently(capsys):
    body = "\n".join("y" * 3800 for _ in range(MAX_PARTS + 3))
    parts = emit_annotation("notice", "huge", body)
    out = capsys.readouterr().out
    assert parts == MAX_PARTS
    assert "::warning title=huge - truncated for the annotation channel::" in out


# ── ۸) CLI و جدول ────────────────────────────────────────────────


def test_main_requires_a_mode():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2, "argparse باید با کدِ ۲ ببندد، نه بی‌صدا برگردد"


def test_main_check_runs_end_to_end_with_an_injected_root(tmp_path, monkeypatch, capsys):
    stats = stats_for(tmp_path, [ruff_item(tmp_path, "a.py")], TWO_ERRORS)
    base = write_baseline(tmp_path / "b.json", stats)
    monkeypatch.setattr("scripts.python_quality_gate.collect",
                        lambda root=None, runner=None: stats)
    assert main(["--check", "--baseline", str(base), "--root", str(tmp_path)]) == 0
    assert "delta +0" in capsys.readouterr().out


def test_locations_reports_only_the_requested_codes(tmp_path):
    stats = stats_for(tmp_path, [ruff_item(tmp_path, "a.py", "F841", 12, 5),
                                 ruff_item(tmp_path, "b.py", "E701", 3, 1)],
                      TWO_ERRORS)
    body = locations_for_codes(stats, {"F841"}, max_per_code=10)
    assert "[ruff] F841 (x1)" in body and "a.py:12:5" in body
    assert "E701" not in body and "arg-type" not in body


def test_locations_caps_the_number_of_positions_per_code(tmp_path):
    items = [ruff_item(tmp_path, f"f{i}.py", "F841", i) for i in range(1, 8)]
    stats = stats_for(tmp_path, items, TWO_ERRORS)
    body = locations_for_codes(stats, {"F841"}, max_per_code=3)
    assert "… and 4 more" in body
    assert body.count("F841") == 1, "سرخطِ شناسه یک بار چاپ می‌شود، نه به ازای هر موقعیت"


def test_compact_table_is_non_empty_and_names_both_tools(tmp_path):
    stats = stats_for(tmp_path, [ruff_item(tmp_path, "a.py")], TWO_ERRORS)
    table = compact_table(stats)
    assert "ruff 0.17.4:" in table and "mypy 2.4.1:" in table
    assert "F841" in table and "arg-type" in table
    assert "checked source files: 9" in table


def test_fingerprint_ignores_only_the_source_field(tmp_path):
    stats = stats_for(tmp_path, [], TWO_ERRORS)
    a = baseline_payload(stats, "one provenance")
    b = baseline_payload(stats, "another provenance")
    assert fingerprint(a) == fingerprint(b)
    c = baseline_payload(stats_for(tmp_path, [ruff_item(tmp_path, "a.py")], TWO_ERRORS), "x")
    assert fingerprint(a) != fingerprint(c)


# ── ۹) دو شاهدِ ریپویِ واقعی ─────────────────────────────────────


def _pinned_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in DEV_REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "==" in line and not line.startswith("#"):
            name, version = line.split("==", 1)
            out[name.strip()] = version.strip()
    return out


def test_committed_baseline_agrees_with_the_pinned_tool_versions():
    """قفلِ اصلیِ این شاهد: اگر کسی ruff/mypy را در requirements-dev.txt ارتقا دهد و
    baseline را تازه نکند، گیت در CI `exit 2` می‌دهد (درست) ولی اینجا هم قرمز می‌شود تا
    علت پیش از یک دورِ CI دیده شود."""
    pins = _pinned_versions()
    assert "ruff" in pins and "mypy" in pins, DEV_REQUIREMENTS
    base = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    assert base["ruff"]["version"] == pins["ruff"]
    assert base["mypy"]["version"] == pins["mypy"]


def test_committed_baseline_is_self_consistent():
    base = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    for tool in ("ruff", "mypy"):
        section = base[tool]
        assert sum(section["by_code"].values()) == section["total"], tool
        assert len(section["by_code"]) == section["distinct_codes"], tool
        assert section["files_with_issues"] >= len(section["top_files"]), tool
        assert sum(section["top_files"].values()) <= section["total"], tool
        assert section["total"] > 0, "baselineِ صفر یعنی گیت بی‌اثر است"
    assert base["totals"]["combined"] == base["ruff"]["total"] + base["mypy"]["total"]
    assert base["mypy"]["checked_files"] >= base["mypy"]["files_with_issues"]
    assert all(p.startswith(("Kharazmi_Server/", "scripts/", "tests/"))
               for p in base["ruff"]["top_files"]), "مسیرها باید نسبیِ ریپو باشند"
