import requests
import secrets

# Config
API_URL = "http://localhost:8001/api"


def _rand_int(low: int, high: int) -> int:
    """عشوائي آمن — يستخدم secrets بدل random (cryptographically secure)."""
    return secrets.randbelow(high - low + 1) + low


def _rand_choice(seq):
    """اختيار آمن من قائمة."""
    return seq[secrets.randbelow(len(seq))]


# Data Generators
def generate_services():
    services = []
    actions = [
        "تغيير",
        "فحص",
        "إصلاح",
        "استبدال",
        "تنظيف",
        "برمجة",
        "وزن",
        "تركيب",
        "صيانة",
        "توضيب",
    ]
    parts = [
        "زيت المحرك",
        "فلتر الزيت",
        "فحمات الفرامل",
        "هوبات",
        "بواجي",
        "كويلات",
        "رديتر",
        "كمبروسر",
        "دينمو",
        "سلف",
        "بطارية",
        "حساسات",
        "بخاخات",
        "ثلاجة المكينة",
        "قير",
        "دفرنس",
        "عكوس",
        "مساعدات",
        "مقصات",
        "أذرعة",
        "كراسي مكينة",
        "كراسي قير",
        "سير التيمن",
        "سير المكينة",
        "طرمبة الماء",
        "طرمبة البنزين",
        "فلتر الهواء",
        "فلتر المكيف",
        "زيت القير",
        "زيت الدفرنس",
    ]

    for i in range(100):
        action = _rand_choice(actions)
        part = _rand_choice(parts)
        name = f"{action} {part} - {i+1}"
        price = _rand_int(50, 2000)
        duration = _rand_choice([30, 60, 90, 120, 180, 240])

        services.append(
            {
                "name": name,
                "category": "ميكانيكا",
                "price": price,
                "duration": duration,
                "active": True,
                "notes": "تمت الإضافة تلقائياً",
            }
        )
    return services


def generate_parts():
    parts_list = []
    names = [
        "بستم",
        "شنبر",
        "سبايك متحركة",
        "سبايك ثابتة",
        "عمود كرنك",
        "عمود تيمن",
        "بلوف",
        "جلد بلوف",
        "وجه راس",
        "وجه غطاء بلوف",
        "كارتير",
        "طرمبة زيت",
        "شخال زيت",
        "جنزير صدر",
        "شداد جنزير",
        "ترس تيمن",
        "ترس كرنك",
        "صوفة مكينة أمامية",
        "صوفة مكينة خلفية",
        "ثلاجة ماء",
        "كوع ماء",
        "بلف حرارة",
        "حساس حرارة",
        "حساس كرنك",
        "حساس تيمن",
        "حساس نوك",
        "حساس شكمان",
        "حساس ماب",
        "حساس ماف",
        "بوابة هواء",
    ]
    brands = [
        "تويوتا",
        "نيسان",
        "هونداي",
        "فورد",
        "مازدا",
        "كيا",
        "شيفروليه",
        "جي إم سي",
        "بي إم دبليو",
        "مرسيدس",
    ]

    for i in range(200):
        name = _rand_choice(names)
        brand = _rand_choice(brands)
        full_name = f"{name} {brand} - {i+1}"

        parts_list.append(
            {
                "partNumber": f"PRT-{_rand_int(10000, 99999)}-{i}",
                "name": full_name,
                "category": "مكينة",
                "purchasePrice": _rand_int(50, 500),
                "sellingPrice": _rand_int(80, 800),
                "quantity": _rand_int(5, 50),
                "minQuantity": 5,
                "location": f"R-{_rand_int(1, 10)}-S-{_rand_int(1, 5)}",
            }
        )
    return parts_list


def seed():
    print("🚀 Starting data seeding...")

    # Seed Services
    services = generate_services()
    print(f"📦 Seeding {len(services)} services...")
    for s in services:
        try:
            requests.post(f"{API_URL}/services", json=s)
        except Exception as e:
            print(f"❌ Error seeding service: {e}")

    # Seed Parts
    parts = generate_parts()
    print(f"📦 Seeding {len(parts)} parts...")
    for p in parts:
        try:
            requests.post(f"{API_URL}/parts", json=p)
        except Exception as e:
            print(f"❌ Error seeding part: {e}")

    print("✅ Seeding complete!")


if __name__ == "__main__":
    seed()
