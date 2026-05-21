"""
MCP Server for Workshop Management System
Exposes Notion workshop data to AI agents via Model Context Protocol
"""

import json
import os
import sys
from datetime import datetime  # FIX: was used at line 133 without import

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("⚠️ MCP not installed. Install with: pip install 'mcp[cli]'")

from notion_service import NotionService

# Initialize services
notion_service = NotionService()

if MCP_AVAILABLE:
    # Create MCP server
    server = Server("workshop-mcp")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available workshop management tools"""
        return [
            Tool(
                name="get_customers",
                description="احصل على قائمة جميع العملاء من قاعدة المعرفة",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="search_customer",
                description="ابحث عن عميل بالاسم",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "اسم العميل للبحث"}
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="get_procedures",
                description="احصل على إجراءات الورشة حسب الفئة",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "فئة الإجراء (مثل: تشخيص، صيانة، سلامة)",
                            "enum": ["تشخيص", "صيانة", "سلامة", "كهرباء"],
                        }
                    },
                },
            ),
            Tool(
                name="create_customer",
                description="أنشئ عميل جديد في قاعدة البيانات",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "اسم العميل"},
                        "email": {"type": "string", "description": "البريد الإلكتروني"},
                        "phone": {"type": "string", "description": "رقم الهاتف"},
                        "company": {"type": "string", "description": "اسم الشركة"},
                    },
                    "required": ["name", "email", "phone"],
                },
            ),
            Tool(
                name="get_workshop_stats",
                description="احصل على إحصائيات الورشة الحالية",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Execute workshop management tools"""

        if name == "get_customers":
            customers = notion_service.get_customers()
            result = json.dumps(customers, ensure_ascii=False, indent=2)
            return [TextContent(type="text", text=result)]

        elif name == "search_customer":
            customer_name = arguments.get("name", "")
            all_customers = notion_service.get_customers()
            matching = [
                c
                for c in all_customers
                if customer_name.lower() in c.get("name", "").lower()
            ]
            result = json.dumps(matching, ensure_ascii=False, indent=2)
            return [TextContent(type="text", text=result)]

        elif name == "get_procedures":
            category = arguments.get("category")
            procedures = notion_service.get_procedures(category)
            result = json.dumps(procedures, ensure_ascii=False, indent=2)
            return [TextContent(type="text", text=result)]

        elif name == "create_customer":
            name_val = arguments.get("name")
            email = arguments.get("email")
            phone = arguments.get("phone")
            company = arguments.get("company", "")

            created = notion_service.create_customer(
                name=name_val, email=email, phone=phone, company=company
            )
            result = json.dumps(created, ensure_ascii=False, indent=2)
            return [TextContent(type="text", text=result)]

        elif name == "get_workshop_stats":
            customers = notion_service.get_customers()
            procedures = notion_service.get_procedures()

            stats = {
                "total_customers": len(customers),
                "total_procedures": len(procedures),
                "mode": "mock" if notion_service.mock_mode else "live",
                "timestamp": datetime.now().isoformat(),
            }
            result = json.dumps(stats, ensure_ascii=False, indent=2)
            return [TextContent(type="text", text=result)]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run MCP server"""
    if not MCP_AVAILABLE:
        print("❌ MCP not available. Install with: pip install 'mcp[cli]'")
        return

    print("🚀 Starting Workshop MCP Server...")
    print(
        f"📊 Mode: {'MOCK (no Notion token)' if notion_service.mock_mode else 'LIVE (Notion connected)'}"
    )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
