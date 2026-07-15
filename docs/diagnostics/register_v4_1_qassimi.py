"""Register v4.1-qassimi-mirror (INACTIVE) — v4 + قاعدة أمانة الأرقام الحرفية.
سبب النسخة: بنك الأسلوب كشف إسقاط الإشارة السالبة (-13,406→13,406) واشتقاق فرق حسابي (3,756)."""
import sys, os
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from pymongo import MongoClient
from core import prompt_registry

db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
V4 = db.prompt_versions.find_one({"version": "v4-qassimi-mirror"})["content"]

OLD = "  • **اللهجة لا تغيّر المحتوى أبداً**: الأرقام تبقى كما هي حرفياً، المصطلحات التقنية والمحاسبية بصيغتها الصحيحة ولا تُستبدل بعامية، والحقائق والقرارات لا تتأثر بالأسلوب إطلاقاً."
NEW = ("  • **اللهجة لا تغيّر المحتوى أبداً**: الأرقام تبقى كما هي حرفياً، المصطلحات التقنية والمحاسبية بصيغتها الصحيحة ولا تُستبدل بعامية، والحقائق والقرارات لا تتأثر بالأسلوب إطلاقاً.\n"
       "  • **أمانة الأرقام الحرفية**: انقلي أرقام الأدوات **بإشارتها كما وردت** (السالب يبقى سالباً — `-13,406` لا `13,406`)، و**لا تشتقي أرقاماً من حسابك** (لا فروقات ولا جموع ولا نسب لم ترد في مخرجات الأدوات) — إن طُلب رقم مشتق غير موجود قولي إنه يحتاج أداة أو تدقيقاً ولا تحسبيه بنفسك.")

assert OLD in V4, "anchor not found — ABORT"
V41 = V4.replace(OLD, NEW)
res = prompt_registry.register(
    version="v4.1-qassimi-mirror",
    content=V41,
    activated_by="main_agent — number-fidelity fix after style bank finding (sign drop + derived diff)",
    activate_now=False,
)
print("register:", res)
active_ver, _ = prompt_registry.get_active()
print("active version still:", active_ver)
