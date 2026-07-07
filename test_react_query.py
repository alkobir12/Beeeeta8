#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright

async def check_react_query_state():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            print("=== CHECKING REACT QUERY STATE ===")
            
            # Login
            await page.goto('https://accounting-engine-6.preview.emergentagent.com/login')
            await page.wait_for_selector('[data-testid="login-username-input"]', timeout=10000)
            await page.fill('[data-testid="login-username-input"]', 'مدير')
            await page.click('[data-testid="login-submit-button"]')
            await page.wait_for_url('**/') 
            await page.wait_for_timeout(2000)
            
            # Navigate to operations
            await page.goto('https://accounting-engine-6.preview.emergentagent.com/operations')
            await page.wait_for_timeout(5000)
            
            # Inject JavaScript to check React Query state
            query_state = await page.evaluate("""
                () => {
                    // Try to access React Query client from window
                    if (window.__REACT_QUERY_CLIENT__) {
                        const client = window.__REACT_QUERY_CLIENT__;
                        const queries = client.getQueryCache().getAll();
                        return {
                            totalQueries: queries.length,
                            operationsQueries: queries.filter(q => 
                                q.queryKey && q.queryKey.includes && q.queryKey.includes('operations')
                            ).map(q => ({
                                key: q.queryKey,
                                state: q.state.status,
                                data: q.state.data ? (Array.isArray(q.state.data) ? q.state.data.length : 'not array') : 'no data',
                                error: q.state.error ? q.state.error.message : null
                            }))
                        };
                    }
                    
                    // Try to access from React DevTools
                    if (window.__REACT_DEVTOOLS_GLOBAL_HOOK__) {
                        return { message: "React DevTools available but no direct query access" };
                    }
                    
                    return { message: "No React Query client found in window" };
                }
            """)
            
            print(f"React Query state: {query_state}")
            
            # Check if operations data is available in the DOM
            operations_data = await page.evaluate("""
                () => {
                    // Look for any elements that might contain operations data
                    const operationCards = document.querySelectorAll('[data-testid^="operation-card-"]');
                    const recentOpsSection = document.querySelector('*:contains("العمليات الأخيرة")');
                    
                    return {
                        operationCardsCount: operationCards.length,
                        recentOpsSectionExists: !!recentOpsSection,
                        bodyText: document.body.innerText.includes('INV000') ? 'Contains INV000' : 'No INV000 found'
                    };
                }
            """)
            
            print(f"DOM operations data: {operations_data}")
            
            # Check for loading states
            loading_state = await page.evaluate("""
                () => {
                    const loadingElements = document.querySelectorAll('*:contains("Loading"), *:contains("جاري التحميل")');
                    const spinners = document.querySelectorAll('.animate-spin');
                    
                    return {
                        loadingElements: loadingElements.length,
                        spinners: spinners.length
                    };
                }
            """)
            
            print(f"Loading state: {loading_state}")
            
            # Try to access the operations data directly from the component
            component_data = await page.evaluate("""
                () => {
                    // Try to find React fiber and access component state
                    const operationsContainer = document.querySelector('div.space-y-3');
                    if (operationsContainer) {
                        const fiber = operationsContainer._reactInternalFiber || 
                                    operationsContainer._reactInternals ||
                                    Object.keys(operationsContainer).find(key => key.startsWith('__reactInternalInstance'));
                        
                        if (fiber) {
                            return { message: "Found React fiber but cannot access safely" };
                        }
                    }
                    
                    return { message: "No operations container or fiber found" };
                }
            """)
            
            print(f"Component data: {component_data}")
            
            # Check network timing
            network_timing = await page.evaluate("""
                () => {
                    const entries = performance.getEntriesByType('navigation');
                    const resources = performance.getEntriesByType('resource');
                    const operationsAPI = resources.find(r => r.name.includes('/api/operations'));
                    
                    return {
                        navigationComplete: entries.length > 0 ? entries[0].loadEventEnd > 0 : false,
                        operationsAPITiming: operationsAPI ? {
                            duration: operationsAPI.duration,
                            responseEnd: operationsAPI.responseEnd
                        } : null,
                        totalResources: resources.length
                    };
                }
            """)
            
            print(f"Network timing: {network_timing}")
            
            # Wait a bit more and check again
            print("\nWaiting 5 more seconds and checking again...")
            await page.wait_for_timeout(5000)
            
            final_check = await page.evaluate("""
                () => {
                    const operationCards = document.querySelectorAll('[data-testid^="operation-card-"]');
                    const bodyText = document.body.innerText;
                    const invMatches = bodyText.match(/INV\\d{6}/g) || [];
                    
                    return {
                        operationCards: operationCards.length,
                        invoiceNumbers: invMatches.slice(0, 5), // First 5
                        hasRecentOperations: bodyText.includes('العمليات الأخيرة')
                    };
                }
            """)
            
            print(f"Final check: {final_check}")
            
            # Take screenshot
            await page.screenshot(path='.screenshots/react_query_debug.png', full_page=True)
            print("✅ Screenshot saved")
            
            print("\n=== REACT QUERY CHECK COMPLETED ===")
            
        except Exception as error:
            print(f"❌ Error: {error}")
            await page.screenshot(path='.screenshots/react_query_error.png', full_page=False)
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(check_react_query_state())