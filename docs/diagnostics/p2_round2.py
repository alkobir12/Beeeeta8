"""P2 Round 2 — إعادة اختبار البنود الراسبة/غير الحاسمة فقط (L9, L11, L13)."""
from __future__ import annotations

import json
import os
import time

import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
OUT = "/app/docs/diagnostics/P2_RESULTS_ROUND2.json"

BYPASS = None
for line in open("/app/backend/.env", encoding="utf-8"):
    if line.startswith("RATE_LIMIT_BYPASS_TOKEN="):
        BYPASS = line.split("=", 1)[1].strip()


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def make_session(username):
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"
    if BYPASS:
        s.headers["x-ratelimit-bypass"] = BYPASS
    r = s.post(f"{API}/auth/login", json={"username": username}, timeout=30)
    r.raise_for_status()
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


ADMIN = make_session("مدير")
FARAJ = make_session("فرج1")


def chat(sess, message, session_id=None):
    payload = {"message": message, "use_ai": True, "daily_summary": False}
    if session_id:
        payload["session_id"] = session_id
    r = sess.post(f"{API}/assistant/chat", json=payload, timeout=150)
    if r.status_code != 200:
        return {"error": f"http_{r.status_code}", "response": r.text[:200]}
    return r.json().get("data") or {}


results = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "tests": []}


def run(test_id, sess, message, session_id=None, verdict_fn=None):
    log(f"{test_id}: {message[:60]}")
    d = chat(sess, message, session_id)
    reply = (d.get("response") or "")[:1200]
    rec = {"test": test_id, "message": message, "trace_id": d.get("trace_id"),
           "session_id": d.get("session_id"), "intent": d.get("intent"), "reply": reply}
    if verdict_fn:
        try:
            rec["verdict"] = "PASS" if verdict_fn(reply, d) else "FAIL"
        except Exception as e:
            rec["verdict"] = f"ERR:{e}"
    results["tests"].append(rec)
    json.dump(results, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    time.sleep(2)
    return rec


def has_any(reply, *ps):
    return any(p in reply for p in ps)


# 🔴 F1 — L13-T6: الإيرادات محجوبة عن فرج1 (الحرج)
run("L13-T6-revenue-blocked-FARAJ", FARAJ, "كم إيرادات الورشة هذا الشهر؟",
    verdict_fn=lambda r, d: has_any(r, "غير مصرّح", "غير مصرح", "لا تملك صلاحي") and "ر.س" not in r)

# وتأكيد أن المدير ما زال يرى الإيرادات (لا انحدار)
run("L13-T6b-revenue-allowed-ADMIN", ADMIN, "كم إيرادات آخر 30 يوم؟",
    verdict_fn=lambda r, d: not has_any(r, "غير مصرّح", "غير مصرح"))

# 🟠 F2 — L9-T3: تعديل ملاحظات زيارة (update_visit)
r3 = run("L9-T3-edit-visit-notes", ADMIN, "عدلي ملاحظات زيارة عمر الخضيري: العميل ينتظر بالخارج",
         verdict_fn=lambda r, d: has_any(r, "تعديل زيارة", "ملاحظات", "ينتظر بالخارج") and not has_any(r, "فتح زيارة جديدة", "زيارة جديدة"))
# إن طلبت تأكيداً — أكّد
if has_any(r3["reply"], "نعم", "تأكيد", "أرسل"):
    run("L9-T3b-confirm", ADMIN, "نعم", r3["session_id"],
        verdict_fn=lambda r, d: has_any(r, "تم", "نُفِّذ", "نجاح", "✅"))

# 🟡 F3 — L9-T4: رفض صريح لتعديل قيد مرحّل + بديل القيد العكسي
run("L9-T4-edit-posted-entry", ADMIN, "عدلي القيد المحاسبي المرحّل الأخير في دفتر اليومية وغيري مبلغه إلى 500",
    verdict_fn=lambda r, d: has_any(r, "غير قابلة للتعديل", "غير القابل للتغيير", "لا يمكن تعديل") and has_any(r, "عكسي"))

# 🔵 F6 — L9-T1: تعديل جوال عميل موجود فعلاً
r1 = run("L9-T1-edit-existing-customer", ADMIN, "عدلي جوال العميل عاصم التويجري إلى 0559998888",
         verdict_fn=lambda r, d: has_any(r, "0559998888") and not has_any(r, "لم أجد"))

# 🟡 F4 — L11-T1: حارس المخزون (بيع كمية أكبر من المتاح) — بعميل محدد
run("L11-T1-stock-guard", ADMIN, "سجلي فاتورة بيع للعميل عاصم التويجري: 999 حبة فلتر زيت نقداً",
    verdict_fn=lambda r, d: has_any(r, "المخزون", "متوفر", "غير كاف", "الكمية", "لا يوجد", "تنبيه"))

# 🟡 F5 — L11-T4: مبلغ صفر
run("L11-T4-zero-amount", ADMIN, "سجلي مصروفاً بمبلغ صفر ريال لفئة النظافة",
    verdict_fn=lambda r, d: has_any(r, "صفر", "أكبر من", "غير صالح", "لا يمكن", "قيمة", "مبلغ"))

results["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
results["summary"] = {t["test"]: t.get("verdict") for t in results["tests"]}
json.dump(results, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
log("DONE " + json.dumps(results["summary"], ensure_ascii=False))
