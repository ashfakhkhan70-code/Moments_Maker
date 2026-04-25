from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from db import get_connection
import os
import uuid

account_bp = Blueprint("account_bp", __name__)

UPLOAD_FOLDER = "static/uploads/profile"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =========================
# PAGE ROUTE
# =========================
@account_bp.route("/account")
def account_page():
    if "user" not in session:
        return redirect(url_for("login_page"))
    return render_template("account.html")


# =========================
# API: GET ACCOUNT DATA
# =========================
@account_bp.route("/api/account-data", methods=["GET"])
def api_account_data():
    if "user" not in session:
        return jsonify({"ok": False}), 401

    user_id = session["user"]["id"]
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT name,email,mobile,profile_photo FROM users WHERE id=%s", (user_id,))
    profile = cursor.fetchone()

    cursor.execute("""
        SELECT line1,line2,road,taluka,city,state,pincode
        FROM addresses WHERE user_id=%s
    """, (user_id,))
    address = cursor.fetchone() or {}

    cursor.close()
    conn.close()

    return jsonify({"ok": True, "profile": profile, "address": address})


# =========================
# API: SAVE PROFILE + PHOTO
# =========================
@account_bp.route("/api/save-profile", methods=["POST"])
def api_save_profile():
    if "user" not in session:
        return jsonify({"ok": False}), 401

    user_id = session["user"]["id"]

    name = request.form.get("name","").strip()
    email = request.form.get("email","").strip().lower()
    mobile = request.form.get("mobile","").strip()
    file = request.files.get("photo")

    photo_path = None

    if file and file.filename:
        ext = file.filename.split('.')[-1]
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        photo_path = f"/{UPLOAD_FOLDER}/{filename}"

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if photo_path:
        cursor.execute("""
            UPDATE users SET name=%s,email=%s,mobile=%s,profile_photo=%s
            WHERE id=%s
        """, (name,email,mobile,photo_path,user_id))
    else:
        cursor.execute("""
            UPDATE users SET name=%s,email=%s,mobile=%s
            WHERE id=%s
        """, (name,email,mobile,user_id))

    conn.commit()
    cursor.close()
    conn.close()

    session["user"]["name"] = name
    session["user"]["email"] = email

    return jsonify({"ok": True, "message": "Profile updated"})


# =========================
# API: SAVE ADDRESS
# =========================
@account_bp.route("/api/save-address", methods=["POST"])
def api_save_address():
    if "user" not in session:
        return jsonify({"ok": False}), 401

    user_id = session["user"]["id"]
    data = request.get_json()

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id FROM addresses WHERE user_id=%s", (user_id,))
    exists = cursor.fetchone()

    cursor2 = conn.cursor()
    if exists:
        cursor2.execute("""
            UPDATE addresses SET line1=%s,line2=%s,road=%s,taluka=%s,city=%s,state=%s,pincode=%s
            WHERE user_id=%s
        """, (data["line1"],data["line2"],data["road"],data["taluka"],
              data["city"],data["state"],data["pincode"],user_id))
    else:
        cursor2.execute("""
            INSERT INTO addresses(user_id,line1,line2,road,taluka,city,state,pincode)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (user_id,data["line1"],data["line2"],data["road"],data["taluka"],
              data["city"],data["state"],data["pincode"]))

    conn.commit()
    cursor.close()
    cursor2.close()
    conn.close()

    return jsonify({"ok": True})


# =========================
# API: UPDATE PASSWORD
# =========================
@account_bp.route("/api/update-password", methods=["POST"])
def api_update_password():
    if "user" not in session:
        return jsonify({"ok": False}), 401

    user_id = session["user"]["id"]
    data = request.get_json()

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT password_hash FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()

    if not user or not check_password_hash(user["password_hash"], data["current_password"]):
        return jsonify({"ok": False, "message": "Wrong password"})

    new_hash = generate_password_hash(data["new_password"])
    cursor2 = conn.cursor()
    cursor2.execute("UPDATE users SET password_hash=%s WHERE id=%s", (new_hash,user_id))
    conn.commit()

    cursor.close()
    cursor2.close()
    conn.close()

    return jsonify({"ok": True, "message": "Password updated"})
