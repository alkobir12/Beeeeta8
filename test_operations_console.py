#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright

async def test_operations_with_console():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Listen to console messages
        console_messages = []
        page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
        
        # Listen to network requests
        network_requests = []
        page.on("request", lambda req: network_requests.append(f"REQUEST: {req.method} {req.url}"))
        page.on("response", lambda resp: network_requests.append(f"RESPONSE: {resp.status} {resp.url}"))
        
        try:
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            print("=== OPERATIONS PAGE WITH CONSOLE MONITORING ===")
            
            # Login
            await page.goto('https://accounting-ssot-fix.preview.emergentagent.com/login')
            await page.wait_for_selector('[data-testid="login-username-input"]', timeout=10000)
            await page.fill('[data-testid="login-username-input"]', 'مدير')
            await page.click('[data-testid="login-submit-button"]')
            await page.wait_for_url('**/') 
            await page.wait_for_timeout(2000)
            print("✅ Logged in")
            
            # Navigate to operations
            await page.goto('https://accounting-ssot-fix.preview.emergentagent.com/operations')
            await page.wait_for_timeout(5000)
            print("✅ Navigated to operations")
            
            # Check for operations API calls
            operations_api_calls = [req for req in network_requests if '/api/operations' in req]
            print(f"\nOperations API calls: {len(operations_api_calls)}")
            for call in operations_api_calls[-5:]:  # Show last 5
                print(f"  {call}")
            
            # Check console for errors
            error_messages = [msg for msg in console_messages if 'error' in msg.lower()]
            print(f"\nConsole errors: {len(error_messages)}")
            for error in error_messages[-5:]:  # Show last 5
                print(f"  {error}")
            
            # Try to create a test operation
            print("\nStep 4: Try to create a test operation")
            
            # Fill the form
            await page.select_option('[data-testid="operation-type-select"]', 'sale')
            await page.fill('[data-testid="operation-partner-name-input"]', 'Test Customer')
            
            # Add an item
            await page.select_option('[data-testid="operation-item-type-select"]', 'service')
            await page.fill('[data-testid="operation-item-quantity-input"]', '1')
            await page.fill('[data-testid="operation-item-price-input"]', '100')
            
            # Click add item
            await page.click('[data-testid="operation-add-item-button"]')
            await page.wait_for_timeout(1000)
            
            # Submit the operation
            await page.click('[data-testid="operation-save-button"]')
            await page.wait_for_timeout(3000)
            
            print("✅ Attempted to create test operation")
            
            # Check if operations appeared
            await page.wait_for_timeout(2000)
            page_content = await page.text_content('body')
            import re
            inv_numbers = re.findall(r'INV\d{6}', page_content)
            print(f"Invoice numbers found after creation: {inv_numbers}")
            
            # Check for operation cards again
            operation_cards = await page.locator('[data-testid^="operation-card-"]').count()
            print(f"Operation cards found: {operation_cards}")
            
            # Take final screenshot
            await page.screenshot(path='.screenshots/operations_after_creation.png', full_page=True)
            print("✅ Screenshot saved: operations_after_creation.png")
            
            # Print recent console messages
            print(f"\nRecent console messages:")
            for msg in console_messages[-10:]:
                print(f"  {msg}")
            
            print("\n=== TESTING WITH CONSOLE COMPLETED ===")
            
        except Exception as error:
            print(f"❌ Error: {error}")
            await page.screenshot(path='.screenshots/operations_console_error.png', full_page=False)
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_operations_with_console())