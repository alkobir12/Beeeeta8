"""
routes_suppliers_extended.py
ميزات موردين متقدمة: التسوية، كشف الحساب PDF، استيراد Excel/CSV
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Body
from fastapi.responses import HTMLResponse
from typing import Any, Dict, List, Optional
import uuid
import json
import csv
import io
from datetime import datetime, timezone
from pathlib import Path

# Shared Supabase client
try:
    from routes_finance import supabase
    from routes_finance import _fetch_journal_entries, invalidate_finance_caches
except Exception:
    supabase = None
    def _fetch_journal_entries(*a, **k): return []
    def invalidate_finance_caches(): pass

router = APIRouter(prefix="/api/suppliers-ext", tags=["suppliers-ext"])

_SETTLEMENTS_FILE = Path("/app/backend/uploads/supplier_settlements.json")

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_settlements() -> List[Dict]:
    try:
        if _SETTLEMENTS_FILE.exists():
            return json.loads(_SETTLEMENTS_FILE.read_text("utf-8"))
    except Exception:
        pass
    return []

def _save_settlements(data: List[Dict]):
    _SETTLEMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SETTLEMENTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _normalize(s: str) -> str:
    return str(s or "").strip().lower().replace("أ","ا").replace("إ","ا").replace("آ","ا")

def _get_supplier_transactions(supplier_name: str, workshop_id: str) -> List[Dict]:
    """جلب كل حركات المورد من قيود اليومية + العمليات المرتبطة."""
    entries = _fetch_journal_entries(workshop_id, "2000-01-01",
                                     datetime.now().strftime("%Y-%m-%d"),
                                     limit=5000, include_rakan=True)
    name_norm = _normalize(supplier_name)
    txns: List[Dict] = []
    seen = set()

    # ─── 1. من قيود اليومية ────────────────────────────────────────────────
    for entry in entries:
        for line in (entry.get("lines") or []):
            acc_name = _normalize(str(line.get("account_name") or ""))
            if not acc_name or name_norm not in acc_name:
                continue
            key = f"je-{entry.get('id')}-{line.get('account')}"
            if key in seen:
                continue
            seen.add(key)
            debit  = float(line.get("debit")  or 0)
            credit = float(line.get("credit") or 0)
            amount = debit if debit > 0 else credit
            if amount <= 0:
                continue
            txns.append({
                "id":          key,
                "je_id":       entry.get("id"),
                "date":        str(entry.get("date") or "")[:10],
                "description": entry.get("description", ""),
                "account":     line.get("account", ""),
                "account_name": line.get("account_name", ""),
                "debit":       debit,
                "credit":      credit,
                "amount":      amount,
                "type":        "credit" if credit > 0 else "debit",
                "source":      "journal_entry",
            })

    # ─── 2. من العمليات (بنود المورد في زيارات المركبات) ──────────────────
    try:
        if supabase:
            ops_res = supabase.table("operations").select(
                "id, date, items, total, payment_method, partner_name, notes, workshop_id"
            ).limit(2000).execute()
            for op in (ops_res.data or []):
                for item in (op.get("items") or []):
                    if str(item.get("itemType") or "").lower() != "supplier":
                        continue
                    item_name = _normalize(str(item.get("name") or ""))
                    if name_norm not in item_name:
                        continue
                    op_id = str(op.get("id") or "")
                    key = f"op-{op_id}-{item_name}"
                    if key in seen:
                        continue
                    seen.add(key)
                    amt = float(item.get("total") or item.get("price") or 0)
                    if amt <= 0:
                        continue
                    txns.append({
                        "id":          key,
                        "je_id":       op_id,
                        "date":        str(op.get("date") or "")[:10],
                        "description": f"عملية — {op.get('partner_name','')[:30]}",
                        "account":     "op",
                        "account_name": f"مورد - {item.get('name','')}",
                        "debit":       0.0,
                        "credit":      amt,
                        "amount":      amt,
                        "type":        "credit",
                        "source":      "operation",
                        "linked_part": item.get("linkedPart", ""),
                    })
    except Exception as e:
        print(f"_get_supplier_transactions operations fetch: {e}")

    txns.sort(key=lambda x: x["date"])
    return txns

def _get_supplier_by_name_or_id(supplier_id: str) -> Optional[Dict]:
    """جلب بيانات المورد من Supabase."""
    if not supabase:
        return None
    try:
        res = supabase.table("suppliers").select("*").eq("id", supplier_id).execute()
        rows = res.data or []
        return rows[0] if rows else None
    except Exception:
        return None

# ─────────────────────────────────────────────────────────────────────────────
# 1. TRANSACTIONS — جلب حركات المورد
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{supplier_id}/transactions")
async def get_supplier_transactions(
    supplier_id: str,
    workshop_id: str = Query("finmodule-sync"),
    supplier_name: str = Query(""),
):
    """جلب كل حركات المورد من قيود اليومية."""
    name = supplier_name or supplier_id
    if not supplier_name and supplier_id:
        sup = _get_supplier_by_name_or_id(supplier_id)
        if sup:
            name = sup.get("name", supplier_id)

    txns = _get_supplier_transactions(name, workshop_id)
    total_debit  = sum(t["debit"]  for t in txns)
    total_credit = sum(t["credit"] for t in txns)

    # تمييز المسوّاة
    settlements = _load_settlements()
    settled_je_ids = set()
    for s in settlements:
        if s.get("supplier_id") == supplier_id:
            for line in s.get("lines", []):
                settled_je_ids.add(line.get("je_id", ""))

    for t in txns:
        t["settled"] = t["je_id"] in settled_je_ids

    return {
        "success": True,
        "data": {
            "transactions": txns,
            "total_debit": round(total_debit, 2),
            "total_credit": round(total_credit, 2),
            "balance": round(total_credit - total_debit, 2),
            "count": len(txns),
        }
    }

# ─────────────────────────────────────────────────────────────────────────────
# 2. SETTLEMENTS — التسوية
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{supplier_id}/settlements")
async def list_settlements(supplier_id: str):
    """قائمة التسويات للمورد."""
    all_s = _load_settlements()
    return {
        "success": True,
        "data": [s for s in all_s if s.get("supplier_id") == supplier_id]
    }

@router.post("/{supplier_id}/settlements")
async def create_settlement(
    supplier_id: str,
    payload: Dict[str, Any] = Body(...),
):
    """
    تنفيذ التسوية.
    Body: { supplier_name, workshop_id, selected_ids: [je_id,...], notes }
    """
    supplier_name = payload.get("supplier_name", supplier_id)
    workshop_id   = payload.get("workshop_id", "finmodule-sync")
    selected_ids  = set(str(x) for x in (payload.get("selected_ids") or []))
    notes         = payload.get("notes", "")

    if not selected_ids:
        raise HTTPException(status_code=400, detail="يرجى اختيار حركة واحدة على الأقل")

    txns = _get_supplier_transactions(supplier_name, workshop_id)
    selected_txns = [t for t in txns if t["je_id"] in selected_ids]

    if not selected_txns:
        raise HTTPException(status_code=400, detail="لم تُعثر على الحركات المختارة")

    total_debit  = sum(t["debit"]  for t in selected_txns)
    total_credit = sum(t["credit"] for t in selected_txns)
    net_amount   = round(total_credit - total_debit, 2)

    settlement = {
        "id":            str(uuid.uuid4()),
        "supplier_id":   supplier_id,
        "supplier_name": supplier_name,
        "workshop_id":   workshop_id,
        "date":          _now_iso()[:10],
        "total_debit":   round(total_debit, 2),
        "total_credit":  round(total_credit, 2),
        "net_amount":    net_amount,
        "notes":         notes,
        "lines": [
            {"je_id": t["je_id"], "date": t["date"], "description": t["description"],
             "debit": t["debit"], "credit": t["credit"]}
            for t in selected_txns
        ],
        "created_at": _now_iso(),
    }

    all_s = _load_settlements()
    all_s.append(settlement)
    _save_settlements(all_s)
    invalidate_finance_caches()

    return {"success": True, "data": settlement}

@router.delete("/{supplier_id}/settlements/{settlement_id}")
async def delete_settlement(supplier_id: str, settlement_id: str):
    """حذف تسوية."""
    all_s = _load_settlements()
    updated = [s for s in all_s if not (s["id"] == settlement_id and s["supplier_id"] == supplier_id)]
    if len(updated) == len(all_s):
        raise HTTPException(status_code=404, detail="التسوية غير موجودة")
    _save_settlements(updated)
    return {"success": True}

# ─────────────────────────────────────────────────────────────────────────────
# 3. PDF — كشف الحساب وتقرير التسوية
# ─────────────────────────────────────────────────────────────────────────────

def _html_style() -> str:
    return """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Noto+Naskh+Arabic&display=swap');
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body { font-family: 'Noto Naskh Arabic', Arial, sans-serif; direction: rtl;
             color: #1e293b; background: #fff; font-size: 13px; }
      .header { background: #0f172a; color: white; padding: 16px 24px;
                display: flex; justify-content: space-between; align-items: center; }
      .header h1 { font-size: 18px; font-weight: bold; }
      .header .meta { font-size: 11px; opacity: 0.8; text-align: left; }
      .supplier-info { padding: 12px 24px; background: #f8fafc; border-bottom: 1px solid #e2e8f0;
                       display: flex; gap: 32px; }
      .supplier-info .lbl { font-size: 11px; color: #64748b; }
      .supplier-info .val { font-size: 14px; font-weight: bold; }
      table { width: 100%; border-collapse: collapse; margin: 0; }
      th { background: #1e293b; color: white; padding: 8px 12px; font-size: 12px; text-align: right; }
      td { padding: 7px 12px; border-bottom: 1px solid #f1f5f9; font-size: 12px; }
      tr:nth-child(even) td { background: #f8fafc; }
      .credit { color: #16a34a; font-weight: bold; }
      .debit  { color: #dc2626; font-weight: bold; }
      .footer { padding: 12px 24px; background: #f8fafc; border-top: 2px solid #e2e8f0;
                display: flex; justify-content: space-between; font-weight: bold; }
      .badge-credit { background:#dcfce7; color:#16a34a; padding:2px 8px; border-radius:4px; font-size:11px; }
      .badge-debit  { background:#fee2e2; color:#dc2626; padding:2px 8px; border-radius:4px; font-size:11px; }
      @media print { @page { margin: 15mm; } }
    </style>
    """

@router.get("/{supplier_id}/statement/pdf", response_class=HTMLResponse)
async def supplier_statement_pdf(
    supplier_id: str,
    workshop_id: str = Query("finmodule-sync"),
    supplier_name: str = Query(""),
    from_date: str = Query(""),
    to_date: str = Query(""),
):
    """كشف حساب المورد بصيغة HTML قابلة للطباعة/PDF."""
    name = supplier_name or supplier_id
    sup  = _get_supplier_by_name_or_id(supplier_id)
    if sup:
        name = sup.get("name", name)

    txns = _get_supplier_transactions(name, workshop_id)

    # فلترة التاريخ
    if from_date:
        txns = [t for t in txns if t["date"] >= from_date]
    if to_date:
        txns = [t for t in txns if t["date"] <= to_date]

    total_debit  = sum(t["debit"]  for t in txns)
    total_credit = sum(t["credit"] for t in txns)
    balance      = total_credit - total_debit

    rows = ""
    running = 0.0
    for t in txns:
        running += t["credit"] - t["debit"]
        d_str = f'<span class="debit">{t["debit"]:,.2f}</span>'  if t["debit"]  else "—"
        c_str = f'<span class="credit">{t["credit"]:,.2f}</span>' if t["credit"] else "—"
        rows += f"""
        <tr>
          <td>{t["date"]}</td>
          <td>{t["description"][:60]}</td>
          <td>{t["account_name"][:30]}</td>
          <td style="text-align:center">{d_str}</td>
          <td style="text-align:center">{c_str}</td>
          <td style="text-align:center;font-weight:bold;color:{'#dc2626' if running<0 else '#16a34a'}">{running:,.2f}</td>
        </tr>"""

    period = f"{from_date or 'البداية'}  →  {to_date or 'اليوم'}"
    html = f"""<!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head><meta charset="UTF-8"><title>كشف حساب — {name}</title>{_html_style()}</head>
    <body>
      <div class="header">
        <h1>كشف حساب المورد</h1>
        <div class="meta">التاريخ: {_now_iso()[:10]}<br>الفترة: {period}</div>
      </div>
      <div class="supplier-info">
        <div><div class="lbl">المورد</div><div class="val">{name}</div></div>
        <div><div class="lbl">الرصيد المستحق</div>
             <div class="val" style="color:{'#dc2626' if balance<0 else '#16a34a'}">{balance:,.2f} ر.س</div></div>
        <div><div class="lbl">إجمالي المدين</div><div class="val debit">{total_debit:,.2f} ر.س</div></div>
        <div><div class="lbl">إجمالي الدائن</div><div class="val credit">{total_credit:,.2f} ر.س</div></div>
      </div>
      <table>
        <thead><tr>
          <th>التاريخ</th><th>الوصف</th><th>الحساب</th>
          <th>مدين (مدفوع)</th><th>دائن (مستحق)</th><th>الرصيد</th>
        </tr></thead>
        <tbody>{rows if rows else '<tr><td colspan="6" style="text-align:center;padding:20px">لا توجد حركات</td></tr>'}</tbody>
      </table>
      <div class="footer">
        <span>إجمالي الحركات: {len(txns)}</span>
        <span>الرصيد الختامي: <span style="color:{'#dc2626' if balance<0 else '#16a34a'}">{balance:,.2f} ر.س</span></span>
      </div>
      <script>window.onload = () => window.print();</script>
    </body></html>"""
    return HTMLResponse(html)

@router.get("/settlements/{settlement_id}/pdf", response_class=HTMLResponse)
async def settlement_pdf(settlement_id: str):
    """تقرير تسوية PDF."""
    all_s = _load_settlements()
    s = next((x for x in all_s if x["id"] == settlement_id), None)
    if not s:
        raise HTTPException(status_code=404, detail="التسوية غير موجودة")

    rows = ""
    for line in s.get("lines", []):
        d_str = f'<span class="debit">{line["debit"]:,.2f}</span>'   if line["debit"]  else "—"
        c_str = f'<span class="credit">{line["credit"]:,.2f}</span>' if line["credit"] else "—"
        rows += f"<tr><td>{line['date']}</td><td>{line['description'][:60]}</td><td>{d_str}</td><td>{c_str}</td></tr>"

    net_color = "#16a34a" if s["net_amount"] >= 0 else "#dc2626"
    html = f"""<!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head><meta charset="UTF-8"><title>تقرير تسوية — {s['supplier_name']}</title>{_html_style()}</head>
    <body>
      <div class="header">
        <h1>تقرير التسوية</h1>
        <div class="meta">رقم: {s['id'][:8]}<br>التاريخ: {s['date']}</div>
      </div>
      <div class="supplier-info">
        <div><div class="lbl">المورد</div><div class="val">{s['supplier_name']}</div></div>
        <div><div class="lbl">إجمالي المدين</div><div class="val debit">{s['total_debit']:,.2f} ر.س</div></div>
        <div><div class="lbl">إجمالي الدائن</div><div class="val credit">{s['total_credit']:,.2f} ر.س</div></div>
        <div><div class="lbl">صافي التسوية</div>
             <div class="val" style="color:{net_color}">{s['net_amount']:,.2f} ر.س</div></div>
      </div>
      <table>
        <thead><tr><th>التاريخ</th><th>الوصف</th><th>مدين</th><th>دائن</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
      <div class="footer">
        <span>ملاحظات: {s.get('notes') or '—'}</span>
        <span>صافي التسوية: <span style="color:{net_color}">{s['net_amount']:,.2f} ر.س</span></span>
      </div>
      <script>window.onload = () => window.print();</script>
    </body></html>"""
    return HTMLResponse(html)

# ─────────────────────────────────────────────────────────────────────────────
# 4. IMPORT — استيراد Excel/CSV
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/import/preview")
async def import_preview(file: UploadFile = File(...)):
    """معاينة ملف الاستيراد وإرجاع الأعمدة والصفوف الأولى."""
    content = await file.read()
    filename = file.filename or ""
    errors: List[str] = []
    rows: List[List[str]] = []
    headers: List[str] = []

    try:
        if filename.endswith(".csv"):
            text = content.decode("utf-8-sig", errors="replace")
            reader = csv.reader(io.StringIO(text))
            all_rows = list(reader)
            if all_rows:
                headers = all_rows[0]
                rows = all_rows[1:51]  # أول 50 صف للمعاينة
        else:
            # Excel — استخدام openpyxl إذا متاح
            try:
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
                ws = wb.active
                all_rows = [[str(c.value or "") for c in row] for row in ws.iter_rows()]
                if all_rows:
                    headers = all_rows[0]
                    rows = all_rows[1:51]
            except ImportError:
                errors.append("openpyxl غير مثبت — يُرجى رفع ملف CSV")
            except Exception as e:
                errors.append(f"خطأ في قراءة Excel: {e}")
    except Exception as e:
        errors.append(f"خطأ في قراءة الملف: {e}")

    return {
        "success": not errors,
        "data": {
            "headers": headers,
            "preview_rows": rows,
            "total_rows": len(rows),
            "filename": filename,
            "errors": errors,
        }
    }


@router.post("/import/execute")
async def import_execute(payload: Dict[str, Any] = Body(...)):
    """
    تنفيذ الاستيراد بناءً على خريطة الأعمدة.
    Body: { rows: [[...]], mapping: {name_col, amount_col, date_col, type_col}, supplier_id, workshop_id }
    """
    rows     = payload.get("rows") or []
    mapping  = payload.get("mapping") or {}
    supplier_name = payload.get("supplier_name", "")
    workshop_id   = payload.get("workshop_id", "finmodule-sync")

    name_col   = mapping.get("name_col")
    amount_col = mapping.get("amount_col")
    date_col   = mapping.get("date_col")
    type_col   = mapping.get("type_col")

    if amount_col is None:
        raise HTTPException(status_code=400, detail="يجب تحديد عمود المبلغ على الأقل")

    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase غير متصل؛ تم إيقاف الاستيراد دون أي كتابة")

    prepared: List[Dict[str, Any]] = []
    validation_errors: List[Dict[str, Any]] = []
    for i, row in enumerate(rows):
        try:
            amount = float(str(row[int(amount_col)]).replace(",", ""))
            if amount <= 0:
                raise ValueError("مبلغ سالب أو صفر")
            name = str(row[int(name_col)]).strip() if name_col is not None else supplier_name
            date = str(row[int(date_col)]).strip()[:10] if date_col is not None else _now_iso()[:10]
            rtype = str(row[int(type_col)]).strip() if type_col is not None else "credit"
            debit = amount if "debit" in rtype.lower() or "مدين" in rtype else 0.0
            credit = amount if "credit" in rtype.lower() or "دائن" in rtype or not debit else 0.0
            if not debit and not credit:
                credit = amount
            identity_seed = f"supplier-import:{workshop_id}:{payload.get('supplier_id') or name}:{i + 1}:{date}:{amount:.2f}:{rtype}"
            entry_id = str(uuid.uuid5(uuid.NAMESPACE_URL, identity_seed))
            prepared.append({
                "row": i + 1,
                "name": name,
                "amount": amount,
                "date": date,
                "entry": {
                    "id": entry_id,
                    "workshop_id": workshop_id,
                    "date": date,
                    "description": f"[مستورد] {name} — {rtype}",
                    "source": "import",
                    "transaction_type": "supplier_import",
                    "reference_id": f"supplier-import:{entry_id}",
                    "business_event_id": f"supplier_import::{entry_id}",
                    "lines": [
                        {"account": "004", "account_name": "البنك", "debit": debit, "credit": credit if not debit else 0},
                        {"account": "2101", "account_name": f"مورد - {name}", "debit": credit if not debit else 0, "credit": debit},
                    ],
                    "total": amount,
                },
            })
        except Exception as error:
            validation_errors.append({"row": i + 1, "error": str(error), "data": row[:5]})

    if validation_errors:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "supplier_import_validation_failed",
                "message": "فشل التحقق؛ لم تُكتب أي حركة مالية",
                "failed_rows": validation_errors[:20],
            },
        )

    from core import accounting_engine
    imported: List[Dict[str, Any]] = []
    for item in prepared:
        posted_rows = accounting_engine.post_entry(item["entry"], fallback=False)
        if not isinstance(posted_rows, list) or not posted_rows or not (posted_rows[0] or {}).get("id"):
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "supplier_import_post_failed",
                    "failed_row": item["row"],
                    "posted_rows_before_failure": len(imported),
                    "message": "لم يعتبر الاستيراد ناجحًا؛ لم يؤكد AccountingEngine حفظ السطر",
                },
            )
        imported.append({"row": item["row"], "name": item["name"], "amount": item["amount"], "date": item["date"]})

    invalidate_finance_caches()

    return {
        "success": True,
        "data": {
            "imported": len(imported),
            "failed":   0,
            "imported_rows": imported[:10],
            "failed_rows":   [],
        }
    }
