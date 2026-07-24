"""
✅ Approvals Router — Customer/Vehicle approval requests + SSE stream + Notifications

Domain: Approval request lifecycle (create, list, public view, public respond,
SSE stream broadcast), customer/vehicle approval-logs, and WhatsApp deeplink
notification preparation.

Extracted from routes_extended.py (lines 3466-4056) on 2026-02-11.
URL paths preserved as-is.
"""

import asyncio
import hashlib
import json
import os
import secrets  # was: random — OTP codes need cryptographic randomness
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import StreamingResponse

from supabase_service import SupabaseService

router = APIRouter(prefix="/api", tags=["approvals"])

# Injected by server.py via set_db(database)
db = None

# Module-local set of SSE subscriber queues.
approvals_subscribers: "set[asyncio.Queue]" = set()


def set_db(database):
    global db
    db = database


# --------------------- Helpers ---------------------
async def _log_approval_event(
    token: str,
    vehicle_id: str,
    customer_id: str,
    title: str,
    amount: float,
    status: str,
    service_items: list = None,
    service_items_text: str = None,
    responded_at: datetime = None,
):
    try:
        doc = await db.customer_approval_logs.find_one({"token": token})
        base = {
            "token": token,
            "vehicleId": vehicle_id,
            "customerId": customer_id,
            "title": title,
            "amount": amount,
            "status": status,
            "serviceItems": service_items or [],
            "serviceItemsText": service_items_text,
        }
        if doc:
            update = {**base, "updatedAt": datetime.utcnow()}
            if responded_at:
                update["respondedAt"] = responded_at
            await db.customer_approval_logs.update_one({"token": token}, {"$set": update})
        else:
            newdoc = {"id": str(uuid.uuid4()), **base, "createdAt": datetime.utcnow()}
            if responded_at:
                newdoc["respondedAt"] = responded_at
            await db.customer_approval_logs.insert_one(newdoc)
    except Exception as e:
        print(f"approval log error: {e}")


async def _approvals_broadcast(event: Dict[str, Any]):
    dead = []
    for q in list(approvals_subscribers):
        try:
            q.put_nowait(event)
        except Exception:
            dead.append(q)
    for q in dead:
        approvals_subscribers.discard(q)


# --------------------- Approval Logs ---------------------
def _map_supabase_approval_row(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": r.get("id"),
        "token": r.get("token"),
        "vehicleId": r.get("vehicle_id"),
        "customerId": r.get("customer_id"),
        "title": r.get("title"),
        "amount": r.get("amount"),
        "status": r.get("status"),
        "serviceItems": r.get("service_items") or [],
        "serviceItemsText": r.get("service_items_text"),
        "createdAt": r.get("created_at"),
        "respondedAt": r.get("responded_at"),
        "responderName": r.get("responder_name"),
        "responderPhone": r.get("responder_phone"),
    }


@router.get("/customers/{customer_id}/approval-logs")
async def get_customer_approval_logs(customer_id: str):
    try:
        if os.environ.get("DB_PROVIDER", "mongo").lower() == "supabase":
            supa = SupabaseService()
            res = (
                supa.client.table("approval_requests").select("*")
                .eq("customer_id", customer_id)
                .order("created_at", desc=True).limit(1000).execute()
            )
            return [_map_supabase_approval_row(r) for r in (res.data or [])]
        docs = (
            await db.customer_approval_logs.find({"customerId": customer_id})
            .sort("createdAt", -1)
            .to_list(length=1000)
        )
        for d in docs:
            d.pop("_id", None)
            for k in ("createdAt", "updatedAt", "respondedAt"):
                if d.get(k) and hasattr(d[k], "isoformat"):
                    d[k] = d[k].isoformat()
        return docs
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vehicles/{vehicle_id}/approval-logs")
async def get_vehicle_approval_logs(vehicle_id: str):
    try:
        if os.environ.get("DB_PROVIDER", "mongo").lower() == "supabase":
            supa = SupabaseService()
            res = (
                supa.client.table("approval_requests").select("*")
                .eq("vehicle_id", vehicle_id)
                .order("created_at", desc=True).limit(1000).execute()
            )
            return [_map_supabase_approval_row(r) for r in (res.data or [])]
        docs = (
            await db.customer_approval_logs.find({"vehicleId": vehicle_id})
            .sort("createdAt", -1)
            .to_list(length=1000)
        )
        for d in docs:
            d.pop("_id", None)
            for k in ("createdAt", "updatedAt", "respondedAt"):
                if d.get(k) and hasattr(d[k], "isoformat"):
                    d[k] = d[k].isoformat()
        return docs
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------- Approval CRUD + Public ---------------------
@router.post("/approvals")
async def create_approval(payload: Dict[str, Any] = Body(...)):
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        token = f"APR-{str(uuid.uuid4())[:8].upper()}"
        expiry_days = int(payload.get("expiryDays", 7))
        images = payload.get("images", [])

        if provider == "supabase":
            supa = SupabaseService()
            otp_code = f"{secrets.randbelow(9000) + 1000}"  # 1000-9999 cryptographically secure
            row = {
                "token": token,
                "otp_code": otp_code,
                "vehicle_id": payload.get("vehicleId"),
                "customer_id": payload.get("customerId"),
                "title": payload.get("title") or "طلب اعتماد",
                "amount": float(payload.get("amount") or 0),
                "service_items": payload.get("serviceItems") or [],
                "service_items_text": payload.get("serviceItemsText"),
                "images": images,
                "status": "pending",
                "expires_at": (datetime.utcnow() + timedelta(days=expiry_days)).isoformat(),
            }
            res = supa.client.table("approval_requests").insert(row).execute()
            r = (res.data or [{}])[0]
            return {
                "id": r.get("id"),
                "token": r.get("token") or token,
                "otp": r.get("otp_code") or otp_code,
                "vehicleId": r.get("vehicle_id"),
                "customerId": r.get("customer_id"),
                "title": r.get("title"),
                "amount": r.get("amount"),
                "serviceItems": r.get("service_items") or [],
                "serviceItemsText": r.get("service_items_text"),
                "images": r.get("images") or [],
                "status": r.get("status"),
                "createdAt": r.get("created_at"),
                "expiresAt": r.get("expires_at"),
            }

        # MongoDB legacy
        otp_code = f"{secrets.randbelow(9000) + 1000}"  # 1000-9999 cryptographically secure
        doc = {
            "id": str(uuid.uuid4()),
            "token": token,
            "otp_code": otp_code,
            "vehicleId": payload.get("vehicleId"),
            "customerId": payload.get("customerId"),
            "title": payload.get("title") or "طلب اعتماد",
            "amount": float(payload.get("amount") or 0),
            "serviceItems": payload.get("serviceItems") or [],
            "serviceItemsText": payload.get("serviceItemsText"),
            "images": images,
            "status": "pending",
            "createdAt": datetime.utcnow(),
            "expiresAt": datetime.utcnow() + timedelta(days=expiry_days),
        }
        await db.approval_requests.insert_one(doc)
        doc.pop("_id", None)
        doc["otp"] = otp_code  # expose to creator response only
        return doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/approvals")
async def list_approvals(vehicle_id: Optional[str] = None, visit_id: Optional[str] = None):
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()

        if provider == "supabase":
            supa = SupabaseService()
            q = supa.client.table("approval_requests").select("*")
            if visit_id:
                q = q.eq("visit_id", visit_id)
            elif vehicle_id:
                q = q.eq("vehicle_id", vehicle_id)
            res = q.order("created_at", desc=True).execute()
            return [
                {
                    "id": r.get("id"),
                    "token": r.get("token"),
                    "vehicleId": r.get("vehicle_id"),
                    "customerId": r.get("customer_id"),
                    "title": r.get("title"),
                    "amount": r.get("amount"),
                    "serviceItems": r.get("service_items") or [],
                    "serviceItemsText": r.get("service_items_text"),
                    "status": r.get("status"),
                    "createdAt": r.get("created_at"),
                    "expiresAt": r.get("expires_at"),
                    "respondedAt": r.get("responded_at"),
                    "responderName": r.get("responder_name"),
                    "responderPhone": r.get("responder_phone"),
                }
                for r in (res.data or [])
            ]

        q = {}
        if visit_id:
            q["visitId"] = visit_id
        elif vehicle_id:
            q["vehicleId"] = vehicle_id
        docs = (
            await db.approval_requests.find(q).sort("createdAt", -1).to_list(length=1000)
        )
        for d in docs:
            d.pop("_id", None)
            for k in ("createdAt", "expiresAt", "respondedAt"):
                if d.get(k) and hasattr(d[k], "isoformat"):
                    d[k] = d[k].isoformat()
        return docs
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/approvals/public/{token}")
async def public_approval(token: str):
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()

        if provider == "supabase":
            supa = SupabaseService()
            res = (
                supa.client.table("approval_requests").select("*").eq("token", token).execute()
            )
            if not res.data:
                raise HTTPException(status_code=404, detail="رابط غير صحيح")

            d = res.data[0]
            if d.get("revoked"):
                raise HTTPException(status_code=410, detail="تم إلغاء الطلب")

            expires_str = d.get("expires_at")
            if expires_str:
                if isinstance(expires_str, str):
                    if expires_str.endswith("Z"):
                        expires_str = expires_str[:-1] + "+00:00"
                    expires_at = datetime.fromisoformat(expires_str)
                else:
                    expires_at = expires_str
                now_utc = datetime.now(timezone.utc)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at < now_utc:
                    raise HTTPException(status_code=410, detail="انتهت صلاحية الرابط")

            return {
                "id": d.get("id"),
                "token": d.get("token"),
                "vehicleId": d.get("vehicle_id"),
                "customerId": d.get("customer_id"),
                "title": d.get("title"),
                "amount": d.get("amount"),
                "serviceItems": d.get("service_items") or [],
                "serviceItemsText": d.get("service_items_text"),
                "images": d.get("images") or [],
                "status": d.get("status"),
                "createdAt": d.get("created_at"),
                "expiresAt": d.get("expires_at"),
                "respondedAt": d.get("responded_at"),
                "signature": d.get("signature"),
                "clientIp": d.get("client_ip"),
            }

        d = await db.approval_requests.find_one({"token": token})
        if not d:
            raise HTTPException(status_code=404, detail="رابط غير صحيح")
        if d.get("revoked"):
            raise HTTPException(status_code=410, detail="تم إلغاء الطلب")
        if d.get("expiresAt") and d["expiresAt"] < datetime.utcnow():
            raise HTTPException(status_code=410, detail="انتهت صلاحية الرابط")
        d.pop("_id", None)
        d.pop("otp", None)
        d.pop("otp_code", None)
        for k in ("createdAt", "expiresAt", "respondedAt"):
            if d.get(k) and hasattr(d[k], "isoformat"):
                d[k] = d[k].isoformat()
        return d
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approvals/public/{token}/respond")
async def respond_public_approval(token: str, request: Request):
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        form_data = await request.form()
        status = form_data.get("status", "approved")
        name = form_data.get("name", "")
        phone = form_data.get("phone", "")
        notes = form_data.get("notes", "")
        otp = form_data.get("otp", "")

        if provider == "supabase":
            supa = SupabaseService()
            res = (
                supa.client.table("approval_requests").select("*").eq("token", token).execute()
            )
            if not res.data:
                raise HTTPException(status_code=404, detail="رابط غير صحيح")
            d = res.data[0]
            if d.get("revoked"):
                raise HTTPException(status_code=410, detail="تم إلغاء الطلب")

            expires_str = d.get("expires_at")
            if expires_str:
                if isinstance(expires_str, str):
                    if expires_str.endswith("Z"):
                        expires_str = expires_str[:-1] + "+00:00"
                    expires_at = datetime.fromisoformat(expires_str)
                else:
                    expires_at = expires_str
                now_utc = datetime.now(timezone.utc)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at < now_utc:
                    raise HTTPException(status_code=410, detail="انتهت صلاحية الرابط")

            client_ip = request.client.host
            user_agent = request.headers.get("user-agent", "unknown")
            timestamp = datetime.utcnow().isoformat()
            raw_data = f"{token}:{status}:{timestamp}:{client_ip}:{user_agent}"
            signature = hashlib.sha256(raw_data.encode()).hexdigest()  # noqa: F841

            meta_parts = []
            if notes:
                meta_parts.append(f"notes={notes}")
            meta_parts.append(f"ip={client_ip}")
            meta_parts.append(f"ua={user_agent[:120]}")

            stored_otp = str(d.get("otp_code") or "").strip()
            if stored_otp:
                if not otp or str(otp).strip() != stored_otp:
                    raise HTTPException(status_code=400, detail="رمز OTP غير صحيح")

            upd = {
                "status": status,
                "responded_at": timestamp,
                "responder_name": name,
                "responder_phone": phone,
                "otp_verified_at": timestamp,
                "service_items_text": (
                    " | ".join(meta_parts) if meta_parts else d.get("service_items_text")
                ),
            }
            supa.client.table("approval_requests").update(upd).eq("token", token).execute()

            res2 = (
                supa.client.table("approval_requests").select("*").eq("token", token).execute()
            )
            nd = (res2.data or [d])[0]

            try:
                await _approvals_broadcast(
                    {
                        "type": "approval_updated",
                        "token": nd.get("token"),
                        "vehicleId": nd.get("vehicle_id"),
                        "customerId": nd.get("customer_id"),
                        "status": nd.get("status"),
                        "respondedAt": nd.get("responded_at"),
                    }
                )
            except Exception:
                pass

            return {
                "id": nd.get("id"),
                "token": nd.get("token"),
                "vehicleId": nd.get("vehicle_id"),
                "customerId": nd.get("customer_id"),
                "title": nd.get("title"),
                "amount": nd.get("amount"),
                "serviceItems": nd.get("service_items") or [],
                "serviceItemsText": nd.get("service_items_text"),
                "images": nd.get("images") or [],
                "status": nd.get("status"),
                "createdAt": nd.get("created_at"),
                "expiresAt": nd.get("expires_at"),
                "respondedAt": nd.get("responded_at"),
                "responderName": nd.get("responder_name"),
                "responderPhone": nd.get("responder_phone"),
                "signature": nd.get("signature"),
                "clientIp": nd.get("client_ip"),
            }

        # MongoDB legacy
        d = await db.approval_requests.find_one({"token": token})
        if not d:
            raise HTTPException(status_code=404, detail="رابط غير صحيح")
        if d.get("revoked"):
            raise HTTPException(status_code=410, detail="تم إلغاء الطلب")
        if d.get("expiresAt") and d["expiresAt"] < datetime.utcnow():
            raise HTTPException(status_code=410, detail="انتهت صلاحية الرابط")

        # OTP gate (Mongo branch) — mirror of Supabase logic
        stored_otp = str(d.get("otp_code") or "").strip()
        if stored_otp:
            if not otp or str(otp).strip() != stored_otp:
                raise HTTPException(status_code=400, detail="رمز OTP غير صحيح")

        client_ip = request.client.host
        user_agent = request.headers.get("user-agent", "unknown")
        timestamp = datetime.utcnow().isoformat()
        raw_data = f"{token}:{status}:{timestamp}:{client_ip}:{user_agent}"
        signature = hashlib.sha256(raw_data.encode()).hexdigest()

        upd = {
            "status": status,
            "respondedAt": datetime.utcnow(),
            "responderName": name,
            "responderPhone": phone,
            "notes": notes,
            "clientIp": client_ip,
            "userAgent": user_agent,
            "signature": signature,
            "otpVerifiedAt": timestamp,
        }
        await db.approval_requests.update_one({"token": token}, {"$set": upd})

        if d.get("customerId"):
            history_entry = {
                "token": token,
                "vehicleId": d.get("vehicleId"),
                "status": status,
                "respondedAt": timestamp,
                "clientIp": client_ip,
                "signature": signature,
                "title": d.get("title"),
            }
            await db.customers.update_one(
                {"id": d.get("customerId")},
                {"$push": {"approvalsHistory": history_entry}},
            )

        nd = await db.approval_requests.find_one({"token": token})
        nd.pop("_id", None)
        for k in ("createdAt", "expiresAt", "respondedAt"):
            if nd.get(k) and hasattr(nd[k], "isoformat"):
                nd[k] = nd[k].isoformat()

        try:
            await _log_approval_event(
                token,
                nd.get("vehicleId"),
                nd.get("customerId"),
                nd.get("title", "طلب اعتماد"),
                float(nd.get("amount") or 0),
                nd.get("status"),
                nd.get("serviceItems") or [],
                nd.get("serviceItemsText"),
                datetime.utcnow(),
            )
        except Exception as le:
            print(f"log approval error: {le}")

        await _approvals_broadcast(
            {
                "type": "approval_updated",
                "token": token,
                "vehicleId": nd.get("vehicleId"),
                "customerId": nd.get("customerId"),
                "status": nd.get("status"),
                "respondedAt": nd.get("respondedAt"),
            }
        )
        return nd
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/approvals/stream")
async def approvals_stream(request: Request):
    async def gen():
        q: asyncio.Queue = asyncio.Queue()
        approvals_subscribers.add(q)
        try:
            while True:
                if await request.is_disconnected():
                    break
                ev = await q.get()
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        finally:
            approvals_subscribers.discard(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


# --------------------- WhatsApp Deeplink ---------------------
@router.post("/notifications/prepare")
async def prepare_notification(payload: Dict[str, Any] = Body(...)):
    try:
        phone = (payload or {}).get("phone", "")
        link = (payload or {}).get("link", "")
        msg = (payload or {}).get("message") or f"مرحباً، نأمل اعتماد الطلب عبر الرابط: {link}"

        norm = "".join([c for c in phone if c.isdigit()])
        if norm.startswith("00"):
            norm = norm[2:]
        if norm.startswith("+"):
            norm = norm[1:]
        if norm.startswith("05"):
            norm = "966" + norm[1:]
        if norm.startswith("5") and len(norm) == 9:
            norm = "966" + norm
        if not norm.startswith("966"):
            norm = "966" + norm

        encoded_msg = urllib.parse.quote(msg)
        whatsapp_url = f"https://api.whatsapp.com/send?phone={norm}&text={encoded_msg}"
        return {"whatsappUrl": whatsapp_url, "phone": norm, "message": msg}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
