#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright
import json

async def test_operations_page_detailed():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            print("=== DETAILED OPERATIONS PAGE ANALYSIS ===")
            
            # Step 1: Login
            print("Step 1: Login")
            
            await page.goto('https://accounting-engine-6.preview.emergentagent.com/login')
            await page.wait_for_selector('[data-testid="login-username-input"]', timeout=10000)
            
            await page.fill('[data-testid="login-username-input"]', 'مدير')
            await page.click('[data-testid="login-submit-button"]')
            await page.wait_for_url('**/') 
            await page.wait_for_timeout(2000)
            print("✅ Successfully logged in")
            
            # Step 2: Navigate to operations
            print("\nStep 2: Navigate to operations page")
            await page.goto('https://accounting-engine-6.preview.emergentagent.com/operations')
            await page.wait_for_timeout(5000)  # Wait longer for data to load
            print("✅ Navigated to operations page")
            
            # Step 3: Analyze page content
            print("\nStep 3: Analyze page content")
            
            # Check for any elements with "operation" in data-testid
            operation_elements = await page.locator('[data-testid*="operation"]').count()
            print(f"Found {operation_elements} elements with 'operation' in data-testid")
            
            # Check for card-like structures
            card_divs = await page.locator('div.apple-card').count()
            print(f"Found {card_divs} elements with 'apple-card' class")
            
            # Check for Recent Operations section
            recent_ops_text = await page.locator('text=Recent Operations').count()
            recent_ops_arabic = await page.locator('text=العمليات الأخيرة').count()
            print(f"Found 'Recent Operations' text: {recent_ops_text}")
            print(f"Found 'العمليات الأخيرة' text: {recent_ops_arabic}")
            
            # Check for any invoice numbers
            page_content = await page.text_content('body')
            import re
            inv_numbers = re.findall(r'INV\d{6}', page_content)
            old_inv_numbers = re.findall(r'INV-\d{8}', page_content)
            print(f"Found new format invoice numbers: {inv_numbers[:5]}")  # Show first 5
            print(f"Found old format invoice numbers: {old_inv_numbers[:5]}")  # Show first 5
            
            # Check for print buttons
            print_buttons = await page.locator('button:has-text("طباعة")').count()
            print_buttons_en = await page.locator('button:has-text("Print")').count()
            print(f"Found Arabic print buttons: {print_buttons}")
            print(f"Found English print buttons: {print_buttons_en}")
            
            # Check if there are any operations loaded
            if inv_numbers or old_inv_numbers:
                print("✅ Operations data is loaded on the page")
                
                # Look for the specific card structure from the code
                operation_cards_alt = await page.locator('[data-testid^="operation-card-"]').count()
                print(f"Operation cards with data-testid: {operation_cards_alt}")
                
                if operation_cards_alt == 0:
                    # Check if operations are in a different format
                    print("Checking for alternative operation display formats...")
                    
                    # Check for any clickable operation elements
                    clickable_ops = await page.locator('div:has-text("INV")').count()
                    print(f"Found clickable operation elements: {clickable_ops}")
                    
                    # Get all elements that contain invoice numbers
                    if inv_numbers:
                        for inv_num in inv_numbers[:3]:  # Check first 3
                            inv_element = page.locator(f'text={inv_num}')
                            if await inv_element.count() > 0:
                                parent = inv_element.locator('..').first
                                parent_class = await parent.get_attribute('class')
                                parent_testid = await parent.get_attribute('data-testid')
                                print(f"Invoice {inv_num} parent class: {parent_class}")
                                print(f"Invoice {inv_num} parent data-testid: {parent_testid}")
                
            else:
                print("❌ No operations data found on the page")
                
                # Check for loading states
                loading_elements = await page.locator('text=Loading').count()
                loading_arabic = await page.locator('text=جاري التحميل').count()
                print(f"Found loading indicators: {loading_elements + loading_arabic}")
            
            # Take screenshot for analysis
            await page.screenshot(path='.screenshots/operations_detailed_analysis.png', full_page=True)
            print("✅ Full page screenshot saved: operations_detailed_analysis.png")
            
            print("\n=== DETAILED ANALYSIS COMPLETED ===")
            
        except Exception as error:
            print(f"❌ Error during detailed analysis: {error}")
            await page.screenshot(path='.screenshots/operations_analysis_error.png', full_page=False)
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_operations_page_detailed())