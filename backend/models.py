from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime
import uuid


# ============ Vehicle Models ============
class VehicleBase(BaseModel):
    plateNumber: str
    brand: str
    model: str
    year: int
    color: str
    vin: Optional[str] = None  # رقم الهيكل اختياري
    fileNumber: Optional[str] = None  # رقم الملف
    customerName: str
    customerPhone: str
    customerEmail: Optional[str] = None
    customerFileNumber: Optional[str] = None
    services: List[str] = []
    technicianId: Optional[str] = None
    technicianName: Optional[str] = None
    notes: Optional[str] = None


class VehicleCreate(VehicleBase):
    pass


class Vehicle(VehicleBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customerId: str
    status: str = "diagnosis"  # diagnosis, quotation, repair, ready
    entryDate: datetime = Field(default_factory=datetime.utcnow)
    estimatedCompletion: Optional[datetime] = None
    completionDate: Optional[datetime] = None
    trackingLink: str
    images: List[str] = []  # URLs للصور
    parts: List[Any] = []  # بنود مرتبطة (خدمات/قطع) أو IDs
    estimatedTotal: Optional[float] = None  # المبلغ التقديري المحسوب من البنود

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class VehicleUpdate(BaseModel):
    plateNumber: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    color: Optional[str] = None
    vin: Optional[str] = None
    status: Optional[str] = None
    technicianId: Optional[str] = None
    notes: Optional[str] = None
    fileNumber: Optional[str] = None
    customerName: Optional[str] = None
    customerPhone: Optional[str] = None
    customerEmail: Optional[str] = None
    estimatedCompletion: Optional[datetime] = None
    completionDate: Optional[datetime] = None
    images: Optional[List[str]] = None
    services: Optional[List[str]] = None
    parts: Optional[List[Any]] = None
    customerFileNumber: Optional[str] = None


# ============ Customer Models ============
class CustomerBase(BaseModel):
    name: str
    phone: str
    fileNumber: Optional[str] = None  # رقم الملف
    email: Optional[str] = None
    address: Optional[str] = None
    vehicleBrand: Optional[str] = None  # نوع المركبة
    vehiclePlate: Optional[str] = None  # رقم اللوحة
    vehicleKm: Optional[int] = None  # الكيلومتر


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    fileNumber: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    vehicleBrand: Optional[str] = None
    vehiclePlate: Optional[str] = None
    vehicleKm: Optional[int] = None


class Customer(CustomerBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vehicles: List[str] = []  # رقم اللوحات
    totalVisits: int = 0
    lastVisit: Optional[datetime] = None
    createdAt: Optional[datetime] = None
    creditLimit: Optional[float] = 10000  # حد الائتمان
    balance: Optional[float] = 0  # الرصيد المستحق
    debitBalance: Optional[float] = 0
    creditBalance: Optional[float] = 0
    overdueBalance: Optional[float] = 0
    ajelBalance: Optional[float] = 0
    settledAmount: Optional[float] = 0
    paymentPlanCount: Optional[int] = 0
    netBalance: Optional[float] = 0
    movements: Optional[List[Any]] = []

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ============ Technician Models ============
class Technician(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    phone: str
    specialty: str
    activeJobs: int = 0
    completedJobs: int = 0
    rating: float = 5.0


# ============ Service Models ============
class Service(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    category: str
    price: float
    duration: int  # بالدقائق
    laborCost: Optional[float] = 0  # تكلفة العمالة
    active: Optional[bool] = True


# ============ Parts (قطع الغيار) Models ============
class PartBase(BaseModel):
    partNumber: str  # رقم القطعة
    name: str
    category: str
    purchasePrice: float  # سعر الشراء
    sellingPrice: float  # سعر البيع
    quantity: int
    minQuantity: int = 5  # الحد الأدنى للتنبيه
    supplier: Optional[str] = None
    image: Optional[str] = None


class PartCreate(PartBase):
    pass


class Part(PartBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class PartUpdate(BaseModel):
    name: Optional[str] = None
    purchasePrice: Optional[float] = None
    sellingPrice: Optional[float] = None
    quantity: Optional[int] = None
    minQuantity: Optional[int] = None
    supplier: Optional[str] = None
    image: Optional[str] = None


# ============ Supplier Models ==========
class SupplierBase(BaseModel):
    name: str
    phone: Optional[str] = None
    contactPerson: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    category: Optional[str] = None
    rating: Optional[float] = 5.0


class SupplierCreate(SupplierBase):
    pass


class Supplier(SupplierBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    balance: Optional[float] = 0
    debitBalance: Optional[float] = 0
    creditBalance: Optional[float] = 0
    overdueBalance: Optional[float] = 0
    ajelBalance: Optional[float] = 0
    settledAmount: Optional[float] = 0
    paymentPlanCount: Optional[int] = 0
    netBalance: Optional[float] = 0
    movements: Optional[List[Any]] = []

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    contactPerson: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    category: Optional[str] = None
    rating: Optional[float] = None


# ============ Invoice Models ============
class InvoiceItem(BaseModel):
    type: str  # "service" or "part"
    itemId: str
    name: str
    quantity: int = 1
    price: float
    total: float


class InvoiceBase(BaseModel):
    vehicleId: str
    customerId: str
    type: str  # "diagnosis" (تشخيص), "quotation" (تسعيرة), "service" (فاتورة خدمة)
    items: List[InvoiceItem]
    subtotal: float
    tax: float = 0.0  # Default 0% VAT per current settings

    tax: float = 0.15  # 15% ضريبة
    total: float
    paymentMethod: str  # "cash" (كاش) or "card" (شبكة)
    notes: Optional[str] = None


class InvoiceCreate(InvoiceBase):
    pass


class Invoice(InvoiceBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    invoiceNumber: str  # رقم الفاتورة
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    status: str = "pending"  # pending, paid, cancelled

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ============ Transaction Models (المبيعات والمصروفات) ============
class TransactionBase(BaseModel):
    type: str  # "income" (مبيعات) or "expense" (مصروفات)
    category: str  # للمصروفات: "rent", "salaries", "utilities", "parts", etc.
    amount: float
    description: str
    paymentMethod: Optional[str] = None
    reference: Optional[str] = None  # رقم الفاتورة أو المرجع
    accountId: Optional[str] = None  # للربط بالفروع
    paymentStatus: Optional[str] = "paid"  # paid, unpaid, pending
    linkedAccounts: Optional[List[dict]] = []  # القيود المحاسبية


class TransactionCreate(TransactionBase):
    pass


class Transaction(TransactionBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: datetime = Field(default_factory=datetime.utcnow)
    createdBy: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ============ AI Chat Models ============
class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    messages: List[ChatMessage] = []
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ChatRequest(BaseModel):
    message: str
    sessionId: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    sessionId: str
