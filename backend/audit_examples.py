"""
مثال عملي على استخدام نظام التدقيق المحاسبي
"""

import sys
sys.path.append('/app/backend')

from accounting_auditor import AccountingSystemAuditor

# ============================================================================
# مثال 1: تدقيق نظام ورشة السيارات
# ============================================================================

def example_workshop_audit():
    """مثال عملي على تدقيق ورشة السيارات"""
    
    print("=" * 70)
    print("🔧 مثال: تدقيق النظام المحاسبي لورشة السيارات")
    print("=" * 70)
    
    # 1. تهيئة البيانات من نظام الورشة
    workshop_data = {
        "balance_sheet": {
            "assets": 450000,      # الأصول: نقدية + ذمم مدينة + معدات
            "liabilities": 180000, # الالتزامات: ذمم دائنة + ضرائب
            "equity": 270000       # حقوق الملكية: رأس المال + أرباح
        },
        "income_statement": {
            "revenue": 125000,     # إيرادات الخدمات لهذا الشهر
            "expenses": 45000,     # مصروفات (قطع غيار + رواتب + إيجار)
            "net_profit": 80000    # صافي الربح
        },
        "cash_flow": {
            "operating": 75000,    # التدفق من الأنشطة التشغيلية
            "investing": -15000,   # شراء معدات جديدة
            "financing": 0         # لا يوجد قروض
        }
    }
    
    # 2. إنشاء مدقق وتشغيل التدقيق
    auditor = AccountingSystemAuditor("ورشة السيارات - الفرع الرئيسي")
    report = auditor.run_comprehensive_audit(workshop_data)
    
    # 3. عرض النتائج
    print(f"\n{'=' * 70}")
    print("📊 نتائج التدقيق:")
    print(f"{'=' * 70}")
    print(f"\n🎯 درجة صحة النظام: {report['health_score']}/100")
    print(f"📅 تاريخ التدقيق: {report['audit_date'][:10]}")
    
    if report['summary']['total_issues'] == 0:
        print("\n✅ النظام سليم - لا توجد مشكلات!")
    else:
        print(f"\n⚠️  عدد المشكلات: {report['summary']['total_issues']}")
        print(f"🔧 التصحيحات المطلوبة: {report['summary']['corrections_needed']}")
    
    print(f"\n📝 الحكم النهائي: {report['summary']['final_verdict']}")
    
    # 4. التصحيحات المطلوبة
    if report.get('corrections_needed'):
        print(f"\n{'=' * 70}")
        print("🔧 التصحيحات المطلوبة:")
        print(f"{'=' * 70}")
        for i, correction in enumerate(report['corrections_needed'], 1):
            print(f"\n{i}. {correction.get('issue', 'غير محدد')}")
            if 'suggestion' in correction:
                print(f"   💡 الاقتراح: {correction['suggestion']}")
    
    # 5. سجل التدقيق
    print(f"\n{'=' * 70}")
    print("📜 سجل التدقيق (آخر 5 إدخالات):")
    print(f"{'=' * 70}")
    for log in report.get('audit_log', [])[-5:]:
        print(f"  {log}")
    
    return report


# ============================================================================
# مثال 2: نظام به مشكلات (للتوضيح)
# ============================================================================

def example_problematic_system():
    """مثال على نظام به مشكلات واضحة"""
    
    print("\n" + "=" * 70)
    print("⚠️  مثال: نظام به مشكلات (للتوضيح)")
    print("=" * 70)
    
    # بيانات غير متوازنة عمداً
    problematic_data = {
        "balance_sheet": {
            "assets": 500000,      # الأصول
            "liabilities": 150000, # الالتزامات
            "equity": 300000       # حقوق الملكية
            # المجموع: 150000 + 300000 = 450000 ≠ 500000 ❌
        },
        "income_statement": {
            "revenue": 1000000,    # إيرادات مليون
            "expenses": 5000,      # مصروفات 5 آلاف فقط! (غير واقعي)
            "net_profit": 995000   # هامش ربح 99.5%! (غير واقعي)
        },
        "cash_flow": {
            "operating": 800000,
            "investing": -20000,
            "financing": 0
        }
    }
    
    # تشغيل التدقيق
    auditor = AccountingSystemAuditor("نظام تجريبي - به مشكلات")
    report = auditor.run_comprehensive_audit(problematic_data)
    
    print(f"\n🎯 درجة صحة النظام: {report['health_score']}/100")
    print(f"\n❌ عدد المشكلات المكتشفة: {report['summary']['total_issues']}")
    
    # عرض المشكلات
    if report.get('corrections_needed'):
        print("\n🔴 المشكلات المكتشفة:")
        for i, correction in enumerate(report['corrections_needed'], 1):
            print(f"\n{i}. {correction.get('issue', '')}")
            if 'correction' in correction:
                print(f"   📊 {correction['correction']}")
            if 'suggestion' in correction:
                print(f"   💡 {correction['suggestion']}")
    
    return report


# ============================================================================
# مثال 3: استخدام البيانات الحقيقية من API
# ============================================================================

async def audit_real_system_data():
    """تدقيق بيانات حقيقية من API"""
    
    print("\n" + "=" * 70)
    print("🌐 مثال: تدقيق بيانات حقيقية من API")
    print("=" * 70)
    
    try:
        import aiohttp
        
        API_URL = "http://localhost:8001/api"
        workshop_id = "finmodule-sync"
        
        async with aiohttp.ClientSession() as session:
            # جلب الميزانية
            async with session.get(f"{API_URL}/finance/reports/balance-sheet?workshop_id={workshop_id}") as resp:
                balance_data = await resp.json()
            
            # جلب قائمة الدخل
            async with session.get(
                f"{API_URL}/finance/reports/income-statement?workshop_id={workshop_id}"
                f"&start_date=2025-01-01&end_date=2025-01-31"
            ) as resp:
                income_data = await resp.json()
            
            # تهيئة البيانات للتدقيق
            real_data = {
                "balance_sheet": {
                    "assets": balance_data.get('data', {}).get('totals', {}).get('assets', 0),
                    "liabilities": balance_data.get('data', {}).get('totals', {}).get('liabilities', 0),
                    "equity": balance_data.get('data', {}).get('totals', {}).get('equity', 0)
                },
                "income_statement": {
                    "revenue": income_data.get('data', {}).get('totals', {}).get('revenue', 0),
                    "expenses": income_data.get('data', {}).get('totals', {}).get('expenses', 0),
                    "net_profit": income_data.get('data', {}).get('totals', {}).get('net_income', 0)
                },
                "cash_flow": {
                    "operating": 0,
                    "investing": 0,
                    "financing": 0
                }
            }
            
            # تشغيل التدقيق
            auditor = AccountingSystemAuditor("النظام الحقيقي - بيانات من API")
            report = auditor.run_comprehensive_audit(real_data)
            
            print("\n✅ تم تدقيق البيانات الحقيقية بنجاح!")
            print(f"🎯 درجة الصحة: {report['health_score']}/100")
            
            return report
    
    except Exception as e:
        print(f"\n❌ خطأ في جلب البيانات: {str(e)}")
        return None


# ============================================================================
# التشغيل
# ============================================================================

if __name__ == "__main__":
    print("\n🛠️  أمثلة على استخدام نظام التدقيق المحاسبي")
    print("=" * 70)
    
    print("\n📋 اختر مثالاً:")
    print("1. تدقيق ورشة السيارات (بيانات سليمة)")
    print("2. تدقيق نظام به مشكلات (للتوضيح)")
    print("3. تدقيق بيانات حقيقية من API")
    print("4. تشغيل جميع الأمثلة")
    
    try:
        choice = input("\nأدخل اختيارك (1-4): ").strip()
        
        if choice == "1":
            report = example_workshop_audit()
            
        elif choice == "2":
            report = example_problematic_system()
            
        elif choice == "3":
            import asyncio
            report = asyncio.run(audit_real_system_data())
            
        elif choice == "4":
            print("\n" + "🔄" * 35)
            example_workshop_audit()
            example_problematic_system()
            
        else:
            print("❌ اختيار غير صحيح")
        
        print("\n" + "=" * 70)
        print("✅ انتهت الأمثلة")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  تم إيقاف البرنامج")
    except Exception as e:
        print(f"\n❌ حدث خطأ: {str(e)}")
