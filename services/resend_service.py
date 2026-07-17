import os
import requests
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import render_template
from jinja2 import Environment, FileSystemLoader

def send_login_greeting(email, name):
    """
    Sends a welcoming greeting email to the authenticated user.
    Supports Gmail SMTP (free, sends to any recipient from Gmail) 
    if SMTP_PASSWORD is set, otherwise falls back to Resend API.
    """
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # 1. Load configurations
    smtp_email = os.getenv("SMTP_EMAIL", "hire.mate.in@gmail.com")
    smtp_password = os.getenv("SMTP_PASSWORD") # 16-char Gmail App Password
    
    api_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv("FROM_EMAIL", "onboarding@resend.dev")

    # 2. Render HTML content
    try:
        try:
            # Try rendering using Flask context if available
            html_content = render_template("emails/login_greeting.html", user_name=name)
        except Exception as render_ex:
            # Fallback to standalone Jinja2 environment if outside application context
            template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
            env = Environment(loader=FileSystemLoader(template_dir))
            template = env.get_template("emails/login_greeting.html")
            html_content = template.render(user_name=name)
    except Exception as e:
        print(f"[{timestamp}] [EMAIL ERROR] Failed to render template: {e}")
        return False

    # 3. If SMTP_PASSWORD is set, dispatch via Gmail SMTP (completely free, bypasses domain restriction)
    if smtp_password:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "🚀 Welcome Back to HireMate!"
            msg["From"] = f"HireMate <{smtp_email}>"
            msg["To"] = email
            
            # Attach HTML body
            part = MIMEText(html_content, "html")
            msg.attach(part)
            
            # Secure connection to Gmail's SSL SMTP server
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
                server.login(smtp_email, smtp_password)
                server.sendmail(smtp_email, [email], msg.as_string())
                
            print(f"[{timestamp}] [SMTP SUCCESS] Greeting email sent successfully to '{email}' via Gmail SMTP.")
            return True
        except Exception as smtp_err:
            print(f"[{timestamp}] [SMTP FAILURE] Failed to send email to '{email}' via SMTP: {smtp_err}")
            return False

    # 4. Fallback to Resend API (requires verified domains for custom recipients)
    if not api_key:
        print(f"[{timestamp}] [EMAIL ERROR] Neither SMTP_PASSWORD nor RESEND_API_KEY is configured. Email skipped.")
        return False
        
    try:
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
            print(f"[{timestamp}] [RESEND SUCCESS] Greeting email sent successfully to email: '{email}' via Resend. Response: {response.text}")
            return True
        else:
            print(f"[{timestamp}] [RESEND FAILURE] API returned non-success code ({response.status_code}) for email: '{email}'. Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"[{timestamp}] [RESEND EXCEPTION] Error occurred while sending email to {email} via Resend: {e}")
        return False
