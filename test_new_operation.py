#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright

async def test_new_operation_creation():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            print("=== TESTING NEW OPERATION CREATION ===")
            
            # Login
            await page.goto('https://canonical-integrity.preview.emergentagent.com/login')
            await page.wait_for_selector('[data-testid="login-username-input"]', timeout=10000)
            await page.fill('[data-testid="login-username-input"]', 'مدير')
            await page.click('[data-testid="login-submit-button"]')
            await page.wait_for_url('**/') 
            await page.wait_for_timeout(2000)
            
            # Navigate to operations
            await page.goto('https://canonical-integrity.preview.emergentagent.com/operations')
            await page.wait_for_timeout(5000)
            
            # Get current operations count and first invoice number
            initial_cards = await page.locator('[data-testid^="operation-card-"]').count()
            print(f"Initial operation cards: {initial_cards}")
            
            if initial_cards > 0:
                first_card = page.locator('[data-testid^="operation-card-"]').first
                first_card_text = await first_card.text_content()
                import re
                initial_inv_numbers = re.findall(r'INV\d{6}', first_card_text)
                print(f"Initial first invoice number: {initial_inv_numbers[0] if initial_inv_numbers else 'None'}")
            
            # Create a new operation
            print("\nCreating new sale operation...")
            
            # Set operation type to sale
            await page.select_option('[data-testid="operation-type-select"]', 'sale')
            print("✅ Selected sale type")
            
            # Set partner name
            await page.fill('[data-testid="operation-partner-name-input"]', 'Test Customer New Operation')
            print("✅ Entered customer name")
            
            # Add an item - first select service type
            await page.select_option('[data-testid="operation-item-type-select"]', 'service')
            print("✅ Selected service item type")
            
            # Wait for services to load and select one
            await page.wait_for_timeout(2000)
            
            # Try to select a service from the dropdown
            service_options = await page.locator('[data-testid="operation-service-select"] option').count()
            print(f"Available services: {service_options}")
            
            if service_options > 1:  # More than just the placeholder
                # Select the first actual service (index 1, since 0 is placeholder)
                await page.select_option('[data-testid="operation-service-select"]', index=1)
                print("✅ Selected a service")
            else:
                # If no services available, create a manual entry
                print("No services available, using manual entry")
                await page.select_option('[data-testid="operation-item-type-select"]', 'part')
                await page.wait_for_timeout(1000)
            
            # Set quantity and price
            await page.fill('[data-testid="operation-item-quantity-input"]', '1')
            await page.fill('[data-testid="operation-item-price-input"]', '150')
            print("✅ Set quantity and price")
            
            # Add the item
            await page.click('[data-testid="operation-add-item-button"]')
            await page.wait_for_timeout(1000)
            print("✅ Added item to operation")
            
            # Check if save button is now enabled
            save_button = page.locator('[data-testid="operation-save-button"]')
            is_enabled = await save_button.is_enabled()
            print(f"Save button enabled: {is_enabled}")
            
            if is_enabled:
                # Submit the operation
                await save_button.click()
                print("✅ Clicked save button")
                
                # Wait for the operation to be created and page to update
                await page.wait_for_timeout(5000)
                
                # Check if new operation appeared
                final_cards = await page.locator('[data-testid^="operation-card-"]').count()
                print(f"Final operation cards: {final_cards}")
                
                if final_cards > initial_cards:
                    print("✅ New operation card appeared!")
                    
                    # Check the first card (should be the newest)
                    new_first_card = page.locator('[data-testid^="operation-card-"]').first
                    new_first_card_text = await new_first_card.text_content()
                    new_inv_numbers = re.findall(r'INV\d{6}', new_first_card_text)
                    
                    if new_inv_numbers:
                        print(f"✅ New operation has invoice number: {new_inv_numbers[0]}")
                        
                        # Check if it contains our test customer name
                        if 'Test Customer New Operation' in new_first_card_text:
                            print("✅ New operation contains correct customer name")
                        else:
                            print("⚠️ Customer name not found in new operation")
                        
                        # Check if it shows as sale type
                        if 'بيع' in new_first_card_text or 'sale' in new_first_card_text.lower():
                            print("✅ New operation shows as sale type")
                        else:
                            print("⚠️ Sale type not clearly visible")
                        
                        # Test print button on new operation
                        new_print_button = new_first_card.locator('text=طباعة')
                        if await new_print_button.count() > 0:
                            print("✅ New operation has print button")
                            
                            await new_print_button.click()
                            await page.wait_for_timeout(3000)
                            
                            current_url = page.url
                            if '/print' in current_url and 'operationId=' in current_url:
                                print("✅ New operation print button works")
                                
                                # Check document number in print page
                                print_page_text = await page.text_content('body')
                                print_inv_numbers = re.findall(r'INV\d{6}', print_page_text)
                                
                                if print_inv_numbers:
                                    print(f"✅ Print page shows invoice number: {print_inv_numbers[0]}")
                                else:
                                    print("⚠️ No invoice number found in print page")
                                
                                await page.screenshot(path='.screenshots/new_operation_print.png', full_page=False)
                                print("✅ New operation print page screenshot saved")
                            else:
                                print("❌ Print button did not work correctly")
                        else:
                            print("❌ No print button found in new operation")
                    else:
                        print("❌ No invoice number found in new operation")
                else:
                    print("❌ New operation did not appear or count did not increase")
            else:
                print("❌ Save button is not enabled - checking form state...")
                
                # Check what's missing
                items_count = await page.locator('tbody tr').count()
                print(f"Items in form: {items_count}")
                
                partner_name = await page.input_value('[data-testid="operation-partner-name-input"]')
                print(f"Partner name: '{partner_name}'")
            
            # Take final screenshot
            await page.screenshot(path='.screenshots/new_operation_final.png', full_page=True)
            print("✅ Final screenshot saved")
            
            print("\n=== NEW OPERATION CREATION TEST COMPLETED ===")
            
        except Exception as error:
            print(f"❌ Error: {error}")
            await page.screenshot(path='.screenshots/new_operation_error.png', full_page=False)
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_new_operation_creation())