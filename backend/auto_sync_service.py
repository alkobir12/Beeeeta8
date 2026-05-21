"""
Auto-Sync Service
يحفظ تلقائياً في MongoDB + Notion + Supabase عند توفر المفاتيح
"""

from typing import Dict, Any

try:
    from notion_service import NotionService
    from supabase_service import SupabaseService
except Exception:
    NotionService = None
    SupabaseService = None


class AutoSyncService:
    """خدمة الحفظ التلقائي في جميع الأنظمة"""

    def __init__(self, db):
        """Initialize with MongoDB client"""
        self.db = db

        # Initialize Notion if available
        if NotionService:
            self.notion = NotionService()
        else:
            self.notion = None

        # Initialize Supabase if available
        if SupabaseService:
            self.supabase = SupabaseService()
        else:
            self.supabase = None

    async def save_customer(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        حفظ عميل في جميع الأنظمة
        1. MongoDB (أساسي - دائماً)
        2. Notion (إذا متوفر)
        3. Supabase (إذا متوفر)
        """
        results = {"mongodb": None, "notion": None, "supabase": None, "success": False}

        try:
            # 1. حفظ في MongoDB (الأساسي)
            mongo_result = await self.db.customers.insert_one(customer_data)
            customer_data["_id"] = str(mongo_result.inserted_id)
            results["mongodb"] = "saved"
            results["success"] = True

            # 2. حفظ في Notion (إذا متوفر ومفعّل)
            if self.notion and not self.notion.mock_mode:
                try:
                    self.notion.create_customer(
                        name=customer_data.get("name", ""),
                        email=customer_data.get("email", ""),
                        phone=customer_data.get("phone", ""),
                        company=customer_data.get("company", ""),
                        notes=customer_data.get("notes", ""),
                    )
                    results["notion"] = "saved"
                except Exception as e:
                    results["notion"] = f"failed: {str(e)}"
            else:
                results["notion"] = "skipped (mock mode or not configured)"

            # 3. حفظ في Supabase (إذا متوفر ومفعّل)
            if self.supabase and not self.supabase.mock_mode:
                try:
                    supabase_data = {
                        "name": customer_data.get("name", ""),
                        "email": customer_data.get("email", ""),
                        "phone": customer_data.get("phone", ""),
                        "company": customer_data.get("company", ""),
                    }
                    (
                        self.supabase.client.table("customers")
                        .insert(supabase_data)
                        .execute()
                    )
                    results["supabase"] = "saved"
                except Exception as e:
                    results["supabase"] = f"failed: {str(e)}"
            else:
                results["supabase"] = "skipped (mock mode or not configured)"

            return results

        except Exception as e:
            results["error"] = str(e)
            return results

    async def save_vehicle(self, vehicle_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        حفظ مركبة في جميع الأنظمة
        """
        results = {"mongodb": None, "supabase": None, "success": False}

        try:
            # 1. MongoDB (الأساسي)
            mongo_result = await self.db.vehicles.insert_one(vehicle_data)
            vehicle_data["_id"] = str(mongo_result.inserted_id)
            results["mongodb"] = "saved"
            results["success"] = True

            # 2. Supabase (إذا متوفر)
            if self.supabase and not self.supabase.mock_mode:
                try:
                    supabase_data = {
                        "plate_number": vehicle_data.get("plateNumber", ""),
                        "make": vehicle_data.get("make", ""),
                        "model": vehicle_data.get("model", ""),
                        "year": vehicle_data.get("year"),
                        "customer_name": vehicle_data.get("customerName", ""),
                        "services": vehicle_data.get("services", []),
                    }
                    self.supabase.create_vehicle(supabase_data)
                    results["supabase"] = "saved"
                except Exception as e:
                    results["supabase"] = f"failed: {str(e)}"
            else:
                results["supabase"] = "skipped"

            return results

        except Exception as e:
            results["error"] = str(e)
            return results

    async def save_service(self, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        حفظ خدمة في جميع الأنظمة
        """
        results = {"mongodb": None, "notion": None, "success": False}

        try:
            # 1. MongoDB
            mongo_result = await self.db.services.insert_one(service_data)
            service_data["_id"] = str(mongo_result.inserted_id)
            results["mongodb"] = "saved"
            results["success"] = True

            # 2. Notion - يمكن إضافة الخدمات كـ procedures
            if self.notion and not self.notion.mock_mode:
                results["notion"] = "ready for integration"
            else:
                results["notion"] = "skipped"

            return results

        except Exception as e:
            results["error"] = str(e)
            return results

    def get_sync_status(self) -> Dict[str, Any]:
        """الحصول على حالة المزامنة"""
        return {
            "mongodb": "active",
            "notion": {
                "available": self.notion is not None,
                "mode": "mock" if (self.notion and self.notion.mock_mode) else "live",
                "status": "ready" if self.notion else "not initialized",
            },
            "supabase": {
                "available": self.supabase is not None,
                "mode": (
                    "mock" if (self.supabase and self.supabase.mock_mode) else "live"
                ),
                "status": "ready" if self.supabase else "not initialized",
            },
        }
