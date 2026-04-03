import smtplib
import os
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

def send_test():
    smtp_server = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("EMAIL_PORT", "587"))
    smtp_username = os.getenv("EMAIL_USERNAME")
    smtp_password = os.getenv("EMAIL_PASSWORD")
    email_from = os.getenv("EMAIL_FROM")

    msg = MIMEText("This is a test email to verify SMTP functionality.")
    msg['Subject'] = 'Test SMTP'
    msg['From'] = email_from
    msg['To'] = email_from

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.set_debuglevel(0)
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(email_from, email_from, msg.as_string())
            return "EMAIL_SENT_SUCCESSFULLY"
    except Exception as e:
        return f"EMAIL_SEND_FAILED: {str(e)}"

if __name__ == "__main__":
    print(send_test())
