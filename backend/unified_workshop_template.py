"""مصدر القالب الموحّد النهائي: ملف HTML المرجعي كما أرسله المستخدم."""

from pathlib import Path


def _reference_template() -> str:
    return (Path(__file__).parent / "templates" / "reference_workshop_template.html").read_text(encoding="utf-8")


def unified_workshop_template(doc_type: str = "invoice") -> str:
    return _reference_template()