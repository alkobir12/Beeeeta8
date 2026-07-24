#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright

async def check_operations_api():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Monitor all network activity and console
        all_requests = []
        all_responses = []
        console_messages = []
        
        page.on("request", lambda req: all_requests.append({
            'method': req.method,
            'url': req.url,
            'headers': dict(req.headers)
        }))
        
        page.on("response", lambda resp: all_responses.append({
            'url': resp.url,
            'status': resp.status,
            'method': resp.request.method
        }))
        
        page.on("console", lambda msg: console_messages.append({
            'type': msg.type,
            'text': msg.text,
            'location': f"{msg.location.get('url', '')}:{msg.location.get('lineNumber', '')}"
        }))
        
        try:
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            print("=== CHECKING OPERATIONS API CALLS ===")
            
            # Login
            await page.goto('https://stamp-approval-flow.preview.emergentagent.com/login')
            await page.wait_for_selector('[data-testid="login-username-input"]', timeout=10000)
            await page.fill('[data-testid="login-username-input"]', 'مدير')
            await page.click('[data-testid="login-submit-button"]')
            await page.wait_for_url('**/') 
            await page.wait_for_timeout(2000)
            
            print("✅ Logged in")
            print(f"Requests so far: {len(all_requests)}")
            print(f"Responses so far: {len(all_responses)}")
            
            # Navigate to operations and wait longer
            await page.goto('https://stamp-approval-flow.preview.emergentagent.com/operations')
            print("✅ Navigated to operations page")
            
            # Wait for potential API calls
            await page.wait_for_timeout(10000)  # Wait 10 seconds
            
            print(f"\nTotal requests: {len(all_requests)}")
            print(f"Total responses: {len(all_responses)}")
            
            # Filter operations-related requests
            operations_requests = [r for r in all_requests if '/api/operations' in r['url']]
            operations_responses = [r for r in all_responses if '/api/operations' in r['url']]
            
            print(f"\nOperations requests: {len(operations_requests)}")
            for req in operations_requests:
                print(f"  {req['method']} {req['url']}")
            
            print(f"\nOperations responses: {len(operations_responses)}")
            for resp in operations_responses:
                print(f"  {resp['method']} {resp['url']} -> {resp['status']}")
            
            # Check for any API-related requests
            api_requests = [r for r in all_requests if '/api/' in r['url']]
            print(f"\nAll API requests: {len(api_requests)}")
            for req in api_requests[-10:]:  # Show last 10
                print(f"  {req['method']} {req['url']}")
            
            # Check console messages
            print(f"\nConsole messages: {len(console_messages)}")
            
            # Show errors
            errors = [msg for msg in console_messages if msg['type'] == 'error']
            print(f"Console errors: {len(errors)}")
            for error in errors:
                print(f"  ERROR: {error['text']} at {error['location']}")
            
            # Show warnings
            warnings = [msg for msg in console_messages if msg['type'] == 'warning']
            print(f"Console warnings: {len(warnings)}")
            for warning in warnings[-5:]:  # Show last 5
                print(f"  WARNING: {warning['text']}")
            
            # Show logs that might be relevant
            relevant_logs = [msg for msg in console_messages if 
                           'operation' in msg['text'].lower() or 
                           'query' in msg['text'].lower() or
                           'fetch' in msg['text'].lower() or
                           'api' in msg['text'].lower()]
            print(f"Relevant logs: {len(relevant_logs)}")
            for log in relevant_logs:
                print(f"  {log['type'].upper()}: {log['text']}")
            
            # Try to manually trigger the operations query by interacting with the page
            print("\nTrying to trigger operations query...")
            
            # Scroll to the Recent Operations section
            recent_ops = page.locator('text=العمليات الأخيرة')
            if await recent_ops.count() > 0:
                await recent_ops.scroll_into_view_if_needed()
                await page.wait_for_timeout(2000)
                
                # Check if this triggered any new requests
                new_operations_requests = [r for r in all_requests if '/api/operations' in r['url']]
                if len(new_operations_requests) > len(operations_requests):
                    print("✅ Scrolling triggered new operations request")
                else:
                    print("❌ Scrolling did not trigger operations request")
            
            # Try refreshing the page
            print("\nRefreshing page to see if that helps...")
            await page.reload()
            await page.wait_for_timeout(5000)
            
            # Check for new operations requests after refresh
            final_operations_requests = [r for r in all_requests if '/api/operations' in r['url']]
            final_operations_responses = [r for r in all_responses if '/api/operations' in r['url']]
            
            print(f"After refresh - Operations requests: {len(final_operations_requests)}")
            print(f"After refresh - Operations responses: {len(final_operations_responses)}")
            
            # Take screenshot
            await page.screenshot(path='.screenshots/operations_api_check.png', full_page=True)
            print("✅ Screenshot saved")
            
            print("\n=== API CHECK COMPLETED ===")
            
        except Exception as error:
            print(f"❌ Error: {error}")
            await page.screenshot(path='.screenshots/operations_api_error.png', full_page=False)
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(check_operations_api())