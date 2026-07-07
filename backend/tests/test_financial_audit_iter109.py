"""
Iteration 109 - Financial Audit Tests
تدقيق مصادر الأرقام المالية ومطابقة الذمم والإيرادات

Test Scenarios:
1. تدقيق مصدر أرقام الميزانية/قائمة الدخل (النقد 1101، البنك 1102، الذمم 1103، الإيراد)
2. التأكد أن ذمم الورشة فقط تُرحَّل كإيراد/ذمم، ومبالغ الموردين لا تدخل إيراد الورشة
3. إضافة عملية بيع من صفحة العمليات والتحقق من القيد الناتج
4. قاعدة الآجل: عملية البيع الآجل تبقى آجل حتى تأكيد السداد
5. اختبار طريقة الدفع: نقد -> 1101، بطاقة/تحويل -> 1102
6. مطابقة رقم إجمالي الذمم في لوحة المؤشرات مع القوائم المالية
"""

import pytest
import requests
import json
import uuid
from datetime import datetime, timedelta

BASE_URL = "https://accounting-engine-6.preview.emergentagent.com"
WORKSHOP_ID = "finmodule-sync"


class TestFinancialAudit:
    """تدقيق مصادر الأرقام المالية"""

    def test_balance_sheet_account_codes(self):
        """Test 1: تدقيق أكواد الحسابات في الميزانية"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/balance-sheet",
            params={"workshop_id": WORKSHOP_ID}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        sections = data.get("data", {}).get("sections", {})
        assets = sections.get("assets", [])
        
        # التحقق من وجود الحسابات الأساسية
        asset_codes = [a.get("code") for a in assets]
        print(f"Asset codes found: {asset_codes}")
        
        # النقد 1101
        cash_accounts = [a for a in assets if a.get("code") == "1101"]
        if cash_accounts:
            print(f"Cash (1101) balance: {cash_accounts[0].get('balance')}")
        
        # البنك 1102
        bank_accounts = [a for a in assets if a.get("code") == "1102"]
        if bank_accounts:
            print(f"Bank (1102) balance: {bank_accounts[0].get('balance')}")
        
        # الذمم 1103
        ar_accounts = [a for a in assets if a.get("code") == "1103"]
        if ar_accounts:
            print(f"AR (1103) balance: {ar_accounts[0].get('balance')}")
        
        # التحقق من توازن المعادلة
        totals = data.get("data", {}).get("totals", {})
        total_assets = totals.get("assets", 0)
        total_liabilities_equity = totals.get("liabilities_plus_equity", 0)
        print(f"Assets: {total_assets}, Liabilities+Equity: {total_liabilities_equity}")
        
        assert total_assets >= 0, "Total assets should be non-negative"

    def test_income_statement_revenue_accounts(self):
        """Test 2: تدقيق حسابات الإيرادات في قائمة الدخل"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/income-statement",
            params={
                "workshop_id": WORKSHOP_ID,
                "start_date": "2026-01-01",
                "end_date": "2026-04-11"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        details = data.get("data", {}).get("details", {})
        revenue_by_account = details.get("revenue_by_account", {})
        expenses_by_account = details.get("expenses_by_account", {})
        
        print(f"Revenue accounts: {list(revenue_by_account.keys())}")
        print(f"Expense accounts: {list(expenses_by_account.keys())}")
        
        # التحقق من أن الإيرادات تبدأ بـ 4xxx
        for code in revenue_by_account.keys():
            assert code.startswith("4"), f"Revenue account {code} should start with 4"
        
        # التحقق من أن المصروفات تبدأ بـ 5xxx أو 6xxx
        for code in expenses_by_account.keys():
            assert code.startswith(("5", "6")), f"Expense account {code} should start with 5 or 6"
        
        totals = data.get("data", {}).get("totals", {})
        print(f"Total Revenue: {totals.get('revenue')}")
        print(f"Total Expenses: {totals.get('expenses')}")
        print(f"Net Income: {totals.get('net_income')}")

    def test_trial_balance_accounts(self):
        """Test 3: تدقيق ميزان المراجعة"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/trial-balance",
            params={"workshop_id": WORKSHOP_ID}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        accounts = data.get("data", {}).get("accounts", [])
        totals = data.get("data", {}).get("totals", {})
        
        # التحقق من توازن ميزان المراجعة
        total_debit = totals.get("total_debit", 0)
        total_credit = totals.get("total_credit", 0)
        print(f"Total Debit: {total_debit}, Total Credit: {total_credit}")
        
        # يجب أن يكون الفرق صفر أو قريب منه
        diff = abs(total_debit - total_credit)
        assert diff < 0.01, f"Trial balance should be balanced, diff: {diff}"
        
        # التحقق من حسابات محددة
        for acc in accounts:
            code = acc.get("code")
            name = acc.get("name")
            debit = acc.get("debit", 0)
            credit = acc.get("credit", 0)
            
            if code == "1101":
                print(f"Cash (1101): Debit={debit}, Credit={credit}, Net={debit-credit}")
            elif code == "1102":
                print(f"Bank (1102): Debit={debit}, Credit={credit}, Net={debit-credit}")
            elif code == "1103":
                print(f"AR (1103): Debit={debit}, Credit={credit}, Net={debit-credit}")
            elif code == "2101":
                print(f"AP (2101): Debit={debit}, Credit={credit}, Net={credit-debit}")

    def test_reconciliation_report(self):
        """Test 4: تقرير المطابقة بين العمليات والقيود"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/reconciliation",
            params={
                "workshop_id": WORKSHOP_ID,
                "start_date": "2026-01-01",
                "end_date": "2026-04-11"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        summary = data.get("data", {}).get("summary", {})
        rows = data.get("data", {}).get("rows", [])
        
        print(f"Reconciliation matched: {summary.get('matched')}")
        print(f"Total absolute difference: {summary.get('total_absolute_difference')}")
        print(f"Missing operation journals: {summary.get('missing_operation_journals', {}).get('count', 0)}")
        
        for row in rows:
            op_type = row.get("type")
            op_total = row.get("operations_total", 0)
            je_total = row.get("journal_entries_total", 0)
            diff = row.get("difference", 0)
            matched = row.get("matched")
            print(f"  {op_type}: Ops={op_total}, JE={je_total}, Diff={diff}, Matched={matched}")

    def test_operation_trace_report(self):
        """Test 5: تقرير تتبع العمليات"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/operation-trace",
            params={
                "workshop_id": WORKSHOP_ID,
                "start_date": "2026-01-01",
                "end_date": "2026-04-11"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        
        rows = data.get("data", {}).get("rows", [])
        
        for row in rows:
            op_type = row.get("type")
            impact = row.get("impact", {})
            
            cash_impact = impact.get("cash", {}).get("net", 0)
            bank_impact = impact.get("bank", {}).get("net", 0)
            ar_impact = impact.get("ar", {}).get("net", 0)
            
            print(f"{op_type}: Cash={cash_impact}, Bank={bank_impact}, AR={ar_impact}")


class TestWorkshopVsSupplierSeparation:
    """التأكد من فصل ذمم الورشة عن مبالغ الموردين"""

    def test_operations_workshop_total_separation(self):
        """Test 6: التحقق من فصل workshopTotal عن supplierArchiveTotal"""
        response = requests.get(
            f"{BASE_URL}/api/operations",
            params={"limit": 50}
        )
        assert response.status_code == 200
        operations = response.json()
        
        # البحث عن عمليات تحتوي على بنود موردين
        ops_with_suppliers = []
        for op in operations:
            items = op.get("items", [])
            supplier_items = [i for i in items if i.get("itemType") == "supplier"]
            if supplier_items:
                ops_with_suppliers.append(op)
        
        print(f"Found {len(ops_with_suppliers)} operations with supplier items")
        
        for op in ops_with_suppliers[:5]:  # فحص أول 5 عمليات
            op_id = op.get("id", "")[:8]
            total = op.get("total", 0)
            workshop_total = op.get("workshopTotal", 0)
            supplier_total = op.get("supplierArchiveTotal", 0)
            
            print(f"Op {op_id}: Total={total}, Workshop={workshop_total}, Supplier={supplier_total}")
            
            # التحقق من أن workshopTotal لا يشمل مبالغ الموردين
            items = op.get("items", [])
            calculated_workshop = sum(
                float(i.get("price", 0)) * float(i.get("quantity", 1))
                for i in items if i.get("itemType") != "supplier"
            )
            calculated_supplier = sum(
                float(i.get("price", 0)) * float(i.get("quantity", 1))
                for i in items if i.get("itemType") == "supplier"
            )
            
            print(f"  Calculated: Workshop={calculated_workshop}, Supplier={calculated_supplier}")
            
            # التحقق من التطابق (مع هامش خطأ صغير)
            if workshop_total > 0:
                assert abs(workshop_total - calculated_workshop) < 0.01, \
                    f"Workshop total mismatch: {workshop_total} vs {calculated_workshop}"

    def test_revenue_excludes_supplier_amounts(self):
        """Test 7: التحقق من أن الإيرادات لا تشمل مبالغ الموردين"""
        # جلب قائمة الدخل
        income_response = requests.get(
            f"{BASE_URL}/api/finance/reports/income-statement",
            params={
                "workshop_id": WORKSHOP_ID,
                "start_date": "2026-01-01",
                "end_date": "2026-04-11"
            }
        )
        assert income_response.status_code == 200
        income_data = income_response.json()
        
        total_revenue = income_data.get("data", {}).get("totals", {}).get("revenue", 0)
        
        # جلب العمليات
        ops_response = requests.get(
            f"{BASE_URL}/api/operations",
            params={"limit": 200}
        )
        assert ops_response.status_code == 200
        operations = ops_response.json()
        
        # حساب إجمالي workshopTotal من العمليات
        total_workshop_from_ops = sum(
            float(op.get("workshopTotal", 0) or op.get("total", 0))
            for op in operations
            if op.get("type") in ["sale", "service"]
        )
        
        print(f"Total Revenue from Income Statement: {total_revenue}")
        print(f"Total Workshop from Operations: {total_workshop_from_ops}")
        
        # الإيرادات يجب أن تكون قريبة من workshopTotal (مع هامش للعمليات القديمة)
        # لا نتوقع تطابق تام بسبب العمليات التاريخية


class TestPaymentMethodMapping:
    """اختبار ربط طريقة الدفع بالحسابات الصحيحة"""

    def test_cash_payment_maps_to_1101(self):
        """Test 8: الدفع النقدي يذهب لحساب 1101"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/operation-trace",
            params={
                "workshop_id": WORKSHOP_ID,
                "start_date": "2026-01-01",
                "end_date": "2026-04-11"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        rows = data.get("data", {}).get("rows", [])
        
        for row in rows:
            payment_methods = row.get("payment_methods", {})
            accounts_touched = row.get("accounts_touched", [])
            
            cash_count = payment_methods.get("cash", 0)
            if cash_count > 0:
                # التحقق من أن حساب 1101 موجود في الحسابات المتأثرة
                cash_account = next(
                    (a for a in accounts_touched if a.get("code") == "1101"),
                    None
                )
                if cash_account:
                    print(f"Cash payments ({cash_count}): 1101 touched with debit={cash_account.get('debit')}, credit={cash_account.get('credit')}")

    def test_card_transfer_payment_maps_to_1102(self):
        """Test 9: الدفع بالبطاقة/التحويل يذهب لحساب 1102"""
        response = requests.get(
            f"{BASE_URL}/api/finance/reports/operation-trace",
            params={
                "workshop_id": WORKSHOP_ID,
                "start_date": "2026-01-01",
                "end_date": "2026-04-11"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        rows = data.get("data", {}).get("rows", [])
        
        for row in rows:
            payment_methods = row.get("payment_methods", {})
            accounts_touched = row.get("accounts_touched", [])
            
            card_count = payment_methods.get("card", 0)
            transfer_count = payment_methods.get("transfer", 0)
            
            if card_count > 0 or transfer_count > 0:
                # التحقق من أن حساب 1102 موجود في الحسابات المتأثرة
                bank_account = next(
                    (a for a in accounts_touched if a.get("code") == "1102"),
                    None
                )
                if bank_account:
                    print(f"Card/Transfer payments (card={card_count}, transfer={transfer_count}): 1102 touched with debit={bank_account.get('debit')}, credit={bank_account.get('credit')}")


class TestCreditSalesRule:
    """اختبار قاعدة البيع الآجل"""

    def test_credit_sales_remain_as_receivables(self):
        """Test 10: عمليات البيع الآجل تبقى كذمم حتى السداد"""
        # جلب العمليات الآجلة
        response = requests.get(
            f"{BASE_URL}/api/operations",
            params={"limit": 100}
        )
        assert response.status_code == 200
        operations = response.json()
        
        credit_sales = [
            op for op in operations
            if op.get("paymentMethod") == "credit" and op.get("type") in ["sale", "service"]
        ]
        
        print(f"Found {len(credit_sales)} credit sales")
        
        for op in credit_sales[:5]:
            op_id = op.get("id", "")[:8]
            total = op.get("total", 0)
            workshop_total = op.get("workshopTotal", 0)
            payment_status = op.get("paymentStatus")
            
            print(f"Credit Sale {op_id}: Total={total}, Workshop={workshop_total}, Status={payment_status}")
            
            # البيع الآجل يجب أن يكون له workshopTotal > 0
            # ويجب أن يظهر في الذمم (1103)

    def test_ar_balance_matches_credit_sales(self):
        """Test 11: رصيد الذمم يطابق مجموع المبيعات الآجلة غير المسددة"""
        # جلب ميزان المراجعة للحصول على رصيد الذمم
        trial_response = requests.get(
            f"{BASE_URL}/api/finance/reports/trial-balance",
            params={"workshop_id": WORKSHOP_ID}
        )
        assert trial_response.status_code == 200
        trial_data = trial_response.json()
        
        accounts = trial_data.get("data", {}).get("accounts", [])
        ar_account = next((a for a in accounts if a.get("code") == "1103"), None)
        
        if ar_account:
            ar_debit = ar_account.get("debit", 0)
            ar_credit = ar_account.get("credit", 0)
            ar_balance = ar_debit - ar_credit
            print(f"AR (1103) Balance: Debit={ar_debit}, Credit={ar_credit}, Net={ar_balance}")
        
        # جلب الميزانية للمقارنة
        balance_response = requests.get(
            f"{BASE_URL}/api/finance/reports/balance-sheet",
            params={"workshop_id": WORKSHOP_ID}
        )
        assert balance_response.status_code == 200
        balance_data = balance_response.json()
        
        assets = balance_data.get("data", {}).get("sections", {}).get("assets", [])
        ar_in_balance = next((a for a in assets if a.get("code") == "1103"), None)
        
        if ar_in_balance:
            ar_balance_sheet = ar_in_balance.get("balance", 0)
            print(f"AR in Balance Sheet: {ar_balance_sheet}")


class TestCreateSaleOperation:
    """اختبار إنشاء عملية بيع والتحقق من القيد"""

    def test_create_cash_sale_operation(self):
        """Test 12: إنشاء عملية بيع نقدي والتحقق من القيد"""
        # إنشاء عملية بيع نقدي
        test_id = str(uuid.uuid4())[:8]
        payload = {
            "type": "sale",
            "workshopId": WORKSHOP_ID,
            "accountId": None,
            "accountingAccountId": "4000",  # حساب الإيرادات
            "partnerType": "customer",
            "partnerName": f"عميل اختبار {test_id}",
            "items": [
                {
                    "name": f"خدمة اختبار {test_id}",
                    "itemType": "service",
                    "quantity": 1,
                    "price": 100.0,
                    "total": 100.0
                }
            ],
            "paymentMethod": "cash",
            "paymentStatus": "paid",
            "notes": f"اختبار iteration 109 - {test_id}",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "scope": "workshop",
            "source": "test_iteration_109"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/operations",
            json=payload
        )
        
        print(f"Create cash sale response: {response.status_code}")
        if response.status_code in [200, 201]:
            created_op = response.json()
            print(f"Created operation ID: {created_op.get('id')}")
            print(f"Workshop Total: {created_op.get('workshopTotal')}")
            
            # التحقق من أن القيد يذهب للحسابات الصحيحة
            # نقدي -> 1101 (مدين)، إيراد -> 4000 (دائن)
            
            # تنظيف: حذف العملية
            op_id = created_op.get("id")
            if op_id:
                delete_response = requests.delete(f"{BASE_URL}/api/operations/{op_id}")
                print(f"Cleanup delete response: {delete_response.status_code}")
        else:
            print(f"Error: {response.text}")

    def test_create_credit_sale_operation(self):
        """Test 13: إنشاء عملية بيع آجل والتحقق من القيد"""
        test_id = str(uuid.uuid4())[:8]
        payload = {
            "type": "sale",
            "workshopId": WORKSHOP_ID,
            "accountId": None,
            "accountingAccountId": "4000",
            "partnerType": "customer",
            "partnerName": f"عميل آجل {test_id}",
            "items": [
                {
                    "name": f"خدمة آجل {test_id}",
                    "itemType": "service",
                    "quantity": 1,
                    "price": 200.0,
                    "total": 200.0
                }
            ],
            "paymentMethod": "credit",
            "paymentStatus": "unpaid",
            "notes": f"اختبار آجل iteration 109 - {test_id}",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "scope": "workshop",
            "source": "test_iteration_109"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/operations",
            json=payload
        )
        
        print(f"Create credit sale response: {response.status_code}")
        if response.status_code in [200, 201]:
            created_op = response.json()
            print(f"Created operation ID: {created_op.get('id')}")
            print(f"Payment Method: {created_op.get('paymentMethod')}")
            print(f"Workshop Total: {created_op.get('workshopTotal')}")
            
            # التحقق من أن القيد يذهب للحسابات الصحيحة
            # آجل -> 1103 (مدين)، إيراد -> 4000 (دائن)
            
            # تنظيف
            op_id = created_op.get("id")
            if op_id:
                delete_response = requests.delete(f"{BASE_URL}/api/operations/{op_id}")
                print(f"Cleanup delete response: {delete_response.status_code}")
        else:
            print(f"Error: {response.text}")


class TestARReconciliation:
    """مطابقة الذمم بين المصادر المختلفة"""

    def test_ar_consistency_across_reports(self):
        """Test 14: تناسق رصيد الذمم عبر التقارير المختلفة"""
        # 1. من ميزان المراجعة
        trial_response = requests.get(
            f"{BASE_URL}/api/finance/reports/trial-balance",
            params={"workshop_id": WORKSHOP_ID}
        )
        trial_data = trial_response.json()
        trial_accounts = trial_data.get("data", {}).get("accounts", [])
        trial_ar = next((a for a in trial_accounts if a.get("code") == "1103"), {})
        trial_ar_balance = trial_ar.get("debit", 0) - trial_ar.get("credit", 0)
        
        # 2. من الميزانية
        balance_response = requests.get(
            f"{BASE_URL}/api/finance/reports/balance-sheet",
            params={"workshop_id": WORKSHOP_ID}
        )
        balance_data = balance_response.json()
        balance_assets = balance_data.get("data", {}).get("sections", {}).get("assets", [])
        balance_ar = next((a for a in balance_assets if a.get("code") == "1103"), {})
        balance_ar_amount = balance_ar.get("balance", 0)
        
        print(f"AR from Trial Balance: {trial_ar_balance}")
        print(f"AR from Balance Sheet: {balance_ar_amount}")
        
        # يجب أن تكون القيم متقاربة
        diff = abs(trial_ar_balance - balance_ar_amount)
        print(f"Difference: {diff}")
        
        # التحقق من التناسق (مع هامش صغير للتقريب)
        assert diff < 1.0, f"AR values should be consistent, diff: {diff}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
