"""🔐 منقّح PDPL — إخفاء المعرّفات الشخصية قبل إرسال أي نص لمزوّد LLM خارجي.

يُطبَّق مركزياً في `_llm_chat` على system_message و msg_text معاً، فيغطي
brief السياق ونتائج الأدوات وتاريخ المحادثة تلقائياً.
ملاحظة معمارية: رسالة المستخدم داخل llm_intent_parser لا تُنقّح — أدخلها
المستخدم بنفسه وقد يعتمد استخراج النية عليها (جوال زيارة مثلاً)؛ خطر PDPL
الأساسي هو تسريب بيانات قاعدة النظام وليس ما كتبه المستخدم لتوّه.
"""
import re

# جوال سعودي (05xxxxxxxx أو +9665xxxxxxxx أو 9665xxxxxxxx)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?966\s?5|05)\d{8}(?!\d)")
# هوية وطنية/إقامة: 10 أرقام تبدأ بـ 1 أو 2
_NID_RE = re.compile(r"(?<!\d)[12]\d{9}(?!\d)")
# آيبان سعودي
_IBAN_RE = re.compile(r"\bSA\d{22}\b", re.IGNORECASE)
# بريد إلكتروني
_EMAIL_RE = re.compile(r"\b([\w.+-]{1,2})[\w.+-]*@([\w-]+\.[\w.]+)\b")
# بطاقة (13-16 رقم متصل أو بفواصل)
_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,16}(?!\d)")


def _mask_keep_tail(m: re.Match, keep: int = 4, prefix: str = "") -> str:
    s = re.sub(r"\D", "", m.group(0))
    return f"{prefix}****{s[-keep:]}"


def redact_pii(text: str) -> str:
    """يخفي الجوال/الهوية/الآيبان/البريد/البطاقات مع إبقاء ذيل تعريفي قصير."""
    if not text:
        return text
    t = str(text)
    t = _IBAN_RE.sub(lambda m: f"SA****{m.group(0)[-4:]}", t)
    t = _CARD_RE.sub(lambda m: _mask_keep_tail(m, keep=4, prefix="💳") if len(re.sub(r"\D", "", m.group(0))) >= 13 else m.group(0), t)
    t = _PHONE_RE.sub(lambda m: _mask_keep_tail(m, keep=4, prefix="05"), t)
    t = _NID_RE.sub(lambda m: _mask_keep_tail(m, keep=2, prefix=m.group(0)[0]), t)
    t = _EMAIL_RE.sub(lambda m: f"{m.group(1)}***@{m.group(2)}", t)
    return t
