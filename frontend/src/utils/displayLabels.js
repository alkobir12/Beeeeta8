const UUID_LIKE_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export const ACCOUNT_NAME_MAP = {
  '001': 'الأصول',
  '003': 'النقد',
  '004': 'البنك',
  '005': 'العملاء (ذمم مدينة)',
  '006': 'نقاط بيع',
  '010': 'معدات ميكانيكية',
  '022': 'مسحوبات المالك',
  '025': 'الإيرادات',
  '026': 'إيرادات الخدمات',
  '027': 'إيرادات خدمات ميكانيكية',
  '028': 'إيرادات إصلاح محركات',
  '029': 'إيرادات فرامل وتعليق',
  '030': 'تكلفة الخدمات',
  '031': 'تكاليف مباشرة',
  '034': 'المصروفات التشغيلية',
  '035': 'مصروفات عامة وإدارية',
  '036': 'رواتب إدارية',
  '042': 'إيراد قطع الورشة',
  '0421': 'تكلفة قطع الورشة',
  '2101': 'الموردون (ذمم دائنة)',
};

export const OPERATION_TYPE_LABELS = {
  sale: 'بيع',
  service: 'خدمة مركبة',
  purchase: 'شراء',
  expense: 'مصروف نقدي',
  payment_order: 'سداد مستحقات',
  receipt_voucher: 'سند قبض',
  settlement: 'تسوية',
  sale_return: 'مرتجع بيع',
  purchase_return: 'مرتجع شراء',
  instant_sale: 'بيع فوري',
  salary: 'رواتب',
  cash_expense: 'صرف نقدي',
  collect_customer: 'تحصيل من عميل',
  pay_supplier: 'سداد لمورد',
  bank_deposit: 'إيداع بنكي',
};

export const PAYMENT_METHOD_LABELS = {
  cash: 'نقدي',
  transfer: 'تحويل بنكي',
  bank: 'بنك',
  card: 'بطاقة / نقاط بيع',
  pos: 'نقاط بيع',
  mada: 'مدى',
  visa: 'بطاقة فيزا',
  mastercard: 'بطاقة ماستر',
  credit: 'آجل',
  supplier_balance: 'رصيد مورد',
};

export const PAYMENT_STATUS_LABELS = {
  paid: 'مدفوع',
  paid_full: 'مسدد بالكامل',
  full: 'مسدد بالكامل',
  unpaid: 'غير مسدد',
  credit: 'آجل',
  deferred: 'مؤجل',
  partial: 'مدفوع جزئياً',
  pending: 'قيد الانتظار',
};

export const STATUS_LABELS = {
  issued: 'صادرة',
  draft: 'مسودة',
  posted: 'مرحّل',
  in_progress: 'جارية',
  completed: 'مكتملة',
  diagnosis: 'تشخيص',
  quotation: 'تسعير',
  approved: 'معتمد',
  repair: 'إصلاح',
  ready: 'جاهزة',
  delivered: 'تم التسليم',
  waiting_approval: 'بانتظار الموافقة',
};

export const PARTNER_TYPE_LABELS = {
  customer: 'عميل',
  supplier: 'مورد',
  open: 'طرف مفتوح',
};

export const SOURCE_LABELS = {
  operation: 'عملية',
  vehicle_visit_sync: 'زيارة مركبة',
  operation_cogs: 'تكلفة بضاعة مباعة',
  parts_pos: 'نقطة بيع القطع',
  rakan_parts_pos: 'نقطة بيع القطع',
  smart_pos_operation: 'POS الذكي',
  visit_receipt_voucher: 'سند قبض زيارة',
  operation_payment: 'سداد عملية',
  operation_payment_income: 'تحصيل عملية',
  supplier_balance_payment: 'سداد رصيد مورد',
  operation_rakan_parts: 'عملية قطع',
  workshop_operation: 'عملية ورشة',
  vehicle_operation: 'عملية مركبة',
  manual: 'يدوي',
};

export const LEGACY_TO_NEW_CODE = {
  "1101": "003",
  "1102": "004",
  "1103": "005",
  "1104": "006",
  "4000": "025",
  "4100": "026",
  "5000": "030",
  "5100": "031",
  "6000": "034",
  "6100": "035",
  "6101": "036",
  "3102": "022",
  "1201": "010",
};

export const normalizeAccountCode = (value) => {
  let raw = String(value || '').trim();
  if (!raw) return '';
  if (raw.startsWith('acc-') && /^acc-\d+$/.test(raw)) raw = raw.replace('acc-', '');
  return LEGACY_TO_NEW_CODE[raw] || raw;
};

export const isRawIdentifier = (value) => {
  const raw = String(value || '').trim();
  if (!raw) return false;
  return UUID_LIKE_REGEX.test(raw) || /^acc-[0-9a-f-]{8,}$/i.test(raw);
};

export const labelFromMap = (value, map, fallback = 'غير محدد') => {
  const key = String(value || '').trim().toLowerCase();
  if (!key) return fallback;
  return map[key] || map[String(value || '').trim()] || (isRawIdentifier(value) ? fallback : String(value));
};

export const formatVisitNumber = (value, fallback = '') => {
  const raw = String(value || '').trim();
  if (!raw) return fallback;
  if (/^\d+$/.test(raw)) return raw.padStart(3, '0');
  return isRawIdentifier(raw) ? (fallback || 'زيارة مرتبطة') : raw;
};

export const resolveVisitDisplay = (operationOrVisit = {}, fallback = 'غير محددة') => {
  const direct = operationOrVisit.visitNumberDisplay || operationOrVisit.visit_number_display;
  if (direct) return formatVisitNumber(direct, fallback);
  const number = operationOrVisit.visitNumber || operationOrVisit.visit_number;
  if (number) return formatVisitNumber(number, fallback);
  const visitId = operationOrVisit.visitId || operationOrVisit.visit_id || operationOrVisit.id;
  return formatVisitNumber(visitId, fallback);
};

export const cleanAccountingText = (value = '') => {
  if (!value) return '';
  return String(value)
    .replace(/\[IDEMP:[^\]]+\]/gi, '')
    .replace(/\[PAYMENT_RECEIPT\]\s*\S+/gi, '')
    .replace(/ACCOUNT_CODE:\s*\S+/gi, '')
    .replace(/ACCOUNTING_TARGET:\s*[^|\n]+/gi, '')
    .replace(/ACCOUNTING_SOURCE:\s*\S+/gi, '')
    .replace(/ACCOUNT_NAME:\s*[^|\n]+/gi, '')
    .replace(/ACCOUNT_CLASS:\s*\S+/gi, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
};

export const extractAccountMetaFromNotes = (notes = '') => {
  const text = String(notes || '');
  const codeMatch = text.match(/ACCOUNT_CODE\s*:\s*([^\s|]+)/i);
  const targetMatch = text.match(/ACCOUNTING_TARGET\s*:\s*([^|\n]+)/i);
  return {
    code: normalizeAccountCode(codeMatch?.[1] || ''),
    name: cleanAccountingText(targetMatch?.[1] || ''),
  };
};

export const resolveAccountDisplay = (operation = {}, accounts = [], businessAccounts = []) => {
  const noteMeta = extractAccountMetaFromNotes(operation.notes);
  const refs = [
    operation.accountingAccountId,
    operation.accounting_account_id,
    operation.accountCode,
    operation.account_code,
    operation.account,
    noteMeta.code,
    operation.accountId,
    operation.account_id,
  ].filter(Boolean).map((v) => String(v).trim());

  const allAccounts = Array.isArray(accounts) ? accounts : [];
  const matchedChart = allAccounts.find((acc) => {
    const accRefs = [acc.id, acc.code, normalizeAccountCode(acc.code), normalizeAccountCode(acc.id)].filter(Boolean).map(String);
    return refs.some((ref) => accRefs.includes(ref) || accRefs.includes(normalizeAccountCode(ref)));
  });

  const directName = operation.accountName || operation.account_name || operation.accountLabel || operation.account_label;
  let code = normalizeAccountCode(
    operation.accountCode ||
    operation.account_code ||
    matchedChart?.code ||
    noteMeta.code ||
    operation.accountingAccountId ||
    operation.accounting_account_id ||
    ''
  );

  let name = directName || matchedChart?.name_ar || matchedChart?.name || ACCOUNT_NAME_MAP[code] || noteMeta.name || '';
  if (!name || isRawIdentifier(name) || name === code) {
    name = ACCOUNT_NAME_MAP[code] || '';
  }

  if (!name) {
    const businessMatch = (businessAccounts || []).find((acc) => refs.includes(String(acc.id || acc.code || '')));
    if (businessMatch && !isRawIdentifier(businessMatch.name || businessMatch.code)) {
      name = businessMatch.name || businessMatch.code;
    }
  }

  if (!name) {
    const type = String(operation.type || '').toLowerCase();
    const partnerType = String(operation.partnerType || operation.partner_type || '').toLowerCase();
    if (['sale', 'service', 'sale_return'].includes(type)) name = 'إيرادات الخدمات';
    else if (['purchase', 'expense', 'purchase_return'].includes(type)) name = 'مصروفات / مشتريات';
    else if (type === 'payment_order' && partnerType === 'supplier') name = 'الموردون';
    else if (type === 'payment_order') name = 'العملاء';
    else name = 'الحساب غير محدد';
  }

  if (!code && name) {
    const compactName = String(name).replace(/\s+/g, ' ').trim();
    const reverseMatch = Object.entries(ACCOUNT_NAME_MAP).find(([, label]) => String(label).replace(/\s+/g, ' ').trim() === compactName);
    if (reverseMatch) code = reverseMatch[0];
    else if (/إيراد|ايراد|خدمات/i.test(compactName)) code = '026';
    else if (/مصروف|تكلفة/i.test(compactName)) code = '034';
    else if (/رواتب/i.test(compactName)) code = '036';
    else if (/مورد/i.test(compactName)) code = '2101';
    else if (/عميل|ذمم مدينة/i.test(compactName)) code = '005';
  }

  return {
    code: code && !isRawIdentifier(code) ? code : '',
    name: cleanAccountingText(name) || 'الحساب غير محدد',
  };
};

export const resolveVehicleDisplay = (operation = {}, vehicles = []) => {
  const vehicleId = operation.vehicleId || operation.vehicle_id;
  const vehicle = (vehicles || []).find((v) => String(v.id) === String(vehicleId));
  const plate = vehicle?.plateNumber || vehicle?.plate_number || operation.vehiclePlate || operation.vehicle_plate;
  const brand = vehicle?.brand || operation.vehicleBrand || operation.vehicle_brand || '';
  const model = vehicle?.model || operation.vehicleModel || operation.vehicle_model || '';
  const label = `${plate || ''} ${brand || ''} ${model || ''}`.trim();
  if (label) return label;
  return vehicleId ? 'مركبة مرتبطة' : 'غير محدد';
};