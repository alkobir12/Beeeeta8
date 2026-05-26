"""
🛡️ Accounting Firewall API — Smart Center

Endpoints:
  • GET  /api/firewall/status               — legacy summary (الإصدار القديم)
  • GET  /api/firewall/dashboard            — JSON شامل للوحة الجديدة
  • GET  /api/firewall/health-score         — درجة الصحة فقط
  • GET  /api/firewall/alerts               — كل التنبيهات (مع فلترة category/severity)
  • GET  /api/firewall/alerts/{alert_id}    — تفاصيل تنبيه واحد
  • POST /api/firewall/alerts/{alert_id}/dismiss
  • POST /api/firewall/alerts/{alert_id}/resolve
  • POST /api/firewall/auto-fix             — تنفيذ إصلاح آلي
  • GET  /api/firewall/live-activity        — آخر القيود
  • GET  /api/firewall/ai-insights          — توصيات ذكية (rules + AI)
  • POST /api/firewall/test/log-rejection   — اختبار تسجيل رفض
"""

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query

import firewall_state
from firewall_engine import FirewallEngine
from firewall_ai_insights import generate_insights

router = APIRouter(prefix="/api/firewall", tags=["firewall"])


def _to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value if value is not None else 0))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _supa():
    """Return Supabase client if provider is supabase, else None."""
    provider = os.environ.get("DB_PROVIDER", "mongo").lower()
    if provider != "supabase":
        return None
    try:
        from supabase_service import SupabaseService
        return SupabaseService()
    except Exception as e:
        print(f"Firewall: Supabase init failed: {e}")
        return None


def _fetch_journal_entries(workshop_id: Optional[str]) -> List[Dict[str, Any]]:
    """Read journal entries from Supabase (preferred) or empty list."""
    supa = _supa()
    if not supa:
        return []
    try:
        query = supa.client.table("journal_entries").select("*")
        if workshop_id:
            query = query.eq("workshop_id", workshop_id)
        res = query.order("created_at", desc=True).limit(2000).execute()
        return res.data or []
    except Exception as e:
        print(f"Firewall: failed to read journal_entries: {e}")
        return []


def _analyze_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Return per-entry analysis: totals, drift, balanced flag."""
    lines = entry.get("lines") or []
    if not isinstance(lines, list):
        lines = []
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for ln in lines:
        if not isinstance(ln, dict):
            continue
        total_debit += _to_decimal(ln.get("debit"))
        total_credit += _to_decimal(ln.get("credit"))
    drift = (total_debit - total_credit).copy_abs()
    return {
        "debit": float(total_debit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "credit": float(total_credit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "drift": float(drift.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        "balanced": drift <= Decimal("0.009"),
    }


@router.get("/status")
async def firewall_status(
    workshop_id: Optional[str] = Query(default=None),
    recent_limit: int = Query(default=20, ge=1, le=100),
):
    """
    حالة جدار حماية المحاسبة الشاملة.

    العائد:
      - summary: مؤشرات شاملة (balanced/unbalanced/COGS/idempotency)
      - drift: أكبر انحراف ومتوسط الانحراف
      - recent_rejections: آخر رفضيات (من السجل الزمني)
      - recent_idempotency_hits: آخر ضربات منع تكرار
      - recent_cogs_entries: آخر قيود COGS مولدة من الـ DB
      - unbalanced_entries_in_db: قيود غير متوازنة تسربت إلى DB (يجب أن تكون 0)
    """
    entries = _fetch_journal_entries(workshop_id)

    total_entries = len(entries)
    balanced_count = 0
    unbalanced_count = 0
    cogs_count = 0
    cogs_total_amount = 0.0
    idemp_tagged_count = 0
    max_drift = 0.0
    drift_sum = 0.0
    unbalanced_entries_in_db: List[Dict[str, Any]] = []
    recent_cogs: List[Dict[str, Any]] = []

    for entry in entries:
        analysis = _analyze_entry(entry)
        if analysis["balanced"]:
            balanced_count += 1
        else:
            unbalanced_count += 1
            if len(unbalanced_entries_in_db) < recent_limit:
                unbalanced_entries_in_db.append({
                    "id": entry.get("id"),
                    "date": entry.get("date"),
                    "description": entry.get("description"),
                    "debit": analysis["debit"],
                    "credit": analysis["credit"],
                    "drift": analysis["drift"],
                    "source": entry.get("source"),
                })

        drift_val = analysis["drift"]
        drift_sum += drift_val
        if drift_val > max_drift:
            max_drift = drift_val

        # COGS detection
        source = str(entry.get("source") or "").lower()
        if source == "operation_cogs":
            cogs_count += 1
            cogs_total_amount += float(entry.get("total") or 0)
            if len(recent_cogs) < recent_limit:
                recent_cogs.append({
                    "id": entry.get("id"),
                    "date": entry.get("date"),
                    "description": entry.get("description"),
                    "total": float(entry.get("total") or 0),
                    "reference_id": entry.get("reference_id"),
                    "balanced": analysis["balanced"],
                })

        # Idempotency tag detection (in description or notes-like fields)
        haystack = " ".join([
            str(entry.get("description") or ""),
            str(entry.get("source") or ""),
        ])
        if "[IDEMP:" in haystack:
            idemp_tagged_count += 1

    avg_drift = round((drift_sum / total_entries) if total_entries else 0.0, 6)

    counters = firewall_state.get_counters()

    return {
        "success": True,
        "workshop_id": workshop_id,
        "summary": {
            "total_entries": total_entries,
            "balanced_entries": balanced_count,
            "unbalanced_entries_in_db": unbalanced_count,
            "cogs_entries": cogs_count,
            "cogs_total_amount": round(cogs_total_amount, 2),
            "entries_with_idemp_tag": idemp_tagged_count,
            "lifetime_rejections": counters.get("unbalanced_rejection", 0),
            "lifetime_idempotency_hits": counters.get("idempotency_hit", 0),
            "lifetime_cogs_generated": counters.get("cogs_generated", 0),
            "balance_health_percent": round(
                (balanced_count / total_entries * 100.0) if total_entries else 100.0, 2
            ),
        },
        "drift": {
            "max": round(max_drift, 6),
            "avg": avg_drift,
            "threshold": 0.009,
        },
        "recent_rejections": firewall_state.get_events("unbalanced_rejection", limit=recent_limit),
        "recent_idempotency_hits": firewall_state.get_events("idempotency_hit", limit=recent_limit),
        "recent_cogs_events": firewall_state.get_events("cogs_generated", limit=recent_limit),
        "recent_cogs_entries": recent_cogs,
        "unbalanced_entries_in_db": unbalanced_entries_in_db,
    }


@router.post("/test/log-rejection")
async def test_log_rejection(payload: Dict[str, Any]):
    """نقطة اختبار: تسجيل رفض اصطناعي (للاختبار فقط)."""
    firewall_state.log_event(
        "unbalanced_rejection",
        {
            "reason": payload.get("reason") or "manual_test",
            "debit": payload.get("debit"),
            "credit": payload.get("credit"),
            "description": payload.get("description"),
        },
    )
    return {"success": True}


# ============================================================
# 🆕 SMART CENTER ENDPOINTS (Phase 2)
# ============================================================

@router.get("/dashboard")
async def firewall_dashboard(workshop_id: Optional[str] = Query(default=None)):
    """JSON شامل للوحة Accounting Firewall Center (Health Score + Alerts + Cash flow + Live)."""
    try:
        engine = FirewallEngine(workshop_id=workshop_id)
        analysis = engine.run_full_analysis()
        return {"success": True, "data": analysis}
    except Exception as e:
        import traceback
        print(f"[firewall_dashboard] error: {e}\n{traceback.format_exc()}")
        return {"success": False, "error": str(e)}


@router.get("/health-score")
async def firewall_health_score(workshop_id: Optional[str] = Query(default=None)):
    """درجة الصحة المالية فقط (للويدجت الخفيفة)."""
    try:
        engine = FirewallEngine(workshop_id=workshop_id)
        analysis = engine.run_full_analysis()
        return {"success": True, "data": {
            "health": analysis["health"],
            "alerts_count": analysis["alerts_count"],
            "counts_by_severity": analysis["counts_by_severity"],
        }}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/alerts")
async def firewall_alerts(
    workshop_id: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    limit: int = Query(default=200, le=1000),
):
    """قائمة التنبيهات مع فلترة."""
    try:
        engine = FirewallEngine(workshop_id=workshop_id)
        analysis = engine.run_full_analysis()
        alerts = analysis.get("alerts", [])
        if category:
            alerts = [a for a in alerts if a.get("category") == category]
        if severity:
            alerts = [a for a in alerts if a.get("severity") == severity]
        return {"success": True, "data": alerts[:limit], "total": len(alerts)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/alerts/{alert_id}")
async def firewall_alert_detail(alert_id: str, workshop_id: Optional[str] = Query(default=None)):
    """تفاصيل تنبيه واحد (يبحث في كل التنبيهات الحية)."""
    try:
        engine = FirewallEngine(workshop_id=workshop_id)
        analysis = engine.run_full_analysis()
        found = next((a for a in analysis.get("alerts", []) if a.get("id") == alert_id), None)
        if not found:
            raise HTTPException(status_code=404, detail="alert not found (قد يكون تم حله أو تجاهله)")
        return {"success": True, "data": found}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/alerts/{alert_id}/dismiss")
async def firewall_dismiss(
    alert_id: str,
    workshop_id: Optional[str] = Query(default="finmodule-sync"),
    payload: Dict[str, Any] = Body(default=None),
):
    """تجاهل تنبيه (مع expiry اختياري)."""
    try:
        from server import db
        from datetime import datetime as _dt, timezone as _tz, timedelta as _td
        body = payload or {}
        hours = int(body.get("expires_in_hours") or 24)
        expires_at = (_dt.now(_tz.utc) + _td(hours=hours)).isoformat()
        await db.firewall_dismissed_alerts.update_one(
            {"alert_id": alert_id, "workshop_id": workshop_id or "finmodule-sync"},
            {"$set": {
                "alert_id": alert_id,
                "workshop_id": workshop_id or "finmodule-sync",
                "dismissed_at": _dt.now(_tz.utc).isoformat(),
                "expires_at": expires_at,
                "reason": body.get("reason") or "user_dismissed",
            }},
            upsert=True,
        )
        return {"success": True, "alert_id": alert_id, "expires_at": expires_at}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/alerts/{alert_id}/resolve")
async def firewall_resolve(
    alert_id: str,
    workshop_id: Optional[str] = Query(default="finmodule-sync"),
    payload: Dict[str, Any] = Body(default=None),
):
    """تعليم كمحلول (يخزّن في collection مختلف للسجل الدائم)."""
    try:
        from server import db
        from datetime import datetime as _dt, timezone as _tz
        body = payload or {}
        await db.firewall_resolved_alerts.insert_one({
            "alert_id": alert_id,
            "workshop_id": workshop_id or "finmodule-sync",
            "resolved_at": _dt.now(_tz.utc).isoformat(),
            "resolved_by": body.get("user") or "system",
            "notes": body.get("notes"),
        })
        # also dismiss permanently
        await db.firewall_dismissed_alerts.update_one(
            {"alert_id": alert_id, "workshop_id": workshop_id or "finmodule-sync"},
            {"$set": {
                "alert_id": alert_id,
                "workshop_id": workshop_id or "finmodule-sync",
                "dismissed_at": _dt.now(_tz.utc).isoformat(),
                "expires_at": None,
                "reason": "resolved",
            }},
            upsert=True,
        )
        return {"success": True, "alert_id": alert_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/auto-fix")
async def firewall_auto_fix(
    workshop_id: Optional[str] = Query(default=None),
    payload: Dict[str, Any] = Body(...),
):
    """تنفيذ Auto-Fix لتنبيه قابل للإصلاح آلياً.

    Body: {alert_id, dry_run?}
    Returns: {success, action_taken, details}
    """
    try:
        body = payload or {}
        alert_id = body.get("alert_id")
        if not alert_id:
            raise HTTPException(status_code=400, detail="alert_id is required")
        dry_run = bool(body.get("dry_run", False))

        engine = FirewallEngine(workshop_id=workshop_id)
        analysis = engine.run_full_analysis()
        alert = next((a for a in analysis.get("alerts", []) if a.get("id") == alert_id), None)
        if not alert:
            raise HTTPException(status_code=404, detail="alert not found")
        if alert.get("auto_fix") != "auto":
            return {"success": False, "error": "هذا التنبيه يحتاج معالجة يدوية أو موجّهة"}

        fix = alert.get("auto_fix_preview") or {}
        fix_type = fix.get("type")
        supa = _supa()
        if not supa:
            raise HTTPException(status_code=400, detail="Auto-Fix requires Supabase provider")

        if fix_type == "delete_orphan_journal":
            journal_id = fix.get("journal_id") or (alert.get("evidence") or {}).get("journal_id")
            if dry_run:
                return {"success": True, "dry_run": True, "would_delete": journal_id}
            supa.client.table("journal_entries").delete().eq("id", journal_id).execute()
            return {"success": True, "action_taken": "deleted_orphan_journal", "journal_id": journal_id}

        elif fix_type == "balancing_adjustment":
            journal_id = (alert.get("evidence") or {}).get("journal_id")
            side = fix.get("side")
            amount = float(fix.get("amount") or 0)
            if dry_run:
                return {"success": True, "dry_run": True, "would_create_adjustment": {
                    "for_journal": journal_id, "side": side, "amount": amount,
                }}
            # ننشئ قيد تعديل
            import uuid as _uuid
            from datetime import datetime as _dt, timezone as _tz
            entry = {
                "id": str(_uuid.uuid4()),
                "workshop_id": workshop_id or "finmodule-sync",
                "date": _dt.now(_tz.utc).date().isoformat(),
                "description": f"تسوية جدار حماية لقيد {journal_id}",
                "source": "firewall_adjustment",
                "reference_id": journal_id,
                "total": amount,
                "lines": [
                    {"account": "9999", "account_name": "تسوية جدار حماية", "debit": amount if side == "debit" else 0, "credit": amount if side == "credit" else 0},
                    {"account": "9998", "account_name": "تسوية مقابلة", "debit": amount if side == "credit" else 0, "credit": amount if side == "debit" else 0},
                ],
                "created_at": _dt.now(_tz.utc).isoformat(),
            }
            supa.client.table("journal_entries").insert(entry).execute()
            return {"success": True, "action_taken": "created_balancing_adjustment", "journal_entry_id": entry["id"]}

        return {"success": False, "error": f"نوع الإصلاح غير مدعوم: {fix_type}"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[firewall_auto_fix] error: {e}\n{traceback.format_exc()}")
        return {"success": False, "error": str(e)}


@router.get("/live-activity")
async def firewall_live_activity(
    workshop_id: Optional[str] = Query(default=None),
    limit: int = Query(default=30, le=200),
):
    """آخر القيود التي حدثت."""
    try:
        engine = FirewallEngine(workshop_id=workshop_id)
        live = engine.run_full_analysis().get("live_activity", [])
        return {"success": True, "data": live[:limit]}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/ai-insights")
async def firewall_ai_insights(
    workshop_id: Optional[str] = Query(default=None),
    use_ai: bool = Query(default=True),
):
    """توصيات ذكية. يستخدم AI provider إن توفر، وإلا rule engine."""
    try:
        engine = FirewallEngine(workshop_id=workshop_id)
        analysis = engine.run_full_analysis()
        result = await generate_insights(analysis, use_ai=use_ai)
        return {"success": True, "data": result}
    except Exception as e:
        import traceback
        print(f"[firewall_ai_insights] error: {e}\n{traceback.format_exc()}")
        return {"success": False, "error": str(e)}
