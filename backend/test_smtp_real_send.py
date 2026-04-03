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

    print(f"Attempting to send email to {email_from}...")

    msg = MIMEText("This is a test email to verify SMTP functionality.")
    msg['Subject'] = 'Test SMTP'
    msg['From'] = email_from
    msg['To'] = email_from

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.set_debuglevel(1)
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(email_from, email_from, msg.as_string())
            print("\nEMAIL_SENT_SUCCESSFULLY!")
            return True
    except Exception as e:
        print(f"\nEMAIL_SEND_FAILED: {str(e)}")
        return False

if __name__ == "__main__":
    send_test()
