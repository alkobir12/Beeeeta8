#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright

async def simple_operations_check():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            print("=== SIMPLE OPERATIONS CHECK ===")
            
            # Login
            await page.goto('https://accounting-ssot-fix.preview.emergentagent.com/login')
            await page.wait_for_selector('[data-testid="login-username-input"]', timeout=10000)
            await page.fill('[data-testid="login-username-input"]', 'مدير')
            await page.click('[data-testid="login-submit-button"]')
            await page.wait_for_url('**/') 
            await page.wait_for_timeout(2000)
            
            # Navigate to operations
            await page.goto('https://accounting-ssot-fix.preview.emergentagent.com/operations')
            await page.wait_for_timeout(8000)  # Wait longer
            
            # Simple checks
            page_text = await page.text_content('body')
            
            # Check for invoice numbers
            import re
            inv_numbers = re.findall(r'INV\d{6}', page_text)
            old_inv_numbers = re.findall(r'INV-\d{8}', page_text)
            
            print(f"New format invoice numbers found: {len(inv_numbers)}")
            if inv_numbers:
                print(f"  Examples: {inv_numbers[:5]}")
            
            print(f"Old format invoice numbers found: {len(old_inv_numbers)}")
            if old_inv_numbers:
                print(f"  Examples: {old_inv_numbers[:5]}")
            
            # Check for operation cards
            operation_cards = await page.locator('[data-testid^="operation-card-"]').count()
            print(f"Operation cards found: {operation_cards}")
            
            # Check for apple-card elements
            apple_cards = await page.locator('.apple-card').count()
            print(f"Apple card elements found: {apple_cards}")
            
            # Check for Recent Operations text
            recent_ops_ar = await page.locator('text=العمليات الأخيرة').count()
            recent_ops_en = await page.locator('text=Recent Operations').count()
            print(f"Recent Operations (Arabic): {recent_ops_ar}")
            print(f"Recent Operations (English): {recent_ops_en}")
            
            # Check for print buttons
            print_buttons = await page.locator('text=طباعة').count()
            print(f"Print buttons found: {print_buttons}")
            
            # If we found invoice numbers but no cards, there might be a display issue
            if inv_numbers and operation_cards == 0:
                print("\n⚠️ Found invoice numbers but no operation cards - checking display...")
                
                # Look for any divs that contain invoice numbers
                for inv_num in inv_numbers[:3]:
                    inv_locator = page.locator(f'text={inv_num}')
                    if await inv_locator.count() > 0:
                        parent = inv_locator.locator('..').first
                        parent_class = await parent.get_attribute('class') or 'no-class'
                        parent_testid = await parent.get_attribute('data-testid') or 'no-testid'
                        print(f"  {inv_num} parent: class='{parent_class}' testid='{parent_testid}'")
            
            # If we found cards, test one
            if operation_cards > 0:
                print(f"\n✅ Found {operation_cards} operation cards - testing first one...")
                
                first_card = page.locator('[data-testid^="operation-card-"]').first
                card_text = await first_card.text_content()
                print(f"First card text (first 200 chars): {card_text[:200]}")
                
                # Look for print button in the card
                print_button = first_card.locator('text=طباعة')
                if await print_button.count() > 0:
                    print("✅ Found print button in card - testing click...")
                    
                    await print_button.click()
                    await page.wait_for_timeout(3000)
                    
                    current_url = page.url
                    print(f"After print click: {current_url}")
                    
                    if '/print' in current_url:
                        print("✅ Print button works!")
                        
                        # Check document number in print page
                        print_page_text = await page.text_content('body')
                        print_inv_numbers = re.findall(r'INV\d{6}', print_page_text)
                        print_old_numbers = re.findall(r'INV-\d{8}', print_page_text)
                        
                        print(f"Print page new format numbers: {print_inv_numbers}")
                        print(f"Print page old format numbers: {print_old_numbers}")
                        
                        await page.screenshot(path='.screenshots/print_page_success.png', full_page=False)
                        print("✅ Print page screenshot saved")
                    else:
                        print("❌ Print button did not navigate to print page")
                else:
                    print("❌ No print button found in card")
            
            # Take final screenshot
            await page.screenshot(path='.screenshots/operations_simple_check.png', full_page=True)
            print("✅ Operations page screenshot saved")
            
            print("\n=== SIMPLE CHECK COMPLETED ===")
            
        except Exception as error:
            print(f"❌ Error: {error}")
            await page.screenshot(path='.screenshots/simple_check_error.png', full_page=False)
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(simple_operations_check())