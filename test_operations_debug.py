#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright

async def debug_operations_display():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Monitor network and console
        console_messages = []
        network_responses = []
        
        page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
        page.on("response", lambda resp: network_responses.append({
            'url': resp.url, 
            'status': resp.status,
            'method': resp.request.method
        }))
        
        try:
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            print("=== DEBUGGING OPERATIONS DISPLAY ===")
            
            # Login
            await page.goto('https://stamp-approval-flow.preview.emergentagent.com/login')
            await page.wait_for_selector('[data-testid="login-username-input"]', timeout=10000)
            await page.fill('[data-testid="login-username-input"]', 'مدير')
            await page.click('[data-testid="login-submit-button"]')
            await page.wait_for_url('**/') 
            await page.wait_for_timeout(2000)
            
            # Navigate to operations
            await page.goto('https://stamp-approval-flow.preview.emergentagent.com/operations')
            await page.wait_for_timeout(5000)
            
            # Check API responses
            operations_responses = [r for r in network_responses if '/api/operations' in r['url']]
            print(f"Operations API responses: {len(operations_responses)}")
            for resp in operations_responses:
                print(f"  {resp['method']} {resp['url']} -> {resp['status']}")
            
            # Check if React Query is working
            react_query_errors = [msg for msg in console_messages if 'query' in msg.lower() or 'react-query' in msg.lower()]
            print(f"React Query related messages: {len(react_query_errors)}")
            for msg in react_query_errors:
                print(f"  {msg}")
            
            # Check the DOM structure around Recent Operations
            print("\nChecking DOM structure...")
            
            # Find the Recent Operations section
            recent_ops_section = page.locator('text=العمليات الأخيرة').locator('..')
            if await recent_ops_section.count() > 0:
                print("✅ Found Recent Operations section")
                
                # Check its siblings/children for operation cards
                parent = recent_ops_section.locator('..')
                children = await parent.locator('> *').count()
                print(f"Parent has {children} children")
                
                # Look for the operations container
                operations_container = parent.locator('div.space-y-3')
                if await operations_container.count() > 0:
                    print("✅ Found operations container")
                    container_children = await operations_container.locator('> *').count()
                    print(f"Operations container has {container_children} children")
                    
                    # Check if there are any divs that might be operation cards
                    potential_cards = await operations_container.locator('div').count()
                    print(f"Found {potential_cards} divs in operations container")
                    
                    # Check for specific operation card structure
                    apple_cards = await operations_container.locator('div.apple-card').count()
                    print(f"Found {apple_cards} apple-card divs")
                    
                    if apple_cards > 0:
                        print("✅ Found operation cards!")
                        
                        # Get the first card and analyze it
                        first_card = operations_container.locator('div.apple-card').first
                        card_text = await first_card.text_content()
                        print(f"First card text: {card_text[:200]}...")
                        
                        # Check for invoice numbers in the card
                        import re
                        inv_numbers = re.findall(r'INV\d{6}', card_text)
                        old_inv_numbers = re.findall(r'INV-\d{8}', card_text)
                        print(f"Invoice numbers in card: {inv_numbers}")
                        print(f"Old format numbers in card: {old_inv_numbers}")
                        
                        # Check for print button
                        print_button = first_card.locator('button:has-text("طباعة")')
                        if await print_button.count() > 0:
                            print("✅ Found print button in card")
                            
                            # Test clicking the print button
                            await print_button.click()
                            await page.wait_for_timeout(2000)
                            
                            current_url = page.url
                            print(f"After clicking print: {current_url}")
                            
                            if '/print' in current_url:
                                print("✅ Print button works - navigated to print page")
                                
                                # Check document number in print page
                                await page.wait_for_timeout(3000)
                                print_page_content = await page.text_content('body')
                                print_inv_numbers = re.findall(r'INV\d{6}', print_page_content)
                                print_old_numbers = re.findall(r'INV-\d{8}', print_page_content)
                                
                                print(f"Print page invoice numbers: {print_inv_numbers}")
                                print(f"Print page old format: {print_old_numbers}")
                                
                                await page.screenshot(path='.screenshots/print_page_test.png', full_page=False)
                                print("✅ Print page screenshot saved")
                            else:
                                print("❌ Print button did not navigate to print page")
                        else:
                            print("❌ No print button found in card")
                    else:
                        print("❌ No apple-card divs found")
                        
                        # Check what's actually in the container
                        container_html = await operations_container.inner_html()
                        print(f"Container HTML (first 500 chars): {container_html[:500]}")
                else:
                    print("❌ No operations container found")
            else:
                print("❌ Recent Operations section not found")
            
            # Take final screenshot
            await page.screenshot(path='.screenshots/operations_debug_final.png', full_page=True)
            print("✅ Debug screenshot saved")
            
            print("\n=== DEBUG COMPLETED ===")
            
        except Exception as error:
            print(f"❌ Error: {error}")
            await page.screenshot(path='.screenshots/operations_debug_error.png', full_page=False)
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_operations_display())