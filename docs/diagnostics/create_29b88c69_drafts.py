"""Task 1 — create 5 invoice DRAFTS (Four-Eyes) for visit 29b88c69 settlement.
Pre-condition verified: unjournalized items == 6474.00 exactly. NO approval here."""
import json, os, sys
import requests
from dotenv import load_dotenv
load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
BYP = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip().strip('"')
S = requests.Session()
S.headers["x-ratelimit-bypass"] = BYP
tok = S.post(f"{API}/auth/login", json={"username": "مدير"}, timeout=30).json()["access_token"]
S.headers["Authorization"] = f"Bearer {tok}"

ITEMS = [
    ("القرعاوي (بند مورد)", 4046.0),
    ("القرعاوي (بند مورد)", 722.0),
    ("مخرطة العوفي (بند مورد)", 1170.0),
    ("سبايك ثابت/متحرك 10 (قطعة)", 416.0),
    ("غسيل ومعجون (خدمة ورشة)", 120.0),
]
assert abs(sum(a for _, a in ITEMS) - 6474.0) < 0.001, "totals drifted — ABORT"

created = []
for name, amount in ITEMS:
    payload = {
        "action": "invoice",
        "proposer": "كاترينا",
        "payload": {
            "customer": "يوسف عبد الرحمن الكبير",
            "plate": "ا ق ر 8825",
            "service": f"تسوية زيارة 29b88c69 — {name}",
            "total": amount,
            "payment_method": "credit",
            "workshop_id": "finmodule-sync",
        },
    }
    r = S.post(f"{API}/runtime/drafts", json=payload, timeout=30)
    d = r.json()
    if r.status_code != 200 or not d.get("success"):
        print("DRAFT CREATE FAILED:", r.status_code, r.text[:300]); sys.exit(1)
    did = d["data"]["id"]
    r2 = S.post(f"{API}/runtime/drafts/{did}/request_approval",
                json={"requester": "كاترينا"}, timeout=30)
    a = r2.json()
    if r2.status_code != 200 or not a.get("success"):
        print("APPROVAL REQUEST FAILED:", r2.status_code, r2.text[:300]); sys.exit(1)
    created.append({"draft_id": did, "approval_id": a["data"]["approval_id"],
                    "item": name, "amount": amount,
                    "status": a["data"]["draft"]["status"]})
    print(f"DRAFT {did} | approval {a['data']['approval_id']} | {name} | {amount} | {a['data']['draft']['status']}")

print(json.dumps({"total": sum(c["amount"] for c in created), "count": len(created)}, ensure_ascii=False))
with open("/app/docs/diagnostics/VISIT_29b88c69_SETTLEMENT_DRAFTS.json", "w", encoding="utf-8") as f:
    json.dump(created, f, ensure_ascii=False, indent=1)
