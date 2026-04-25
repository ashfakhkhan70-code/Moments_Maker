from flask import Blueprint, render_template, request, jsonify, session
from werkzeug.security import generate_password_hash
from db import get_connection
import random, string
from datetime import datetime, timedelta
from notification import send_email   # 👈 SMTP wala send_email

forget_bp = Blueprint("forget_bp", __name__)

# ==================================================
# 🔐 FORGOT PASSWORD PAGE
# ==================================================
@forget_bp.route("/forget", methods=["GET"])
def forget_page():
    return render_template("forget.html")


# ==================================================
# 1️⃣ SEND OTP
# API: /api/reset-password/send-otp
# ==================================================
@forget_bp.route("/api/reset-password/send-otp", methods=["POST"])
def send_otp():

    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email required"}), 400

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT id, name FROM users WHERE email=%s", (email,))
    user = cur.fetchone()

    cur.close()
    conn.close()

    if not user:
        return jsonify({"error": "Email not registered"}), 404

    # 🔐 OTP
    otp = "".join(random.choices(string.digits, k=6))

    session["reset_email"] = email
    session["reset_otp"] = otp
    session["reset_expiry"] = (
        datetime.now() + timedelta(minutes=5)
    ).timestamp()

    # 📧 EMAIL
    html = f"""
    <h2>Password Reset OTP</h2>
    <p>Hello <b>{user['name']}</b>,</p>
    <p>Your OTP is:</p>
    <h1 style="color:#2563eb">{otp}</h1>
    <p>This OTP is valid for <b>5 minutes</b>.</p>
    """

    send_email(
        email,
        "🔐 Password Reset OTP | MomentsMaker",
        html
    )

    return jsonify({"ok": True})


# ==================================================
# 2️⃣ VERIFY OTP
# API: /api/reset-password/verify-otp
# ==================================================
@forget_bp.route("/api/reset-password/verify-otp", methods=["POST"])
def verify_otp():

    data = request.get_json()
    email = data.get("email")
    otp = data.get("otp")

    if (
        session.get("reset_email") == email
        and session.get("reset_otp") == otp
        and datetime.now().timestamp() <= session.get("reset_expiry", 0)
    ):
        session["otp_verified"] = True
        return jsonify({"ok": True})

    return jsonify({"error": "Invalid or expired OTP"}), 401


# ==================================================
# 3️⃣ RESET PASSWORD
# API: /api/reset-password/confirm
# ==================================================
@forget_bp.route("/api/reset-password/confirm", methods=["POST"])
def reset_password():

    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not session.get("otp_verified"):
        return jsonify({"error": "Unauthorized"}), 401

    if session.get("reset_email") != email:
        return jsonify({"error": "Email mismatch"}), 401

    if not password or len(password) < 6:
        return jsonify({"error": "Weak password"}), 400

    hashed = generate_password_hash(password)

    conn = get_connection()
    cur = conn.cursor()

    # ⚠️ IMPORTANT: column name = password_hash
    cur.execute(
        "UPDATE users SET password_hash=%s WHERE email=%s",
        (hashed, email)
    )

    conn.commit()
    cur.close()
    conn.close()

    # 🧹 CLEAR SESSION
    session.pop("reset_email", None)
    session.pop("reset_otp", None)
    session.pop("reset_expiry", None)
    session.pop("otp_verified", None)

    return jsonify({"ok": True})
