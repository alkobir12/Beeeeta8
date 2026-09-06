"""
Script to clear all data from MongoDB database
Run this to start fresh with empty database
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")


async def clear_all_data():
    """Clear all collections in the database"""
    mongo_url = os.environ["MONGO_URL"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ.get("DB_NAME", "workshop_db")]

    print("🗑️  Starting to clear all data...")

    # List of all collections to clear
    collections = [
        "vehicles",
        "customers",
        "technicians",
        "services",
        "parts",
        "invoices",
        "transactions",
        "appointments",
        "employees",
        "advances",
        "salary_payments",
        "loyalty_points",
        "loyalty_transactions",
        "coupons",
        "maintenance_reminders",
        "warranties",
        "warranty_claims",
        "suppliers",
        "purchase_orders",
        "products",
        "shop_orders",
        "ai_bots",
        "bot_conversations",
        "ceo_alerts",
        "business_metrics",
        "workshop_services",
        "service_packages",
        "tickets",
        "ticket_responses",
        "customer_feedback",
        "faqs",
        "chat_sessions",
    ]

    for collection_name in collections:
        try:
            result = await db[collection_name].delete_many({})
            if result.deleted_count > 0:
                print(
                    f"✅ Cleared {collection_name}: {result.deleted_count} documents deleted"
                )
            else:
                print(f"⚪ {collection_name}: already empty")
        except Exception as e:
            print(f"❌ Error clearing {collection_name}: {e}")

    print("\n✨ Database cleared successfully!")
    print("🚀 You can now start fresh with your workshop system")

    client.close()


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(ROOT_DIR))
    from core.destructive_guard import require_destructive_cli

    require_destructive_cli("clear_all_data")
    asyncio.run(clear_all_data())
