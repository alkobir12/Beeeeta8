"""دمج العملاء المكررين — بتحقق مزدوج (الاسم الموحد + الهاتف أو مركبة مشتركة).
يعيد ربط المركبات وطلبات الاعتماد بالسجل الأساسي ثم يحذف المكرر. يطبع تقرير JSON.
Usage: python merge_duplicate_customers.py [--apply]
"""
import json
import re
import sys
from collections import defaultdict

from dotenv import load_dotenv
load_dotenv()
from supabase_service import SupabaseService  # noqa: E402


def norm_name(v):
    s = re.sub(r"\s+", " ", str(v or "").strip())
    return s


def norm_phone(v):
    return re.sub(r"\D", "", str(v or ""))


def main(apply=False):
    s = SupabaseService()
    customers = s.client.table("customers").select("*").execute().data or []
    vehicles = s.client.table("vehicles").select("id,customer_id,customer_name").execute().data or []

    veh_by_customer = defaultdict(list)
    for v in vehicles:
        cid = str(v.get("customer_id") or "")
        if cid:
            veh_by_customer[cid].append(v["id"])

    groups = defaultdict(list)
    for c in customers:
        groups[norm_name(c.get("name"))].append(c)

    report = {"merged": [], "needs_review": [], "apply": apply}
    for name, rows in groups.items():
        if len(rows) < 2 or not name:
            continue
        phones = {norm_phone(r.get("phone")) for r in rows if norm_phone(r.get("phone"))}
        same_phone = len(phones) <= 1
        with_vehicles = [r for r in rows if veh_by_customer.get(str(r["id"]))]
        # تحقق: نفس الهاتف أو واحد فقط منهم يملك مركبات
        confident = same_phone or len(with_vehicles) <= 1
        if not confident:
            report["needs_review"].append({
                "name": name,
                "records": [{"id": r["id"], "phone": r.get("phone"), "vehicles": veh_by_customer.get(str(r["id"]), [])} for r in rows],
                "reason": "هواتف مختلفة وكلاهما يملك مركبات — يحتاج قرارك",
            })
            continue
        # الأساسي: من يملك مركبات، وإلا الأقدم
        primary = (with_vehicles[0] if with_vehicles else sorted(rows, key=lambda r: str(r.get("created_at") or ""))[0])
        dupes = [r for r in rows if r["id"] != primary["id"]]
        entry = {"name": name, "primary": primary["id"], "merged_ids": [d["id"] for d in dupes], "relinked_vehicles": []}
        if apply:
            for d in dupes:
                for tbl, col in (("vehicles", "customer_id"), ("approval_requests", "customer_id")):
                    try:
                        res = s.client.table(tbl).update({col: primary["id"]}).eq(col, d["id"]).execute()
                        if tbl == "vehicles":
                            entry["relinked_vehicles"] += [r["id"] for r in (res.data or [])]
                    except Exception as e:
                        entry.setdefault("warnings", []).append(f"{tbl}: {str(e)[:120]}")
                # نقل الهاتف إن كان الأساسي بلا هاتف
                if not norm_phone(primary.get("phone")) and norm_phone(d.get("phone")):
                    try:
                        s.client.table("customers").update({"phone": d.get("phone")}).eq("id", primary["id"]).execute()
                    except Exception:
                        pass
                try:
                    s.client.table("customers").delete().eq("id", d["id"]).execute()
                except Exception as e:
                    entry.setdefault("warnings", []).append(f"delete: {str(e)[:120]}")
        report["merged"].append(entry)

    print(json.dumps(report, ensure_ascii=False, indent=1))
    return report


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
