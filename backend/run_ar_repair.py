import asyncio, json
from dotenv import load_dotenv
load_dotenv()
from supabase_service import SupabaseService
from visit_sync import _sync_visit_to_operation

async def main():
    supa = SupabaseService()
    visits = supa.client.table("vehicle_visits").select("*").limit(3000).execute().data or []
    ok, skip, errs = 0, 0, []
    for v in visits:
        vid = str(v.get("id") or "")
        notes = v.get("notes")
        try:
            payload = json.loads(notes) if isinstance(notes, str) and notes.strip().startswith("{") else (notes if isinstance(notes, dict) else {})
        except Exception:
            payload = {}
        if not (payload or {}).get("items"):
            skip += 1
            continue
        try:
            await _sync_visit_to_operation(vid, {"vehicleId": v.get("vehicle_id"), "notes": notes}, supa_service=supa)
            ok += 1
        except Exception as e:
            errs.append({"visit": vid[:8], "err": str(e)[:150]})
    print(json.dumps({"processed": ok, "skipped": skip, "errors": errs[:10], "error_count": len(errs)}, ensure_ascii=False))

asyncio.run(main())
