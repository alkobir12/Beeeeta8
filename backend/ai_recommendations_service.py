"""
خدمة التوصيات الذكية بالذكاء الاصطناعي
AI-Powered Recommendations Service
"""

from typing import List, Dict
import statistics

# Gemini AI (إن وجد)
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    GEMINI_AVAILABLE = True
except Exception:
    GEMINI_AVAILABLE = False


class AIRecommendations:
    """نظام التوصيات الذكية"""

    def __init__(self):
        self.llm = None
        if GEMINI_AVAILABLE:
            try:
                self.llm = LlmChat(model="gemini-2.0-flash-exp")
            except Exception:
                pass

    def analyze_pricing(
        self, services: List[Dict], operations: List[Dict]
    ) -> List[Dict]:
        """
        تحليل الأسعار واقتراح تحسينات
        """
        recommendations = []

        # حساب متوسط سعر السوق لكل خدمة (من العمليات السابقة)
        service_stats = {}

        for op in operations:
            for item in op.get("items", []):
                if item.get("itemType") == "service":
                    name = item.get("itemName", "")
                    price = item.get("unitPrice", 0)

                    if name not in service_stats:
                        service_stats[name] = []
                    service_stats[name].append(price)

        # مقارنة مع الأسعار الحالية
        for service in services:
            name = service.get("name", "")
            current_price = service.get("price", 0)

            if name in service_stats and len(service_stats[name]) > 3:
                avg_price = statistics.mean(service_stats[name])

                # إذا كان السعر الحالي أقل من المتوسط بنسبة >10%
                if current_price < avg_price * 0.9:
                    recommendations.append(
                        {
                            "id": f"PRICE_{service.get('id')}",
                            "type": "pricing",
                            "title": f"تحسين سعر خدمة {name}",
                            "description": f"السعر الحالي ({current_price:.0f} ر.س) أقل من متوسط السوق ({avg_price:.0f} ر.س). يُقترح رفع السعر.",
                            "current_value": current_price,
                            "recommended_value": round(avg_price, 0),
                            "expected_impact": f"+{round((avg_price - current_price) / current_price * 100, 0)}% زيادة في الإيرادات",
                            "priority": (
                                "high"
                                if (avg_price - current_price) / current_price > 0.2
                                else "medium"
                            ),
                        }
                    )

        return recommendations

    def analyze_inventory(
        self, parts: List[Dict], operations: List[Dict]
    ) -> List[Dict]:
        """
        تحليل المخزون واقتراح إعادة الطلب
        """
        recommendations = []

        # حساب معدل استهلاك كل قطعة (من العمليات)
        parts_usage = {}

        for op in operations[-90:]:  # آخر 90 يوم
            for item in op.get("items", []):
                if item.get("itemType") == "part":
                    name = item.get("itemName", "")
                    qty = item.get("quantity", 0)

                    if name not in parts_usage:
                        parts_usage[name] = 0
                    parts_usage[name] += qty

        # تحليل كل قطعة
        for part in parts:
            name = part.get("name", "")
            current_stock = part.get("quantity", part.get("current_stock", 0))
            min_stock = part.get("minQuantity", part.get("min_stock", 5))

            # معدل الاستهلاك الشهري
            monthly_usage = parts_usage.get(name, 0) / 3  # متوسط آخر 3 أشهر

            # إذا كان المخزون منخفض
            if current_stock < min_stock:
                reorder_qty = max(int(monthly_usage * 2), min_stock * 2)  # مخزون لشهرين

                recommendations.append(
                    {
                        "id": f"INV_{part.get('id')}",
                        "type": "inventory",
                        "title": f"إعادة طلب {name}",
                        "description": f"المخزون الحالي ({current_stock}) أقل من الحد الأدنى ({min_stock}). معدل الاستهلاك الشهري: {monthly_usage:.0f} قطعة.",
                        "current_value": current_stock,
                        "recommended_value": reorder_qty,
                        "expected_impact": "منع نفاد المخزون وضمان استمرارية العمل",
                        "priority": (
                            "high" if current_stock < min_stock * 0.5 else "medium"
                        ),
                    }
                )

        return recommendations

    def analyze_customers(
        self, customers: List[Dict], operations: List[Dict]
    ) -> List[Dict]:
        """
        تحليل العملاء واقتراح عروض
        """
        recommendations = []

        # تحليل العملاء الأكثر قيمة
        customer_value = {}

        for op in operations:
            customer_id = op.get("customerId")
            if customer_id:
                if customer_id not in customer_value:
                    customer_value[customer_id] = {"total": 0, "count": 0}
                customer_value[customer_id]["total"] += op.get("total", 0)
                customer_value[customer_id]["count"] += 1

        # اقتراح عروض للعملاء ذوي القيمة العالية
        for customer in customers:
            customer_id = customer.get("id")
            name = customer.get("name", "")
            balance = customer.get("balance", 0)

            if customer_id in customer_value:
                value = customer_value[customer_id]

                # عميل قيم مع رصيد مستحق
                if value["total"] > 5000 and balance > 1000:
                    recommendations.append(
                        {
                            "id": f"CUST_{customer_id}",
                            "type": "customer",
                            "title": f"عرض خاص للعميل {name}",
                            "description": f'عميل قيم (إجمالي تعاملات: {value["total"]:.0f} ر.س، {value["count"]} زيارة). لديه {balance:.0f} ر.س مستحقة. مقترح: خصم 10% على الصيانة القادمة لتشجيع الدفع.',
                            "current_value": balance,
                            "recommended_value": 0,
                            "expected_impact": "زيادة ولاء العميل وتحصيل المستحقات",
                            "priority": "medium",
                        }
                    )

        return recommendations

    def generate_ai_recommendations_with_gemini(self, data: Dict) -> str:
        """
        توليد توصيات ذكية باستخدام Gemini AI
        """

        if not self.llm:
            return "خدمة AI غير متوفرة حالياً"

        try:
            prompt = f"""أنت خبير مالي في ورشة صيانة سيارات. قم بتحليل البيانات التالية وقدم 3 توصيات ذكية:

البيانات المالية:
- إجمالي الإيرادات: {data.get('revenue', 0):.2f} ر.س
- إجمالي المصروفات: {data.get('expenses', 0):.2f} ر.س
- صافي الربح: {data.get('net_profit', 0):.2f} ر.س
- نسبة التداول: {data.get('current_ratio', 0)}
- هامش الربح: {data.get('net_margin', 0)}%

قدم توصيات عملية قصيرة ومحددة بالعربية (كل توصية في سطر واحد)."""

            messages = [UserMessage(content=prompt)]
            response = self.llm.run(messages=messages)
            return response.content

        except Exception as e:
            return f"خطأ في AI: {str(e)}"

    def get_all_recommendations(
        self,
        services: List[Dict],
        parts: List[Dict],
        customers: List[Dict],
        operations: List[Dict],
        accounts: List[Dict],
    ) -> List[Dict]:
        """
        جمع جميع التوصيات
        """

        all_recommendations = []

        # توصيات الأسعار
        pricing_recs = self.analyze_pricing(services, operations)
        all_recommendations.extend(pricing_recs)

        # توصيات المخزون
        inventory_recs = self.analyze_inventory(parts, operations)
        all_recommendations.extend(inventory_recs)

        # توصيات العملاء
        customer_recs = self.analyze_customers(customers, operations)
        all_recommendations.extend(customer_recs)

        # ترتيب حسب الأولوية
        priority_order = {"high": 0, "medium": 1, "low": 2}
        all_recommendations.sort(
            key=lambda x: priority_order.get(x.get("priority", "low"), 3)
        )

        return all_recommendations


# Instance للاستخدام
ai_recommendations = AIRecommendations()
