"""arabic_nlp — dialect-aware tokenisation + reference resolution for the
floating assistant.

Covers:
  • Modern Standard Arabic (فصحى)
  • Saudi Arabic
  • Qassimi (قصيمي): "ورّني" / "وش" / "للحين" / "طلّع" / "حقّه"
  • Yemeni (يمني):   "هات" / "وريني" / "حقّه" / "كم عليه"
  • Mixed Arabic/English

The goal here is shallow but useful: normalise common dialect words to
their MSA equivalent so the existing intent + entity patterns keep working
across dialects without exploding the regex catalogue.

NOT a real NER / morphological analyser — just rule-based normalisation.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple

# ---------- Dialect → MSA normaliser ----------

# Words that mean "show me / display / list" across dialects.
_SHOW_VERBS = [
    # MSA
    "اعرض", "أعرض", "اظهر", "أظهر", "أرني", "ارني",
    # Saudi / Qassimi
    "ورّني", "وريني", "ورني", "طلّع", "طلع", "خلّني\\s+اشوف", "اعطني",
    # Yemeni
    "هات", "هاتلي", "وريّني",
]

# Words that mean "what / how much" → normalize to "كم" or "ما".
_QUESTION_WORDS = {
    "وش": "ما",       # Saudi/Qassimi: وش عليه → ما عليه
    "ايش": "ما",      # Levantine/Saudi
    "إيش": "ما",
    "شو": "ما",       # Levantine
    "وين": "أين",     # Saudi: وين السيارة
    "كيف": "كيف",
    "للحين": "حتى الآن",  # Qassimi
    "لسا": "لا يزال",     # Levantine/Saudi
}

# Possessive markers that should be stripped (don't add meaning to entity search)
_POSSESSIVE_TAILS = ["حقّه", "حقه", "حقّها", "حقها", "حقّي", "حقي", "بتاع", "بتاعة", "تبع", "تبعه"]

# Pronouns that mean "this / last / previous"
_REFERENCE_WORDS = [
    "السابق", "السابقة", "الأخير", "الأخيرة", "آخر", "الماضي", "الماضية",
    "اعرضه", "اعرضها", "ارسلها", "أرسلها", "ارسله", "أرسله",
    "اطبعها", "أطبعها", "اطبعه", "أطبعه",
    "اعتمدها", "اعتمده", "وافق", "وافقت",
    "هذا", "هذه", "ذاك", "تلك", "ذي",
]

# Pre-compile a single regex that strips/normalises noise in one pass.
_VERB_RE = re.compile(r"\b(" + "|".join(_SHOW_VERBS) + r")\b", re.IGNORECASE)
_TAIL_RE = re.compile(r"\b(" + "|".join(map(re.escape, _POSSESSIVE_TAILS)) + r")\b", re.IGNORECASE)
_QUESTION_RE = re.compile(r"\b(" + "|".join(map(re.escape, list(_QUESTION_WORDS.keys()))) + r")\b", re.IGNORECASE)


def normalise(text: str) -> str:
    """Return an MSA-normalised version of `text` suitable for regex intent
    detection. Idempotent. Preserves the original meaning.
    """
    if not text:
        return ""
    s = text.strip()
    # 1) Replace dialect question words with MSA equivalents
    def _q_sub(m):
        return _QUESTION_WORDS.get(m.group(0), m.group(0))
    s = _QUESTION_RE.sub(_q_sub, s)
    # 2) Normalise all dialect "show me" verbs to "اعرض" so intent regex hits
    s = _VERB_RE.sub("اعرض", s)
    # 3) Drop possessive trailers ("حقّه" etc.)
    s = _TAIL_RE.sub(" ", s)
    # 4) Compact whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ---------- Reference resolution ----------

_REF_PATTERN = re.compile(r"\b(" + "|".join(map(re.escape, _REFERENCE_WORDS)) + r")\b", re.IGNORECASE)


def detect_reference(text: str) -> Optional[str]:
    """Returns the matched reference word (e.g. "السابق") if `text` contains
    a pronoun/reference that points back to a previously-mentioned entity.
    """
    if not text:
        return None
    m = _REF_PATTERN.search(text)
    return m.group(0) if m else None


def resolve_reference(text: str, memory: Dict[str, dict]) -> Optional[Tuple[str, dict]]:
    """If `text` contains a reference word, return the matching last_*
    entity from `memory`. Heuristic mapping:
      • "فاتورة" / "اعتمدها" / "ارسلها"      → last_invoice
      • "عميل" / "زبون"                       → last_customer
      • "مركبة" / "سيارة" / "اللوحة"          → last_vehicle
      • "مورد"                                → last_supplier
      • "زيارة"                               → last_visit
      • "عملية"                               → last_operation
      • (default — pronoun-only)              → most-recently-touched
    """
    if not text or not memory:
        return None
    if not detect_reference(text):
        return None
    t = text.lower()
    candidates = []
    if any(w in t for w in ("فاتورة", "الفاتورة", "اعتمد", "ارسل", "اطبع")):
        candidates.append("last_invoice")
    if any(w in t for w in ("عميل", "العميل", "زبون")):
        candidates.append("last_customer")
    if any(w in t for w in ("مركبة", "المركبة", "سيارة", "السيارة", "لوحة", "اللوحة")):
        candidates.append("last_vehicle")
    if "مورد" in t:
        candidates.append("last_supplier")
    if "زيارة" in t or "الزيارة" in t:
        candidates.append("last_visit")
    if "عملية" in t or "العملية" in t:
        candidates.append("last_operation")
    # Generic pronoun (e.g., "السابق", "اعرضه") — fall back to the most-recent
    if not candidates:
        candidates = ["last_invoice", "last_customer", "last_vehicle", "last_operation",
                      "last_supplier", "last_visit"]
    for key in candidates:
        ent = memory.get(key)
        if ent:
            return key, ent
    return None


# ---------- Lightweight entity extraction ----------

_PLATE_RE = re.compile(r"\b(?:لوحة\s*)?([أ-يa-zA-Z]?\s*\d{3,4}\s*[أ-يa-zA-Z]?\s*[أ-يa-zA-Z]?\s*[أ-يa-zA-Z]?)\b")
_PHONE_RE = re.compile(r"\b(05\d{8}|009665\d{8}|\+9665\d{8})\b")
_AMOUNT_RE = re.compile(r"\b(\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?\s*(?:ر(?:يال)?|sar|ريال|﷼)?\b", re.IGNORECASE)
_INVOICE_RE = re.compile(r"\b(?:فاتورة|inv|invoice|رقم)\s*[#:]?\s*([A-Za-z0-9\-]{3,})\b", re.IGNORECASE)


def extract_entities(text: str) -> Dict[str, List[str]]:
    """Extract candidate entity tokens from `text` — purely regex-based.

    Returns a dict like:
      {"plate": ["1234 أ ب ج"], "phone": ["0551234567"], "amount": ["500"],
       "invoice": ["INV-001"]}

    No DB lookups happen here; the caller decides what to do with the
    candidates (e.g., pass to `vehicles.search(query=plate)`).
    """
    out: Dict[str, List[str]] = {"plate": [], "phone": [], "amount": [], "invoice": []}
    if not text:
        return out

    for m in _PLATE_RE.finditer(text):
        token = m.group(1).strip()
        # Skip tokens that look more like phone numbers / amounts
        if len(re.sub(r"\D", "", token)) >= 7:
            continue
        if token and token not in out["plate"]:
            out["plate"].append(token)

    for m in _PHONE_RE.finditer(text):
        if m.group(0) not in out["phone"]:
            out["phone"].append(m.group(0))

    for m in _AMOUNT_RE.finditer(text):
        raw = m.group(1).replace(",", "")
        try:
            n = float(raw)
            if 1 <= n <= 10_000_000 and raw not in out["amount"]:
                out["amount"].append(raw)
        except Exception:
            pass

    for m in _INVOICE_RE.finditer(text):
        if m.group(1) not in out["invoice"]:
            out["invoice"].append(m.group(1))

    return out


# ---------- Intent classification (V2 — broader than V1 regex catalogue) ----------

# Maps a high-level intent label → list of regex patterns that match it.
# These intents are detected ONLY for classification/audit; whether the
# corresponding action runs (create/delete/etc.) is gated by the Phase 3C
# Action Runtime that is NOT enabled yet.
_INTENT_V2_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # CREATE
    (re.compile(r"(أنشئ|انشئ|اضف|أضف|سجّل|سجل|أدخل|ادخل|create|add|new)\s+(زيار|مركب|عمل|بند|قطع|فاتور|عميل|مورد)", re.IGNORECASE), "create"),
    # UPDATE
    (re.compile(r"(عدّل|عدل|حدّث|حدث|غيّر|غير|update|edit)", re.IGNORECASE), "update"),
    # DELETE
    (re.compile(r"(احذف|أحذف|ألغ|الغ|delete|cancel|remove)", re.IGNORECASE), "delete"),
    # AUDIT
    (re.compile(r"(دقّق|دقق|راجع|audit|inspect|review|investigate)", re.IGNORECASE), "audit"),
    # APPROVE
    (re.compile(r"(اعتمد|أعتمد|وافق|approve|confirm\s+approval)", re.IGNORECASE), "approve"),
    # REJECT
    (re.compile(r"(ارفض|أرفض|reject|deny|اعترض)", re.IGNORECASE), "reject"),
    # SEND
    (re.compile(r"(ارسل|أرسل|send|whatsapp|واتساب|إيميل|email|أرسلها)", re.IGNORECASE), "send"),
    # GENERATE / EXPORT
    (re.compile(r"(انتج|أنتج|أصدر|اصدر|generate|export|pdf|excel|اطبع|طباعة|print)", re.IGNORECASE), "generate"),
    # COMPARE
    (re.compile(r"(قارن|قارني|قارن\s+ب|compare)", re.IGNORECASE), "compare"),
    # ANALYZE
    (re.compile(r"(حلل|حلّل|تحليل|analyze|analyse)", re.IGNORECASE), "analyze"),
    # FORECAST
    (re.compile(r"(توقّع|توقع|forecast|projected|تنبؤ)", re.IGNORECASE), "forecast"),
    # SEARCH (broadest — matches as fallback for any other intent)
    (re.compile(r"(ابحث|أبحث|search|find|اعرض|اظهر|أرني|كم|ما|من|أكثر|أعلى|أقل|متى|أين)", re.IGNORECASE), "search"),
]


def classify_intent_v2(text: str) -> str:
    """Classifies the user's intent into one of the V2 categories.

    Returns the FIRST matching label. Intents are checked in order of
    specificity (create > update > delete > audit > … > search). Defaults
    to "other".
    """
    if not text:
        return "other"
    norm = normalise(text)
    for pattern, label in _INTENT_V2_PATTERNS:
        if pattern.search(norm) or pattern.search(text):
            return label
    return "other"


# ---------- Natural Language ERP Search hints ----------

# Maps a free-form Arabic question to a (tool, args) tuple that should fire.
# These are *strong* signals that complement the existing _TOOL_PATTERNS;
# they are checked separately in assistant_kernel.chat().
NLP_SEARCH_HINTS: List[Tuple[re.Pattern, str, Dict[str, str]]] = [
    (re.compile(r"(أكثر|اعلى|أعلى)\s+(?:ال)?عملاء\s+مديوني", re.IGNORECASE), "finance.ar_summary", {}),
    (re.compile(r"(?:ال)?فواتير\s+(?:ال)?متأخر", re.IGNORECASE), "operations.recent", {"limit": "10"}),
    (re.compile(r"(?:ال)?مركبات\s+داخل\s+(?:ال)?ورشة", re.IGNORECASE), "workshop.active_visits", {}),
    (re.compile(r"(?:ال)?زيارات\s+(?:ال)?مفتوح", re.IGNORECASE), "workshop.active_visits", {}),
    (re.compile(r"(?:ال)?مخزون\s+(?:ال)?ناقص", re.IGNORECASE), "inventory.low_stock", {}),
    (re.compile(r"(أعلى|اعلى)\s+(?:ال)?مورد", re.IGNORECASE), "finance.payables_summary", {}),
    (re.compile(r"(أرباح|إيرادات|ربحية)\s+(?:هذا\s+)?(اليوم|الشهر|الأسبوع)", re.IGNORECASE), "firewall.cash_flow", {}),
    (re.compile(r"(?:ال)?تدفّ?ق\s+(?:ال)?نقد", re.IGNORECASE), "firewall.cash_flow", {}),
    (re.compile(r"(?:ال)?صحة\s+(?:ال)?مالي", re.IGNORECASE), "firewall.health_score", {}),
]


def nlp_search_hint(text: str) -> Optional[Tuple[str, Dict[str, str]]]:
    """If `text` matches a known NLP search query, return (tool_name, args)."""
    if not text:
        return None
    norm = normalise(text)
    for pattern, tool, args in NLP_SEARCH_HINTS:
        if pattern.search(norm) or pattern.search(text):
            return tool, args
    return None



# ---------- Arabic text normalisation for robust/tolerant search ----------

# Strip harakat (tashkeel), dagger alef, Quranic marks, etc.
_TASHKEEL_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_TATWEEL_RE = re.compile(r"\u0640")

# Variant → canonical letter map (hamza/alef/taa-marbuta/alef-maqsura forms).
_LETTER_MAP = {
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ٲ": "ا", "ٵ": "ا",
    "ة": "ه",
    "ى": "ي", "ئ": "ي", "ي": "ي",
    "ؤ": "و",
    "ﻷ": "لا", "ﻵ": "لا", "ﻹ": "لا", "ﻻ": "لا",
    "ک": "ك", "گ": "ك",
    "ٹ": "ت", "ﺔ": "ه",
    "ۀ": "ه",
}

# Arabic-Indic & Persian digits → ASCII so "٠٥٠" matches "050".
_DIGIT_MAP = {
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
}

_AR_STOPWORDS = {
    "عن", "في", "من", "الى", "إلى", "على", "هل", "كم", "ما", "او", "أو", "و",
    "ابحث", "ابي", "ابغى", "ودي", "اعرض", "اعطني", "رقم", "اسم", "بيانات",
    "عميل", "العميل", "زبون", "الزبون", "مركبه", "المركبه", "سياره", "السياره",
    "عمليه", "العمليه", "عمليات", "العمليات", "مورد", "المورد", "قطعه", "القطعه",
}


def normalize_arabic(text: str) -> str:
    """Normalise Arabic text for tolerant matching:
      • strip tashkeel + tatweel
      • unify alef/hamza variants (أإآٱ → ا), ة → ه, ى/ئ → ي, ؤ → و
      • convert Arabic-Indic digits → ASCII
      • lowercase latin + collapse whitespace
    Idempotent. Safe on mixed Arabic/English/numbers.
    """
    if not text:
        return ""
    s = str(text)
    s = _TASHKEEL_RE.sub("", s)
    s = _TATWEEL_RE.sub("", s)
    s = "".join(_LETTER_MAP.get(ch, _DIGIT_MAP.get(ch, ch)) for ch in s)
    s = s.lower()
    # unify the common "عبد ال..." compound: «عبد العزيز» ↔ «عبدالعزيز»
    s = re.sub(r"\bعبد\s+(?=ال)", "عبد", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def arabic_tokens(text: str) -> List[str]:
    """Normalised, article-insensitive, stopword-free tokens for matching."""
    norm = normalize_arabic(text)
    toks: List[str] = []
    for t in norm.split():
        base = t
        # Strip leading definite article "ال" for 4+ char words so
        # "المصري" matches "مصري" and vice-versa.
        if len(t) >= 4 and t.startswith("ال"):
            base = t[2:]
        if base in _AR_STOPWORDS or t in _AR_STOPWORDS:
            continue
        if len(base) >= 2:
            toks.append(base)
    return toks


def arabic_match(query: str, *fields: object) -> bool:
    """True if EVERY meaningful query token appears (normalised,
    hamza/article-insensitive) somewhere in the concatenated fields.

    Falls back to a full normalised-substring check when the query has no
    meaningful tokens (e.g. a bare plate number or a single stopword).
    """
    haystack = normalize_arabic(" ".join(str(f or "") for f in fields))
    if not haystack:
        return False
    toks = arabic_tokens(query)
    if not toks:
        nq = normalize_arabic(query)
        return bool(nq) and nq in haystack
    return all(t in haystack for t in toks)
