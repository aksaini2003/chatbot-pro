import smtplib
import os
from dotenv import load_dotenv

load_dotenv()

def test_connection():
    smtp_server = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("EMAIL_PORT", "587"))
    smtp_username = os.getenv("EMAIL_USERNAME")
    smtp_password = os.getenv("EMAIL_PASSWORD")
    email_from = os.getenv("EMAIL_FROM")

    print(f"Trying username: {smtp_username}")
    print(f"Trying from: {email_from}")

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.set_debuglevel(1)
            server.starttls()
            try:
                server.login(smtp_username, smtp_password)
                return f"SUCCESS with username: {smtp_username}"
            except Exception as e1:
                print(f"Failed with username '{smtp_username}': {e1}")
                if email_from and email_from != smtp_username:
                    print(f"Trying again with from as username: {email_from}")
                    server.login(email_from, smtp_password)
                    return f"SUCCESS with username: {email_from}"
                raise e1
    except Exception as e:
        return f"FAILURE: {str(e)}"

if __name__ == "__main__":
    result = test_connection()
    print(f"SMTP_TEST_RESULT: {result}")
