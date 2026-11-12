from __future__ import annotations

from pathlib import Path

from scripts.validate_app_map import evaluate_gate, parse_retrofit_calls


def test_retrofit_parser_handles_multiline_annotations_and_trailing_comments(tmp_path: Path):
    source = tmp_path / "Api.kt"
    source.write_text(
        '''package audit
interface ExampleApi {
    @POST(
        "classes/{course_id}/start_live", // nested path; keep the literal
    ) // annotation tail comment
    suspend fun start(@Body request: StartRequest): Response<LiveStartResponse>

    @GET("reports/summary/{id}") // request has parentheses below
    suspend fun get(@Path("id") id: Int): List<SummaryItem>
}
''',
        encoding="utf-8",
    )

    calls = parse_retrofit_calls(tmp_path)
    assert [(call["method"], call["path"]) for call in calls] == [
        ("POST", "classes/{course_id}/start_live"),
        ("GET", "reports/summary/{id}"),
    ]
    assert [(call["function"], call["response_type"]) for call in calls] == [
        ("start", "Response<LiveStartResponse>"),
        ("get", "List<SummaryItem>"),
    ]
    assert all(call["interface"] == "ExampleApi" for call in calls)


def test_current_android_inventory_is_source_grounded_and_complete():
    calls = parse_retrofit_calls()
    assert len(calls) == 170
    assert any(call["method"] == "POST" and call["path"] == "auth/device_token" for call in calls)
    assert not [call for call in calls if call["path"] == "<missing-path>"]
    assert not [call for call in calls if call["function"] == "<unknown>"]
    assert sum(call["path"].startswith("dynamic ") for call in calls) == 1
    live_api = {(call["method"], call["path"]) for call in calls if call["interface"] == "LiveApi"}
    assert {
        ("POST", "attendance/{course_id}/start_live"),
        ("POST", "attendance/{session_id}/live_status"),
        ("POST", "attendance/{session_id}/end_live"),
        ("POST", "attendance/{session_id}/cancel_live"),
        ("GET", "attendance/live/current"),
        ("GET", "admin/live_sessions"),
        ("GET", "admin/live_sessions/{session_id}/roster"),
    } <= live_api


# ── حالتِ `--gate` در scripts/validate_app_map.py ────────────────────────────────
# چرا این تست‌ها: exit code پیش‌فرضِ آن اسکریپت **عمداً** قرمز می‌ماند چون
# `docs/app-map/android-api-calls.csv` یک ورودیِ منجمدِ فازِ صفر است و ۸ اعلامِ
# LiveApi/`auth/device_token` را ندارد (تستِ بالا ۱۷۰ را برایِ سورس پین کرده).
# اسکریپتی که همیشه ۱ می‌دهد نمی‌تواند گیتِ CI باشد، پس سیگنال‌هایِ واقعاً مفیدش
# (`android_only_routes == 0`، `server_map_exact`، نبودِ اعلامِ شبح) هیچ‌وقت خودکار
# اجرا نمی‌شدند. `--gate` فقط همان‌ها را اجبار می‌کند و این سه تست مرزِ دقیقش را
# قفل می‌کنند: دریفتِ تاریخی **نباید** شکست بدهد، و هر سه نقضِ زنده **باید**.

def _clean_report(**over):
    rep = {
        "android_only_routes": 0,
        "android_only_list": [],
        "server_map_exact": True,
        "server_runtime_count": 221,
        "server_map_missing": [],
        "server_map_stale": [],
        "retrofit_source_map_missing": [],
        # دریفتِ تاریخیِ واقعیِ امروز: ۸ اعلامِ موجود در سورس ولی نه در CSVِ منجمد
        "retrofit_source_map_extra": [["POST", "auth/device_token"]],
    }
    rep.update(over)
    return rep


def test_gate_passes_when_only_the_historical_map_drifts():
    """دریفتِ فازِ صفر به‌تنهایی نباید گیت را بشکند، وگرنه گیت همیشه قرمز است."""
    assert evaluate_gate(_clean_report(), saved_count=221, live_keys={("GET", "students")}) == []


def test_gate_fails_on_every_live_contract_violation():
    live = {("GET", "students")}
    only_android = evaluate_gate(
        _clean_report(android_only_routes=1,
                      android_only_list=[["POST", "finance/ghost"]]),
        saved_count=221, live_keys=live)
    assert len(only_android) == 1 and "404" in only_android[0] and "finance/ghost" in only_android[0]

    csv_drift = evaluate_gate(
        _clean_report(server_map_exact=False,
                      server_map_missing=[["GET", "new/route"]], server_map_stale=[]),
        saved_count=221, live_keys=live)
    assert len(csv_drift) == 1 and "server_map_exact is False" in csv_drift[0]

    count_drift = evaluate_gate(_clean_report(server_runtime_count=222),
                                saved_count=221, live_keys=live)
    assert len(count_drift) == 1 and "count drift" in count_drift[0]

    no_scan = evaluate_gate(_clean_report(), saved_count=221, live_keys=None)
    assert len(no_scan) == 1 and "--skip-server-import" in no_scan[0]


def test_gate_fails_on_phantom_map_entries():
    """اعلامی که در CSVِ تاریخی هست ولی از سورسِ Kotlin ناپدید شده = نقشهٔ دروغین."""
    out = evaluate_gate(
        _clean_report(retrofit_source_map_missing=[["GET", "classes/deleted_long_ago"]]),
        saved_count=221, live_keys={("GET", "students")})
    assert len(out) == 1 and "classes/deleted_long_ago" in out[0]
