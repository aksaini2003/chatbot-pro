import smtplib
import os
from dotenv import load_dotenv

load_dotenv()

def test_connection():
    smtp_server = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("EMAIL_PORT", "587"))
    smtp_username = os.getenv("EMAIL_USERNAME")
    smtp_password = os.getenv("EMAIL_PASSWORD")

    print(f"Testing connection to {smtp_server}:{smtp_port} as {smtp_username}...")

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.set_debuglevel(1)
            server.starttls()
            server.login(smtp_username, smtp_password)
            print("\nSUCCESS: SMTP connection and login successful!")
            return True
    except Exception as e:
        print(f"\nFAILURE: SMTP connection or login failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_connection()
