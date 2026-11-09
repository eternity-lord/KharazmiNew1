from __future__ import annotations

from pathlib import Path

from scripts.validate_app_map import parse_retrofit_calls


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
