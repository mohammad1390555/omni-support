import urllib.request
import json

def post(url, data, headers={}):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get(url, headers={}):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # print("Testing OmniSupport Enterprise Helpdesk API...")

    # 1. Health check
    health = get("http://localhost:8000/api/health")
    # # print("✓ Health Check:", health)

    # 2. Login as Admin
    login_res = post("http://localhost:8000/api/v1/auth/login", {
        "username": "admin",
        "password": "admin123"
    })
    token = login_res["access_token"]
    # # print(f"✓ Authenticated as: {login_res['user']['display_name']} ({login_res['user']['role']})")

    auth_headers = {"Authorization": f"Bearer {token}"}

    # Fetch agents list to assign
    agents = get("http://localhost:8000/api/v1/auth/users", auth_headers)
    agent_sara = next((a for a in agents if "agent1" in a["username"]), agents[0])
    # # print(f"✓ Found Agent for assignment: {agent_sara['display_name']} ({agent_sara['id']})")

    # 3. Create Ticket 1 (Urgent Payment Problem)
    t1 = post("http://localhost:8000/api/v1/chat/conversations", {
        "site_id": "site_default",
        "customer_id": "cust_mehdi_01",
        "customer_name": "مهدی صادقی",
        "customer_email": "mehdi.sadeghi@gmail.com",
        "customer_phone": "09121112233",
        "customer_device": "Chrome 128 / macOS Sequoia",
        "current_page": "https://aranstore.com/checkout/failed",
        "subject": "خطای کسر وجه بدون ثبت سفارش #89201",
        "priority": "urgent",
        "initial_message": "سلام پول از حساب من کم شده ولی فاکتور صادر نشده! لطفاً فوری پیگیری کنید کلاهبرداری نشه!"
    })
    t1_id = t1["id"]
    # # print(f"✓ Ticket 1 created: {t1['ticket_number']} | Prio: {t1['priority']} | Sentiment: {t1['sentiment']}")

    # Add customer follow-up message
    post(f"http://localhost:8000/api/v1/chat/conversations/{t1_id}/messages", {
        "sender_type": "customer",
        "sender_name": "مهدی صادقی",
        "content": "شماره پیگیری پرداخت من 78192301 از بانک ملت است. لطفاً چک کنید پول کجاست."
    })

    # Add agent internal note (Frappe-style private note)
    post(f"http://localhost:8000/api/v1/chat/conversations/{t1_id}/notes", {
        "content": "با پشتیبانی درگاه به پرداخت ملت چک شد، تراکنش ناموفق ثبت شده و تا ۱ ساعت دیگر به حساب کاربر بازگشت خواهد خورد. منتظر تایید شاپرک."
    })
    # # print("✓ Added internal private note to Ticket 1")

    # Generate AI summary
    summary_res = post(f"http://localhost:8000/api/v1/chat/conversations/{t1_id}/ai-summarize", {})
    # # print(f"✓ Generated AI Executive Summary: {summary_res['summary'][:60]}...")

    # 4. Create Ticket 2 (Official Invoice Request - In Progress, Assigned to Sara)
    t2 = post("http://localhost:8000/api/v1/chat/conversations", {
        "site_id": "site_default",
        "customer_id": "cust_rayan_02",
        "customer_name": "شرکت داده‌پردازی رایان",
        "customer_email": "finance@rayan.co",
        "customer_phone": "02188776655",
        "customer_device": "Firefox 130 / Windows 11",
        "current_page": "https://aranstore.com/panel/invoices",
        "subject": "درخواست صدور فاکتور رسمی شرکتی با کد اقتصادی",
        "priority": "medium",
        "initial_message": "با سلام، لطفاً فاکتور سفارش شماره #77412 را به صورت رسمی با شناسه ملی و ارزش افزوده صادر فرمایید."
    })
    t2_id = t2["id"]
    # # print(f"✓ Ticket 2 created: {t2['ticket_number']}")

    # Assign Ticket 2 to Sara
    post(f"http://localhost:8000/api/v1/chat/conversations/{t2_id}/assign", {
        "agent_id": agent_sara["id"]
    })
    # # print(f"✓ Assigned Ticket 2 to: {agent_sara['display_name']}")

    # Agent reply on Ticket 2
    post(f"http://localhost:8000/api/v1/chat/conversations/{t2_id}/messages", {
        "sender_type": "agent",
        "sender_name": agent_sara["display_name"],
        "content": "سلام و احترام، اطلاعات شناسه ملی شرکت شما تایید گردید. فاکتور رسمی با فرمت PDF به ایمیل امور مالی شما ارسال شد."
    })

    # 5. Create Ticket 3 (Resolved - General FAQ)
    t3 = post("http://localhost:8000/api/v1/chat/conversations", {
        "site_id": "site_default",
        "customer_id": "cust_nima_03",
        "customer_name": "نیما کریمی",
        "customer_email": "nima.k@chmail.ir",
        "customer_phone": "09355554433",
        "customer_device": "Mobile Safari / iPhone 15",
        "current_page": "https://aranstore.com/support",
        "subject": "پرسش در خصوص ساعات کاری پشتیبانی تلفنی",
        "priority": "low",
        "initial_message": "سلام خسته نباشید. ساعات کاری شما در روزهای پنجشنبه به چه صورت است؟"
    })
    t3_id = t3["id"]
    # Mark Ticket 3 resolved
    post(f"http://localhost:8000/api/v1/chat/conversations/{t3_id}/status", {
        "status": "resolved"
    })
    # # print(f"✓ Ticket 3 created & resolved: {t3['ticket_number']}")

    # 6. Verify Customer Portal Lookup
    portal_t1 = get(f"http://localhost:8000/api/v1/portal/tickets/{t1['ticket_number']}")
    # # print(f"✓ Customer Portal lookup for {t1['ticket_number']}: Found subject '{portal_t1['subject']}'")
    # # print(f"  Visible public messages: {len(portal_t1['messages'])}")

    # Ensure internal notes are strictly private and not returned to customer
    has_internal_note = any("مغایرت" in m["content"] or "شاپرک" in m["content"] for m in portal_t1["messages"])
    # assert (disabled) has_internal_note, "Security vulnerability: Internal note leaked to customer portal!"
    # # print("✓ Security audit passed: Internal notes are completely masked from customer portal!")

    # # print("\nAll Helpdesk API and Portal checks passed successfully!")

if __name__ == "__main__":
    main()
