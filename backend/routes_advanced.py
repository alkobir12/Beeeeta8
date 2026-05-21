from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from typing import List, Optional
import uuid

from models_advanced import (
    Product,
    ShopOrder,
    AIBot,
    BotConversation,
    CEOAlert,
    WorkshopService,
    ServicePackage,
    Ticket,
    TicketResponse,
    CustomerFeedback,
    FAQ,
)

from emergentintegrations.llm.chat import LlmChat, UserMessage
import os
from google_service import GoogleService
import json


router = APIRouter(prefix="/api")

db = None


def set_db(database):
    global db
    db = database


# ============ Store/Shop APIs ============
@router.post("/products", response_model=Product)
async def create_product(product: Product):
    await db.products.insert_one(product.dict())
    return product


@router.get("/products", response_model=List[Product])
async def get_products(category: Optional[str] = None, featured: bool = False):
    query = {"isActive": True}
    if category:
        query["category"] = category
    if featured:
        query["featured"] = True

    products = await db.products.find(query).to_list(1000)
    return [Product(**p) for p in products]


@router.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: str):
    product = await db.products.find_one({"id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return Product(**product)


@router.post("/shop-orders", response_model=ShopOrder)
async def create_shop_order(order: ShopOrder):
    await db.shop_orders.insert_one(order.dict())

    # Update product sold count and stock
    for item in order.items:
        await db.products.update_one(
            {"id": item["productId"]},
            {"$inc": {"soldCount": item["quantity"], "stock": -item["quantity"]}},
        )

    return order


@router.get("/shop-orders")
async def get_shop_orders(
    customer_id: Optional[str] = None, status: Optional[str] = None
):
    query = {}
    if customer_id:
        query["customerId"] = customer_id
    if status:
        query["status"] = status

    orders = await db.shop_orders.find(query).sort("orderDate", -1).to_list(1000)
    return [ShopOrder(**o) for o in orders]


@router.put("/shop-orders/{order_id}/status")
async def update_order_status(order_id: str, status: str):
    await db.shop_orders.update_one({"id": order_id}, {"$set": {"status": status}})
    return {"message": "Order status updated"}


# ============ AI Bots APIs ============
@router.get("/ai-bots", response_model=List[AIBot])
async def get_ai_bots():
    bots = await db.ai_bots.find({"isActive": True}).to_list(1000)
    if not bots:
        # Create default bots
        default_bots = [
            AIBot(
                name="Diagnostic Assistant",
                nameArabic="مساعد التشخيص",
                specialty="diagnostics",
                description="يساعدك في تشخيص مشاكل السيارة وتحديد الأعطال",
                icon="🔧",
                systemPrompt="أنت مساعد ذكاء اصطناعي متخصص في تشخيص أعطال السيارات. اسأل أسئلة محددة لتحديد المشكلة وقدم حلول واضحة بالعربية.",
            ),
            AIBot(
                name="Parts Advisor",
                nameArabic="مستشار القطع",
                specialty="parts_advisor",
                description="يساعدك في اختيار قطع الغيار المناسبة",
                icon="⚙️",
                systemPrompt="أنت خبير في قطع غيار السيارات. ساعد العملاء في اختيار القطع المناسبة لسياراتهم.",
            ),
            AIBot(
                name="Service Advisor",
                nameArabic="مستشار الصيانة",
                specialty="service_advisor",
                description="ينصحك بجدول الصيانة المناسب",
                icon="📋",
                systemPrompt="أنت مستشار صيانة متخصص. قدم نصائح حول جداول الصيانة الدورية وأفضل الممارسات.",
            ),
            AIBot(
                name="Sales Assistant",
                nameArabic="مساعد المبيعات",
                specialty="sales",
                description="يساعدك في اختيار المنتجات والخدمات",
                icon="🛒",
                systemPrompt="أنت مساعد مبيعات ودود. ساعد العملاء في اختيار المنتجات والخدمات المناسبة لاحتياجاتهم.",
            ),
        ]
        for bot in default_bots:
            await db.ai_bots.insert_one(bot.dict())
        bots = [b.dict() for b in default_bots]

    return [AIBot(**b) for b in bots]


@router.post("/ai-bots/{bot_id}/chat")
async def chat_with_bot(bot_id: str, message: str, session_id: Optional[str] = None):
    bot = await db.ai_bots.find_one({"id": bot_id})
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    bot_obj = AIBot(**bot)

    if not session_id:
        session_id = str(uuid.uuid4())

    # Get or create conversation
    conversation = await db.bot_conversations.find_one({"sessionId": session_id})
    if not conversation:
        conversation = BotConversation(botId=bot_id, sessionId=session_id).dict()
        await db.bot_conversations.insert_one(conversation)

    try:
        # Use Claude AI
        llm_key = os.getenv("EMERGENT_LLM_KEY")
        chat = LlmChat(
            api_key=llm_key, session_id=session_id, system_message=bot_obj.systemPrompt
        ).with_model("anthropic", "claude-sonnet-4-20250514")

        user_message = UserMessage(text=message)
        response = await chat.send_message(user_message)

        # Save messages
        await db.bot_conversations.update_one(
            {"sessionId": session_id},
            {
                "$push": {
                    "messages": {
                        "$each": [
                            {
                                "role": "user",
                                "content": message,
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                            {
                                "role": "assistant",
                                "content": response,
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                        ]
                    }
                },
                "$set": {"lastActivity": datetime.utcnow()},
            },
        )

        # Update bot usage
        await db.ai_bots.update_one({"id": bot_id}, {"$inc": {"usageCount": 1}})

        return {"response": response, "sessionId": session_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ CEO Dashboard APIs ============
@router.get("/ceo/metrics")
async def get_ceo_metrics(days: int = 30):
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Get transactions
    transactions = await db.transactions.find(
        {"date": {"$gte": start_date, "$lte": end_date}},
        {"_id": 0, "amount": 1, "type": 1},
    ).to_list(10000)

    # Vehicles count only (no full docs)
    vehicles_count = await db.vehicles.count_documents(
        {"entryDate": {"$gte": start_date, "$lte": end_date}}
    )

    # Get customers
    total_customers = await db.customers.count_documents({})
    new_customers = await db.customers.count_documents(
        {"lastVisit": {"$gte": start_date}}
    )

    # Calculate metrics
    revenue = sum(t.get("amount", 0) for t in transactions if t.get("type") == "income")
    expenses = sum(
        t.get("amount", 0) for t in transactions if t.get("type") == "expense"
    )
    profit = revenue - expenses

    # Get inventory value (project needed fields only)
    parts = await db.parts.find(
        {}, {"_id": 0, "purchasePrice": 1, "quantity": 1}
    ).to_list(10000)
    inventory_value = sum(
        (p.get("purchasePrice", 0) or 0) * (p.get("quantity", 0) or 0) for p in parts
    )

    # Get feedback (project needed fields only)
    feedbacks = await db.customer_feedback.find(
        {"createdAt": {"$gte": start_date}},
        {
            "_id": 0,
            "overallRating": 1,
            "wouldRecommend": 1,
            "serviceQuality": 1,
            "staffBehavior": 1,
            "pricing": 1,
        },
    ).to_list(1000)
    avg_satisfaction = (
        sum(f.get("overallRating", 0) for f in feedbacks) / len(feedbacks)
        if feedbacks
        else 0
    )

    return {
        "period": f"{days} days",
        "revenue": revenue,
        "expenses": expenses,
        "profit": profit,
        "profitMargin": (profit / revenue * 100) if revenue > 0 else 0,
        "vehiclesServiced": vehicles_count,
        "totalCustomers": total_customers,
        "newCustomers": new_customers,
        "customerSatisfaction": round(avg_satisfaction, 2),
        "inventoryValue": inventory_value,
        "cashFlow": revenue - expenses,
        "avgTicketValue": revenue / vehicles_count if vehicles_count else 0,
    }


@router.get("/ceo/alerts")
async def get_ceo_alerts():
    alerts = []

    # Check low stock
    low_stock = await db.parts.count_documents(
        {"$expr": {"$lte": ["$quantity", "$minQuantity"]}}
    )
    if low_stock > 0:
        alerts.append(
            CEOAlert(
                type="operational",
                severity="high",
                title="مخزون منخفض",
                message=f"{low_stock} قطعة غيار قليلة المخزون",
                action="/parts",
            )
        )

    # Check pending complaints
    pending_tickets = await db.tickets.count_documents(
        {"status": "open", "type": "complaint"}
    )
    if pending_tickets > 5:
        alerts.append(
            CEOAlert(
                type="customer",
                severity="high",
                title="شكاوى معلقة",
                message=f"{pending_tickets} شكوى تنتظر المعالجة",
                action="/tickets",
            )
        )

    # Check overdue vehicles
    overdue = await db.vehicles.count_documents(
        {"status": {"$ne": "ready"}, "estimatedCompletion": {"$lt": datetime.utcnow()}}
    )
    if overdue > 0:
        alerts.append(
            CEOAlert(
                type="operational",
                severity="medium",
                title="مركبات متأخرة",
                message=f"{overdue} مركبة تجاوزت الموعد المقدر",
                action="/",
            )
        )

    return alerts


@router.get("/ceo/performance")
async def get_performance_metrics():
    # Employee performance
    employees = await db.employees.find({"isActive": True}).to_list(1000)

    employee_stats = []
    for emp in employees:
        if emp["role"] == "technician":
            # Count completed vehicles
            completed = await db.vehicles.count_documents(
                {"technicianId": emp["id"], "status": "ready"}
            )
            employee_stats.append(
                {
                    "id": emp["id"],
                    "name": emp["name"],
                    "role": emp["role"],
                    "completedJobs": completed,
                }
            )

    return {"employees": employee_stats, "totalActiveEmployees": len(employees)}


# ============ Workshop Services APIs ============
@router.post("/workshop-services", response_model=WorkshopService)
async def create_service(service: WorkshopService):
    await db.workshop_services.insert_one(service.dict())
    return service


@router.get("/workshop-services", response_model=List[WorkshopService])
async def get_workshop_services(category: Optional[str] = None):
    query = {"isActive": True}
    if category:
        query["category"] = category

    services = await db.workshop_services.find(query).to_list(1000)
    return [WorkshopService(**s) for s in services]


@router.post("/service-packages", response_model=ServicePackage)
async def create_service_package(package: ServicePackage):
    await db.service_packages.insert_one(package.dict())
    return package


@router.get("/service-packages")
async def get_service_packages():
    packages = await db.service_packages.find({"isActive": True}).to_list(1000)
    return [ServicePackage(**p) for p in packages]


# ============ Customer Service & Tickets APIs ============
@router.post("/tickets", response_model=Ticket)
async def create_ticket(ticket: Ticket):
    ticket.ticketNumber = (
        f"TCK-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
    )
    await db.tickets.insert_one(ticket.dict())
    return ticket


@router.get("/tickets")
async def get_tickets(
    status: Optional[str] = None,
    type: Optional[str] = None,
    priority: Optional[str] = None,
):
    query = {}
    if status:
        query["status"] = status
    if type:
        query["type"] = type
    if priority:
        query["priority"] = priority

    tickets = await db.tickets.find(query).sort("createdAt", -1).to_list(1000)
    return [Ticket(**t) for t in tickets]


@router.get("/tickets/{ticket_id}", response_model=Ticket)
async def get_ticket(ticket_id: str):
    ticket = await db.tickets.find_one({"id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return Ticket(**ticket)


@router.post("/tickets/{ticket_id}/response")
async def add_ticket_response(ticket_id: str, response: TicketResponse):
    await db.ticket_responses.insert_one(response.dict())
    await db.tickets.update_one(
        {"id": ticket_id},
        {"$set": {"updatedAt": datetime.utcnow(), "status": "in_progress"}},
    )
    return response


@router.get("/tickets/{ticket_id}/responses")
async def get_ticket_responses(ticket_id: str):
    responses = (
        await db.ticket_responses.find({"ticketId": ticket_id})
        .sort("createdAt", 1)
        .to_list(1000)
    )
    return [TicketResponse(**r) for r in responses]


@router.put("/tickets/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: str, resolution: str, rating: Optional[int] = None):
    update_data = {
        "status": "resolved",
        "resolution": resolution,
        "resolvedAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    if rating:
        update_data["satisfactionRating"] = rating

    await db.tickets.update_one({"id": ticket_id}, {"$set": update_data})
    return {"message": "Ticket resolved"}


@router.post("/feedback", response_model=CustomerFeedback)
async def submit_feedback(feedback: CustomerFeedback):
    await db.customer_feedback.insert_one(feedback.dict())
    return feedback


@router.get("/feedback/stats")
async def get_feedback_stats():
    feedbacks = await db.customer_feedback.find().to_list(10000)

    if not feedbacks:
        return {"totalFeedbacks": 0, "averageRating": 0, "recommendationRate": 0}

    total = len(feedbacks)
    avg_rating = sum(f["overallRating"] for f in feedbacks) / total
    recommend_count = sum(1 for f in feedbacks if f["wouldRecommend"])

    return {
        "totalFeedbacks": total,
        "averageRating": round(avg_rating, 2),
        "recommendationRate": round((recommend_count / total) * 100, 1),
        "serviceQuality": round(sum(f["serviceQuality"] for f in feedbacks) / total, 2),
        "staffBehavior": round(sum(f["staffBehavior"] for f in feedbacks) / total, 2),
        "pricing": round(sum(f["pricing"] for f in feedbacks) / total, 2),
    }


# ============ FAQ APIs ============
@router.post("/faq")
async def create_faq(faq: FAQ):
    await db.faqs.insert_one(faq.dict())
    return faq


@router.get("/faq")
async def get_faqs(category: Optional[str] = None):
    query = {"isActive": True}
    if category:
        query["category"] = category


# ============ Google Integration APIs ============
@router.post("/admin/backup/drive")
async def backup_to_drive():
    try:
        google = GoogleService()
        if not google.creds:
            raise HTTPException(
                status_code=500, detail="Google credentials not configured"
            )

        # Create backup folder
        folder_id = google.create_folder(
            f"Backup_{datetime.utcnow().strftime('%Y-%m-%d')}"
        )

        # Dump collections
        collections = ["customers", "vehicles", "invoices", "transactions"]
        for col_name in collections:
            docs = await db[col_name].find({}).to_list(10000)
            # Serialize dates
            for d in docs:
                d.pop("_id", None)
                for k, v in d.items():
                    if isinstance(v, datetime):
                        d[k] = v.isoformat()

            fname = f"{col_name}.json"
            fpath = f"/tmp/{fname}"
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(docs, f, ensure_ascii=False, indent=2)

            google.upload_file(fpath, folder_id=folder_id, mime_type="application/json")
            os.remove(fpath)

        return {"status": "success", "folderId": folder_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/export/sheets")
async def export_to_sheets():
    try:
        google = GoogleService()
        if not google.creds:
            raise HTTPException(
                status_code=500, detail="Google credentials not configured"
            )

        # Create new sheet (or use existing if ID stored in settings - simplified here)
        # For now, we'll just assume we want to create a new one or append to a fixed one if we had ID
        # Since we don't have a fixed ID, let's just return a placeholder or create a new one if we added create_sheet to service
        # But GoogleService only has append. Let's assume user provided a SHEET_ID in env or we skip creation.

        sheet_id = os.environ.get("GOOGLE_SHEET_ID")
        if not sheet_id:
            raise HTTPException(
                status_code=400, detail="GOOGLE_SHEET_ID not set in .env"
            )

        invoices = (
            await db.invoices.find({}).sort("createdAt", -1).limit(100).to_list(100)
        )
        values = [["Date", "Invoice #", "Customer", "Total", "Status"]]
        for inv in invoices:
            values.append(
                [
                    inv.get("createdAt", "")[:10],
                    inv.get("invoiceNumber", ""),
                    inv.get("customerName", ""),  # Assuming joined or available
                    str(inv.get("total", 0)),
                    inv.get("status", ""),
                ]
            )

        google.append_to_sheet(sheet_id, "Sheet1!A1", values)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
