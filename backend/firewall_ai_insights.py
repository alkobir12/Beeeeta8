"""
🤖 Firewall AI Insights — توليد توصيات ذكية بناءً على تحليل المحرك.

نمط Modular:
  • Local Rules Engine (لا يحتاج مفتاح، يعمل دائماً)
  • Emergent LLM (Claude/GPT/Gemini) عند توفر EMERGENT_LLM_KEY

كل insight يحوي:
  • title: عنوان مختصر
  • body: شرح موسع
  • severity: critical/high/medium/info
  • action: إجراء مقترح
  • related_alerts: قائمة معرّفات تنبيهات
"""

from __future__ import annotations
import os
from typing import Any, Dict, List


# ---------- Local Rules Engine (fallback) ----------

def _rule_engine_insights(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """قواعد محلية تعمل بدون AI key."""
    out: List[Dict[str, Any]] = []
    health = analysis.get("health") or {}
    cf = analysis.get("cash_flow") or {}
    counts = analysis.get("counts_by_category") or {}
    counts_sev = analysis.get("counts_by_severity") or {}

    # 1) Health score insight
    score = health.get("score", 0)
    if score < 60:
        out.append({
            "title": "صحة النظام المالي تحت المتوسط",
            "body": f"درجة الصحة الحالية {score}/100 ({health.get('status')}). راجع التنبيهات الحرجة أولاً واتخذ إجراءات فورية.",
            "severity": "critical",
            "action": "ابدأ بإصلاح التنبيهات بترتيب الخطورة من الأعلى للأدنى.",
            "related_alerts": [],
        })
    elif score < 80:
        out.append({
            "title": "هناك مجال لتحسين الصحة المالية",
            "body": f"درجة الصحة {score}/100. النظام مستقر لكن يوجد {counts_sev.get('high', 0)} تنبيهات عالية الخطورة.",
            "severity": "medium",
            "action": "خصّص ساعة أسبوعياً لمراجعة التنبيهات وحلها.",
            "related_alerts": [],
        })

    # 2) Cash flow
    if cf.get("is_negative"):
        out.append({
            "title": "تدفق نقدي سلبي خلال 30 يوماً",
            "body": f"المصاريف ({cf.get('outflow')} ر.س) تجاوزت الإيرادات ({cf.get('inflow')} ر.س) بمقدار {abs(cf.get('net', 0))} ر.س.",
            "severity": "high",
            "action": "خفّض المشتريات غير الضرورية أو فعّل حملة تحصيل من العملاء.",
            "related_alerts": [],
        })

    # 3) Duplicate operations
    dup_count = counts.get("duplicate_detection", 0)
    if dup_count > 0:
        out.append({
            "title": f"اكتشاف {dup_count} عملية/بند مكرر",
            "body": "تم رصد عمليات أو بنود بنفس المبلغ والطرف خلال نوافذ زمنية مختلفة. قد يكون إدخال مزدوج بالخطأ.",
            "severity": "high" if dup_count > 2 else "medium",
            "action": "افتح كل تنبيه تكرار وحدّد ما إذا كان شرعياً أم مزدوجاً، ثم احذف المكررات.",
            "related_alerts": [],
        })

    # 4) Consistency issues
    incons = counts.get("consistency", 0)
    if incons > 0:
        out.append({
            "title": f"{incons} حالة عدم تطابق بين بنود الزيارة والعمليات",
            "body": "البنود في الزيارة لا تساوي إجمالي العملية المسجلة. هذا قد يعني تعديل بعد الحفظ بدون مزامنة.",
            "severity": "medium",
            "action": "افتح كل ملف مركبة ذو مشكلة واضغط 'حفظ' لإعادة المزامنة التلقائية.",
            "related_alerts": [],
        })

    # 5) Anomaly
    anom = counts.get("anomaly", 0)
    if anom > 0:
        out.append({
            "title": f"رصد {anom} شذوذ في المصاريف أو القيود",
            "body": "هناك ارتفاع غير معتاد أو قيود مشبوهة (خارج ساعات العمل أو مبالغ كبيرة).",
            "severity": "medium",
            "action": "افتح التنبيهات الشاذة وراجع كل قيد قبل اعتماده.",
            "related_alerts": [],
        })

    # 6) Integrity
    integ = counts.get("integrity", 0)
    if integ > 0:
        out.append({
            "title": f"{integ} قيد يومية يتيم (Orphan Journal)",
            "body": "قيود يومية تشير إلى عمليات محذوفة. الأمان: حذفها يحفظ نزاهة الـ ledger.",
            "severity": "medium",
            "action": "استخدم Auto-Fix لحذف القيود اليتيمة بأمان.",
            "related_alerts": [],
        })

    if not out:
        out.append({
            "title": "النظام المالي في حالة ممتازة",
            "body": "لم تُكتشف أي مشاكل حرجة. واصل المراقبة الدورية وحدّث القوائم المالية شهرياً.",
            "severity": "info",
            "action": "تابع المراجعة الأسبوعية لإبقاء الصحة المالية مرتفعة.",
            "related_alerts": [],
        })

    return out


# ---------- AI Provider (Emergent LLM) ----------

async def _ai_insights(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """يستدعي Claude/GPT للحصول على insights أكثر عمقاً."""
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        return []

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception as e:
        print(f"[FirewallAI] emergentintegrations import failed: {e}")
        return []

    # Summarize analysis for the LLM
    summary = {
        "health_score": (analysis.get("health") or {}).get("score"),
        "status": (analysis.get("health") or {}).get("status"),
        "cash_flow": analysis.get("cash_flow"),
        "alerts_count": analysis.get("alerts_count"),
        "counts_by_category": analysis.get("counts_by_category"),
        "counts_by_severity": analysis.get("counts_by_severity"),
        "top_alerts": [
            {"title": a["title"], "severity": a["severity"], "category": a["category"], "impact": a.get("financial_impact")}
            for a in (analysis.get("alerts") or [])[:8]
        ],
    }

    system_msg = (
        "أنت محلل مالي خبير لورشة سيارات. مهمتك توليد ٣-٥ توصيات ذكية باللغة العربية "
        "بناءً على البيانات المُعطاة. كل توصية يجب أن تكون عملية ومحددة (ليست عامة). "
        "أعد قائمة JSON صرفة (بدون markdown أو أي شرح خارجي) بهذا الشكل: "
        '[{"title": "...", "body": "...", "severity": "critical|high|medium|info", "action": "إجراء محدد"}]'
    )

    user_msg = f"بيانات النظام:\n{summary}\n\nأعطني توصيات JSON صرف."

    try:
        import uuid
        session_id = f"firewall-insights-{uuid.uuid4().hex[:8]}"
        chat = LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message=system_msg,
        ).with_model("openai", "gpt-4o-mini").with_max_tokens(900)
        response = await chat.send_message(UserMessage(text=user_msg))
        text = str(response or "").strip()
        # extract JSON list
        import json
        import re
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            arr = json.loads(match.group(0))
            cleaned = []
            for item in arr:
                if not isinstance(item, dict):
                    continue
                cleaned.append({
                    "title": item.get("title") or "توصية",
                    "body": item.get("body") or "",
                    "severity": str(item.get("severity") or "info").lower(),
                    "action": item.get("action") or "—",
                    "related_alerts": [],
                    "source": "ai",
                })
            return cleaned
    except Exception as e:
        print(f"[FirewallAI] LLM call failed: {e}")
    return []


# ---------- Public Entry ----------

async def generate_insights(analysis: Dict[str, Any], use_ai: bool = True) -> Dict[str, Any]:
    """يُرجع insights مع علامة source = 'ai' أو 'rules'."""
    local = _rule_engine_insights(analysis)
    ai = []
    if use_ai:
        ai = await _ai_insights(analysis)
    # Mark sources
    for item in local:
        item.setdefault("source", "rules")
    insights = ai + local  # AI أولاً، ثم rules كـ backup
    return {
        "insights": insights,
        "ai_enabled": bool(ai),
        "count": len(insights),
    }
