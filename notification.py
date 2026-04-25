import smtplib
import secrets
import os
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from db import get_connection
from decimal import Decimal

# ===============================
# ⚙️ CONFIG (GMAIL SMTP)
# ===============================
load_dotenv()
FROM_EMAIL = os.getenv("SMTP_EMAIL")
GMAIL_APP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

BASE_URL = "http://127.0.0.1:5000"


# ===============================
# 📧 SEND EMAIL CORE
# ===============================
def send_email(to_email, subject, html_content):
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = FROM_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(html_content, "html"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(FROM_EMAIL, GMAIL_APP_PASSWORD)
        server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        server.quit()

        print(f"✅ Email sent to {to_email}")

    except Exception as e:
        print("❌ Email Error:", e)


# ===============================
# 📦 GET BOOKING DETAILS
# ===============================
def get_booking_details(booking_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, booking_code, theme_name, booking_date,
               amount, advance_amount, venue_address
        FROM bookings
        WHERE id=%s
    """, (booking_id,))
    booking = cursor.fetchone()

    cursor.close()
    conn.close()

    if booking:
        booking["remaining"] = booking["amount"] - booking["advance_amount"]

    return booking


# ===============================
# 🔐 GENERATE / REUSE PAYMENT TOKEN
# ===============================
def generate_payment_token(booking_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT payment_token FROM bookings WHERE id=%s",
        (booking_id,)
    )
    row = cursor.fetchone()

    # reuse existing token
    if row and row["payment_token"]:
        cursor.close()
        conn.close()
        return row["payment_token"]

    token = secrets.token_urlsafe(32)

    cursor.execute("""
        UPDATE bookings
        SET payment_token=%s
        WHERE id=%s
    """, (token, booking_id))

    conn.commit()
    cursor.close()
    conn.close()

    return token


# ===============================
# 🎉 BOOKING CONFIRMATION EMAIL
# ===============================
def booking_confirmation_email(user_email, booking_id):
    booking = get_booking_details(booking_id)
    if not booking:
        return

    html = f"""
    <h2>🎉 Booking Confirmed!</h2>

    <p>Your advance payment has been received successfully.</p>

    <p><b>Booking Code:</b> {booking['booking_code']}</p>
    <p><b>Theme:</b> {booking['theme_name']}</p>
    <p><b>Event Date:</b> {booking['booking_date']}</p>

    <p><b>Venue Address:</b><br>
    {(booking['venue_address'] or '').replace(chr(10), "<br>")}
    </p>

    <p><b>Total Amount:</b> ₹{booking['amount']}</p>
    <p><b>Advance Paid:</b> ₹{booking['advance_amount']}</p>
    <p><b>Remaining:</b> ₹{booking['remaining']}</p>

    <p>We’ll contact you before the event ❤️</p>
    """

    send_email(
        user_email,
        "Booking Confirmed | MomentsMaker",
        html
    )


# ===============================
# ✨ EVENT COMPLETED + PAYMENT EMAIL
# ===============================
def event_completed_email(user_email, booking_id):
    booking = get_booking_details(booking_id)
    if not booking:
        return

    token = generate_payment_token(booking_id)
    pay_link = f"{BASE_URL}/pay/remaining/{token}"

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif;">
    
    <div style="max-width:600px;margin:30px auto;background:#ffffff;
                padding:25px;border-radius:12px;
                box-shadow:0 4px 12px rgba(0,0,0,0.08);">

        <h2 style="color:#16a34a;margin-top:0;">
            ✨ Event Completed Successfully
        </h2>

        <p>Thank you for choosing <b>MomentsMaker</b> ❤️</p>

        <p><b>Booking Code:</b> {booking['booking_code']}</p>
        <p><b>Total Amount:</b> ₹{booking['amount']}</p>
        <p><b>Advance Paid:</b> ₹{booking['advance_amount']}</p>
        <p><b>Remaining Amount:</b> ₹{booking['remaining']}</p>

        <hr style="margin:20px 0;">

        <p>Please complete your remaining payment using the button below:</p>

        <div style="text-align:center;margin:25px 0;">
            <a href="{pay_link}"
               style="background:#16a34a;
                      color:#ffffff;
                      padding:14px 30px;
                      text-decoration:none;
                      border-radius:8px;
                      font-size:16px;
                      font-weight:bold;
                      display:inline-block;">
                💳 Pay Remaining Amount
            </a>
        </div>

        <p style="font-size:13px;color:#555;">
            If the button doesn’t work, copy & paste this link into your browser:
        </p>

        <p style="font-size:12px;color:#2563eb;word-break:break-all;">
            {pay_link}
        </p>

        <p style="font-size:12px;color:#777;margin-top:20px;">
            No login required • Secure one-time payment link
        </p>

    </div>
    </body>
    </html>
    """

    send_email(
        user_email,
        "Event Completed & Payment Pending | MomentsMaker",
        html
    )

# ===============================
# ❌ BOOKING CANCEL EMAIL
# ==============================
def send_cancel_email(contact_email, booking_id, refund_amount, cancelled_by):

    # 🔹 Fetch booking_code from DB
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT booking_code
        FROM bookings
        WHERE id=%s
    """, (booking_id,))

    row = cur.fetchone()
    cur.close()
    conn.close()

    booking_code = (
        row["booking_code"]
        if row and row["booking_code"]
        else f"MM-{str(booking_id).zfill(6)}"
    )

    subject = "Booking Cancellation Confirmation | MomentsMaker"

    if cancelled_by == "user":
        refund_note = (
            "A 10% service charge has been deducted as per our cancellation policy."
        )
    else:
        refund_note = (
            "This booking was cancelled by our team. You will receive a full refund."
        )

    refund_amount = Decimal(refund_amount).quantize(Decimal("0.01"))

    html = f"""
    <html>
    <body style="font-family:Arial, sans-serif; background:#f4f6f9; padding:20px;">
        
        <div style="max-width:600px;margin:auto;background:white;
                    padding:25px;border-radius:12px;
                    box-shadow:0 4px 12px rgba(0,0,0,0.08);">

            <h2 style="color:#ef4444;">Booking Cancelled</h2>

            <p>Your booking has been successfully cancelled.</p>

            <p><b>Booking Code:</b> {booking_code}</p>

            <p>
                <b>Refund Amount:</b>
                <span style="color:#16a34a;font-weight:bold;">
                    ₹{refund_amount}
                </span>
            </p>

            <p style="color:#555;">{refund_note}</p>

            <p>
                Refund will be credited within <b>3–5 business days</b>.
            </p>

            <p style="font-size:14px;color:#777;">
                Thank you for choosing MomentsMaker ❤️
            </p>

        </div>
    </body>
    </html>
    """

    send_email(contact_email, subject, html)
