def send_otp_email(email: str, otp_code: str):
    """
    Mock Email Service. 
    In production, integrate SMTP, SendGrid, AWS SES, or Mailgun here.
    """
    print(f"========== EMAIL DISPATCH ==========")
    print(f"To: {email}")
    print(f"Subject: Your QueryBridge AI Password Reset OTP")
    print(f"Body: Your 6-digit OTP code is: {otp_code}. It expires in 10 minutes.")
    print(f"====================================")
    return True