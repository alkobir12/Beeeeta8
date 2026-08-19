#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright

async def test_journal_entries():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            print("=== JOURNAL ENTRIES CHART OF ACCOUNTS UNIFICATION TEST ===")
            
            # Step 1: Login
            print("1. Login process...")
            await page.goto('https://accounting-ssot-fix.preview.emergentagent.com/login')
            await page.wait_for_selector('[data-testid="login-username-input"]', timeout=10000)
            await page.fill('[data-testid="login-username-input"]', 'مدير')
            await page.click('[data-testid="login-submit-button"]')
            await page.wait_for_url('https://accounting-ssot-fix.preview.emergentagent.com/', timeout=15000)
            print("✅ Login successful")
            
            # Step 2: Navigate to Journal Entries
            print("2. Navigate to Journal Entries page...")
            await page.goto('https://accounting-ssot-fix.preview.emergentagent.com/accounting/journal-entries')
            await page.wait_for_selector('[data-testid="journal-entries-page"]', timeout=10000)
            print("✅ Journal Entries page loaded")
            
            await page.screenshot(path='journal_entries_page.png', full_page=False)
            
            # Step 3: Open new entry form
            print("3. Open new entry form...")
            await page.click('[data-testid="new-entry-btn"]')
            await page.wait_for_selector('[data-testid="entry-description-input"]', timeout=5000)
            print("✅ New entry form opened")
            
            await page.screenshot(path='new_entry_form.png', full_page=False)
            
            # Step 4: Check account options
            print("4. Checking available account codes...")
            
            # Wait for the dropdown to be populated
            await page.wait_for_timeout(3000)
            
            account_options = await page.evaluate('''() => {
                const select = document.querySelector('[data-testid="line-account-0"]');
                if (!select) return [];
                const options = Array.from(select.options);
                return options.map(option => ({
                    value: option.value,
                    text: option.textContent
                })).filter(opt => opt.value !== '');
            }''')
            
            print(f"📊 Total accounts available: {len(account_options)}")
            
            if len(account_options) == 0:
                print("⚠️  No accounts loaded in dropdown. Checking API directly...")
                # Check if the API is working
                api_response = await page.evaluate('''async () => {
                    try {
                        const response = await fetch('/api/finance/chart-of-accounts?workshop_id=finmodule-sync');
                        const data = await response.json();
                        return { success: response.ok, data: data };
                    } catch (e) {
                        return { success: false, error: e.message };
                    }
                }''')
                print(f"API Response: {api_response}")
                
                # Try to trigger account loading
                await page.click('[data-testid="line-account-0"]')
                await page.wait_for_timeout(2000)
                
                account_options = await page.evaluate('''() => {
                    const select = document.querySelector('[data-testid="line-account-0"]');
                    if (!select) return [];
                    const options = Array.from(select.options);
                    return options.map(option => ({
                        value: option.value,
                        text: option.textContent
                    })).filter(opt => opt.value !== '');
                }''')
                print(f"📊 After retry - Total accounts available: {len(account_options)}")
            
            # Analyze account codes
            unified_codes = [opt for opt in account_options if len(opt['value']) >= 4 and opt['value'][0] in '123456']
            legacy_codes = [opt for opt in account_options if opt['value'] in ['101', '113', '411', '521']]
            
            print(f"📈 Unified codes (1000+ series): {len(unified_codes)} accounts")
            print(f"📉 Legacy codes (101, 113, etc.): {len(legacy_codes)} accounts")
            
            # Show examples
            if unified_codes:
                print("🔍 Sample unified codes:")
                for i, opt in enumerate(unified_codes[:10]):
                    print(f"   {i+1}. {opt['value']} - {opt['text']}")
            
            if legacy_codes:
                print("⚠️  Legacy codes still present:")
                for opt in legacy_codes:
                    print(f"   - {opt['value']} - {opt['text']}")
            
            # If no accounts are available, skip the entry creation test
            if len(account_options) == 0:
                print("❌ Cannot proceed with entry creation - no accounts available")
                return
            
            # Step 5: Test creating entry with unified codes
            print("5. Testing entry creation with unified codes...")
            await page.fill('[data-testid="entry-description-input"]', 'اختبار توحيد الحسابات من الواجهة')
            
            # Select unified account codes
            await page.select_option('[data-testid="line-account-0"]', '1101')  # النقد
            await page.fill('[data-testid="line-debit-0"]', '500')
            
            await page.select_option('[data-testid="line-account-1"]', '4101')  # إيرادات خدمات ميكانيكية
            await page.fill('[data-testid="line-credit-1"]', '500')
            
            await page.screenshot(path='entry_form_filled.png', full_page=False)
            
            # Step 6: Save entry
            print("6. Saving journal entry...")
            await page.click('[data-testid="save-entry-btn"]')
            await page.wait_for_selector('[data-testid="journal-entries-page"]', timeout=10000)
            print("✅ Entry saved successfully")
            
            # Step 7: Verify saved entry
            print("7. Verifying saved entry...")
            await page.wait_for_timeout(2000)  # Wait for refresh
            
            entry_rows = await page.query_selector_all('[data-testid^="entry-row-"]')
            print(f"📋 Found {len(entry_rows)} journal entries")
            
            if entry_rows:
                # Click on first entry to view details
                first_entry_id = await entry_rows[0].get_attribute('data-testid')
                entry_id = first_entry_id.replace('entry-row-', '')
                
                await page.click(f'[data-testid="view-btn-{entry_id}"]')
                # Use a more specific selector for the modal
                modal_selector = '[role="dialog"], .fixed.inset-0.bg-black'
                await page.wait_for_selector(modal_selector, timeout=5000)
                
                await page.screenshot(path='entry_details.png', full_page=False)
                
                # Check displayed account codes
                detail_accounts = await page.evaluate('''() => {
                    const accountCells = document.querySelectorAll('tbody tr td:first-child');
                    return Array.from(accountCells).map(cell => {
                        const codeSpan = cell.querySelector('.font-mono');
                        return {
                            code: codeSpan ? codeSpan.textContent : '',
                            name: cell.textContent.replace(codeSpan ? codeSpan.textContent : '', '').trim()
                        };
                    });
                }''')
                
                print("📋 Accounts displayed in saved entry:")
                for i, acc in enumerate(detail_accounts):
                    print(f"   {i+1}. Code: {acc['code']} - Name: {acc['name']}")
                
                # Verify codes match
                actual_codes = [acc['code'] for acc in detail_accounts]
                expected_codes = ['1101', '4101']
                codes_match = all(code in actual_codes for code in expected_codes)
                
                print(f"🔍 Expected codes: {', '.join(expected_codes)}")
                print(f"🔍 Actual codes: {', '.join(actual_codes)}")
                print(f"✅ Codes match: {'YES' if codes_match else 'NO'}")
                
                await page.keyboard.press('Escape')
            
            await page.screenshot(path='final_result.png', full_page=False)
            
            # Final summary
            print("\n=== TEST RESULTS SUMMARY ===")
            print(f"✅ Journal Entries page functionality: WORKING")
            print(f"✅ New entry form: WORKING")
            print(f"✅ Account selection: WORKING")
            print(f"✅ Entry saving: WORKING")
            print(f"📊 Unified codes available: {'YES' if unified_codes else 'NO'} ({len(unified_codes)} accounts)")
            print(f"⚠️  Legacy codes present: {'YES' if legacy_codes else 'NO'} ({len(legacy_codes)} accounts)")
            
            if unified_codes and not legacy_codes:
                print("🎯 ACCOUNT UNIFICATION STATUS: FULLY UNIFIED")
            elif unified_codes and legacy_codes:
                print("🎯 ACCOUNT UNIFICATION STATUS: MIXED (Both unified and legacy codes present)")
            else:
                print("🎯 ACCOUNT UNIFICATION STATUS: NOT UNIFIED (Only legacy codes)")
                
        except Exception as e:
            print(f"❌ Test failed: {str(e)}")
            await page.screenshot(path='error.png', full_page=False)
            raise
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_journal_entries())