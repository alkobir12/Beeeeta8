#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright
import json

async def test_operations_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            print("=== ARABIC OPERATIONS PAGE TESTING ===")
            print("Testing Operations page updates after converting Recent Operations to Cards + invoice_number renumbering")
            
            # Step 1: Login
            print("Step 1: Login with 'مدير'")
            
            await page.goto('https://workshop-operator.preview.emergentagent.com/login')
            await page.wait_for_selector('[data-testid="login-username-input"]', timeout=10000)
            
            await page.fill('[data-testid="login-username-input"]', 'مدير')
            print("✅ Entered username 'مدير'")
            
            await page.click('[data-testid="login-submit-button"]')
            print("✅ Clicked login button")
            
            await page.wait_for_url('**/') 
            await page.wait_for_timeout(2000)
            print("✅ Successfully logged in and navigated to dashboard")
            
            # Step 2: Navigate to /operations
            print("\nStep 2: Navigate to /operations page")
            await page.goto('https://workshop-operator.preview.emergentagent.com/operations')
            await page.wait_for_timeout(3000)
            print("✅ Navigated to operations page")
            
            # Take screenshot of operations page
            await page.screenshot(path='.screenshots/operations_page_initial.png', full_page=False)
            print("✅ Screenshot taken: operations_page_initial.png")
            
            # Step 3: Check if Recent Operations is now Cards format
            print("\nStep 3: Verify Recent Operations format (Cards vs Table)")
            
            # Look for card format elements
            operation_cards = await page.locator('[data-testid^="operation-card-"]').count()
            print(f"Found {operation_cards} operation cards")
            
            # Look for table format elements (old format)
            operation_table = await page.locator('table').count()
            print(f"Found {operation_table} tables on page")
            
            if operation_cards > 0:
                print("✅ Recent Operations is using CARDS format")
                
                # Step 4: Check invoice numbers in cards
                print("\nStep 4: Check invoice numbers in operation cards")
                
                card_elements = await page.locator('[data-testid^="operation-card-"]').all()
                new_format_count = 0
                old_format_count = 0
                
                for i, card in enumerate(card_elements[:5]):  # Check first 5 cards
                    card_text = await card.text_content()
                    
                    # Look for INV0000xx format (new)
                    import re
                    new_format_match = re.search(r'INV\d{6}', card_text)
                    # Look for INV-YYYYMMDD format (old)
                    old_format_match = re.search(r'INV-\d{8}', card_text)
                    
                    if new_format_match:
                        new_format_count += 1
                        print(f"✅ Card {i+1}: Found new format invoice number: {new_format_match.group(0)}")
                    elif old_format_match:
                        old_format_count += 1
                        print(f"❌ Card {i+1}: Found old format invoice number: {old_format_match.group(0)}")
                    else:
                        print(f"⚠️ Card {i+1}: No clear invoice number format detected")
                
                print(f"\nInvoice Number Format Summary:")
                print(f"New format (INV0000xx): {new_format_count}")
                print(f"Old format (INV-YYYYMMDD): {old_format_count}")
                
                # Step 5: Test print button functionality
                print("\nStep 5: Test print button in operation card")
                
                if card_elements:
                    first_card = card_elements[0]
                    print_button = first_card.locator('[data-testid^="operation-print-button-"]')
                    
                    if await print_button.count() > 0:
                        print("✅ Found print button in operation card")
                        
                        # Get the operation ID from the button's data-testid
                        print_button_test_id = await print_button.get_attribute('data-testid')
                        operation_id = print_button_test_id.replace('operation-print-button-', '')
                        print(f"Operation ID: {operation_id}")
                        
                        # Click print button
                        await print_button.click()
                        print("✅ Clicked print button")
                        
                        # Wait for navigation to print page
                        await page.wait_for_timeout(2000)
                        
                        # Check if we're on the print page
                        current_url = page.url
                        print(f"Current URL: {current_url}")
                        
                        if '/print' in current_url and 'operationId=' in current_url:
                            print("✅ Successfully navigated to print page with operationId parameter")
                            
                            # Step 6: Verify document number in print page
                            print("\nStep 6: Verify document number in print page")
                            
                            await page.wait_for_timeout(3000)
                            
                            # Take screenshot of print page
                            await page.screenshot(path='.screenshots/print_page_document.png', full_page=False)
                            print("✅ Screenshot taken: print_page_document.png")
                            
                            # Look for document number display
                            page_content = await page.text_content('body')
                            new_format_in_print = re.search(r'INV\d{6}', page_content)
                            old_format_in_print = re.search(r'INV-\d{8}', page_content)
                            
                            if new_format_in_print:
                                print(f"✅ Print page shows new format document number: {new_format_in_print.group(0)}")
                            elif old_format_in_print:
                                print(f"❌ Print page shows old format document number: {old_format_in_print.group(0)}")
                            else:
                                print("⚠️ Could not detect document number format in print page")
                                
                        else:
                            print("❌ Print button did not navigate to expected print page")
                    else:
                        print("❌ No print button found in operation card")
                
            else:
                print("❌ Recent Operations is still using TABLE format (not Cards)")
            
            print("\n=== OPERATIONS PAGE TESTING COMPLETED ===")
            
        except Exception as error:
            print(f"❌ Error during operations page testing: {error}")
            
            # Take error screenshot
            await page.screenshot(path='.screenshots/operations_error.png', full_page=False)
            print("Error screenshot saved: operations_error.png")
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_operations_page())