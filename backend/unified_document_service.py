"""
خدمة توليد المستندات الموحدة
Unified Document Generation Service

تدمج:
- فواتير المبيعات
- تقارير التشخيص
- عروض الأسعار
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
# qrcode removed: approvals should not be embedded in printed documents
from arabic_quotation import ArabicQuotationBuilder


from fastapi import Body

class UnifiedDocumentGenerator:
    """مولد المستندات الموحد"""

    def __init__(self):
        self.builder = ArabicQuotationBuilder()
        self.document_types = {
            "invoice": "فاتورة مبيعات",
            "diagnosis": "تقرير تشخيص",
            "quote": "عرض سعر",
            "receipt": "إيصال استلام",
        }

    def generate_document(
        self,
        doc_type: str,
        workshop_data: Dict,
        customer_data: Dict,
        vehicle_data: Optional[Dict],
        items: List[Dict],
        settings: Optional[Dict] = None,
    ) -> str:
        """توليد مستند HTML مع دعم توقيع الموافقة الإلكترونية"""

        settings = settings or {}

        # حسب طلب الورشة: لا نعرض QR/Barcode أو أي بيانات موافقة داخل المستندات المطبوعة.
        # تبقى بيانات الاعتماد داخل النظام فقط (ملف العميل/الزيارة).

        """توليد مستند موحد"""

        settings = settings or {}
        theme = settings.get("theme", "أزرق")
        style = settings.get("style", "حديث")
        # الضرائب غير مستخدمة حسب متطلبات الورشة
        tax_rate = 0

        # إعادة تعيين البيانات
        self.builder.reset_quotation()



        # تعيين بيانات الورشة/الشركة
        self.builder.set_company(
            name=workshop_data.get("name", "ورشة الصيانة"),
            name_en=workshop_data.get("name_en", "Maintenance Workshop"),
            address=workshop_data.get("address", ""),
            phone=workshop_data.get("phone", ""),
            email=workshop_data.get("email", ""),
            website=workshop_data.get("website", ""),
            slogan=workshop_data.get("slogan", workshop_data.get("sloganEnglish", "")),
            
            commercial_register=workshop_data.get(
                "commercial_register",
                workshop_data.get(
                    "commercialRegister",
                    "",
                ),
            ),
            logo=workshop_data.get("logo", ""),
        )

        # تعيين بيانات العميل
        self.builder.set_client(
            name=customer_data.get("name", customer_data.get("customerName", "")),
            company=customer_data.get("company", ""),
            address=customer_data.get("address", ""),
            phone=customer_data.get("phone", customer_data.get("customerPhone", "")),
            email=customer_data.get("email", ""),
        )

        # تعيين وصف المشروع/المركبة
        project_desc = self._build_project_description(doc_type, vehicle_data, settings)
        self.builder.set_project(project_desc)

        # تعيين التاريخ إذا كان موجوداً في الإعدادات
        if settings.get("date"):
            # تحويل التاريخ من YYYY-MM-DD إلى YYYY/MM/DD
            date_str = settings["date"].replace("-", "/")
            self.builder.quotation["date"] = date_str

        # تعيين نسبة الضريبة
        self.builder.quotation["tax_rate"] = tax_rate

        # إضافة البنود
        for item in items:
            self.builder.add_item(
                description=item.get("description", item.get("name", "")),
                quantity=float(item.get("quantity", item.get("qty", 1))),
                unit_price=float(item.get("unit_price", item.get("price", 0))),
                discount=float(item.get("discount", 0)),
            )

        # تعيين الشروط حسب نوع المستند
        # إذا كان المستخدم قد أدخل شروط مخصصة، استخدمها
        if (
            settings.get("terms")
            and isinstance(settings["terms"], list)
            and len(settings["terms"]) > 0
        ):
            self.builder.quotation["terms"] = settings["terms"]
        else:
            self.builder.quotation["terms"] = self._get_terms_for_type(
                doc_type, settings
            )

        # تعديل العنوان حسب النوع
        self._customize_for_type(doc_type, settings)

        # توليد HTML
        return self.builder.generate_html(theme=theme, style=style)

    def _build_project_description(
        self, doc_type: str, vehicle_data: Optional[Dict], settings: Dict
    ) -> str:
        """بناء وصف المشروع/المركبة"""
        if not vehicle_data:
            return settings.get("description", "")

        parts = []

        # معلومات المركبة
        brand = vehicle_data.get("brand", "")
        model = vehicle_data.get("model", "")
        year = vehicle_data.get("year", "")
        plate = vehicle_data.get("plateNumber", vehicle_data.get("plate", ""))
        vin = vehicle_data.get("vin", "")
        color = vehicle_data.get("color", "")
        mileage = vehicle_data.get("mileage", "")

        if brand or model:
            parts.append(f"المركبة: {brand} {model} {year}".strip())
        if plate:
            parts.append(f"اللوحة: {plate}")
        if vin:
            parts.append(f"الهيكل: {vin}")
        if color:
            parts.append(f"اللون: {color}")
        if mileage:
            parts.append(f"العداد: {mileage} كم")

        # ملاحظات إضافية
        notes = vehicle_data.get("notes", settings.get("notes", ""))
        if notes:
            parts.append(f"\nملاحظات: {notes}")

        return " | ".join(parts) if parts else "خدمات صيانة وإصلاح"

    def _get_terms_for_type(self, doc_type: str, settings: Dict) -> List[str]:
        """الحصول على الشروط حسب نوع المستند"""

        custom_terms = settings.get("terms", [])
        if custom_terms:
            return custom_terms

        if doc_type == "invoice":
            return [
                "الأسعار بالريال السعودي",
                "يرجى التحقق من البنود قبل مغادرة الورشة",
                "ضمان الإصلاح حسب نوع الخدمة",
                "لا يتم استرداد المبلغ بعد الخروج",
            ]
        elif doc_type == "diagnosis":
            return [
                "هذا تقرير تشخيصي فقط وليس أمر إصلاح",
                "الأسعار تقديرية وقابلة للتغيير",
                "يتطلب موافقة العميل قبل البدء بالإصلاح",
                "صلاحية التقرير 7 أيام من تاريخ الإصدار",
            ]
        elif doc_type == "quote":
            return [
                "هذا العرض صالح لمدة 30 يوماً من تاريخ الإصدار",
                "يتطلب دفع 50% مقدماً لبدء العمل",
                "الأسعار لا تشمل التعديلات الإضافية غير المذكورة",
                "جميع الأسعار بالريال السعودي",
            ]
        elif doc_type == "receipt":
            return [
                "تم استلام المركبة بحالتها الحالية",
                "يرجى الاحتفاظ بهذا الإيصال",
                "سيتم التواصل معكم عند جاهزية المركبة",
            ]

        return []

    def _customize_for_type(self, doc_type: str, settings: Dict):
        """تخصيص المستند حسب النوع"""

        # تعديل عنوان المستند حسب النوع
        custom_title = settings.get("document_title") if isinstance(settings, dict) else None
        if custom_title:
            self.builder.quotation["doc_title"] = custom_title
            return

        title_map = {
            "invoice": "فاتورة مبيعات",
            "diagnosis": "تقرير تشخيص",
            "quote": "عرض سعر",
            "receipt": "إيصال استلام",
        }
        self.builder.quotation["doc_title"] = title_map.get(doc_type, "مستند")
        self.builder.quotation["doc_type"] = doc_type

        # تعديل رقم المستند
        doc_number = settings.get("document_number")
        if doc_number:
            self.builder.quotation["number"] = doc_number
        else:
            prefix_map = {
                "invoice": "INV",
                "diagnosis": "DIG",
                "quote": "QT",
                "receipt": "RCP",
            }
            prefix = prefix_map.get(doc_type, "DOC")
            now = datetime.now()
            self.builder.quotation["number"] = (
                f"{prefix}-{now.year}-{now.month:02d}{now.day:02d}-{now.hour:02d}{now.minute:02d}"
            )

        # تعديل صلاحية العرض
        validity_days = settings.get("validity_days", 30 if doc_type == "quote" else 7)
        self.builder.quotation["valid_until"] = (
            datetime.now() + timedelta(days=validity_days)
        ).strftime("%Y/%m/%d")

    def get_document_data(self) -> Dict:
        """الحصول على بيانات المستند"""
        return self.builder.to_dict()


# FastAPI Integration
def create_unified_document_routes(router):
    """إنشاء مسارات API للمستندات الموحدة"""
    from fastapi import HTTPException
    from fastapi.responses import HTMLResponse
    from pydantic import BaseModel
    from typing import List, Optional, Any

    class DocumentItem(BaseModel):
        description: Optional[str] = ""
        name: Optional[str] = ""
        quantity: Optional[float] = 1
        qty: Optional[float] = 1
        unit_price: Optional[float] = 0
        price: Optional[float] = 0
        discount: Optional[float] = 0

        class Config:
            extra = "allow"

    class DocumentCustomer(BaseModel):
        name: Optional[str] = ""
        customerName: Optional[str] = ""
        company: Optional[str] = ""
        address: Optional[str] = ""
        phone: Optional[str] = ""
        customerPhone: Optional[str] = ""
        email: Optional[str] = ""

        class Config:
            extra = "allow"

    class DocumentWorkshop(BaseModel):
        name: Optional[str] = ""
        name_en: Optional[str] = ""
        address: Optional[str] = ""
        phone: Optional[str] = ""
        email: Optional[str] = ""
        website: Optional[str] = ""
        commercial_register: Optional[str] = ""
        commercialRegister: Optional[str] = ""

        class Config:
            extra = "allow"

    class DocumentVehicle(BaseModel):
        brand: Optional[str] = ""
        model: Optional[str] = ""
        year: Optional[Any] = ""
        plateNumber: Optional[str] = ""
        plate: Optional[str] = ""
        vin: Optional[str] = ""
        color: Optional[str] = ""
        mileage: Optional[Any] = ""
        notes: Optional[str] = ""

        class Config:
            extra = "allow"

    class DocumentSettings(BaseModel):
        theme: Optional[str] = "أزرق"
        style: Optional[str] = "حديث"
        tax_rate: Optional[float] = 15
        document_number: Optional[str] = None
        validity_days: Optional[int] = 30
        description: Optional[str] = ""
        notes: Optional[str] = ""
        terms: Optional[List[str]] = None

        class Config:
            extra = "allow"

    class GenerateDocumentRequest(BaseModel):
        doc_type: str = "invoice"  # invoice, diagnosis, quote, receipt
        workshop: Optional[DocumentWorkshop] = None
        customer: Optional[DocumentCustomer] = None
        vehicle: Optional[DocumentVehicle] = None
        items: List[DocumentItem] = []
        settings: Optional[DocumentSettings] = None

    async def _load_workshop_profile_fallback() -> Dict:
        """Best-effort fetch of workshop profile from the same backend.

        NOTE: use async http client to avoid blocking event loop.
        """
        try:
            import httpx

            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get("http://127.0.0.1:8001/api/profile")
                if r.status_code == 200:
                    data = r.json() or {}
                    if "commercialRegister" in data and "commercial_register" not in data:
                        data["commercial_register"] = data.get("commercialRegister")
                    return data
        except Exception:
            pass
        return {}

    @router.post("/documents/generate")
    async def generate_document(payload: Dict = Body(...)):
        """توليد مستند (فاتورة/تشخيص/عرض سعر)

        Accepts both:
        - New payload: {doc_type, workshop, customer, vehicle, items, settings}
        - Legacy payload: {doc_type, workshop_id, company, client, vehicle, items, totals, language}
        """
        try:
            import logging

            doc_type = payload.get("doc_type") or "invoice"

            # Normalize workshop/customer from multiple possible keys
            workshop_data = payload.get("workshop") or payload.get("company") or {}
            customer_data = payload.get("customer") or payload.get("client") or {}
            vehicle_data = payload.get("vehicle") or None
            items = payload.get("items") or []
            settings = payload.get("settings") or {}

            # If workshop missing, fallback to stored profile
            if not workshop_data or not isinstance(workshop_data, dict):
                workshop_data = {}

            # Always merge stored profile as defaults, so missing legal fields (like commercial register) still appear.
            workshop_data = {**(await _load_workshop_profile_fallback()), **workshop_data}

            logging.info(f"Document generation request received: doc_type={doc_type}")
            logging.info(f"Workshop keys: {list((workshop_data or {}).keys())[:10]}")
            logging.info(f"Customer keys: {list((customer_data or {}).keys())[:10]}")
            logging.info(f"Items count: {len(items) if isinstance(items, list) else 0}")

            generator = UnifiedDocumentGenerator()

            # Convert to dicts
            if vehicle_data and not isinstance(vehicle_data, dict):
                vehicle_data = {}
            if not isinstance(items, list):
                items = []
            if not isinstance(settings, dict):
                settings = {}

            # Map workshop keys

            if "commercialRegister" in workshop_data and "commercial_register" not in workshop_data:
                workshop_data["commercial_register"] = workshop_data.get("commercialRegister")
            # Back-compat: some older profiles stored commercial register in tax_number.
            if not workshop_data.get("commercial_register") and workshop_data.get("tax_number"):
                workshop_data["commercial_register"] = workshop_data.get("tax_number")

            # إذا تم تمرير approval_token نحاول جلب بيانات الموافقة من Supabase
            raw_token = settings.get("approval_token")
            token = str(raw_token).strip() if raw_token is not None else ""
            if token:
                try:
                    # نحاول دائماً جلب بيانات الموافقة من Supabase بغض النظر عن نوع مزود قاعدة البيانات
                    from supabase_service import SupabaseService

                    supa = SupabaseService()
                    # رموز الموافقة تحفظ حالياً بصيغة APR-XXXX كبيرة، لذلك نحوّل الإدخال إلى حروف كبيرة
                    token_norm = token.upper()
                    res = (
                        supa.client.table("approval_requests")
                        .select("*")
                        .eq("token", token_norm)
                        .execute()
                    )
                    rows = res.data or []
                    if rows:
                        r = rows[0]
                        meta = {}
                        text = r.get("service_items_text") or ""
                        for part in text.split("|"):
                            if "=" in part:
                                k, v = part.split("=", 1)
                                meta[k.strip()] = v.strip()
                        # نملأ بيانات الموافقة حتى لو كانت الحالة مختلفة، وسيتم عرضها كما هي في الفاتورة
                        settings["approval_info"] = {
                            "token": r.get("token"),
                            "status": r.get("status"),
                            "responderName": r.get("responder_name"),
                            "responderPhone": r.get("responder_phone"),
                            "respondedAt": r.get("responded_at"),
                            "clientIp": meta.get("ip"),
                            "userAgent": meta.get("ua"),
                        }
                except Exception:
                    # في حال فشل جلب الموافقة، نستمر بدون تعطيل توليد المستند
                    pass

            # في حال لم يتم تمرير approval_info لكن لدينا معرف مركبة، نحاول جلب أحدث موافقة تلقائياً حسب رقم المركبة
            if not settings.get("approval_info"):
                # نأخذ vehicle_id إما من الإعدادات أو من بيانات المركبة
                approval_vehicle_id = (
                    settings.get("approval_vehicle_id")
                    or (vehicle_data or {}).get("id")
                    or (vehicle_data or {}).get("vehicleId")
                )
                if approval_vehicle_id:
                    try:
                        from supabase_service import SupabaseService

                        supa = SupabaseService()
                        # نجلب أحدث موافقة لهذه المركبة (الأحدث حسب responded_at أو created_at)
                        res2 = (
                            supa.client.table("approval_requests")
                            .select("*")
                            .eq("vehicle_id", approval_vehicle_id)
                            .order("responded_at", desc=True)
                            .limit(1)
                            .execute()
                        )
                        rows2 = res2.data or []
                        if rows2:
                            r2 = rows2[0]
                            meta2 = {}
                            text2 = r2.get("service_items_text") or ""
                            for part in text2.split("|"):
                                if "=" in part:
                                    k, v = part.split("=", 1)
                                    meta2[k.strip()] = v.strip()
                            settings["approval_info"] = {
                                "token": r2.get("token"),
                                "status": r2.get("status"),
                                "responderName": r2.get("responder_name"),
                                "responderPhone": r2.get("responder_phone"),
                                "respondedAt": r2.get("responded_at"),
                                "clientIp": meta2.get("ip"),
                                "userAgent": meta2.get("ua"),
                            }
                    except Exception:
                        # إذا فشلنا في الجلب التلقائي لا نكسر توليد المستند
                        pass

            # توليد HTML
            html_content = generator.generate_document(
                doc_type=doc_type,
                workshop_data=workshop_data,
                customer_data=customer_data,
                vehicle_data=vehicle_data,
                items=items,
                settings=settings,
            )

            return {
                "success": True,
                "doc_type": doc_type,
                "document_number": generator.builder.quotation["number"],
                "html": html_content,
                "data": generator.get_document_data(),
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/documents/generate-html", response_class=HTMLResponse)
    async def generate_document_html(request: GenerateDocumentRequest):
        """توليد مستند وإرجاع HTML مباشرة"""
        try:
            generator = UnifiedDocumentGenerator()

            workshop_data = request.workshop.dict()
            customer_data = request.customer.dict()
            vehicle_data = request.vehicle.dict() if request.vehicle else None
            items = [item.dict() for item in request.items]
            settings = request.settings.dict() if request.settings else {}

            html_content = generator.generate_document(
                doc_type=request.doc_type,
                workshop_data=workshop_data,
                customer_data=customer_data,
                vehicle_data=vehicle_data,
                items=items,
                settings=settings,
            )

            return HTMLResponse(content=html_content)

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/documents/types")
    async def get_document_types():
        """الحصول على أنواع المستندات المتاحة"""
        generator = UnifiedDocumentGenerator()
        return {
            "types": generator.document_types,
            "themes": list(generator.builder.themes.keys()),
            "styles": ["حديث", "كلاسيكي", "فاخر"],
        }

    return router


if __name__ == "__main__":
    # اختبار سريع
    generator = UnifiedDocumentGenerator()

    html = generator.generate_document(
        doc_type="invoice",
        workshop_data={
            "name": "ورشة الخليج للصيانة",
            "phone": "+966 11 123 4567",
            "tax_number": "300012345600003",
        },
        customer_data={"name": "أحمد محمد", "phone": "+966 50 123 4567"},
        vehicle_data={
            "brand": "تويوتا",
            "model": "كامري",
            "year": "2022",
            "plateNumber": "أ ب ج 1234",
        },
        items=[
            {"description": "تغيير زيت", "quantity": 1, "unit_price": 150},
            {"description": "فلتر زيت", "quantity": 1, "unit_price": 50},
            {"description": "فحص شامل", "quantity": 1, "unit_price": 200},
        ],
        settings={"theme": "أزرق", "style": "حديث"},
    )

    print(f"✅ تم توليد المستند: {generator.builder.quotation['number']}")
    print(f"المجموع: {generator.builder.quotation['total']:,.2f} ر.س")
