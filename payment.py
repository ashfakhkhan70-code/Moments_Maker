import razorpay
import uuid
import os
from dotenv import load_dotenv
from flask import Blueprint, render_template, request, redirect, url_for, session
from db import get_connection
from notification import (
    booking_confirmation_email,
    event_completed_email
)

payment_bp = Blueprint("payment_bp", __name__)

# ===============================
# 🔐 Razorpay Keys
# ===============================
load_dotenv()

RAZORPAY_KEY = os.getenv("RAZORPAY_KEY")
RAZORPAY_SECRET = os.getenv("RAZORPAY_SECRET")

if not RAZORPAY_KEY or not RAZORPAY_SECRET:
    raise Exception("Missing Razorpay keys")


client = razorpay.Client(auth=(RAZORPAY_KEY, RAZORPAY_SECRET))

# =========================================================
# 💳 PAYMENT PAGE (LOGIN REQUIRED – ADVANCE ONLY)
# =========================================================
@payment_bp.route("/payment/<int:booking_id>/<string:ptype>")
def payment_page(booking_id, ptype):

    if "user" not in session:
        return redirect(url_for("login_page", next=request.url))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM bookings WHERE id=%s", (booking_id,))
    booking = cursor.fetchone()

    if not booking:
        cursor.close()
        conn.close()
        return "Booking not found", 404

    # Only advance payment allowed here
    if ptype != "advance":
        return "Invalid payment type", 400

    pay_amount = booking["advance_amount"]

    order = client.order.create({
        "amount": int(pay_amount * 100),
        "currency": "INR",
        "payment_capture": 1
    })

    cursor.close()
    conn.close()

    return render_template(
        "payment.html",
        booking=booking,
        pay_amount=pay_amount,
        razorpay_key=RAZORPAY_KEY,
        order_id=order["id"],
        ptype="advance"
    )

# =========================================================
# 💳 REMAINING PAYMENT PAGE (NO LOGIN – TOKEN BASED)
# =========================================================
@payment_bp.route("/pay/remaining/<token>")
def pay_remaining(token):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM bookings
        WHERE payment_token=%s
    """, (token,))
    booking = cursor.fetchone()

    if not booking:
        cursor.close()
        conn.close()
        return "Invalid or expired payment link", 404

    remaining = booking["amount"] - booking["advance_amount"]

    order = client.order.create({
        "amount": int(remaining * 100),
        "currency": "INR",
        "payment_capture": 1
    })

    cursor.close()
    conn.close()

    return render_template(
        "payment.html",
        booking=booking,
        pay_amount=remaining,
        razorpay_key=RAZORPAY_KEY,
        order_id=order["id"],
        ptype="remaining"
    )
# =========================================================
# ✅ PAYMENT SUCCESS (BOTH CASES)
# =========================================================
@payment_bp.route("/payment-success", methods=["POST"])
def payment_success():

    data = request.form

    booking_id = int(data.get("booking_id"))
    payment_id = data.get("razorpay_payment_id")
    order_id = data.get("razorpay_order_id")
    signature = data.get("razorpay_signature")
    ptype = data.get("ptype")
    amount = float(data.get("amount"))

    # 🔐 Verify Razorpay signature
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature
        })
    except:
        return "Payment verification failed", 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # 🚫 Prevent duplicate payment
    cursor.execute("SELECT id FROM payments WHERE payment_id=%s", (payment_id,))
    if cursor.fetchone():
        cursor.close()
        conn.close()

        # 🔀 duplicate → redirect safely
        if ptype == "advance":
            return redirect(url_for("booking_history_bp.booking_history_page"))
        else:
            return redirect(url_for("payment_bp.payment_success_page"))

    # 💾 Save payment
    cursor.execute("""
        INSERT INTO payments (booking_id, payment_id, order_id, amount, type)
        VALUES (%s,%s,%s,%s,%s)
    """, (booking_id, payment_id, order_id, amount, ptype))

    # 📧 Get user email
    cursor.execute("""
        SELECT contact_email
        FROM bookings
        WHERE id=%s
    """, (booking_id,))
    row = cursor.fetchone()
    user_email = row["contact_email"] if row else None

    # 🎯 ADVANCE PAYMENT
    if ptype == "advance":
        booking_code = "MM-" + uuid.uuid4().hex[:12].upper()

        cursor.execute("""
            UPDATE bookings
            SET status='advance_paid',
                booking_code=%s
            WHERE id=%s
        """, (booking_code, booking_id))

        conn.commit()

        if user_email:
            booking_confirmation_email(user_email, booking_id)

    # 🎯 REMAINING PAYMENT
    else:
        cursor.execute("""
            UPDATE bookings
            SET status='completed',
                payment_token=NULL
            WHERE id=%s
        """, (booking_id,))
        conn.commit()

    cursor.close()
    conn.close()

    # 🔀 FINAL REDIRECT
    if ptype == "advance":
        return redirect(url_for("booking_history_bp.booking_history_page"))
    else:
        return redirect(url_for("payment_bp.payment_success_page"))


# =====================================================
# 🎉 PAYMENT SUCCESS PAGE (PUBLIC – NO LOGIN)
# =====================================================
@payment_bp.route("/payment-success-page")
def payment_success_page():
    return render_template("payment_success.html")
