"""🎭 بنك اختبارات أسلوب v4-qassimi-mirror — عبر LLM مباشرة (v4 غير مفعّلة في الإنتاج).
يستخدم نفس مسار _llm_chat (claude-sonnet-4-6 عبر Emergent) مع محتوى v4 كـ system prompt.
النتائج: /app/docs/diagnostics/V4_STYLE_RESULTS.json — كل نتيجة بمخرجات حرفية."""
import asyncio, json, re, sys, time
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

from core import prompt_registry
from core.assistant_kernel import _llm_chat

docs = prompt_registry.list_versions()
V4 = None
import os
from pymongo import MongoClient
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
V4 = db.prompt_versions.find_one({"version": "v4.1-qassimi-mirror"})["content"]

FAKE_TOOLS = ("\n\n🛠️ نتائج الأدوات المنفّذة لهذا السؤال:\n"
              "  • finance.ar_summary: {'ledger_ar_total': -13406.0, 'stored_balances_total': 9650.0, "
              "'top_debtor': {'name': 'عمر الخضيري', 'balance': 4500.0}}\n"
              "  • customers.search: {'name': 'يوسف عبد الرحمن الكبير', 'visit': '29b88c69', 'pending_drafts_total': 6474.0}\n")

FORMAL_BANNED = ["يسرني إعلامكم", "يرجى التكرم", "نفيدكم", "بناءً على طلبكم", "أشكرك على استفسارك", "يسعدني أن أوضح"]
DIALECT_MARKERS = ["وش", "ابي", "ابغى", "زين", "إيه", "ايه", "الحين", "أبشر", "ابشر", "تبي", "عليه", "هلا", "ودّك", "ودك", "لا هنت", "طلّع", "ورّني", "يصير"]

SCENARIOS = [
    {"id": "S1-fusha-stays-fusha",
     "msg": "ما هو رصيد ذمم العملاء الحالي وفق دفتر القيود؟",
     # 23,056 اشتقاق صحيح رياضياً — قفل الاشتقاق كلياً مؤجل للـHybrid Router (موثق في التقرير)
     "checks": {"no_formal_fake": True, "number_must_appear": "[-−]\\s?13,?406", "no_forced_dialect_opener": True,
                "no_wrong_numbers": ["3,756", "3756"]}},
    {"id": "S2-qassimi-number-only",
     "msg": "وش عليه عمر الخضيري الحين؟ ابي الرقم بس",
     "checks": {"number_must_appear": "4,500|4500", "max_chars": 120}},
    {"id": "S7-qassimi-conversational-mirror",
     "msg": "هلا كاترينا، وش وضع الذمم اليوم؟ عطني نبذة سريعة لا تطول علي",
     "checks": {"dialect_mirror": True, "no_formal_fake": True, "max_chars": 1200,
                "no_wrong_numbers": ["3,756", "3756", "23,056"]}},
    {"id": "S3-no-fake-formality",
     "msg": "ابي كشف سريع لذمم يوسف الكبير",
     "checks": {"no_formal_fake": True, "number_must_appear": "6,474|6474"}},
    {"id": "S4-numbers-untouched",
     "msg": "كم مجموع مسودات يوسف المعلقة؟",
     "checks": {"number_must_appear": "6,474|6474", "no_wrong_numbers": ["6475", "6.474", "647.4"]}},
    {"id": "S5-answer-first",
     "msg": "هل رصيد القيود سالب؟",
     "checks": {"answer_in_first_120": "نعم|إيه|ايه|سالب", "max_chars": 1200}},
    {"id": "S6-formal-request-respected",
     "msg": "أرجو تزويدي بصيغة رسمية موجزة عن رصيد الذمم لعرضها على المحاسب القانوني.",
     "checks": {"number_must_appear": "13,406|13406"}},
]

async def run():
    results = []
    for sc in SCENARIOS:
        t0 = time.time()
        resp = await _llm_chat(
            session_id=f"v4-style-{sc['id']}",
            system_message=V4 + FAKE_TOOLS,
            user_message=sc["msg"],
            history=[],
        )
        checks, ok = {}, True
        c = sc["checks"]
        if c.get("no_formal_fake"):
            hits = [w for w in FORMAL_BANNED if w in resp]
            checks["no_formal_fake"] = {"pass": not hits, "hits": hits}
            ok &= not hits
        if c.get("number_must_appear"):
            found = bool(re.search(c["number_must_appear"], resp))
            checks["number_must_appear"] = {"pass": found, "pattern": c["number_must_appear"]}
            ok &= found
        if c.get("no_wrong_numbers"):
            bad = [n for n in c["no_wrong_numbers"] if n in resp]
            checks["no_wrong_numbers"] = {"pass": not bad, "bad": bad}
            ok &= not bad
        if c.get("dialect_mirror"):
            hits = [w for w in DIALECT_MARKERS if w in resp]
            checks["dialect_mirror"] = {"pass": bool(hits), "markers_found": hits[:6]}
            ok &= bool(hits)
        if c.get("no_forced_dialect_opener"):
            first = resp[:120]
            forced = [w for w in ("وش", "ابشر", "أبشر", "تبي") if w in first]
            checks["no_forced_dialect_opener"] = {"pass": not forced, "forced": forced}
            ok &= not forced
        if c.get("max_chars"):
            checks["max_chars"] = {"pass": len(resp) <= c["max_chars"], "len": len(resp), "limit": c["max_chars"]}
            ok &= len(resp) <= c["max_chars"]
        if c.get("answer_in_first_120"):
            found = bool(re.search(c["answer_in_first_120"], resp[:120]))
            checks["answer_in_first_120"] = {"pass": found}
            ok &= found
        results.append({"id": sc["id"], "message": sc["msg"], "pass": ok,
                        "checks": checks, "duration_s": round(time.time() - t0, 1),
                        "response": resp})
        print(f"{'✅' if ok else '❌'} {sc['id']} ({round(time.time()-t0,1)}s) — {json.dumps({k: v['pass'] for k, v in checks.items()}, ensure_ascii=False)}")

    passed = sum(1 for r in results if r["pass"])
    out = {"ran_at": time.strftime("%Y-%m-%d %H:%M:%S"), "prompt_version": "v4.1-qassimi-mirror (inactive)",
           "model": "emergent/claude-sonnet-4-6", "passed": passed, "total": len(results), "results": results}
    json.dump(out, open("/app/docs/diagnostics/V4_STYLE_RESULTS.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n{passed}/{len(results)} passed — saved V4_STYLE_RESULTS.json")

asyncio.run(run())
