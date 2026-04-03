import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

def send_reset_password_email(to_email: str, reset_link: str):
    """
    Sends a password reset email using SMTP settings from .env.
    """
    smtp_server = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("EMAIL_PORT", "587"))
    smtp_username = os.getenv("EMAIL_USERNAME")
    smtp_password = os.getenv("EMAIL_PASSWORD")
    email_from = os.getenv("EMAIL_FROM")

    if not smtp_username or not smtp_password:
        print(f"Skipping email sending: EMAIL_USERNAME/PASSWORD not provided in .env. Link: {reset_link}")
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = "Password Reset Request - ChatBot Pro"
    message["From"] = email_from
    message["To"] = to_email

    # Professional email template
    text_content = f"Hi,\n\nYou requested a password reset. Please use the following link to reset your password:\n{reset_link}\n\nIf you did not request this, please ignore this email."
    
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
          <h2 style="color: #3b82f6; text-align: center;">Password Reset Request</h2>
          <p>Hello,</p>
          <p>You requested a password reset for your account on <strong>ChatBot Pro</strong>. Click the button below to set a new password:</p>
          <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_link}" style="background-color: #3b82f6; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
              Reset Password
            </a>
          </div>
          <p>If the button doesn't work, you can copy and paste this link into your browser:</p>
          <p style="color: #6b7280; font-size: 14px; word-break: break-all;">{reset_link}</p>
          <hr style="border: 0; border-top: 1px solid #e5e7eb; margin: 20px 0;">
          <p style="font-size: 12px; color: #9ca3af; text-align: center;">
            If you did not request this, you can safely ignore this email.
          </p>
        </div>
      </body>
    </html>
    """

    message.attach(MIMEText(text_content, "plain"))
    message.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port,timeout=10) as server:
            server.set_debuglevel(0)
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(email_from, to_email, message.as_string())
        print(f"Password reset email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"Failed to send password reset email: {str(e)}")
        return False
