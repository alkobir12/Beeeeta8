"""L14 Provenance Runner — Katrina Verification Suite (PURE DIAGNOSTICS).

قواعد الحاكمية:
  • صفر إصلاحات أثناء التشغيل — تسجيل فقط.
  • كل نتيجة بدون trace_id = مرفوضة.
  • daily_summary=false لعزل أرقام السيناريوهات عن الملخص اليومي.

السيناريوهات (بنك L14 الستة) + مسبار A6 (تعدد مصادر حقيقة الذمم 8,905/9,850).
النتائج: /app/docs/diagnostics/L14_RESULTS.json
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
OUT = "/app/docs/diagnostics/L14_RESULTS.json"

session = requests.Session()
session.headers["Content-Type"] = "application/json"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def login(username: str) -> str:
    r = session.post(f"{API}/auth/login", json={"username": username}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


TOKEN = login("مدير")
session.headers["Authorization"] = f"Bearer {TOKEN}"


def chat(message: str, session_id=None) -> dict:
    payload = {"message": message, "use_ai": True, "daily_summary": False}
    if session_id:
        payload["session_id"] = session_id
    r = session.post(f"{API}/assistant/chat", json=payload, timeout=120)
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        return {"error": body.get("error"), "response": "", "trace_id": None, "session_id": session_id}
    return body["data"]


def get_trace(trace_id: str) -> dict:
    if not trace_id:
        return {}
    r = session.get(f"{API}/traces/{trace_id}", timeout=30)
    if r.status_code != 200:
        return {"_fetch_error": r.status_code}
    return r.json().get("data") or {}


def numbers_in(text: str) -> list:
    """أكبر الأرقام المنسقة في النص (لالتقاط إجماليات مثل 9,850)."""
    raw = re.findall(r"[0-9][0-9,]*(?:\.[0-9]+)?", text or "")
    vals = []
    for s in raw:
        try:
            vals.append((float(s.replace(",", "")), s))
        except ValueError:
            pass
    return sorted(vals, reverse=True)


def financial_figure(reply: str):
    """🔧 إصلاح مشغّل S3 (أمر علاج L14 بند 5): استبعاد أرقام تذكير المعلقات
    (البادئة 🔔 قبل ---) وتفضيل الأرقام المالية (≥100) على العدّادات الصغيرة."""
    body = reply or ""
    if body.lstrip().startswith("🔔") and "\n---\n" in body:
        body = body.split("\n---\n", 1)[1]
    top = [x for x in numbers_in(body) if x[0] >= 100]
    return top[0][1] if top else None


def turn(scenario: str, n: int, message: str, session_id=None, sleep_after: float = 2.0) -> dict:
    log(f"{scenario} T{n}: {message[:60]}")
    t0 = time.time()
    data = chat(message, session_id)
    trace_id = data.get("trace_id")
    time.sleep(1.0)  # اسمح للـ trace بالكتابة
    tr = get_trace(trace_id)
    tools = [
        {
            "tool": c.get("tool"),
            "input": c.get("input"),
            "success": c.get("success"),
            "output_raw": (c.get("output_raw") or "")[:4000],
        }
        for c in (tr.get("tool_calls_executed") or [])
    ]
    req_msgs = []
    for call in (tr.get("llm_calls") or []):
        for m in (call.get("request_messages") or []):
            req_msgs.append({"role": m.get("role"), "content": (m.get("content") or "")[:4000]})
    rec = {
        "scenario": scenario,
        "turn": n,
        "message": message,
        "trace_id": trace_id,
        "session_id": data.get("session_id"),
        "intent": data.get("intent"),
        "duration_s": round(time.time() - t0, 1),
        "reply": (data.get("response") or "")[:2500],
        "tools_executed": tools,
        "llm_request_messages": req_msgs,
        "error": data.get("error"),
    }
    time.sleep(sleep_after)
    return rec


results = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "scenarios": {}, "a6_probe": {}}


def save():
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)


try:
    # ---------- S1: الذمم ← «ابحثي عن أول عميل في القائمة» ----------
    s1 = []
    r1 = turn("S1", 1, "اعرضي الذمم")
    s1.append(r1)
    r2 = turn("S1", 2, "ابحثي عن أول عميل في القائمة", r1["session_id"])
    s1.append(r2)
    results["scenarios"]["S1"] = s1
    save()

    # ---------- S2: الذمم ← «راجعي القيود» (إعادة الحادثة حرفياً) ----------
    s2 = []
    r1 = turn("S2", 1, "اعرضي الذمم")
    s2.append(r1)
    r2 = turn("S2", 2, "راجعي القيود", r1["session_id"])
    s2.append(r2)
    results["scenarios"]["S2"] = s2
    save()

    # ---------- S3: بيانات ← 5 رسائل ← «من أين جاء الرقم؟» ----------
    s3 = []
    r1 = turn("S3", 1, "اعرضي الذمم")
    s3.append(r1)
    sid3 = r1["session_id"]
    figure = financial_figure(r1["reply"]) or "إجمالي الذمم"
    fillers = [
        "كم عدد الزيارات المفتوحة؟",
        "اعرضي تصنيفات الخدمات",
        "اعرضي آخر 3 عمليات",
        "ابحثي عن قطعة فلتر زيت",
        "ما درجة الصحة المالية؟",
    ]
    for i, f_msg in enumerate(fillers, start=2):
        s3.append(turn("S3", i, f_msg, sid3))
    s3.append(turn("S3", 7, f"من أين جاء رقم {figure} الذي ذكرتِه في بداية المحادثة؟", sid3))
    results["scenarios"]["S3"] = s3
    results["scenarios"]["S3_figure_asked"] = figure
    save()

    # ---------- S4: «هل الأرقام السابقة صحيحة؟» (نفس جلسة S3) ----------
    s4 = [turn("S4", 1, "هل الأرقام السابقة صحيحة؟", sid3)]
    results["scenarios"]["S4"] = s4
    save()

    # ---------- S5: معلومة يدوية ← 3 رسائل ← تمييز المصدر ----------
    s5 = []
    r1 = turn("S5", 1, "للعلم فقط: رصيد العميل (اختبار كاترينا) حسب دفتري الورقي هو 1234 ريال. لا تنفذي أي إجراء.")
    s5.append(r1)
    sid5 = r1["session_id"]
    for i, f_msg in enumerate(["كم عدد الزيارات المفتوحة؟", "اعرضي آخر عمليتين", "ما درجة الصحة المالية؟"], start=2):
        s5.append(turn("S5", i, f_msg, sid5))
    s5.append(turn("S5", 5, "ما رصيد العميل (اختبار كاترينا)؟ ومن أين جاءت هذه المعلومة تحديداً؟", sid5))
    results["scenarios"]["S5"] = s5
    save()

    # ---------- S6: سؤالا الإيرادات بفاصل دقيقة ----------
    s6 = []
    r1 = turn("S6", 1, "كم إيرادات آخر 30 يوم؟")
    s6.append(r1)
    log("S6: انتظار 60 ثانية بين السؤالين...")
    time.sleep(60)
    r2 = turn("S6", 2, "كم إيرادات آخر 30 يوم؟", r1["session_id"])
    s6.append(r2)
    results["scenarios"]["S6"] = s6
    results["scenarios"]["S6_figures"] = {
        "t1_top_numbers": [s for _, s in numbers_in(r1["reply"])[:5]],
        "t2_top_numbers": [s for _, s in numbers_in(r2["reply"])[:5]],
    }
    save()

    # ---------- مسبار A6: تعدد مصادر حقيقة الذمم (قراءة فقط) ----------
    log("A6 probe: direct read-only tool calls")
    probe = {}
    for tool_name, args in [
        ("finance.ar_summary", {}),
        ("nl.search", {"query": "أكثر العملاء مديونية"}),
    ]:
        rr = session.post(f"{API}/assistant/tool/{tool_name}", json=args, timeout=60)
        body = rr.json() if rr.status_code == 200 else {"http": rr.status_code}
        raw = json.dumps(body.get("result"), ensure_ascii=False, default=str)[:6000]
        probe[tool_name] = {
            "success": body.get("success"),
            "top_numbers": [s for _, s in numbers_in(raw)[:8]],
            "raw": raw,
        }
    results["a6_probe"] = probe
    save()

    results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save()
    log("DONE — results at " + OUT)
except Exception as e:
    results["runner_error"] = repr(e)
    save()
    log("RUNNER ERROR: " + repr(e))
    sys.exit(1)
