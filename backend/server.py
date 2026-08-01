from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables FIRST before any other imports
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from core.environment_guard import configure_database_environment

DATABASE_ENVIRONMENT = configure_database_environment()

from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import uuid
import json
import re

from models import (
    Vehicle,
    VehicleCreate,
    VehicleUpdate,
    Customer,
    CustomerBase,
    CustomerUpdate,
    Supplier,
    SupplierCreate,
    SupplierUpdate,
    ChatRequest,
    ChatResponse,
)

from emergentintegrations.llm.chat import LlmChat, UserMessage

# Import Arabic Quotation Builder
from arabic_quotation import create_quotation_routes
from unified_document_service import create_unified_document_routes

# Import extended routes
from routes_extended import router as extended_router, set_db as set_db_extended
from routes_templates_extended import router as templates_extended_router, set_db as set_db_templates_extended
from routes_workshop_config import router as workshop_config_router, set_db as set_db_workshop_config
from routes_approvals import router as approvals_router, set_db as set_db_approvals
from routes_accounts_extended import router as accounts_extended_router, set_db as set_db_accounts_extended
from routes_technicians import router as technicians_router
from routes_services import router as services_router
from routes_parts import router as parts_router
import app_state as _app_state
import perf_cache as _perf_cache
from routes_advanced import router as advanced_router, set_db as set_db_advanced

# Import Import Routes
from routes_import import router as import_router, set_db as set_db_import

# Import Injector Routes
from routes_injectors import router as injectors_router, set_db as set_db_injectors

# Import User Routes
from routes_users import router as users_router, set_db as set_db_users
from routes_user_layouts import router as user_layouts_router, set_db as set_db_user_layouts
from routes_parts_ocr import router as parts_ocr_router

# Import Gemini Chat Routes
from routes_gemini_chat import (
    router as gemini_chat_router,
    set_db as set_db_gemini_chat,
)
from routes_payroll import set_db as set_db_payroll

# Import Fault Knowledge Routes
from routes_fault_knowledge import router as fault_knowledge_router

# Import Templates Routes
from routes_templates import router as templates_router
from routes_document_templates import router as document_templates_router, set_db as set_db_document_templates
from routes_outbound import router as outbound_router, set_db as set_db_outbound

# Import Chart of Accounts Routes
from routes_accounts_chart import router as accounts_chart_router

# Import Advanced Analytics Routes
from routes_analytics_advanced import router as analytics_advanced_router

# Import AI Recommendations Routes
from routes_ai_recommendations import router as ai_recommendations_router

# Import Finance Routes
from routes_finance import router as finance_router, set_db as set_db_finance, build_current_visit_ar_snapshot
from routes_finance_bot import router as finance_bot_router
from routes_suppliers_extended import router as suppliers_ext_router
from routes_stitch import router as stitch_router

# Import Invoices Routes
from routes_invoices import (
    router as invoices_router,
    set_db as set_db_invoices,
    delete_invoices_by_vehicle_id,
)

from supabase_service import SupabaseService
from routes_language import router as language_router
from routes_workshop_bot import router as workshop_bot_router
from routes_cleanup import router as cleanup_router
from routes_whatsapp_bot import router as whatsapp_bot_router
from routes_smart_inventory import (
    router as smart_inventory_router,
    set_db as set_db_smart_inventory,
)

from routes_alkabeer_bot import router as alkabeer_bot_router
from routes_moltbot import router as moltbot_router
from routes_nlp_page_assistant import router as nlp_page_assistant_router, set_db as set_db_nlp_page_assistant
# Provider mode
DB_PROVIDER = os.environ.get("DB_PROVIDER", "mongo").lower()
SUPPLIERS_TABLE_AVAILABLE = True
SUPPLIERS_TABLE_AVAILABLE = True
supabase_service = SupabaseService()

# Simple file-based storage for memory mode
MEM_DIR = ROOT_DIR / "uploads"
MEM_DIR.mkdir(exist_ok=True)


def _mem_path(name: str) -> Path:
    return MEM_DIR / f"{name}.json"


def _mem_read(name: str) -> list:
    p = _mem_path(name)
    if not p.exists():
        # seed minimal datasets
        seed = []
        if name == "services":
            seed = [
                {
                    "id": str(uuid.uuid4()),
                    "name": "تغيير زيت",
                    "category": "زيوت",
                    "price": 120,
                    "duration": 30,
                    "active": True,
                },
                {
                    "id": str(uuid.uuid4()),
                    "name": "فحص كمبيوتر",
                    "category": "تشخيص",
                    "price": 150,
                    "duration": 40,
                    "active": True,
                },
            ]
        elif name == "technicians":
            seed = [
                {
                    "id": str(uuid.uuid4()),
                    "name": "فني أحمد",
                    "phone": "",
                    "specialty": "ميكانيكا",
                },
                {
                    "id": str(uuid.uuid4()),
                    "name": "فني علي",
                    "phone": "",
                    "specialty": "كهرباء",
                },
            ]
        elif name == "vehicles":
            seed = []
        elif name == "parts":
            seed = []
        with open(p, "w", encoding="utf-8") as f:
            json.dump(seed, f, ensure_ascii=False, indent=2)
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _mem_write(name: str, items: list):
    p = _mem_path(name)
    # ensure all data is JSON-serializable (e.g., convert datetime to ISO strings)
    serializable_items = []
    for item in items:
        if isinstance(item, dict):
            cleaned = {}
            for k, v in item.items():
                if hasattr(v, "isoformat"):
                    cleaned[k] = v.isoformat()
                else:
                    cleaned[k] = v
            serializable_items.append(cleaned)
        else:
            serializable_items.append(item)

    with open(p, "w", encoding="utf-8") as f:
        json.dump(serializable_items, f, ensure_ascii=False, indent=2)


def _is_suppliers_table_missing(err: Exception) -> bool:
    message = str(err)
    return "PGRST205" in message and "suppliers" in message


async def _derive_suppliers_from_parts(provider: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fallback: build supplier rows from parts.supplier values when suppliers source is empty."""
    active_provider = (provider or DB_PROVIDER or "mongo").lower()

    def _build_rows(names: List[str]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        now_utc = datetime.now(timezone.utc)
        for idx, name in enumerate(sorted(set(names))):
            clean_name = (name or "").strip()
            if not clean_name:
                continue
            stable_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"supplier::{clean_name}")
            rows.append(
                {
                    "id": f"derived-{idx}-{stable_id.hex[:12]}",
                    "name": clean_name,
                    "phone": "",
                    "contactPerson": "",
                    "email": "",
                    "address": "",
                    "city": "",
                    "category": "مستخرج من قطع الغيار",
                    "rating": 5.0,
                    "createdAt": now_utc,
                }
            )
        return rows

    try:
        if active_provider == "supabase":
            if supabase_service.client and not supabase_service.mock_mode:
                res = supabase_service.client.table("parts").select("supplier").execute()
                names = [str((row or {}).get("supplier") or "").strip() for row in (res.data or [])]
                rows = _build_rows([n for n in names if n])
                if rows:
                    return rows
            mem_parts = _mem_read("parts")
            names = [str((row or {}).get("supplier") or "").strip() for row in mem_parts]
            return _build_rows([n for n in names if n])

        if active_provider == "memory":
            mem_parts = _mem_read("parts")
            names = [str((row or {}).get("supplier") or "").strip() for row in mem_parts]
            return _build_rows([n for n in names if n])

        if db is not None:
            part_rows = await db.parts.find({}, {"_id": 0, "supplier": 1}).to_list(5000)
            names = [str((row or {}).get("supplier") or "").strip() for row in part_rows]
            return _build_rows([n for n in names if n])
    except Exception as e:
        print(f"derive suppliers from parts failed: {e}")

    return []


async def _enrich_suppliers_from_accounts(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    يُضيف الموردين الموجودين في دليل الحسابات (حسابات نوع liability باسم 'مورد - X')
    إلى قائمة الموردين الحالية — يتجنب التكرار بناءً على الاسم.
    """
    try:
        acc_rows: List[Dict[str, Any]] = []
        if DB_PROVIDER == "supabase" and supabase_service.client and not supabase_service.mock_mode:
            res = supabase_service.client.table("accounts").select("id,code,name,type").execute()
            acc_rows = res.data or []
        elif db is not None:
            acc_rows = await db.accounts.find({}, {"_id": 0, "id": 1, "code": 1, "name": 1, "type": 1}).to_list(5000)

        existing_names = {str(r.get("name") or "").strip().lower() for r in rows}
        now_utc = datetime.now(timezone.utc)
        added = []
        for acc in acc_rows:
            acc_name = str(acc.get("name") or "").strip()
            # استخراج اسم المورد من "مورد - X" أو "مورد-X"
            if acc_name.startswith("مورد - "):
                supplier_name = acc_name[len("مورد - "):].strip()
            elif acc_name.startswith("مورد-"):
                supplier_name = acc_name[len("مورد-"):].strip()
            else:
                continue
            if not supplier_name:
                continue
            if supplier_name.lower() in existing_names:
                continue
            existing_names.add(supplier_name.lower())
            stable_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"acc_supplier::{supplier_name}")
            added.append({
                "id": f"acc-{stable_id.hex[:12]}",
                "name": supplier_name,
                "phone": "",
                "contactPerson": "",
                "email": "",
                "address": "",
                "city": "",
                "category": "من دليل الحسابات",
                "rating": 5.0,
                "createdAt": now_utc,
                "accountCode": acc.get("code", ""),
            })
        return rows + added
    except Exception as e:
        print(f"_enrich_suppliers_from_accounts failed: {e}")
        return rows


def _is_suppliers_table_missing(err: Exception) -> bool:
    message = str(err)
    return "PGRST205" in message and "suppliers" in message


# MongoDB connection (always initialize for extended routes)
mongo_url = os.environ.get("MONGO_URL")
client = AsyncIOMotorClient(mongo_url) if mongo_url else None

# Important: DB name must be provided explicitly via environment in deployment
db_name = os.environ.get("DB_NAME") if client is not None else None
db = client[db_name] if (client is not None and db_name) else None

# Set database for extended and advanced routes (FIXED ORDER)
set_db_users(db)
set_db_user_layouts(db)
set_db_import(db)
set_db_injectors(db)
set_db_gemini_chat(db)
set_db_payroll(db)
set_db_extended(db)
set_db_templates_extended(db)
set_db_document_templates(db)
set_db_outbound(db)
set_db_workshop_config(db)
set_db_approvals(db)
set_db_accounts_extended(db)
_app_state.configure(db, DB_PROVIDER, supabase_service)
set_db_advanced(db)
set_db_finance(db)
set_db_invoices(db)
set_db_smart_inventory(db)
set_db_nlp_page_assistant(db)

# Initialize WhatsApp service (optional)
try:
    from whatsapp_service import WhatsAppService

    whatsapp_svc = WhatsAppService(db)
    print("✅ WhatsApp Service initialized")
except Exception as e:
    print(f"⚠️  WhatsApp Service initialization warning: {e}")

# Create upload directory
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Create the main app
app = FastAPI(title="Workshop Management API")


@app.on_event("startup")
async def initialize_quick_manager_login():
    from core import auth_store
    from auth_jwt import _get_jwt_secret

    _get_jwt_secret()
    username = os.environ.get("MANAGER_QUICK_USERNAME")
    pin = os.environ.get("MANAGER_QUICK_PIN")
    if not username or not pin or not pin.isdigit() or len(pin) != 6:
        raise RuntimeError("MANAGER_QUICK_USERNAME / MANAGER_QUICK_PIN must configure a 6-digit PIN")
    changed = await auth_store.ensure_pin(username, pin)
    if changed:
        await auth_store.audit("seed_pin", username=username, success=True, detail="configured_from_env")

# Runtime guard middleware (مراقبة وحماية خفيفة أثناء التشغيل)
from runtime_guard import runtime_guard_middleware

app.middleware("http")(runtime_guard_middleware)


# Health check endpoint for deployment readiness
@app.get("/health")
async def health_check():
    """Simple health check used by deployment platform."""
    # Optional: check DB connectivity when using Mongo
    if DB_PROVIDER == "mongo":
        try:
            if client is None or db is None:
                return {"status": "degraded", "db": "not_configured"}
            # Use a lightweight ping command
            await db.command("ping")
            return {"status": "ok", "db": "connected"}
        except Exception as e:
            # Do not crash app on health check failure – just report degraded state
            return {"status": "degraded", "db": "error", "detail": str(e)[:200]}
    # For other providers (supabase/memory), just return ok
    return {"status": "ok"}


@app.get("/api/health")
async def api_health_check():
    return await health_check()


# Add validation error handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    import logging

    logging.error(f"Validation Error: {exc.errors()}")
    # Don't log full request body to avoid leaking sensitive data into logs.
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

# NOTE (Security): This codebase can be hardened further (rate limiting, auth, CSP). No app can be 100% vulnerability-free.



# Enable CORS for frontend access
# Configure via env to support custom domains + emergent host during deployment.
cors_origins_raw = os.environ.get(
    "CORS_ORIGINS",
    "https://fixsa.online,https://www.fixsa.online,http://localhost:3000",
)
allow_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]


def _credentialed_cors_origin(origin: Optional[str]) -> Optional[str]:
    if not origin:
        return None
    if origin in allow_origins:
        return origin
    if "*" in allow_origins:
        return origin
    return None

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def enforce_credentialed_cors(request, call_next):
    response = await call_next(request)
    origin = _credentialed_cors_origin(request.headers.get("origin"))
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response


# --------------------- Basic Security Hardening Middleware ---------------------
# NOTE: This is a lightweight in-memory limiter (single-process). It is designed to
# reduce abuse for low-volume deployments. For stronger protection, use Cloudflare WAF/Rate Limiting.
from time import time
from fastapi import Request

_RATE_STATE = {}  # (ip, bucket, window) -> count
_RATE_STATE_MAX = 10000  # FIX-B011: bound memory growth
# secret-gated bypass so automated test suites aren't throttled (header x-ratelimit-bypass)
_RATE_BYPASS_TOKEN = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip()


def _get_client_ip(request: Request) -> str:
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return (request.client.host if request.client else "unknown")


def _rate_bucket(path: str, method: str):
    """Return (bucket_name, limit_per_minute) or None if not rate-limited."""
    if method == "OPTIONS":
        return None
    if not path.startswith("/api"):
        return None

    if path.startswith("/api/import/"):
        return ("import", 6)
    if path.startswith("/api/auth/"):
        return ("auth", 30)
    if path.startswith("/api/ai/") or path.startswith("/api/finance-bot/"):
        return ("ai", 30)
    if path.startswith("/api/approvals"):
        if path.startswith("/api/approvals/public/") and method == "GET":
            return ("approvals_public", 120)
        return ("approvals", 30)

    return ("api", 240)


from starlette.datastructures import MutableHeaders
from auth_guard import authenticate as _auth_authenticate


class SecurityHeadersAndRateLimitMiddleware:
    """Pure-ASGI security headers + lightweight in-memory rate limiter.

    Replaces the previous BaseHTTPMiddleware (`@app.middleware('http')`) which
    raised h11 `LocalProtocolError: Can't send data when our state is ERROR`
    (surfacing as intermittent 502s) whenever a client disconnected mid-response
    — e.g. rapid SPA navigation cancelling in-flight requests. A pure-ASGI
    middleware tolerates client disconnects cleanly and never buffers responses.
    """

    def __init__(self, app):
        self.app = app

    @staticmethod
    def _headers(scope) -> dict:
        return {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}

    @classmethod
    def _client_ip(cls, scope, headers) -> str:
        cf_ip = headers.get("cf-connecting-ip")
        if cf_ip:
            return cf_ip.strip()
        xff = headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        client = scope.get("client")
        return client[0] if client else "unknown"

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")
        headers_in = self._headers(scope)
        origin = headers_in.get("origin")

        def _send_json(status_code: int, payload: dict):
            import json as _json

            async def _do(send_):
                body = _json.dumps(payload).encode("utf-8")
                out_headers = [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("latin-1")),
                ]
                cors_origin = _credentialed_cors_origin(origin)
                if cors_origin:
                    out_headers.append((b"access-control-allow-origin", cors_origin.encode("latin-1")))
                    out_headers.append((b"access-control-allow-credentials", b"true"))
                    out_headers.append((b"vary", b"Origin"))
                await send_({"type": "http.response.start", "status": status_code, "headers": out_headers})
                await send_({"type": "http.response.body", "body": body})
            return _do

        # ── 1) Rate limiting ─────────────────────────────────────────────
        bucket = _rate_bucket(path, method)
        if _RATE_BYPASS_TOKEN and headers_in.get("x-ratelimit-bypass") == _RATE_BYPASS_TOKEN:
            bucket = None
        if bucket is not None:
            bucket_name, limit = bucket
            ip = self._client_ip(scope, headers_in)
            window = int(time() // 60)
            key = (ip, bucket_name, window)
            if len(_RATE_STATE) > _RATE_STATE_MAX:
                _RATE_STATE.clear()
            count = _RATE_STATE.get(key, 0) + 1
            _RATE_STATE[key] = count
            if count > limit:
                await _send_json(429, {"success": False, "error": "Rate limit exceeded. Please try again shortly."})(send)
                return

        # ── 2) Auth guard — يفرض JWT على كل /api/* عدا القائمة البيضاء ────
        auth_result = _auth_authenticate(path, method, headers_in)
        if auth_result is None:
            await _send_json(401, {"success": False, "error": "Not authenticated", "detail": "Not authenticated"})(send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                cors_origin = _credentialed_cors_origin(origin)
                if cors_origin:
                    headers["Access-Control-Allow-Origin"] = cors_origin
                    headers["Access-Control-Allow-Credentials"] = "true"
                    headers.setdefault("Vary", "Origin")
                elif origin:
                    if "access-control-allow-credentials" in headers:
                        del headers["access-control-allow-credentials"]
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-XSS-Protection", "1; mode=block")
                headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
                headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
                headers.setdefault(
                    "Permissions-Policy",
                    "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
                )
            await send(message)

        await self.app(scope, receive, send_wrapper)


app.add_middleware(SecurityHeadersAndRateLimitMiddleware)

# ============ Settings: simple JSON-based global settings ============

SETTINGS_FILE = ROOT_DIR / "uploads" / "settings.json"


def read_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def write_settings(data: dict):
    SETTINGS_FILE.parent.mkdir(exist_ok=True, parents=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# Include Routers
from auth_jwt import router as auth_router
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(user_layouts_router)
app.include_router(injectors_router)
app.include_router(import_router)
app.include_router(gemini_chat_router)
app.include_router(fault_knowledge_router)
app.include_router(templates_router)
app.include_router(document_templates_router)
app.include_router(accounts_chart_router)
app.include_router(analytics_advanced_router)
app.include_router(ai_recommendations_router)
# Temporarily disable payroll router - needs Supabase implementation
# app.include_router(payroll_router)
app.include_router(language_router)
app.include_router(workshop_bot_router)
app.include_router(parts_ocr_router)
app.include_router(cleanup_router)
app.include_router(whatsapp_bot_router)
app.include_router(smart_inventory_router)
app.include_router(extended_router)
app.include_router(templates_extended_router)
app.include_router(outbound_router)
app.include_router(workshop_config_router)
app.include_router(approvals_router)
app.include_router(accounts_extended_router)
app.include_router(technicians_router)
app.include_router(services_router)
app.include_router(parts_router)
app.include_router(advanced_router)
app.include_router(finance_router)
app.include_router(finance_bot_router)
app.include_router(suppliers_ext_router)
from routes_smart_accounting import router as smart_accounting_router
app.include_router(smart_accounting_router)
app.include_router(stitch_router)
app.include_router(invoices_router)
app.include_router(alkabeer_bot_router)
app.include_router(moltbot_router)
app.include_router(nlp_page_assistant_router)
from routes_firewall import router as firewall_router
app.include_router(firewall_router)
from routes_assistant import router as assistant_router, limiter as assistant_limiter
app.include_router(assistant_router)

# 🔬 llm_traces — المرحلة 2 من بروتوكول التشريح (شرط Katrina Verification Suite)
from routes_traces import router as traces_router
app.include_router(traces_router)

# 🆕 Phase 3C — Action Runtime (Approval Matrix + Commit + Rollback)
from routes_action_runtime import router as action_runtime_router
app.include_router(action_runtime_router)

from routes_financial_actions import router as financial_actions_router
app.include_router(financial_actions_router)

# 🆕 مركز الرقابة المالية (findings + approvals matrix + four-eyes)
from financial_control.router import router as financial_control_router, set_db as set_db_financial_control
set_db_financial_control(db)
app.include_router(financial_control_router)

# 🆕 Phase 3A — register slowapi limiter so @limiter.limit() actually fires.
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
app.state.limiter = assistant_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Unified document generation routes (documents/generate, documents/generate-html, documents/types)
# Arabic quotation (quotations/generate, quotations/themes)
create_quotation_routes(api_router)

create_unified_document_routes(api_router)

# ============ Invoice Studio Integration ============
try:
    static_path = ROOT_DIR.parent / "frontend" / "public" / "invoice-studio"
    if static_path.exists():
        app.mount(
            "/invoice-studio",
            StaticFiles(directory=str(static_path), html=True),
            name="invoice-studio",
        )
except Exception as e:
    print(f"❌ Error mounting Invoice Studio: {e}")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============ Helper Functions ============
def generate_tracking_link():
    return f"TRK-{str(uuid.uuid4())[:8].upper()}"


def generate_invoice_number():
    prefix = "INV"
    return (
        f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
    )


async def get_or_create_customer(name: str, phone: str, email: Optional[str] = None):
    if DB_PROVIDER == "supabase":
        c = supabase_service.customers_find_by_phone(phone)
        if c:
            return c["id"]
        new_c = supabase_service.customers_create(
            {
                "name": name,
                "phone": phone,
                "email": email,
                "totalVisits": 1,
                "lastVisit": datetime.utcnow().isoformat(),
            }
        )
        return new_c["id"]

    if DB_PROVIDER == "memory":
        rows = _mem_read("customers")
        for r in rows:
            if r.get("phone") == phone:
                return r["id"]
        new_c = {
            "id": str(uuid.uuid4()),
            "name": name,
            "phone": phone,
            "email": email,
            "totalVisits": 1,
            "lastVisit": datetime.utcnow().isoformat(),
            "createdAt": datetime.utcnow().isoformat(),
            "vehicles": [],
        }
        rows.append(new_c)
        _mem_write("customers", rows)
        return new_c["id"]

    customer = await db.customers.find_one({"phone": phone})
    if customer:
        return customer["id"]

    new_customer = Customer(
        name=name, phone=phone, email=email, totalVisits=1, lastVisit=datetime.utcnow()
    )
    await db.customers.insert_one(new_customer.dict())
    return new_customer.id


# ============ Base API Routes (Vehicles, Customers, etc) ============


@api_router.post("/vehicles", response_model=Vehicle)
async def create_vehicle(vehicle_data: VehicleCreate):
    try:
        customer_id = await get_or_create_customer(
            vehicle_data.customerName,
            vehicle_data.customerPhone,
            vehicle_data.customerEmail,
        )

        vehicle_dict = {
            **vehicle_data.dict(),
            "id": str(uuid.uuid4()),
            "customerId": customer_id,
            "trackingLink": generate_tracking_link(),
            "estimatedCompletion": (datetime.utcnow() + timedelta(days=2)).isoformat(),
            "entryDate": datetime.utcnow().isoformat(),
        }
        customer_file_map = await _get_customer_file_number_map([customer_id])
        linked_customer_file = customer_file_map.get(customer_id)
        vehicle_dict["customerFileNumber"] = linked_customer_file or None

        if DB_PROVIDER == "supabase":
            # supabase_service expects camelCase dict
            v_res = supabase_service.vehicles_create(vehicle_dict)
            v_res["customerFileNumber"] = linked_customer_file or None
            return Vehicle(**v_res)

        if DB_PROVIDER == "memory":
            rows = _mem_read("vehicles")
            rows.append(vehicle_dict)
            _mem_write("vehicles", rows)
            return Vehicle(**vehicle_dict)

        await db.vehicles.insert_one(vehicle_dict)
        return Vehicle(**vehicle_dict)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/vehicles", response_model=List[Vehicle])
async def get_vehicles():
    if DB_PROVIDER == "supabase":
        rows = supabase_service.vehicles_list()
        rows = await _attach_customer_file_numbers_to_vehicles(rows)
        # Ensure status has a default value if None
        for r in rows:
            if r.get("status") is None:
                r["status"] = "diagnosis"
            # مركبات كاترينا قد لا تحمل سنة عند إنشائها. نموذج الاستجابة يتطلب
            # عدداً صحيحاً، لذلك نطبع القيمة الناقصة بدلاً من إسقاط لوحة التحكم.
            if r.get("year") is None:
                r["year"] = 0
        return [Vehicle(**r) for r in rows]

    if DB_PROVIDER == "memory":
        rows = _mem_read("vehicles")
        rows = await _attach_customer_file_numbers_to_vehicles(rows)
        # Ensure status has a default value if None
        for r in rows:
            if r.get("status") is None:
                r["status"] = "diagnosis"
            if r.get("year") is None:
                r["year"] = 0
        return [Vehicle(**r) for r in rows]

    # استخدام Projection وحد للحفاظ على الأداء في الإنتاج
    vehicles = (
        await db.vehicles.find({}, {"_id": 0})
        .sort("entryDate", -1)
        .limit(200)
        .to_list(200)
    )
    vehicles = await _attach_customer_file_numbers_to_vehicles(vehicles)
    # Ensure status has a default value if None and calculate estimatedTotal
    for v in vehicles:
        if v.get("status") is None:
            v["status"] = "diagnosis"
        
        # Calculate estimatedTotal from parts/services
        estimated_total = 0
        if v.get("parts") and isinstance(v.get("parts"), list):
            for part in v["parts"]:
                if isinstance(part, dict):
                    # Sum up price * quantity for each part
                    price = part.get("price", 0) or 0
                    quantity = part.get("quantity", 1) or 1
                    estimated_total += price * quantity
        
        v["estimatedTotal"] = estimated_total
    
    return [Vehicle(**v) for v in vehicles]


@api_router.get("/vehicles/{vehicle_id}", response_model=Vehicle)
async def get_vehicle(vehicle_id: str):
    if DB_PROVIDER == "supabase":
        v = supabase_service.vehicles_get(vehicle_id)
        if not v:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        patched = await _attach_customer_file_numbers_to_vehicles([v])
        v = patched[0] if patched else v
        v["status"] = v.get("status") or "diagnosis"
        v["year"] = v.get("year") if v.get("year") is not None else 0
        return Vehicle(**v)

    if DB_PROVIDER == "memory":
        rows = _mem_read("vehicles")
        for r in rows:
            if r.get("id") == vehicle_id:
                patched = await _attach_customer_file_numbers_to_vehicles([r])
                r = patched[0] if patched else r
                r["status"] = r.get("status") or "diagnosis"
                r["year"] = r.get("year") if r.get("year") is not None else 0
                return Vehicle(**r)
        raise HTTPException(status_code=404, detail="Vehicle not found")

    vehicle = await db.vehicles.find_one({"id": vehicle_id})
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    patched = await _attach_customer_file_numbers_to_vehicles([vehicle])
    vehicle = patched[0] if patched else vehicle
    vehicle["status"] = vehicle.get("status") or "diagnosis"
    vehicle["year"] = vehicle.get("year") if vehicle.get("year") is not None else 0
    return Vehicle(**vehicle)


async def settle_vehicle_credit_operations(vehicle_id: str):
    if DB_PROVIDER != "supabase":
        return
    if not supabase_service.client or supabase_service.mock_mode:
        return

    try:
        ops_res = (
            supabase_service.client.table("operations")
            .select("id, total_amount, amount, total, workshop_id, payment_method")
            .eq("vehicle_id", vehicle_id)
            .eq("payment_method", "credit")
            .execute()
        )
        operations = ops_res.data or []
    except Exception:
        return

    for op in operations:
        amount = float(op.get("total_amount") or op.get("amount") or op.get("total") or 0)
        if amount <= 0:
            continue

        try:
            exists = (
                supabase_service.client.table("journal_entries")
                .select("id")
                .eq("operation_id", op.get("id"))
                .eq("status", "paid")
                .limit(1)
                .execute()
            )
            if exists.data:
                continue
        except Exception:
            pass

        entry = {
            "id": str(uuid.uuid4()),
            "workshop_id": op.get("workshop_id"),
            "entry_date": datetime.utcnow().isoformat(),
            "description": f"تحصيل دفعة للفاتورة {op.get('id')}",
            "total_debit": amount,
            "total_credit": amount,
            "lines": [
                {
                    "account": "1101",
                    "account_name": "الصندوق",
                    "debit": amount,
                    "credit": 0,
                },
                {
                    "account": "1103",
                    "account_name": "العملاء (ذمم مدينة)",
                    "debit": 0,
                    "credit": amount,
                },
            ],
            "status": "paid",
            "operation_id": op.get("id"),
        }

        try:
            from core import accounting_engine
            accounting_engine.post_entry(entry)
            supabase_service.client.table("operations").update({"payment_method": "cash"}).eq("id", op.get("id")).execute()
        except Exception:
            continue


@api_router.put("/vehicles/{vehicle_id}", response_model=Vehicle)
async def update_vehicle(vehicle_id: str, update_data: VehicleUpdate):
    raw_update = update_data.dict(exclude_unset=True)
    customer_file_present = "customerFileNumber" in raw_update
    customer_file_value = raw_update.pop("customerFileNumber", None) if customer_file_present else None
    upd = {k: v for k, v in raw_update.items() if v is not None}

    if DB_PROVIDER == "supabase":
        existing_vehicle = supabase_service.vehicles_get(vehicle_id)
        if not existing_vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        v = supabase_service.vehicles_update(vehicle_id, upd) if upd else existing_vehicle
        if not v:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        customer_id = str(v.get("customerId") or existing_vehicle.get("customerId") or "").strip()
        if customer_file_present and customer_id:
            await _set_customer_file_number(customer_id, customer_file_value)

        if upd.get("status") == "delivered":
            await settle_vehicle_credit_operations(vehicle_id)

        patched_rows = await _attach_customer_file_numbers_to_vehicles([v])
        patched = patched_rows[0] if patched_rows else v
        return Vehicle(**patched)

    if DB_PROVIDER == "memory":
        rows = _mem_read("vehicles")
        for i, r in enumerate(rows):
            if r.get("id") == vehicle_id:
                # handle dates
                if "estimatedCompletion" in upd and isinstance(
                    upd["estimatedCompletion"], datetime
                ):
                    upd["estimatedCompletion"] = upd["estimatedCompletion"].isoformat()
                if "completionDate" in upd and isinstance(
                    upd["completionDate"], datetime
                ):
                    upd["completionDate"] = upd["completionDate"].isoformat()

                rows[i] = {**r, **upd}
                customer_id = str(rows[i].get("customerId") or "").strip()
                if customer_file_present and customer_id:
                    await _set_customer_file_number(customer_id, customer_file_value)
                rows = await _attach_customer_file_numbers_to_vehicles(rows)
                _mem_write("vehicles", rows)
                return Vehicle(**rows[i])
        raise HTTPException(status_code=404, detail="Vehicle not found")

    vehicle_before = await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0})
    if not vehicle_before:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    if upd:
        await db.vehicles.update_one({"id": vehicle_id}, {"$set": upd})

    vehicle = await db.vehicles.find_one({"id": vehicle_id})
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    customer_id = str(vehicle.get("customerId") or vehicle_before.get("customerId") or "").strip()
    if customer_file_present and customer_id:
        await _set_customer_file_number(customer_id, customer_file_value)

    vehicle.pop("_id", None)
    patched_rows = await _attach_customer_file_numbers_to_vehicles([vehicle])
    patched = patched_rows[0] if patched_rows else vehicle
    return Vehicle(**patched)



@api_router.post("/vehicles/{vehicle_id}/save-parts-and-create-journal")
async def save_vehicle_parts_and_create_journal(
    vehicle_id: str,
    parts: List[dict],
    request: Request,
):
    """
    حفظ بنود المركبة + إنشاء قيد محاسبي + إنشاء فاتورة مفتوحة
    """
    # 🔐 SEC-002: هذه النقطة تُنشئ عملية+قيد+فاتورة مباشرةً (تتجاوز الأربع أعين) —
    # تتطلب صلاحية كتابة مالية صريحة. بلا توكن ⇒ 401، دور غير مخوّل ⇒ 403.
    from core import rbac
    ident = rbac.extract_identity(request)
    if not ident.get("user_id"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    actor = await rbac.resolve_actor(
        user_id=ident["user_id"], name=ident["name"], role_hint=ident["role_hint"]
    )
    allowed = rbac.check_permission(actor, "invoices", "create")
    if not allowed.allowed:
        allowed = rbac.check_permission(actor, "journal_entries", "create")
    rbac.require(allowed)
    try:
        workshop_id = os.getenv("REACT_APP_WORKSHOP_ID", "workshop-1")
        
        # 1. حساب المجموع
        total = sum(item.get('price', 0) * item.get('quantity', 1) for item in parts)
        
        if total <= 0:
            raise HTTPException(status_code=400, detail="المجموع يجب أن يكون أكبر من صفر")
        
        # 2. تحديث بنود المركبة
        upd = {"parts": parts}
        
        if DB_PROVIDER == "supabase":
            vehicle = supabase_service.vehicles_update(vehicle_id, upd)
            if not vehicle:
                raise HTTPException(status_code=404, detail="Vehicle not found")
        elif DB_PROVIDER == "memory":
            rows = _mem_read("vehicles")
            vehicle = None
            for i, r in enumerate(rows):
                if r.get("id") == vehicle_id:
                    rows[i] = {**r, **upd}
                    _mem_write("vehicles", rows)
                    vehicle = rows[i]
                    break
            if not vehicle:
                raise HTTPException(status_code=404, detail="Vehicle not found")
        else:
            await db.vehicles.update_one({"id": vehicle_id}, {"$set": upd})
            vehicle = await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0})
        
        # 3. إنشاء عملية (operation) في Supabase لتظهر في التقارير
        operation_id = str(uuid.uuid4())
        operation_data = {
            "id": operation_id,
            "workshop_id": workshop_id,
            "type": "sale",
            "vehicle_id": vehicle_id,
            "partner_name": vehicle.get('customerName', ''),
            "items": parts,
            "total": total,
            "payment_method": "credit",  # آجل لأنه لم يُدفع بعد
            "op_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # حفظ العملية
        if DB_PROVIDER == "supabase":
            try:
                supabase_service.client.table("operations").insert(operation_data).execute()
                print("✅ Operation created in Supabase")
            except Exception as e:
                print(f"Failed to create operation in Supabase: {e}")
        
        if db:
            try:
                await db.operations.insert_one(operation_data)
                print("✅ Operation created in MongoDB")
            except Exception as e:
                print(f"Failed to create operation in MongoDB: {e}")
        
        # 4. إنشاء قيد محاسبي تلقائي
        journal_entry = {
            "id": str(uuid.uuid4()),
            "workshop_id": workshop_id,
            "date": datetime.now(timezone.utc).isoformat(),
            "description": f"إضافة بنود للمركبة {vehicle.get('plateNumber', vehicle_id)}",
            "lines": [
                {
                    "account": "1103",
                    "account_name": "ذمم مدينة عملاء",
                    "debit": total,
                    "credit": 0
                },
                {
                    "account": "4000",
                    "account_name": "الإيرادات",
                    "debit": 0,
                    "credit": total
                }
            ],
            "total": total,
            "source": "operation",
            "transaction_type": "sale",
            "reference_id": operation_id
        }
        
        # حفظ القيد
        # حفظ في Supabase
        if DB_PROVIDER == "supabase":
            try:
                from core import accounting_engine
                accounting_engine.post_entry(journal_entry)
                print("✅ Journal entry saved to Supabase")
            except Exception as e:
                print(f"Failed to save journal entry to Supabase: {e}")
        
        # حفظ في MongoDB إذا كان متاحاً
        if db:
            try:
                await db.journal_entries.insert_one(journal_entry)
                print("✅ Journal entry saved to MongoDB")
            except Exception as e:
                print(f"Failed to save journal entry to MongoDB: {e}")
        
        # 5. إنشاء فاتورة مفتوحة أو تحديث الموجودة
        invoice_id = None
        
        # التحقق من وجود فاتورة مفتوحة
        if DB_PROVIDER == "supabase":
            try:
                existing_invoices = supabase_service.client.table("invoices")\
                    .select("*")\
                    .eq("vehicle_id", vehicle_id)\
                    .neq("status", "paid")\
                    .neq("status", "cancelled")\
                    .execute()
                
                if existing_invoices.data and len(existing_invoices.data) > 0:
                    # تحديث الفاتورة الموجودة
                    invoice = existing_invoices.data[0]
                    invoice_id = invoice['id']
                    
                    updated_items = invoice.get('items', []) + parts
                    new_total = sum(item.get('price', 0) * item.get('quantity', 1) for item in updated_items)
                    
                    supabase_service.client.table("invoices").update({
                        "items": updated_items,
                        "subtotal": new_total,
                        "tax": new_total * 0.15,
                        "total": new_total * 1.15
                    }).eq("id", invoice_id).execute()
                    
                    print(f"✅ Updated existing invoice: {invoice_id}")
                else:
                    # إنشاء فاتورة جديدة
                    invoice_id = str(uuid.uuid4())
                    new_invoice = {
                        "id": invoice_id,
                        "vehicle_id": vehicle_id,
                        "customer_name": vehicle.get('customerName', ''),
                        "customer_phone": vehicle.get('customerPhone', ''),
                        "items": parts,
                        "subtotal": total,
                        "tax": total * 0.15,
                        "total": total * 1.15,
                        "status": "draft",
                        "issue_date": datetime.now(timezone.utc).isoformat(),
                        "due_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
                    }
                    supabase_service.client.table("invoices").insert(new_invoice).execute()
                    print(f"✅ Created new invoice: {invoice_id}")
            except Exception as e:
                print(f"Invoice creation/update in Supabase failed: {e}")
                invoice_id = None
        
        return {
            "success": True,
            "message": "تم حفظ البنود وإنشاء العملية والقيد والفاتورة بنجاح",
            "vehicle": vehicle,
            "operation_id": operation_id,
            "journal_entry_id": journal_entry['id'],
            "invoice_id": invoice_id,
            "total": total
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في حفظ البنود: {str(e)}")



# ============ Print & Quote Settings API ============


@api_router.get("/settings")
async def get_settings():
    """إرجاع إعدادات الورشة/الطباعة المخزنة في ملف JSON بسيط.
    ملاحظة: هذا مسار عام يمكن توسيعه لاحقًا لدمج إعدادات أخرى.
    """
    data = read_settings()
    return data


@api_router.post("/settings/print-defaults")
async def save_print_defaults(payload: dict):
    """حفظ الإعدادات الافتراضية للطباعة وعروض الأسعار (theme/style/tax_rate)."""
    data = read_settings()
    data.setdefault("printDefaults", {})
    data["printDefaults"]["theme"] = payload.get("theme")
    data["printDefaults"]["style"] = payload.get("style")
    data["printDefaults"]["tax_rate"] = payload.get("tax_rate")
    write_settings(data)
    return {"success": True, "printDefaults": data["printDefaults"]}


@api_router.delete("/vehicles/{vehicle_id}")
async def delete_vehicle(vehicle_id: str):
    """Delete a vehicle and its related invoices and operations."""
    # Supabase mode
    if DB_PROVIDER == "supabase":
        try:
            # Delete invoices linked to this vehicle (if invoices table exists)
            if (
                hasattr(supabase_service, "client")
                and supabase_service.client
                and not supabase_service.mock_mode
            ):
                try:
                    supabase_service.client.table("invoices").delete().eq(
                        "vehicle_id", vehicle_id
                    ).execute()
                except Exception as invoice_error:
                    # Invoices table might not exist - this is acceptable
                    print(
                        f"⚠️ Could not delete invoices for vehicle {vehicle_id}: {invoice_error}"
                    )

                # Delete operations linked to this vehicle
                try:
                    supabase_service.client.table("operations").delete().eq(
                        "vehicleId", vehicle_id
                    ).execute()
                except Exception as ops_error:
                    print(
                        f"⚠️ Could not delete operations for vehicle {vehicle_id}: {ops_error}"
                    )
            supabase_service.vehicles_delete(vehicle_id)

            # تنظيف فواتير الملفات المرتبطة بهذه المركبة (نظام الفواتير القائم على الملفات)
            try:
                delete_invoices_by_vehicle_id(vehicle_id)
            except Exception as cleanup_err:
                print(
                    f"⚠️ File-based invoice cleanup failed for vehicle {vehicle_id}: {cleanup_err}"
                )

            return {"success": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # In-memory mode
    if DB_PROVIDER == "memory":
        rows = _mem_read("vehicles")
        rows = [r for r in rows if r.get("id") != vehicle_id]
        _mem_write("vehicles", rows)

        # Delete operations for this vehicle
        ops = _mem_read("operations")
        ops = [op for op in ops if op.get("vehicleId") != vehicle_id]
        _mem_write("operations", ops)

        return {"success": True}

    # MongoDB mode (legacy)
    # حذف الفواتير من مجموعة MongoDB (إن وجدت)
    try:
        await db.invoices.delete_many({"vehicleId": vehicle_id})
    except Exception:
        pass

    # حذف العمليات المرتبطة
    try:
        await db.operations.delete_many({"vehicleId": vehicle_id})
    except Exception:
        pass

    # حذف سجل المركبة
    await db.vehicles.delete_one({"id": vehicle_id})

    # تنظيف فواتير الملفات لنفس المركبة في أي وضع غير Supabase
    try:
        delete_invoices_by_vehicle_id(vehicle_id)
    except Exception as cleanup_err:
        print(
            f"⚠️ File-based invoice cleanup failed for vehicle {vehicle_id}: {cleanup_err}"
        )

    return {"success": True}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _normalize_partner_name(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _parse_json_like(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _op_field(row: Dict[str, Any], snake: str, camel: str) -> Any:
    return row.get(snake) if row.get(snake) is not None else row.get(camel)


def _partner_summary_template() -> Dict[str, Any]:
    return {
        "debitBalance": 0.0,
        "creditBalance": 0.0,
        "overdueBalance": 0.0,
        "ajelBalance": 0.0,
        "settledAmount": 0.0,
        "paymentPlanCount": 0,
        "movements": [],
        "balance": 0.0,
        "netBalance": 0.0,
    }


def _append_partner_movement(summary: Dict[str, Any], movement: Dict[str, Any]):
    if not movement:
        return
    summary.setdefault("movements", []).append(movement)


async def _fetch_operations_for_partner_financials(
    workshop_id: Optional[str],
) -> List[Dict[str, Any]]:
    # 🚀 TTL cache (15s) — partner financials are read-heavy & expensive
    cache_key = workshop_id or "_"
    cached = _perf_cache.get_cached("ops_for_partner_fin", cache_key)
    if cached is not None:
        return cached

    rows = await _fetch_operations_for_partner_financials_uncached(workshop_id)
    _perf_cache.set_cached("ops_for_partner_fin", rows, cache_key)
    return rows


async def _fetch_operations_for_partner_financials_uncached(
    workshop_id: Optional[str],
) -> List[Dict[str, Any]]:
    if DB_PROVIDER == "supabase":
        if not (supabase_service.client and not supabase_service.mock_mode):
            return []

        select_expr = (
            "id,type,partner_type,partner_id,partner_name,total,payment_method,payment_status,"
            "payment_amount,op_date,created_at,notes,workshop_id,vehicle_id,visit_id"
        )

        def _exec_query(expr: str, with_workshop_filter: bool) -> List[Dict[str, Any]]:
            q = supabase_service.client.table("operations").select(expr).order("created_at", desc=True)
            if workshop_id and with_workshop_filter:
                q = q.eq("workshop_id", workshop_id)
            return q.execute().data or []

        try:
            return _exec_query(select_expr, with_workshop_filter=True)
        except Exception as e:
            error_text = str(e).lower()
            try:
                if workshop_id and "workshop_id" in error_text:
                    return _exec_query(select_expr, with_workshop_filter=False)
            except Exception as second_error:
                error_text = str(second_error).lower()

            if "does not exist" in error_text or "column" in error_text:
                try:
                    return _exec_query("*", with_workshop_filter=True)
                except Exception as fallback_error:
                    fallback_text = str(fallback_error).lower()
                    if workshop_id and "workshop_id" in fallback_text:
                        try:
                            return _exec_query("*", with_workshop_filter=False)
                        except Exception as final_error:
                            print(f"Partner financial fallback query failed: {final_error}")
                            return []
                    print(f"Partner financial fallback query failed: {fallback_error}")
                    return []

            print(f"Partner financial operations query failed: {e}")
            return []

    if DB_PROVIDER == "memory":
        rows = _mem_read("operations")
        if workshop_id:
            rows = [
                r
                for r in rows
                if str(r.get("workshopId") or r.get("workshop_id") or "") == str(workshop_id)
            ]
        return rows

    if db is None:
        return []

    query: Dict[str, Any] = {}
    if workshop_id:
        query["$or"] = [{"workshopId": workshop_id}, {"workshop_id": workshop_id}]
    projection = {
        "_id": 0,
        "id": 1,
        "type": 1,
        "partnerType": 1,
        "partner_type": 1,
        "partnerId": 1,
        "partner_id": 1,
        "partnerName": 1,
        "partner_name": 1,
        "total": 1,
        "paymentMethod": 1,
        "payment_method": 1,
        "paymentStatus": 1,
        "payment_status": 1,
        "paymentAmount": 1,
        "payment_amount": 1,
        "vehicleId": 1,
        "vehicle_id": 1,
        "visitId": 1,
        "visit_id": 1,
        "date": 1,
        "op_date": 1,
        "createdAt": 1,
        "created_at": 1,
        "notes": 1,
    }
    return await db.operations.find(query, projection).to_list(5000)


async def _resolved_live_vehicle_ids_for_current_scope(workshop_id: Optional[str]) -> set:
    ids = set()
    if DB_PROVIDER != "supabase" or not (supabase_service.client and not supabase_service.mock_mode):
        return ids
    try:
        rows = []
        if workshop_id:
            try:
                rows = supabase_service.client.table("vehicles").select("id,status").eq("workshop_id", workshop_id).execute().data or []
            except Exception:
                rows = []
        if not rows:
            rows = supabase_service.client.table("vehicles").select("id,status").execute().data or []
        for row in rows:
            vehicle_id = str(row.get("id") or "").strip()
            status = str(row.get("status") or "").strip().lower()
            if vehicle_id and status != "delivered":
                ids.add(vehicle_id)
    except Exception as exc:
        print(f"partner live vehicle scope lookup failed: {exc}")
    return ids


async def _filter_partner_operations_to_current_scope(rows: List[Dict[str, Any]], workshop_id: Optional[str]) -> List[Dict[str, Any]]:
    live_ids = await _resolved_live_vehicle_ids_for_current_scope(workshop_id)
    if not live_ids:
        return rows
    filtered = []
    for row in rows or []:
        vehicle_id = str(_op_field(row, "vehicle_id", "vehicleId") or "").strip()
        if not vehicle_id or vehicle_id in live_ids:
            filtered.append(row)
    return filtered


async def _fetch_operation_payment_map(
    workshop_id: Optional[str],
) -> Dict[str, List[Dict[str, Any]]]:
    # 🚀 TTL cache (15s) — journal_entries scan is expensive
    cache_key = workshop_id or "_"
    cached = _perf_cache.get_cached("op_payment_map", cache_key)
    if cached is not None:
        return cached
    result = await _fetch_operation_payment_map_uncached(workshop_id)
    _perf_cache.set_cached("op_payment_map", result, cache_key)
    return result


async def _fetch_operation_payment_map_uncached(
    workshop_id: Optional[str],
) -> Dict[str, List[Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = []

    if DB_PROVIDER == "supabase":
        if supabase_service.client and not supabase_service.mock_mode:
            try:
                q = (
                    supabase_service.client.table("journal_entries")
                    .select("id,reference_id,total,date,description,source,workshop_id")
                    .eq("source", "operation_payment")
                )
                if workshop_id:
                    q = q.eq("workshop_id", workshop_id)
                rows = q.execute().data or []
            except Exception as e:
                if workshop_id and "workshop_id" in str(e).lower():
                    try:
                        rows = (
                            supabase_service.client.table("journal_entries")
                            .select("id,reference_id,total,date,description,source")
                            .eq("source", "operation_payment")
                            .execute()
                            .data
                            or []
                        )
                    except Exception:
                        rows = []
                else:
                    rows = []
    elif DB_PROVIDER == "memory":
        rows = [r for r in _mem_read("journal_entries") if str(r.get("source") or "") == "operation_payment"]
        if workshop_id:
            rows = [
                r
                for r in rows
                if str(r.get("workshopId") or r.get("workshop_id") or "") == str(workshop_id)
            ]
    else:
        if db is None:
            return {}
        query: Dict[str, Any] = {"source": "operation_payment"}
        if workshop_id:
            query["workshop_id"] = workshop_id
        rows = await db.journal_entries.find(query, {"_id": 0}).to_list(5000)

    by_ref: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        ref_id = str(row.get("reference_id") or row.get("referenceId") or "").strip()
        if not ref_id:
            continue
        by_ref.setdefault(ref_id, []).append(row)
    return by_ref


async def _fetch_vehicle_customer_lookup(workshop_id: Optional[str]) -> Dict[str, str]:
    # 🚀 TTL cache (15s) — vehicles list is read-heavy
    cache_key = workshop_id or "_"
    cached = _perf_cache.get_cached("vehicle_customer_lookup", cache_key)
    if cached is not None:
        return cached
    result = await _fetch_vehicle_customer_lookup_uncached(workshop_id)
    _perf_cache.set_cached("vehicle_customer_lookup", result, cache_key)
    return result


async def _fetch_vehicle_customer_lookup_uncached(workshop_id: Optional[str]) -> Dict[str, str]:
    rows: List[Dict[str, Any]] = []

    if DB_PROVIDER == "supabase":
        if supabase_service.client and not supabase_service.mock_mode:
            try:
                q = supabase_service.client.table("vehicles").select("id,customer_id")
                if workshop_id:
                    q = q.eq("workshop_id", workshop_id)
                rows = q.execute().data or []
            except Exception:
                try:
                    rows = supabase_service.client.table("vehicles").select("id,customer_id").execute().data or []
                except Exception:
                    rows = []
    elif DB_PROVIDER == "memory":
        rows = _mem_read("vehicles") or []
        if workshop_id:
            rows = [
                r
                for r in rows
                if str(r.get("workshopId") or r.get("workshop_id") or "") == str(workshop_id)
            ]
    else:
        if db is None:
            return {}
        query: Dict[str, Any] = {}
        if workshop_id:
            query["$or"] = [{"workshopId": workshop_id}, {"workshop_id": workshop_id}]
        rows = await db.vehicles.find(query, {"_id": 0, "id": 1, "customerId": 1, "customer_id": 1}).to_list(5000)

    lookup: Dict[str, str] = {}
    for row in rows:
        vehicle_id = str(row.get("id") or "").strip()
        customer_id = str(row.get("customer_id") or row.get("customerId") or "").strip()
        if vehicle_id and customer_id:
            lookup[vehicle_id] = customer_id
    return lookup


async def _fetch_vehicle_visits_for_financials(workshop_id: Optional[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    if DB_PROVIDER == "supabase":
        if supabase_service.client and not supabase_service.mock_mode:
            try:
                q = supabase_service.client.table("vehicle_visits").select("id,vehicle_id,entry_date,created_at,notes")
                if workshop_id:
                    q = q.eq("workshop_id", workshop_id)
                rows = q.execute().data or []
            except Exception:
                try:
                    rows = (
                        supabase_service.client.table("vehicle_visits")
                        .select("id,vehicle_id,entry_date,created_at,notes")
                        .execute()
                        .data
                        or []
                    )
                except Exception:
                    rows = []
    elif DB_PROVIDER == "memory":
        rows = _mem_read("vehicle_visits") or []
        if workshop_id:
            rows = [
                r
                for r in rows
                if str(r.get("workshopId") or r.get("workshop_id") or "") == str(workshop_id)
            ]
    else:
        if db is None:
            return []
        query: Dict[str, Any] = {}
        if workshop_id:
            query["$or"] = [{"workshopId": workshop_id}, {"workshop_id": workshop_id}]
        rows = await db.vehicle_visits.find(
            query,
            {
                "_id": 0,
                "id": 1,
                "vehicleId": 1,
                "vehicle_id": 1,
                "entryDate": 1,
                "entry_date": 1,
                "createdAt": 1,
                "created_at": 1,
                "notes": 1,
            },
        ).to_list(5000)

    return rows


def _round_partner_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    summary["debitBalance"] = round(_safe_float(summary.get("debitBalance")), 2)
    summary["creditBalance"] = round(_safe_float(summary.get("creditBalance")), 2)
    summary["overdueBalance"] = round(_safe_float(summary.get("overdueBalance")), 2)
    summary["ajelBalance"] = round(_safe_float(summary.get("ajelBalance")), 2)
    summary["settledAmount"] = round(_safe_float(summary.get("settledAmount")), 2)
    summary["balance"] = round(_safe_float(summary.get("overdueBalance")), 2)
    summary["netBalance"] = round(
        _safe_float(summary.get("debitBalance")) - _safe_float(summary.get("creditBalance")),
        2,
    )
    summary["movements"] = sorted(
        summary.get("movements") or [],
        key=lambda m: str(m.get("date") or ""),
        reverse=True,
    )[:20]
    return summary


async def _build_partner_financial_map(
    partner_type: str,
    entities: List[Dict[str, Any]],
    workshop_id: Optional[str],
) -> Dict[str, Dict[str, Any]]:
    p_type = str(partner_type or "").strip().lower()

    # 🚀 TTL cache (15s) — financial map computation iterates ALL operations × ALL entities
    # Cache key includes entity count + first/last IDs to detect when caller passes different sets.
    entity_ids = sorted(str(e.get("id") or "") for e in (entities or []) if str(e.get("id") or ""))
    cache_signature = f"{len(entity_ids)}:{entity_ids[0] if entity_ids else ''}:{entity_ids[-1] if entity_ids else ''}"
    cache_key = f"visit-ar-v2|{p_type}|{workshop_id or '_'}|{cache_signature}"
    cached = _perf_cache.get_cached("partner_fin_map", cache_key)
    if cached is not None:
        return cached

    result = await _build_partner_financial_map_uncached(partner_type, entities, workshop_id)
    _perf_cache.set_cached("partner_fin_map", result, cache_key)
    return result


async def _build_partner_financial_map_uncached(
    partner_type: str,
    entities: List[Dict[str, Any]],
    workshop_id: Optional[str],
) -> Dict[str, Dict[str, Any]]:
    p_type = str(partner_type or "").strip().lower()
    by_id: Dict[str, Dict[str, Any]] = {}
    by_name: Dict[str, str] = {}

    for entity in entities or []:
        entity_id = str(entity.get("id") or "").strip()
        if not entity_id:
            continue
        by_id[entity_id] = _partner_summary_template()
        normalized_name = _normalize_partner_name(entity.get("name"))
        if normalized_name:
            by_name[normalized_name] = entity_id

    if not by_id:
        return {}

    if p_type == "customer":
        try:
            snapshot = build_current_visit_ar_snapshot(workshop_id or "finmodule-sync")
            for vehicle_row in snapshot.get("vehicles") or []:
                customer_key = _normalize_partner_name(vehicle_row.get("customer"))
                target_id = by_name.get(customer_key)
                if not target_id or target_id not in by_id:
                    continue
                summary = by_id[target_id]
                workshop_amount = _safe_float(vehicle_row.get("workshop_amount"))
                confirmed_paid = _safe_float(vehicle_row.get("confirmed_paid"))
                receivable = _safe_float(vehicle_row.get("receivable"))
                if workshop_amount <= 0 and confirmed_paid <= 0 and receivable <= 0:
                    continue
                summary["debitBalance"] += workshop_amount
                summary["creditBalance"] += confirmed_paid
                summary["settledAmount"] += confirmed_paid
                summary["overdueBalance"] += receivable
                summary["ajelBalance"] += receivable
                if receivable > 0:
                    summary["paymentPlanCount"] += 1
                _append_partner_movement(
                    summary,
                    {
                        "id": f"vehicle-visit-ar-{vehicle_row.get('vehicle_id')}",
                        "direction": "debit",
                        "label": "آجل — غير مسدد" if confirmed_paid <= 0 else ("سداد جزئي" if receivable > 0 else "مسدد بالكامل"),
                        "amount": round(workshop_amount, 2),
                        "date": "",
                        "flow": "in",
                        "flowLabel": "داخل",
                        "visitId": "",
                        "vehicleId": vehicle_row.get("vehicle_id"),
                        "source": "vehicle_visit_current_ar",
                        "operationId": "",
                        "note": "بنود الورشة فقط ناقص قيود السداد المؤكدة",
                    },
                )
                if confirmed_paid > 0:
                    _append_partner_movement(
                        summary,
                        {
                            "id": f"vehicle-visit-paid-{vehicle_row.get('vehicle_id')}",
                            "direction": "credit",
                            "label": "سداد مؤكد",
                            "amount": round(confirmed_paid, 2),
                            "date": "",
                            "flow": "in",
                            "flowLabel": "داخل",
                            "visitId": "",
                            "vehicleId": vehicle_row.get("vehicle_id"),
                            "source": "operation_payment",
                            "operationId": "",
                            "note": "قيود يومية مؤكدة مرتبطة بالزيارة/العملية",
                        },
                    )
            for summary in by_id.values():
                summary["debitBalance"] = round(_safe_float(summary.get("debitBalance")), 2)
                summary["creditBalance"] = round(_safe_float(summary.get("creditBalance")), 2)
                summary["overdueBalance"] = round(_safe_float(summary.get("overdueBalance")), 2)
                summary["ajelBalance"] = round(_safe_float(summary.get("ajelBalance")), 2)
                summary["settledAmount"] = round(_safe_float(summary.get("settledAmount")), 2)
                summary["balance"] = round(_safe_float(summary.get("overdueBalance")), 2)
                summary["netBalance"] = round(summary["debitBalance"] - summary["creditBalance"], 2)
            return by_id
        except Exception as visit_ar_error:
            print(f"customer visit AR snapshot failed, falling back to operations: {visit_ar_error}")

    operations = await _filter_partner_operations_to_current_scope(
        await _fetch_operations_for_partner_financials(workshop_id),
        workshop_id,
    )
    payment_map = await _fetch_operation_payment_map(workshop_id)
    vehicle_customer_lookup = await _fetch_vehicle_customer_lookup(workshop_id) if p_type == "customer" else {}

    # 🔗 canonical per-visit paid map (single source with operations page)
    prefetched_visit_rows: List[Dict[str, Any]] = []
    visit_paid_map: Dict[str, float] = {}
    if p_type == "customer":
        prefetched_visit_rows = await _fetch_vehicle_visits_for_financials(workshop_id)
        for _visit in prefetched_visit_rows:
            _vid = str(_visit.get("id") or "").strip()
            if not _vid:
                continue
            _payload = _parse_json_like(_visit.get("notes"))
            _pays = _payload.get("payments") if isinstance(_payload.get("payments"), list) else []
            _net = 0.0
            for _p in _pays:
                _amt = _safe_float(_p.get("amount"))
                if _amt <= 0:
                    continue
                _kind = str(_p.get("kind") or _p.get("type") or "payment").strip().lower()
                _net += -_amt if _kind in {"refund", "return"} else _amt
            visit_paid_map[_vid] = round(max(_net, 0.0), 2)
    op_visit_ids: set = set()

    for op in operations:
        op_partner_type = str(_op_field(op, "partner_type", "partnerType") or "").strip().lower()
        if op_partner_type and op_partner_type != p_type:
            continue

        partner_id = str(_op_field(op, "partner_id", "partnerId") or "").strip()
        partner_name_norm = _normalize_partner_name(_op_field(op, "partner_name", "partnerName"))
        vehicle_id = str(_op_field(op, "vehicle_id", "vehicleId") or "").strip()
        visit_id = str(_op_field(op, "visit_id", "visitId") or "").strip()

        # 🎯 attribution priority: partner_id → vehicle→customer link → normalized name
        target_id = partner_id if partner_id in by_id else None
        if not target_id and p_type == "customer" and vehicle_id:
            mapped_customer = vehicle_customer_lookup.get(vehicle_id)
            if mapped_customer and mapped_customer in by_id:
                target_id = mapped_customer
        if not target_id:
            target_id = by_name.get(partner_name_norm)

        if not target_id:
            continue

        summary = by_id[target_id]
        op_id = str(op.get("id") or "")
        op_type = str(op.get("type") or "").strip().lower()
        total_amount = _safe_float(op.get("total"))
        if total_amount <= 0:
            total_amount = _safe_float(_op_field(op, "payment_amount", "paymentAmount"))

        payment_method = str(_op_field(op, "payment_method", "paymentMethod") or "").strip().lower()
        payment_status = str(_op_field(op, "payment_status", "paymentStatus") or "").strip().lower()
        paid_rows = payment_map.get(op_id, [])
        paid_amount = round(sum(_safe_float(row.get("total")) for row in paid_rows), 2)
        # canonical paid = max(journalized, visit-notes payments) — same as operations page
        if visit_id and visit_id in visit_paid_map:
            paid_amount = round(max(paid_amount, visit_paid_map[visit_id]), 2)

        movement_date = str(_op_field(op, "op_date", "date") or _op_field(op, "created_at", "createdAt") or "")
        movement_note = str(op.get("notes") or "")
        if not visit_id:
            visit_id = f"op-{op_id}"

        is_credit_origin = (
            payment_method == "credit"
            or payment_status in {"credit", "unpaid", "pending", "partial"}
            or paid_amount > 0
        )
        movement_logged = False

        if p_type == "customer" and op_type in {"sale", "service"} and is_credit_origin:
            if visit_id and not visit_id.startswith("op-"):
                op_visit_ids.add(visit_id)
            summary["debitBalance"] += total_amount
            remaining = max(0.0, total_amount - paid_amount)
            summary["overdueBalance"] += remaining
            summary["ajelBalance"] += remaining
            summary["paymentPlanCount"] += 1
            _append_partner_movement(
                summary,
                {
                    "id": f"op-{op_id}",
                    "direction": "debit",
                    "label": "مبيعات آجل",
                    "amount": round(total_amount, 2),
                    "date": movement_date,
                    "flow": "in",
                    "flowLabel": "داخل",
                    "visitId": visit_id,
                    "vehicleId": vehicle_id,
                    "source": "operation",
                    "operationId": op_id,
                    "note": movement_note,
                },
            )
            movement_logged = True

            if paid_amount > 0:
                summary["creditBalance"] += paid_amount
                summary["settledAmount"] += paid_amount
                _append_partner_movement(
                    summary,
                    {
                        "id": f"pay-{op_id}",
                        "direction": "credit",
                        "label": "سداد آجل",
                        "amount": round(paid_amount, 2),
                        "date": movement_date,
                        "flow": "in",
                        "flowLabel": "داخل",
                        "visitId": visit_id,
                        "vehicleId": vehicle_id,
                        "source": "operation_payment",
                        "operationId": op_id,
                        "note": "تحصيل دفعة من العميل",
                    },
                )

        elif p_type == "supplier" and op_type in {"purchase", "expense"} and is_credit_origin:
            summary["creditBalance"] += total_amount
            remaining = max(0.0, total_amount - paid_amount)
            summary["overdueBalance"] += remaining
            summary["ajelBalance"] += remaining
            summary["paymentPlanCount"] += 1
            _append_partner_movement(
                summary,
                {
                    "id": f"op-{op_id}",
                    "direction": "credit",
                    "label": "مشتريات آجل",
                    "amount": round(total_amount, 2),
                    "date": movement_date,
                    "flow": "out",
                    "flowLabel": "خارج",
                    "visitId": visit_id,
                    "vehicleId": vehicle_id,
                    "source": "operation",
                    "operationId": op_id,
                    "note": movement_note,
                },
            )
            movement_logged = True

            if paid_amount > 0:
                summary["debitBalance"] += paid_amount
                summary["settledAmount"] += paid_amount
                _append_partner_movement(
                    summary,
                    {
                        "id": f"pay-{op_id}",
                        "direction": "debit",
                        "label": "سداد آجل",
                        "amount": round(paid_amount, 2),
                        "date": movement_date,
                        "flow": "out",
                        "flowLabel": "خارج",
                        "visitId": visit_id,
                        "vehicleId": vehicle_id,
                        "source": "operation_payment",
                        "operationId": op_id,
                        "note": "دفعة سداد للمورد",
                    },
                )

        elif op_type == "payment_order" and total_amount > 0:
            if p_type == "customer":
                summary["creditBalance"] += total_amount
                summary["settledAmount"] += total_amount
                _append_partner_movement(
                    summary,
                    {
                        "id": f"po-{op_id}",
                        "direction": "credit",
                        "label": "أمر سداد",
                        "amount": round(total_amount, 2),
                        "date": movement_date,
                        "flow": "in",
                        "flowLabel": "داخل",
                        "visitId": visit_id,
                        "vehicleId": vehicle_id,
                        "source": "payment_order",
                        "operationId": op_id,
                        "note": movement_note,
                    },
                )
                movement_logged = True
            elif p_type == "supplier":
                summary["debitBalance"] += total_amount
                summary["settledAmount"] += total_amount
                _append_partner_movement(
                    summary,
                    {
                        "id": f"po-{op_id}",
                        "direction": "debit",
                        "label": "أمر سداد",
                        "amount": round(total_amount, 2),
                        "date": movement_date,
                        "flow": "out",
                        "flowLabel": "خارج",
                        "visitId": visit_id,
                        "vehicleId": vehicle_id,
                        "source": "payment_order",
                        "operationId": op_id,
                        "note": movement_note,
                    },
                )
                movement_logged = True

        if not movement_logged and total_amount > 0:
            flow = "in"
            flow_label = "داخل"
            movement_label = "حركة مالية"
            direction = "credit"

            if p_type == "customer":
                if op_type in {"sale", "service"}:
                    movement_label = "دفعة" if payment_method != "credit" else "مبيعات آجل"
                    flow = "in"
                    flow_label = "داخل"
                    direction = "credit" if payment_method != "credit" else "debit"
                    if payment_method != "credit":
                        summary["creditBalance"] += total_amount
                        summary["settledAmount"] += total_amount
                elif op_type in {"sale_return", "refund"}:
                    movement_label = "مرتجع بيع"
                    flow = "out"
                    flow_label = "خارج"
                    direction = "debit"
                else:
                    movement_label = "حركة عميل"
            else:
                if op_type in {"purchase", "expense"}:
                    movement_label = "شراء نقدي" if payment_method != "credit" else "مشتريات آجل"
                    flow = "out"
                    flow_label = "خارج"
                    direction = "debit" if payment_method != "credit" else "credit"
                    if payment_method != "credit":
                        summary["debitBalance"] += total_amount
                        summary["settledAmount"] += total_amount
                elif op_type in {"purchase_return"}:
                    movement_label = "مرتجع شراء"
                    flow = "in"
                    flow_label = "داخل"
                    direction = "credit"
                else:
                    movement_label = "حركة مورد"
                    flow = "out"
                    flow_label = "خارج"
                    direction = "debit"

            _append_partner_movement(
                summary,
                {
                    "id": f"raw-{op_id}",
                    "direction": direction,
                    "label": movement_label,
                    "amount": round(total_amount, 2),
                    "date": movement_date,
                    "flow": flow,
                    "flowLabel": flow_label,
                    "visitId": visit_id,
                    "vehicleId": vehicle_id,
                    "source": "operation_raw",
                    "operationId": op_id,
                    "note": movement_note,
                },
            )

    if p_type == "customer" and vehicle_customer_lookup:
        visit_rows = prefetched_visit_rows
        seen_visit_payments = set()

        for visit in visit_rows:
            vehicle_id = str(visit.get("vehicle_id") or visit.get("vehicleId") or "").strip()
            if not vehicle_id:
                continue

            # ⛔ payments of visits already reflected in an operation's remaining are skipped
            if str(visit.get("id") or "").strip() in op_visit_ids:
                continue

            customer_id = vehicle_customer_lookup.get(vehicle_id)
            if not customer_id or customer_id not in by_id:
                continue

            notes_payload = _parse_json_like(visit.get("notes"))
            payments = notes_payload.get("payments") if isinstance(notes_payload.get("payments"), list) else []
            if not payments:
                continue

            summary = by_id[customer_id]
            visit_id = str(visit.get("id") or "").strip() or f"visit-{vehicle_id}"
            visit_date = str(
                visit.get("entry_date")
                or visit.get("entryDate")
                or visit.get("created_at")
                or visit.get("createdAt")
                or ""
            )

            for idx, payment in enumerate(payments):
                amount = _safe_float(payment.get("amount"))
                if amount <= 0:
                    continue

                raw_payment_id = str(
                    payment.get("id")
                    or payment.get("operationId")
                    or payment.get("reference_id")
                    or f"{visit_id}-{idx}"
                )
                movement_key = f"{visit_id}:{raw_payment_id}"
                if movement_key in seen_visit_payments:
                    continue
                seen_visit_payments.add(movement_key)

                kind = str(payment.get("kind") or payment.get("type") or "payment").strip().lower()
                movement_date = str(payment.get("date") or visit_date)

                if kind in {"refund", "return"}:
                    flow = "out"
                    flow_label = "خارج"
                    direction = "debit"
                    label = "مرتجع دفعة"
                    summary["debitBalance"] += amount
                else:
                    flow = "in"
                    flow_label = "داخل"
                    direction = "credit"
                    label = "دفعة مقدمة" if kind in {"advance", "deposit", "down_payment", "prepayment"} else "دفعة"
                    summary["creditBalance"] += amount
                    summary["settledAmount"] += amount
                    summary["overdueBalance"] = max(0.0, _safe_float(summary.get("overdueBalance")) - amount)
                    summary["ajelBalance"] = max(0.0, _safe_float(summary.get("ajelBalance")) - amount)

                _append_partner_movement(
                    summary,
                    {
                        "id": f"visit-payment-{raw_payment_id}",
                        "direction": direction,
                        "label": label,
                        "amount": round(amount, 2),
                        "date": movement_date,
                        "flow": flow,
                        "flowLabel": flow_label,
                        "visitId": visit_id,
                        "vehicleId": vehicle_id,
                        "source": "visit_payment",
                        "operationId": str(payment.get("operationId") or ""),
                        "note": str(payment.get("note") or payment.get("description") or ""),
                    },
                )

    # 🔁 Augment supplier movements from journal entries.
    # Operations table doesn't always carry a clean partner_id link, but the
    # general ledger does (each supplier has its own sub-account "مورد - <name>").
    # We scan all journal lines that reference such a supplier sub-account and
    # turn them into movement rows on the matching supplier file.
    if p_type == "supplier":
        try:
            await _augment_supplier_movements_from_journal(by_id, by_name, workshop_id)
        except Exception as exc:
            print(f"_augment_supplier_movements_from_journal failed: {exc}")

    for entity_id, summary in by_id.items():
        by_id[entity_id] = _round_partner_summary(summary)

    return by_id


async def _augment_supplier_movements_from_journal(
    by_id: Dict[str, Dict[str, Any]],
    by_name: Dict[str, str],
    workshop_id: Optional[str],
) -> None:
    """Read journal_entries and append matching lines to each supplier's movements list.

    Match strategy (broad substring match by normalized supplier name):
      - For each line, check the account name (and/or fallback `name`/`acc_name`).
      - For each registered supplier, if its normalized name appears in the account
        name we attach the line as a movement to that supplier.
      - This catches both dedicated sub-accounts ("مورد - <name>") and themed
        expense accounts ("مصروفات شخصيه راكان", "مصروفات بنزين راكان"…).
    """
    if not (supabase_service.client and not supabase_service.mock_mode):
        return
    if not by_name:
        return

    # Reuse the finance routes journal entry cache to avoid an extra Supabase
    # roundtrip on every Suppliers page load.
    entries: List[Dict[str, Any]] = []
    try:
        from routes_finance import _fetch_journal_entries as _finance_fetch_je
        entries = _finance_fetch_je(workshop_id or "", limit=5000, include_rakan=True)
    except Exception:
        try:
            q = supabase_service.client.table("journal_entries").select("id,date,description,lines,source").limit(5000)
            if workshop_id:
                q = q.eq("workshop_id", workshop_id)
            res = q.execute()
            entries = res.data or []
        except Exception as exc:
            print(f"journal_entries fetch failed: {exc}")
            return

    # Pre-build (normalized_supplier_name, supplier_id) sorted by name length desc
    # so longer names match first ("الزايدي ليات" before "الزايدي").
    supplier_targets = sorted(
        ((name_norm, sid) for name_norm, sid in by_name.items() if name_norm),
        key=lambda t: len(t[0]),
        reverse=True,
    )

    seen_movement_keys: set = set()

    for entry in entries:
        entry_id = str(entry.get("id") or "")
        entry_date = str(entry.get("date") or "")
        entry_desc = str(entry.get("description") or "")
        manual_party_match = re.search(r"\[PARTY:([^\]]+)\]", entry_desc)
        manual_party_type_match = re.search(r"\[PARTY_TYPE:([^\]]+)\]", entry_desc)
        manual_party_norm = _normalize_partner_name(manual_party_match.group(1).strip()) if manual_party_match else ""
        manual_party_type = str(manual_party_type_match.group(1) or "").strip().lower() if manual_party_type_match else ""
        for idx, line in enumerate(entry.get("lines") or []):
            if not isinstance(line, dict):
                continue
            acc_name_raw = str(line.get("account_name") or line.get("name") or "").strip()
            acc_name_norm = _normalize_partner_name(acc_name_raw)
            line_account_code = str(line.get("account") or "").strip()

            # Find first matching supplier by substring on normalized account name.
            target_id = None
            if manual_party_norm and manual_party_type == "supplier":
                for sup_name, sid in supplier_targets:
                    if sup_name == manual_party_norm or manual_party_norm in sup_name or sup_name in manual_party_norm:
                        target_id = sid
                        break

                # POS / manual supplier journal entries must only attach the supplier-side line,
                # not the cash/bank line of the same entry.
                if target_id and not (
                    line_account_code.startswith("2101")
                    or "مورد" in acc_name_norm
                    or "supplier" in acc_name_norm
                ):
                    target_id = None

            if not target_id:
                if not acc_name_raw or not acc_name_norm:
                    continue
                for sup_name, sid in supplier_targets:
                    if sup_name in acc_name_norm:
                        target_id = sid
                        break
            if not target_id or target_id not in by_id:
                continue

            debit = _safe_float(line.get("debit"))
            credit = _safe_float(line.get("credit"))
            amount = round(debit if debit > 0 else credit, 2)
            if amount <= 0:
                continue

            direction = "debit" if debit > 0 else "credit"
            label = "سداد للمورد" if direction == "debit" else "مشتريات / مستحق"
            flow = "out" if direction == "debit" else "in"

            mv_id = f"je-{entry_id}-{idx}"
            mv_key = f"{target_id}:{mv_id}"
            if mv_key in seen_movement_keys:
                continue
            seen_movement_keys.add(mv_key)

            _append_partner_movement(
                by_id[target_id],
                {
                    "id": mv_id,
                    "direction": direction,
                    "label": label,
                    "amount": amount,
                    "date": entry_date,
                    "flow": flow,
                    "flowLabel": "خارج" if flow == "out" else "داخل",
                    "visitId": "",
                    "vehicleId": "",
                    "source": "journal_entry",
                    "operationId": "",
                    "note": entry_desc or acc_name_raw,
                    "accountName": acc_name_raw,
                },
            )

            if direction == "credit":
                by_id[target_id]["creditBalance"] += amount
                by_id[target_id]["overdueBalance"] += amount
                by_id[target_id]["ajelBalance"] += amount
                by_id[target_id]["paymentPlanCount"] += 1
            else:
                by_id[target_id]["debitBalance"] += amount
                by_id[target_id]["settledAmount"] += amount


def _normalize_account_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": raw.get("id"),
        "code": str(raw.get("code") or ""),
        "name": raw.get("name") or raw.get("name_ar"),
        "type": raw.get("type"),
        "parent_id": raw.get("parent_id") if raw.get("parent_id") is not None else raw.get("parentId"),
        "is_system": bool(raw.get("is_system") if raw.get("is_system") is not None else raw.get("isSystem", False)),
        "balance": _safe_float(raw.get("balance")),
    }


async def _load_chart_accounts_rows() -> List[Dict[str, Any]]:
    if DB_PROVIDER == "supabase":
        if supabase_service.client and not supabase_service.mock_mode:
            try:
                res = supabase_service.client.table("accounts").select("*").execute()
                return [_normalize_account_row(r) for r in (res.data or [])]
            except Exception:
                return []
        return []

    if DB_PROVIDER == "memory":
        return [_normalize_account_row(r) for r in (_mem_read("accounts") or [])]

    if db is None:
        return []

    rows = await db.accounts.find({}, {"_id": 0}).to_list(5000)
    return [_normalize_account_row(r) for r in rows]


def _next_partner_sub_code(accounts: List[Dict[str, Any]], prefix: str) -> str:
    max_suffix = 0
    for account in accounts:
        code = str(account.get("code") or "")
        if not code.startswith(prefix) or code == prefix:
            continue
        suffix = code[len(prefix):]
        if suffix.isdigit():
            max_suffix = max(max_suffix, int(suffix))
    return f"{prefix}{max_suffix + 1:04d}"


async def _upsert_chart_account(account: Dict[str, Any]):
    if DB_PROVIDER == "supabase":
        if not (supabase_service.client and not supabase_service.mock_mode):
            return
        existing = (
            supabase_service.client.table("accounts")
            .select("id")
            .eq("id", account["id"])
            .limit(1)
            .execute()
            .data
            or []
        )
        payload = {
            "id": account["id"],
            "code": account.get("code"),
            "name": account.get("name"),
            "name_en": account.get("name_en") or "",
            "type": account.get("type"),
            "parent_id": account.get("parent_id"),
            "is_system": bool(account.get("is_system", False)),
            "balance": _safe_float(account.get("balance")),
        }
        if existing:
            supabase_service.client.table("accounts").update(payload).eq("id", account["id"]).execute()
        else:
            supabase_service.client.table("accounts").insert(payload).execute()
        return

    if DB_PROVIDER == "memory":
        rows = _mem_read("accounts") or []
        idx = next((i for i, row in enumerate(rows) if str(row.get("id")) == str(account.get("id"))), -1)
        memory_row = {
            "id": account.get("id"),
            "code": account.get("code"),
            "name": account.get("name"),
            "nameEn": account.get("name_en") or "",
            "type": account.get("type"),
            "parentId": account.get("parent_id"),
            "isSystem": bool(account.get("is_system", False)),
            "balance": _safe_float(account.get("balance")),
        }
        if idx >= 0:
            rows[idx] = memory_row
        else:
            rows.append(memory_row)
        _mem_write("accounts", rows)
        return

    await db.accounts.update_one(
        {"id": account["id"]},
        {
            "$set": {
                "code": account.get("code"),
                "name": account.get("name"),
                "nameEn": account.get("name_en") or "",
                "type": account.get("type"),
                "parentId": account.get("parent_id"),
                "isSystem": bool(account.get("is_system", False)),
                "balance": _safe_float(account.get("balance")),
            }
        },
        upsert=True,
    )


async def _ensure_parent_partner_account(partner_type: str, accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
    if partner_type == "customer":
        parent_code = "1103"
        parent_name = "العملاء"
        acc_type = "asset"
    else:
        parent_code = "2101"
        parent_name = "الموردون"
        acc_type = "liability"

    parent = next((a for a in accounts if str(a.get("code") or "") == parent_code), None)
    if parent:
        return parent

    parent = {
        "id": f"acc-{parent_code}",
        "code": parent_code,
        "name": parent_name,
        "name_en": "",
        "type": acc_type,
        "parent_id": None,
        "is_system": True,
        "balance": 0.0,
    }
    await _upsert_chart_account(parent)
    accounts.append(_normalize_account_row(parent))
    return _normalize_account_row(parent)


async def _sync_partner_subaccounts(
    partner_type: str,
    entities: List[Dict[str, Any]],
    financial_map: Dict[str, Dict[str, Any]],
):
    if not entities:
        return
    accounts = await _load_chart_accounts_rows()
    parent = await _ensure_parent_partner_account(partner_type, accounts)
    parent_id = str(parent.get("id") or "")
    code_prefix = "1103" if partner_type == "customer" else "2101"
    acc_type = "asset" if partner_type == "customer" else "liability"

    for entity in entities:
        entity_id = str(entity.get("id") or "").strip()
        if not entity_id:
            continue
        sub_id = f"acc-{partner_type}-{entity_id}"
        existing = next((a for a in accounts if str(a.get("id") or "") == sub_id), None)
        if existing:
            code = str(existing.get("code") or "") or _next_partner_sub_code(accounts, code_prefix)
        else:
            code = _next_partner_sub_code(accounts, code_prefix)

        summary = financial_map.get(entity_id) or {}
        account_payload = {
            "id": sub_id,
            "code": code,
            "name": f"{'عميل' if partner_type == 'customer' else 'مورد'} - {entity.get('name') or entity_id}",
            "name_en": "",
            "type": acc_type,
            "parent_id": parent_id,
            "is_system": False,
            "balance": _safe_float(summary.get("overdueBalance")),
        }
        await _upsert_chart_account(account_payload)
        if not existing:
            accounts.append(_normalize_account_row(account_payload))


async def _safe_sync_partner_subaccounts(
    partner_type: str,
    entities: List[Dict[str, Any]],
    financial_map: Dict[str, Dict[str, Any]],
):
    try:
        await _sync_partner_subaccounts(partner_type, entities, financial_map)
    except Exception as sync_error:
        print(f"⚠️ partner subaccounts sync warning ({partner_type}): {sync_error}")


async def _get_customer_file_number_map(customer_ids: List[str]) -> Dict[str, str]:
    valid_ids = [str(cid).strip() for cid in customer_ids if str(cid).strip()]
    if not valid_ids:
        return {}

    if DB_PROVIDER == "memory":
        rows = _mem_read("customer_file_numbers")
        return {
            str(r.get("customerId") or ""): str(r.get("fileNumber") or "")
            for r in rows
            if str(r.get("customerId") or "") in valid_ids and str(r.get("fileNumber") or "").strip()
        }

    if DB_PROVIDER == "supabase" or db is None:
        settings_raw = read_settings()
        settings = (
            settings_raw
            if isinstance(settings_raw, dict)
            else (settings_raw[0] if isinstance(settings_raw, list) and settings_raw and isinstance(settings_raw[0], dict) else {})
        )
        raw_map = settings.get("customerFileNumbers") or {}
        return {
            str(cid): str(raw_map.get(cid) or "")
            for cid in valid_ids
            if str(raw_map.get(cid) or "").strip()
        }

    rows = await db.customer_file_numbers.find(
        {"customerId": {"$in": valid_ids}},
        {"_id": 0, "customerId": 1, "fileNumber": 1},
    ).to_list(5000)
    return {
        str(r.get("customerId") or ""): str(r.get("fileNumber") or "")
        for r in rows
        if str(r.get("fileNumber") or "").strip()
    }


async def _set_customer_file_number(customer_id: str, file_number: Optional[str]) -> None:
    cid = str(customer_id or "").strip()
    if not cid:
        return
    cleaned = str(file_number or "").strip()

    if DB_PROVIDER == "memory":
        rows = [r for r in _mem_read("customer_file_numbers") if str(r.get("customerId") or "") != cid]
        if cleaned:
            rows.append({"customerId": cid, "fileNumber": cleaned})
        _mem_write("customer_file_numbers", rows)
        return

    if DB_PROVIDER == "supabase" or db is None:
        settings_raw = read_settings()
        settings = (
            settings_raw
            if isinstance(settings_raw, dict)
            else (settings_raw[0] if isinstance(settings_raw, list) and settings_raw and isinstance(settings_raw[0], dict) else {})
        )
        raw_map = settings.get("customerFileNumbers")
        if not isinstance(raw_map, dict):
            raw_map = {}
        if cleaned:
            raw_map[cid] = cleaned
        else:
            raw_map.pop(cid, None)
        settings["customerFileNumbers"] = raw_map
        write_settings(settings)
        return

    if cleaned:
        await db.customer_file_numbers.update_one(
            {"customerId": cid},
            {"$set": {"customerId": cid, "fileNumber": cleaned}},
            upsert=True,
        )
    else:
        await db.customer_file_numbers.delete_one({"customerId": cid})


async def _delete_customer_file_number(customer_id: str) -> None:
    cid = str(customer_id or "").strip()
    if not cid:
        return

    if DB_PROVIDER == "memory":
        _mem_write(
            "customer_file_numbers",
            [r for r in _mem_read("customer_file_numbers") if str(r.get("customerId") or "") != cid],
        )
        return

    if DB_PROVIDER == "supabase" or db is None:
        settings_raw = read_settings()
        settings = (
            settings_raw
            if isinstance(settings_raw, dict)
            else (settings_raw[0] if isinstance(settings_raw, list) and settings_raw and isinstance(settings_raw[0], dict) else {})
        )
        raw_map = settings.get("customerFileNumbers")
        if isinstance(raw_map, dict) and cid in raw_map:
            raw_map.pop(cid, None)
            settings["customerFileNumbers"] = raw_map
            write_settings(settings)
        return

    await db.customer_file_numbers.delete_one({"customerId": cid})


async def _attach_customer_file_numbers_to_vehicles(rows: List[dict]) -> List[dict]:
    if not rows:
        return rows

    customer_ids = [
        str(r.get("customerId") or r.get("customer_id") or "").strip()
        for r in rows
        if str(r.get("customerId") or r.get("customer_id") or "").strip()
    ]
    file_map = await _get_customer_file_number_map(customer_ids)

    for row in rows:
        cid = str(row.get("customerId") or row.get("customer_id") or "").strip()
        customer_file = file_map.get(cid)
        row["customerFileNumber"] = customer_file or row.get("customerFileNumber") or None

    return rows


# ----------------------------------------------------------------------
# 📦 Customers domain — extracted to /app/backend/domains/customers/*
# (router mounted below via api_router.include_router)
# Endpoints removed from server.py: GET /customers, GET /customers/{id},
# POST /customers, PUT /customers/{id}, DELETE /customers/{id}
# ----------------------------------------------------------------------



@api_router.post("/admin/reset-inventory")
async def reset_inventory_data():
    try:
        updated_parts = 0
        updated_services = 0

        if DB_PROVIDER == "supabase":
            parts = supabase_service.parts_list() or []
            for part in parts:
                part_id = part.get("id")
                if part_id:
                    supabase_service.parts_update(part_id, {"quantity": 0})
                    updated_parts += 1

            services = supabase_service.services_list() or []
            for service in services:
                service_id = service.get("id")
                if service_id:
                    supabase_service.services_update(service_id, {"price": 0})
                    updated_services += 1
        elif DB_PROVIDER == "memory":
            parts = _mem_read("parts", [])
            for part in parts:
                part["quantity"] = 0
            _mem_write("parts", parts)
            updated_parts = len(parts)

            services = _mem_read("services", [])
            for service in services:
                service["price"] = 0
            _mem_write("services", services)
            updated_services = len(services)
        else:
            updated_parts = db.parts.update_many({}, {"$set": {"quantity": 0}}).modified_count
            updated_services = db.services.update_many({}, {"$set": {"price": 0}}).modified_count

        return {
            "success": True,
            "updated_parts": updated_parts,
            "updated_services": updated_services
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")


@api_router.post("/vehicles/{vehicle_id}/upload-file")
async def upload_vehicle_file(
    vehicle_id: str, file: UploadFile = File(...), file_type: str = "diagnostic"
):
    """رفع ملف أو صورة أو فاتورة لمركبة (يُخزَّن في نظام الملفات مع سجل ميتاداتا)."""
    try:
        # تحقّق من وجود المركبة في وضع Supabase
        if DB_PROVIDER == "supabase":
            v = supabase_service.vehicles_get(vehicle_id)
            if not v:
                raise HTTPException(status_code=404, detail="المركبة غير موجودة")

        # مجلد رفع الملفات العام موجود مسبقًا كـ UPLOAD_DIR
        vehicle_dir = UPLOAD_DIR / "vehicles" / vehicle_id
        vehicle_dir.mkdir(parents=True, exist_ok=True)

        # FIX-B027: فلتر نوع الملف (MIME)
        ALLOWED_CONTENT_TYPES = {
            "image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf",
        }
        if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(status_code=400, detail="نوع الملف غير مسموح به")

        # FIX-B006: حماية من Path Traversal — اسم ملف آمن وضمن مجلد المركبة
        original_name = file.filename or "upload.bin"
        safe_name = re.sub(
            r"[^A-Za-z0-9._\-\u0600-\u06FF]", "_", os.path.basename(original_name)
        )
        if not safe_name or safe_name in {".", ".."}:
            safe_name = f"upload-{uuid.uuid4().hex[:8]}.bin"
        file_path = vehicle_dir / safe_name
        if not str(file_path.resolve()).startswith(str(vehicle_dir.resolve())):
            raise HTTPException(status_code=400, detail="اسم ملف غير صالح")

        # FIX-B026: فحص الحجم قبل الكتابة (10MB)
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="الملف أكبر من الحد المسموح (10MB)")

        with open(file_path, "wb") as f:
            f.write(content)

        # حفظ سجل الملف في تخزين JSON (ذاكرة)
        rows = _mem_read("vehicle_files")
        record = {
            "id": str(uuid.uuid4()),
            "vehicleId": vehicle_id,
            "filename": safe_name,
            "fileType": file_type,
            "filePath": str(file_path),
            "uploadedAt": datetime.now(timezone.utc).isoformat(),
            "uploadedBy": "system",
        }
        rows.append(record)
        _mem_write("vehicle_files", rows)
        return record
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/vehicles/{vehicle_id}/files")
async def get_vehicle_files(vehicle_id: str):
    """إرجاع قائمة ملفات المركبة من تخزين JSON."""
    try:
        rows = _mem_read("vehicle_files")
        files = [r for r in rows if r.get("vehicleId") == vehicle_id]
        # أحدث الملفات أولاً
        files.sort(key=lambda x: x.get("uploadedAt") or "", reverse=True)
        return {"files": files, "count": len(files)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/vehicles/{vehicle_id}/files/{file_id}")
async def download_vehicle_file(vehicle_id: str, file_id: str):
    """تنزيل/عرض ملف معيّن لمركبة."""
    try:
        rows = _mem_read("vehicle_files")
        for r in rows:
            if r.get("id") == file_id and r.get("vehicleId") == vehicle_id:
                path = Path(r.get("filePath", ""))
                if not path.exists():
                    raise HTTPException(status_code=404, detail="الملف غير موجود")
                return FileResponse(str(path), filename=r.get("filename") or path.name)
        raise HTTPException(status_code=404, detail="الملف غير موجود")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))






@api_router.post("/parts/{part_id}/sell")
async def sell_part(part_id: str, quantity: int = 1):
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="الكمية غير صحيحة")
    if DB_PROVIDER == "supabase":
        res = (
            supabase_service.client.table("parts")
            .select("id, quantity")
            .eq("id", part_id)
            .limit(1)
            .execute()
        )
        part = (res.data or [None])[0]
        if not part:
            raise HTTPException(status_code=404, detail="القطعة غير موجودة")
        current_qty = int(part.get("quantity") or 0)
        if current_qty < quantity:
            raise HTTPException(status_code=400, detail="الكمية المطلوبة غير متوفرة")
        new_qty = current_qty - quantity
        supabase_service.client.table("parts").update({
            "quantity": new_qty,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", part_id).execute()
        return {"success": True, "new_quantity": new_qty}
    if DB_PROVIDER == "memory":
        parts = _mem_read("parts")
        for p in parts:
            if p.get("id") == part_id:
                current_qty = int(p.get("quantity") or 0)
                if current_qty < quantity:
                    raise HTTPException(status_code=400, detail="الكمية المطلوبة غير متوفرة")
                p["quantity"] = current_qty - quantity
                _mem_write("parts", parts)
                return {"success": True, "new_quantity": p["quantity"]}
        raise HTTPException(status_code=404, detail="القطعة غير موجودة")
    part = await db.parts.find_one({"id": part_id})
    if not part:
        raise HTTPException(status_code=404, detail="القطعة غير موجودة")
    current_qty = int(part.get("quantity") or 0)
    if current_qty < quantity:
        raise HTTPException(status_code=400, detail="الكمية المطلوبة غير متوفرة")
    new_qty = current_qty - quantity
    await db.parts.update_one({"id": part_id}, {"$set": {"quantity": new_qty, "updatedAt": datetime.utcnow().isoformat()}})
    part["quantity"] = new_qty
    part.pop("_id", None)
    return {"success": True, "part": part}


@api_router.post("/parts/{part_id}/restock")
async def restock_part(part_id: str, quantity: int = 1):
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="الكمية غير صحيحة")
    if DB_PROVIDER == "supabase":
        res = (
            supabase_service.client.table("parts")
            .select("id, quantity")
            .eq("id", part_id)
            .limit(1)
            .execute()
        )
        part = (res.data or [None])[0]
        if not part:
            raise HTTPException(status_code=404, detail="القطعة غير موجودة")
        current_qty = int(part.get("quantity") or 0)
        new_qty = current_qty + quantity
        supabase_service.client.table("parts").update({
            "quantity": new_qty,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", part_id).execute()
        return {"success": True, "new_quantity": new_qty}
    if DB_PROVIDER == "memory":
        parts = _mem_read("parts")
        for p in parts:
            if p.get("id") == part_id:
                current_qty = int(p.get("quantity") or 0)
                p["quantity"] = current_qty + quantity
                _mem_write("parts", parts)
                return {"success": True, "new_quantity": p["quantity"]}
        raise HTTPException(status_code=404, detail="القطعة غير موجودة")
    part = await db.parts.find_one({"id": part_id})
    if not part:
        raise HTTPException(status_code=404, detail="القطعة غير موجودة")
    current_qty = int(part.get("quantity") or 0)
    new_qty = current_qty + quantity
    await db.parts.update_one({"id": part_id}, {"$set": {"quantity": new_qty, "updatedAt": datetime.utcnow().isoformat()}})
    part["quantity"] = new_qty
    part.pop("_id", None)
    return {"success": True, "part": part}


@api_router.delete("/parts/{part_id}")
async def delete_part(part_id: str):
    if DB_PROVIDER == "supabase":
        supabase_service.parts_delete(part_id)
        return {"status": "success"}
    if DB_PROVIDER == "memory":
        parts = _mem_read("parts")
        parts = [p for p in parts if p.get("id") != part_id]
        _mem_write("parts", parts)
        return {"status": "success"}
    await db.parts.delete_one({"id": part_id})
    return {"status": "success"}


# 🆕 L5 DDD slice — Suppliers domain extracted to /app/backend/domains/suppliers/*
# (replaces ~265 lines of inline GET/POST/PUT/DELETE/migrate handlers).
# Helpers `_derive_suppliers_from_parts`, `_enrich_suppliers_from_accounts`,
# `_is_suppliers_table_missing`, and the global `SUPPLIERS_TABLE_AVAILABLE` flag
# are still defined above and consumed by domains.suppliers.repository.



@api_router.get("/stats")
async def get_stats():
    """Get dashboard statistics"""
    try:
        # Get current month data
        now = datetime.utcnow()
        first_day = datetime(now.year, now.month, 1)

        if DB_PROVIDER == "supabase":
            # Get transactions for current month
            transactions = supabase_service.transactions_list()

            # Calculate monthly stats
            monthly_income = sum(
                t.get("amount", 0)
                for t in transactions
                if t.get("type") == "income"
                and t.get("date", "").startswith(f"{now.year}-{now.month:02d}")
            )
            monthly_expenses = sum(
                t.get("amount", 0)
                for t in transactions
                if t.get("type") == "expense"
                and t.get("date", "").startswith(f"{now.year}-{now.month:02d}")
            )

            # Get vehicle stats
            vehicles = supabase_service.vehicles_list()
            active_vehicles = len(
                [
                    v
                    for v in vehicles
                    if v.get("status") not in ["delivered", "cancelled"]
                ]
            )

            # Get customer count
            customers = supabase_service.customers_list()

            return {
                "totalCustomers": len(customers),
                "activeVehicles": active_vehicles,
                "thisMonth": {
                    "income": monthly_income,
                    "expenses": monthly_expenses,
                    "profit": monthly_income - monthly_expenses,
                },
                "lastMonth": {"income": 0, "expenses": 0, "profit": 0},
            }

        if DB_PROVIDER == "memory":
            vehicles = _mem_read("vehicles")
            customers = _mem_read("customers")

            return {
                "totalCustomers": len(customers),
                "activeVehicles": len(
                    [
                        v
                        for v in vehicles
                        if v.get("status") not in ["delivered", "cancelled"]
                    ]
                ),
                "thisMonth": {"income": 0, "expenses": 0, "profit": 0},
                "lastMonth": {"income": 0, "expenses": 0, "profit": 0},
            }

        # MongoDB implementation
        vehicles = await db.vehicles.count_documents(
            {"status": {"$nin": ["delivered", "cancelled"]}}
        )
        customers = await db.customers.count_documents({})

        # Get transactions for this month
        transactions = await db.transactions.find(
            {"date": {"$gte": first_day}}
        ).to_list(10000)

        monthly_income = sum(
            t.get("amount", 0) for t in transactions if t.get("type") == "income"
        )
        monthly_expenses = sum(
            t.get("amount", 0) for t in transactions if t.get("type") == "expense"
        )

        return {
            "totalCustomers": customers,
            "activeVehicles": vehicles,
            "thisMonth": {
                "income": monthly_income,
                "expenses": monthly_expenses,
                "profit": monthly_income - monthly_expenses,
            },
            "lastMonth": {"income": 0, "expenses": 0, "profit": 0},
        }
    except Exception as e:
        print(f"Stats error: {e}")
        # Return default stats on error
        return {
            "totalCustomers": 0,
            "activeVehicles": 0,
            "thisMonth": {"income": 0, "expenses": 0, "profit": 0},
            "lastMonth": {"income": 0, "expenses": 0, "profit": 0},
        }


@api_router.get("/business-accounts")
async def get_business_accounts():
    if DB_PROVIDER == "supabase":
        rows = supabase_service.business_accounts_list()
        return rows
    if DB_PROVIDER == "memory":
        return _mem_read("business_accounts")
    accounts = await db.business_accounts.find({}, {"_id": 0}).to_list(1000)
    return accounts


@api_router.post("/business-accounts")
async def create_business_account(account: dict):
    if DB_PROVIDER == "supabase":
        acc = supabase_service.business_accounts_create(account)
        return acc
    if DB_PROVIDER == "memory":
        accounts = _mem_read("business_accounts")
        new_acc = {**account, "id": str(uuid.uuid4())}
        accounts.append(new_acc)
        _mem_write("business_accounts", accounts)
        return new_acc
    account["id"] = str(uuid.uuid4())
    await db.business_accounts.insert_one(account)
    account.pop("_id", None)  # drop the BSON ObjectId injected by insert_one (not JSON-serializable)
    return account


@api_router.get("/salaries")
async def get_salaries():
    """Get all salaries"""
    if DB_PROVIDER == "supabase":
        # Return empty list for now - payroll feature needs completion
        try:
            res = supabase_service.client.table("salaries").select("*").execute()
            return res.data or []
        except Exception:
            return []

    if DB_PROVIDER == "memory":
        return []

    # MongoDB
    try:
        salaries = await db.salaries.find({}, {"_id": 0}).to_list(1000)
        return salaries
    except Exception as e:
        print(f"Salaries error: {e}")
        return []


# 🆕 L5 DDD slice — Customers domain extracted to /app/backend/domains/customers/*
from domains.customers.router import router as customers_domain_router
api_router.include_router(customers_domain_router)

# 🆕 L5 DDD slice — Suppliers domain extracted to /app/backend/domains/suppliers/*
from domains.suppliers.router import router as suppliers_domain_router
api_router.include_router(suppliers_domain_router)

# Include the api_router
app.include_router(api_router)

# Add AI Financial Analysis route
from pydantic import BaseModel
from typing import Dict, Any


class FinancialAnalysisRequest(BaseModel):
    query: str
    financial_data: Dict[str, Any]


@app.post("/api/ai/financial-analysis")
async def financial_analysis(request: FinancialAnalysisRequest):
    """AI-powered financial analysis endpoint"""
    try:
        openai_key = os.getenv("OPENAI_API_KEY")

        if not openai_key:
            # Return mock analysis if no API key
            return {
                "analysis": generate_mock_financial_analysis(
                    request.query, request.financial_data
                )
            }

        import openai

        client = openai.OpenAI(api_key=openai_key)

        # Prepare context with financial data
        context = f"""
        أنت محلل مالي خبير متخصص في ورش السيارات والأعمال الصغيرة.
        
        البيانات المالية الحالية:
        - الإيرادات: {request.financial_data.get('revenue', 0):,.0f} ريال
        - المصروفات: {request.financial_data.get('expenses', 0):,.0f} ريال
        - صافي الربح: {request.financial_data.get('net_income', 0):,.0f} ريال
        - هامش الربح الإجمالي: {request.financial_data.get('gross_margin', 0):.1f}%
        - هامش صافي الربح: {request.financial_data.get('net_margin', 0):.1f}%
        - نسبة السيولة الحالية: {request.financial_data.get('current_ratio', 0):.2f}
        - نسبة الدين إلى حقوق الملكية: {request.financial_data.get('debt_to_equity', 0):.2f}
        - إجمالي الأصول: {request.financial_data.get('assets', 0):,.0f} ريال
        - إجمالي الالتزامات: {request.financial_data.get('liabilities', 0):,.0f} ريال
        - حقوق الملكية: {request.financial_data.get('equity', 0):,.0f} ريال
        
        التزم برد مختصر جداً: سطر ملخص + 3 نقاط ملاحظات + توصيتين فقط.
        أجب باللغة العربية بتنسيق Markdown خفيف.
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": context},
                {"role": "user", "content": request.query},
            ],
            temperature=0.4,
            max_tokens=400,
        )

        return {"analysis": response.choices[0].message.content}

    except Exception as e:
        logger.error(f"Financial analysis error: {e}")
        return {
            "analysis": generate_mock_financial_analysis(
                request.query, request.financial_data
            )
        }


def generate_mock_financial_analysis(query: str, data: Dict[str, Any]) -> str:
    """Generate mock financial analysis when API is unavailable"""
    gross_margin = data.get("gross_margin", 75.4)
    net_margin = data.get("net_margin", 11.9)
    current_ratio = data.get("current_ratio", 3.28)

    return f"""
**ملخص سريع:** الأداء جيد لكن يحتاج ضبط مصاريف لرفع الربحية.

**ملاحظات:**
- هامش الربح الإجمالي قوي ({gross_margin}%).
- هامش صافي الربح متوسط ({net_margin}%).
- السيولة ممتازة ({current_ratio}).

**توصيات:**
- خفّض المصاريف التشغيلية غير الضرورية.
- حسّن دورة التحصيل لرفع السيولة.
"""


# Add AI Chat route
@app.post("/api/ai/chat", response_model=ChatResponse)
async def chat_with_ai(chat_request: ChatRequest):
    try:
        session_id = chat_request.sessionId or str(uuid.uuid4())
        llm_key = os.getenv("EMERGENT_LLM_KEY")

        if not llm_key:
            return ChatResponse(
                response="مفتاح الذكاء الاصطناعي غير متوفر.", sessionId=session_id
            )

        chat = LlmChat(
            api_key=llm_key,
            session_id=session_id,
            system_message="أنت مساعد ذكي لورشة سيارات.",
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")

        response = await chat.send_message(UserMessage(text=chat_request.message))
        return ChatResponse(response=response, sessionId=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
