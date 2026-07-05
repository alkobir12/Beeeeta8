"""🔬 اختبارات llm_traces — المرحلة 0 من Katrina Verification Suite (الشرط المسبق)."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from core import llm_traces


def test_start_and_finish_roundtrip():
    tid = llm_traces.start_trace(session_id="pytest-s1", user="مدير", role="admin",
                                 message="سؤال اختباري")
    assert tid.startswith("tr-")
    assert llm_traces.active_trace_id() == tid
    out = llm_traces.finish_trace(session_id="pytest-s1", final_response="رد",
                                  intent="question", status=None)
    assert out == tid
    assert llm_traces.active_trace_id() is None
    doc = llm_traces.get_trace(tid)
    assert doc is not None
    assert doc["user_message"] == "سؤال اختباري"
    assert doc["final_response"] == "رد"
    assert doc["user"] == "مدير"
    assert doc["duration_ms"] is not None


def test_tool_and_llm_calls_recorded():
    tid = llm_traces.start_trace(session_id="pytest-s2", message="م")
    llm_traces.add_tool_call(tool="finance.ar_summary", tool_input={"workshop_id": "w"},
                             output_raw={"total_ar": 9850}, success=True, duration_ms=12.5)
    llm_traces.add_llm_call(purpose="chat", provider="anthropic", model="claude-sonnet-4-6",
                            system_message="sys", request_messages=[{"role": "user", "content": "م"}],
                            response_raw="raw resp", duration_ms=100.0)
    llm_traces.finish_trace(final_response="ok")
    doc = llm_traces.get_trace(tid)
    assert len(doc["tool_calls_executed"]) == 1
    tc = doc["tool_calls_executed"][0]
    assert tc["tool"] == "finance.ar_summary"
    assert "9850" in tc["output_raw"]
    assert len(doc["llm_calls"]) == 1
    lc = doc["llm_calls"][0]
    assert lc["response_raw"] == "raw resp"
    assert lc["request_messages"][0]["content"] == "م"


def test_no_active_trace_is_noop():
    llm_traces.add_tool_call(tool="x", success=True)
    llm_traces.add_llm_call(purpose="chat", provider="p", model="m")
    assert llm_traces.finish_trace() is None


def test_field_cap_truncation():
    tid = llm_traces.start_trace(session_id="pytest-s3", message="م")
    big = "x" * 100000
    llm_traces.add_tool_call(tool="big", output_raw=big, success=True)
    llm_traces.finish_trace()
    doc = llm_traces.get_trace(tid)
    out = doc["tool_calls_executed"][0]["output_raw"]
    assert len(out) < 70000
    assert "truncated" in out


def test_error_path_records_error():
    tid = llm_traces.start_trace(session_id="pytest-s4", message="م")
    llm_traces.add_llm_call(purpose="intent_parse", provider="anthropic",
                            model="claude-sonnet-4-6", error="Budget has been exceeded")
    llm_traces.finish_trace(status="error", error="boom")
    doc = llm_traces.get_trace(tid)
    assert doc["error"] == "boom"
    assert doc["llm_calls"][0]["error"] == "Budget has been exceeded"


def test_list_traces_by_session():
    rows = llm_traces.list_traces(session_id="pytest-s2", limit=5)
    assert any(r["session_id"] == "pytest-s2" for r in rows)


def test_context_isolation_between_tasks():
    async def _worker(sid):
        tid = llm_traces.start_trace(session_id=sid, message=sid)
        await asyncio.sleep(0.01)
        llm_traces.add_tool_call(tool=f"tool-{sid}", success=True)
        return llm_traces.finish_trace(final_response=sid)

    async def _main():
        return await asyncio.gather(_worker("iso-a"), _worker("iso-b"))

    ta, tb = asyncio.run(_main())
    da, db = llm_traces.get_trace(ta), llm_traces.get_trace(tb)
    assert da["tool_calls_executed"][0]["tool"] == "tool-iso-a"
    assert db["tool_calls_executed"][0]["tool"] == "tool-iso-b"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
