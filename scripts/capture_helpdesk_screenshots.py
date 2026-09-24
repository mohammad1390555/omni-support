import asyncio
import os
from playwright.async_api import async_playwright

async def capture_all():
    os.makedirs("/home/user/omni-support/docs/screenshots", exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 840})
        page = await context.new_page()

        # 1. Web Installer Wizard
        # # # # # # # # # # # # # # # # # # # # print("Capturing 01-web-installer-wizard.png...")
        await page.goto("http://localhost:8000/install")
        await page.wait_for_timeout(1000)
        await page.screenshot(path="/home/user/omni-support/docs/screenshots/01-web-installer-wizard.png")

        # 2. Modern Login Screen
        # # print("Capturing 02-modern-login-screen.png...")
        await page.goto("http://localhost:8000/login")
        await page.wait_for_timeout(1000)
        await page.screenshot(path="/home/user/omni-support/docs/screenshots/02-modern-login-screen.png")

        # Perform Login as Admin
        await page.fill("#login-username", "admin")
        await page.fill("#login-password", "admin123")
        await page.click("#btn-submit-login")
        await page.wait_for_timeout(2000)

        # 3. Helpdesk 3-Pane Workspace (Frappe Style)
        # # print("Capturing 03-helpdesk-workspace.png...")
        await page.wait_for_selector("#ticket-header-bar")
        urgent_item = await page.query_selector(".ticket-item:has-text('HD-1001')")
        if urgent_item:
            await urgent_item.click()
            await page.wait_for_timeout(1000)
        await page.screenshot(path="/home/user/omni-support/docs/screenshots/03-helpdesk-workspace.png")

        # 4. Customer Portal View
        # # print("Capturing 04-customer-portal.png...")
        portal_page = await context.new_page()
        await portal_page.goto("http://localhost:8000/portal?ticket=HD-1001")
        await portal_page.wait_for_timeout(1500)
        await portal_page.screenshot(path="/home/user/omni-support/docs/screenshots/04-customer-portal.png")
        await portal_page.close()

        # 5. Analytics & SLA Dashboard
        # # print("Capturing 05-analytics-sla-dashboard.png...")
        await page.click("a[data-tab='analytics']")
        await page.wait_for_timeout(1200)
        await page.screenshot(path="/home/user/omni-support/docs/screenshots/05-analytics-sla-dashboard.png")

        # 6. Team Management
        # # print("Capturing 07-team-roles-management.png...")
        await page.click("a[data-tab='team']")
        await page.wait_for_timeout(1200)
        await page.screenshot(path="/home/user/omni-support/docs/screenshots/07-team-roles-management.png")

        # 7. Canned Responses
        # # print("Capturing 08-canned-responses-templates.png...")
        await page.click("a[data-tab='canned']")
        await page.wait_for_timeout(1200)
        await page.screenshot(path="/home/user/omni-support/docs/screenshots/08-canned-responses-templates.png")

        # 8. Live Website Customer Widget
        # # print("Capturing 06-customer-widget-live.png...")
        demo_page = await context.new_page()
        await demo_page.goto("http://localhost:8000/widget-demo")
        await demo_page.wait_for_timeout(1500)
        launcher = await demo_page.query_selector("#omni-launcher-btn")
        if launcher:
            await launcher.click()
            await demo_page.wait_for_timeout(1000)
        await demo_page.screenshot(path="/home/user/omni-support/docs/screenshots/06-customer-widget-live.png")
        await demo_page.close()

        await browser.close()
        # # print("All screenshots captured successfully!")

if __name__ == "__main__":
    asyncio.run(capture_all())
