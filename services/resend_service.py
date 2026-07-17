import os
import requests
import datetime
from flask import render_template
from jinja2 import Environment, FileSystemLoader

def send_login_greeting(email, name):
    """
    Sends a welcoming greeting email to the authenticated user using the Resend API.
    Guaranteed to fail silently to prevent blocking the user's login experience.
    """
    api_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv("FROM_EMAIL", "onboarding@resend.dev")
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    if not api_key:
        print(f"[{timestamp}] [RESEND ERROR] RESEND_API_KEY environment variable is not configured. Email skipped.")
        return False
        
    try:
        # 1. Render the HTML email template
        try:
            # Try rendering using Flask context if available
            html_content = render_template("emails/login_greeting.html", user_name=name)
        except Exception as render_ex:
            # Fallback to standalone Jinja2 environment if outside application/request context
            print(f"[{timestamp}] [RESEND INFO] Flask render context unavailable, falling back to standalone Jinja2: {render_ex}")
            template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
            env = Environment(loader=FileSystemLoader(template_dir))
            template = env.get_template("emails/login_greeting.html")
            html_content = template.render(user_name=name)

        # 2. Dispatch request to Resend API
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "from": from_email,
            "to": [email],
            "subject": "🚀 Welcome Back to HireMate!",
            "html": html_content
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code in [200, 201, 202]:
            print(f"[{timestamp}] [RESEND SUCCESS] Greeting email sent successfully to email: '{email}', Name: '{name}'. Response: {response.text}")
            return True
        else:
            print(f"[{timestamp}] [RESEND FAILURE] API returned non-success code ({response.status_code}) for email: '{email}'. Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"[{timestamp}] [RESEND EXCEPTION] Error occurred while sending email to {email}: {e}")
        return False
