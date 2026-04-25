from flask import Blueprint, jsonify, request, render_template
from db import get_connection
from datetime import timedelta
from notification import event_completed_email
from models import db, Theme, Addon
from notification import send_cancel_email
import os
from decimal import Decimal
import uuid
import datetime
from flask import request
from flask import make_response
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
from flask import session

admin_bp = Blueprint("admin_bp", __name__)

THEME_UPLOAD_FOLDER = "static/uploads/themes"
ADDON_UPLOAD_FOLDER = "static/uploads/addons"

# =====================================================
# 📊 DASHBOARD STATS
@admin_bp.route("/api/dashboard-stats")
def dashboard_stats():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # 👥 Users
    cur.execute("SELECT COUNT(*) total FROM users WHERE is_admin=0")
    users = cur.fetchone()["total"]

    # 📦 Booking breakdown (PROOFED QUERY)
    cur.execute("""
         SELECT
      COUNT(*) AS total,
SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed,
SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) AS cancelled,
SUM(CASE WHEN status='advance_paid' THEN 1 ELSE 0 END) AS pending
FROM bookings
""")
    booking_stats = cur.fetchone()

    # 💰 Earnings (non-cancelled)
    cur.execute("""
        SELECT IFNULL(SUM(p.amount),0) total
        FROM payments p
        JOIN bookings b ON p.booking_id = b.id
        WHERE b.status != 'cancelled'
    """)
    earnings = cur.fetchone()["total"]

    # ⏳ Pending Amount
    cur.execute("""
        SELECT IFNULL(SUM(amount),0) total
        FROM bookings
        WHERE status != 'cancelled'
    """)
    total_booking_amount = cur.fetchone()["total"]

    cur.execute("""
        SELECT IFNULL(SUM(p.amount),0) total
        FROM payments p
        JOIN bookings b ON p.booking_id = b.id
        WHERE b.status != 'cancelled'
    """)
    total_paid = cur.fetchone()["total"]

    pending_amount = max(total_booking_amount - total_paid, 0)

    cur.close()
    conn.close()

    return jsonify(
    users=users,
    bookings=booking_stats["total"],
    completed=booking_stats["completed"],
    cancelled=booking_stats["cancelled"],
    pending_bookings=booking_stats["pending"],
    earnings=earnings,
    pending=pending_amount
)

# =====================================================
# 👥 USERS
# =====================================================
@admin_bp.route("/api/users")
def get_users():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT id, name, email, mobile
        FROM users
        WHERE is_admin=0
        ORDER BY id DESC
    """)
    users = cur.fetchall()

    cur.close()
    conn.close()
    return jsonify(users)

# =====================================================
# 🧾 BOOKINGS
# =====================================================
@admin_bp.route("/api/bookings")
def get_bookings():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT 
            b.id,
            b.booking_code,
            DATE(b.booking_date) AS event_date,
            b.event_time,
            b.theme_name,
            b.amount,
            b.advance_amount,
            b.status
        FROM bookings b
        ORDER BY b.id DESC
    """)
    bookings = cur.fetchall()

    for b in bookings:
        # booking code fallback
        if not b["booking_code"]:
            b["booking_code"] = f"MM-{str(b['id']).zfill(6)}"

        # event time fix
        et = b["event_time"]
        if isinstance(et, timedelta):
            sec = int(et.total_seconds())
            b["event_time"] = f"{sec//3600:02d}:{(sec%3600)//60:02d}"

        # addons
        cur.execute("""
            SELECT addon_name AS name
            FROM booking_addons
            WHERE booking_id=%s
        """, (b["id"],))
        b["addons"] = cur.fetchall()

        # 🔥🔥 PAYMENT STATUS (THIS WAS MISSING)
        cur.execute("""
            SELECT IFNULL(SUM(amount),0) AS paid
            FROM payments
            WHERE booking_id=%s
        """, (b["id"],))
        paid = cur.fetchone()["paid"]

        if paid >= b["amount"] and b["amount"] > 0:
            b["payment_status"] = "Fully Paid"
        elif paid > 0:
            b["payment_status"] = "Advance Paid"
        else:
            b["payment_status"] = "Not Paid"

    cur.close()
    conn.close()
    return jsonify(bookings)


# =====================================================
# 📄 BOOKING DETAIL
# =====================================================
@admin_bp.route("/api/booking/<int:booking_id>")
def booking_detail(booking_id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT 
            b.id,
            b.booking_code,
            b.theme_name,
            b.theme_image,
            b.amount,
            b.advance_amount,
            b.venue_address,
            b.contact_email,
            DATE(b.booking_date) AS event_date,
            b.event_time,
            b.status,
            COALESCE(u.name,'—') AS customer_name,
            u.mobile
        FROM bookings b
        LEFT JOIN users u ON b.user_id = u.id
        WHERE b.id=%s
    """, (booking_id,))
    b = cur.fetchone()

    if not b:
         return jsonify({"error": "Not found"}), 404

# 🔥 FIX EVENT TIME
    et = b["event_time"]

    if isinstance(et, timedelta):
        sec = int(et.total_seconds())
        b["event_time"] = f"{sec//3600:02d}:{(sec%3600)//60:02d}"
    elif et:
        b["event_time"] = str(et)
    else:
        b["event_time"] = "N/A"


    # 🔥 PAYMENT CALCULATION
    cur.execute("""
        SELECT IFNULL(SUM(amount),0) AS paid
        FROM payments
        WHERE booking_id=%s
    """, (booking_id,))
    paid = cur.fetchone()["paid"]

    remaining = max(b["amount"] - paid, 0)

    b["total_paid"] = paid
    b["remaining"] = remaining

    # 🔥 STATUS LOGIC
    if b["status"] == "cancelled":
        b["payment_status"] = "Cancelled"
        b["remaining"] = 0
    elif remaining == 0 and b["amount"] > 0:
        b["payment_status"] = "Fully Paid"
    elif paid > 0:
        b["payment_status"] = "Advance Paid"
    else:
        b["payment_status"] = "Not Paid"

    # Fix theme image path
    b["theme_image"] = (
        "/static/" + b["theme_image"]
        if b["theme_image"]
        else "/static/default.jpg"
    )

    # 🔥 Addons
    cur.execute("""
        SELECT addon_name AS name, addon_image, price, qty
        FROM booking_addons
        WHERE booking_id=%s
    """, (booking_id,))
    addons = cur.fetchall()

    for a in addons:
        a["image"] = (
            "/static/" + a["addon_image"]
            if a["addon_image"]
            else "/static/default.jpg"
        )

    b["addons"] = addons

    cur.close()
    conn.close()

    return jsonify(b)


# =====================================================
# 🔄 UPDATE BOOKING STATUS
# =====================================================
@admin_bp.route("/api/update-booking-status/<int:booking_id>", methods=["POST"])
def update_booking_status(booking_id):

    status = request.json.get("status")
    cancelled_by = request.json.get("cancelled_by", "admin")

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # 🔍 Get booking details
    cur.execute("""
        SELECT amount, contact_email, status
        FROM bookings
        WHERE id=%s
    """, (booking_id,))
    booking = cur.fetchone()

    if not booking:
        return jsonify({"error": "Booking not found"}), 404

    # Prevent double cancel
    if booking["status"] == "cancelled":
        return jsonify({"error": "Already cancelled"}), 400

    # ==========================
    # 🎯 CANCEL LOGIC
    # ==========================
    if status == "cancelled":

        # 💰 Total Paid
        cur.execute("""
            SELECT IFNULL(SUM(amount),0) AS paid
            FROM payments
            WHERE booking_id=%s
        """, (booking_id,))
        paid = cur.fetchone()["paid"]

      # Convert to Decimal safely
        paid = paid or Decimal("0")

        if cancelled_by == "user":
            refund_amount = (paid * Decimal("0.90")).quantize(Decimal("0.01"))
        else:
             refund_amount = paid


        # Update booking
        cur.execute("""
            UPDATE bookings
            SET status='cancelled',
                cancelled_by=%s
            WHERE id=%s
        """, (cancelled_by, booking_id))

        conn.commit()

        # 📧 Send email
        if booking["contact_email"]:
           send_cancel_email(
            booking["contact_email"],
            booking_id,
           refund_amount,
           cancelled_by)

        cur.close()
        conn.close()

        return jsonify({
            "status": "cancelled",
            "refund_amount": refund_amount
        })

    # ==========================
    # ✅ COMPLETE LOGIC
    # ==========================
    cur.execute("""
        UPDATE bookings
        SET status=%s
        WHERE id=%s
    """, (status, booking_id))
    conn.commit()

    cur.close()
    conn.close()

    if status == "completed" and booking["contact_email"]:
        event_completed_email(booking["contact_email"], booking_id)

    return jsonify({"ok": True})

# =====================================================
# 💳 PAYMENTS
# ====================================================

@admin_bp.route("/api/payments")
def get_payments():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT 
            p.id,
            p.payment_id,
            p.amount,
            p.type AS payment_type,
            DATE(p.created_at) AS date,

            b.id AS booking_id,
            COALESCE(b.booking_code, CONCAT('MM-', LPAD(b.id,6,'0'))) AS booking_code,
            b.amount AS total_amount,
            b.status AS booking_status,
            b.cancelled_by
        FROM payments p
        JOIN bookings b ON p.booking_id = b.id
        ORDER BY p.created_at DESC
    """)
    payments = cur.fetchall()

    for p in payments:
        # total paid
        cur.execute("""
            SELECT IFNULL(SUM(amount),0) AS paid
            FROM payments
            WHERE booking_id=%s
        """, (p["booking_id"],))
        paid = float(cur.fetchone()["paid"])

        # 🔥 STATUS DECISION
        if p["booking_status"] == "cancelled":
            p["status"] = "Cancelled"

            # refund calculation
            if p["cancelled_by"] == "user":
                p["refund_amount"] = round(paid * 0.90, 2)
            else:
                p["refund_amount"] = round(paid, 2)

        elif paid >= p["total_amount"]:
            p["status"] = "Paid"
            p["refund_amount"] = 0

        elif paid > 0:
            p["status"] = "Partial"
            p["refund_amount"] = 0

        else:
            p["status"] = "Pending"
            p["refund_amount"] = 0

        p["is_fully_paid"] = paid >= p["total_amount"]

    cur.close()
    conn.close()
    return jsonify(payments)


@admin_bp.route("/api/payment/<payment_id>")
def payment_detail(payment_id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT 
            p.payment_id,
            p.amount,
            p.type AS payment_type,
            DATE(p.created_at) AS date,

            b.id AS booking_id,
            COALESCE(b.booking_code, CONCAT('MM-', LPAD(b.id,6,'0'))) AS booking_code,
            b.amount AS total_amount,
            DATE(b.booking_date) AS event_date,
            b.status AS booking_status,
            b.cancelled_by,

            u.name AS customer_name,
            u.mobile,
            u.email
        FROM payments p
        JOIN bookings b ON p.booking_id=b.id
        JOIN users u ON b.user_id=u.id
        WHERE p.payment_id=%s
    """, (payment_id,))

    d = cur.fetchone()

    # total paid
    cur.execute("""
        SELECT IFNULL(SUM(amount),0) AS paid
        FROM payments
        WHERE booking_id=%s
    """, (d["booking_id"],))
    paid = float(cur.fetchone()["paid"])

    d["total_paid"] = paid

    # 🔥 STATUS + REFUND LOGIC
    if d["booking_status"] == "cancelled":
        d["status"] = "Cancelled"
        d["remaining"] = 0

        if d["cancelled_by"] == "user":
            d["refund_amount"] = round(paid * 0.90, 2)
        else:
            d["refund_amount"] = round(paid, 2)

    else:
        d["refund_amount"] = 0
        d["remaining"] = max(d["total_amount"] - paid, 0)

        if paid >= d["total_amount"]:
            d["status"] = "Paid"
        elif paid > 0:
            d["status"] = "Partial"
        else:
            d["status"] = "Pending"

    cur.close()
    conn.close()
    return jsonify(d)



@admin_bp.route("/api/invoice/<booking_code>")
def generate_invoice_pdf(booking_code):

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    # ================= BOOKING + USER =================
    cur.execute("""
        SELECT 
            b.id, b.booking_code, b.amount,
            b.advance_amount,
            DATE(b.booking_date) AS event_date,
            b.event_time,
            b.theme_name,
            b.venue_address,
            u.name, u.email, u.mobile
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        WHERE b.booking_code=%s
    """, (booking_code,))
    booking = cur.fetchone()

    if not booking:
        return "Booking not found", 404

    # ================= ADDONS =================
    cur.execute("""
        SELECT addon_name, price, qty
        FROM booking_addons
        WHERE booking_id=%s
    """, (booking["id"],))
    addons = cur.fetchall()

    # 🔥 CALCULATE ADDONS TOTAL
    addons_total = sum(float(a["price"]) * int(a["qty"]) for a in addons)

# 🔥 THEME BASE PRICE (TOTAL - ADDONS)
    theme_price = float(booking["amount"]) - addons_total

    # ================= PAYMENTS =================
    cur.execute("""
        SELECT payment_id, amount, type, DATE(created_at) AS date
        FROM payments
        WHERE booking_id=%s
        ORDER BY created_at ASC
    """, (booking["id"],))
    payments = cur.fetchall()

    cur.close()
    conn.close()

    total_paid = sum(float(p["amount"]) for p in payments)
    remaining = float(booking["amount"]) - total_paid

    if remaining <= 0:
        payment_status = "FULLY PAID"
    elif total_paid > 0:
        payment_status = "PARTIALLY PAID"
    else:
        payment_status = "PENDING"

    # ================= PDF START =================
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 40

    # ===== HEADER =====
    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, y, "MOMENTS MAKER")
    y -= 20

    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Invoice No: INV-{booking_code}")
    c.drawRightString(550, y, f"Invoice Date: {datetime.now().strftime('%d %b %Y')}")
    y -= 18

    c.drawString(40, y, f"Booking ID: {booking_code}")
    c.drawRightString(550, y, f"Payment Status: {payment_status}")

    # ===== CUSTOMER DETAILS =====
    y -= 40
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Bill To")

    y -= 18
    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Name: {booking['name']}")
    y -= 15
    c.drawString(40, y, f"Email: {booking['email']}")
    y -= 15
    c.drawString(40, y, f"Mobile: {booking['mobile']}")
    y -= 15
    c.drawString(40, y, f"Event Date: {booking['event_date']} {booking['event_time']}")
    y -= 15
    c.drawString(40, y, f"Event Address: {booking['venue_address']}")

    # ===== ITEM TABLE =====
    y -= 35
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Description")
    c.drawRightString(350, y, "Qty")
    c.drawRightString(430, y, "Price")
    c.drawRightString(550, y, "Total")

    y -= 12
    c.line(40, y, 550, y)

    # Theme Row
    y -= 20
    c.setFont("Helvetica", 10)
    # Theme Row (FIXED)
    c.drawString(40, y, f"Theme: {booking['theme_name']}")
    c.drawRightString(350, y, "1")
    c.drawRightString(430, y, f"₹{theme_price}")
    c.drawRightString(550, y, f"₹{theme_price}")
    # Add-ons Rows
    for a in addons:
        y -= 18
        total = float(a["price"]) * int(a["qty"])
        c.drawString(40, y, f"Add-on: {a['addon_name']}")
        c.drawRightString(350, y, str(a["qty"]))
        c.drawRightString(430, y, f"₹{a['price']}")
        c.drawRightString(550, y, f"₹{total}")

    # ===== PAYMENT HISTORY =====
    y -= 40
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Payment History")

    y -= 20
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, "Date")
    c.drawString(150, y, "Transaction ID")
    c.drawString(350, y, "Type")
    c.drawRightString(550, y, "Amount")

    y -= 12
    c.line(40, y, 550, y)

    c.setFont("Helvetica", 10)

    for p in payments:
        y -= 18
        c.drawString(40, y, str(p["date"]))
        c.drawString(150, y, p["payment_id"][:20])
        c.drawString(350, y, p["type"].capitalize())
        c.drawRightString(550, y, f"₹{p['amount']}")

    # ===== SUMMARY =====
    y -= 40
    c.line(300, y, 550, y)

    y -= 20
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(550, y, f"Grand Total: ₹{booking['amount']}")

    y -= 18
    c.drawRightString(550, y, f"Advance Paid: ₹{booking['advance_amount']}")

    y -= 18
    c.drawRightString(550, y, f"Total Paid: ₹{total_paid}")

    y -= 18
    c.drawRightString(550, y, f"Remaining: ₹{remaining if remaining > 0 else 0}")

    # ===== FOOTER =====
    y -= 40
    c.setFont("Helvetica", 9)
    c.drawCentredString(width/2, y, "Thank you for choosing Moments Maker!")

    c.showPage()
    c.save()

    buffer.seek(0)

    response = make_response(buffer.read())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = (
        f"attachment; filename=Invoice-{booking_code}.pdf"
    )

    return response

# =====================================================
# 📄 CONTENT PAGE
# =====================================================
@admin_bp.route("/admin/content")
def admin_content_page():
    return render_template("admin_content.html")

# =====================================================
# 🎨 THEMES CRUD
# =====================================================
@admin_bp.route("/api/admin/themes")
def admin_get_themes():
    themes = Theme.query.order_by(Theme.category).all()
    return jsonify([
        {
            "id": t.id,
            "name": t.name,
            "category": t.category,
            "price": t.price,
            "image": t.images[0] if t.images else "default.jpg"
        } for t in themes
    ])

@admin_bp.route("/api/admin/themes", methods=["POST"])
def admin_add_theme():
    name = request.form.get("name")
    category = request.form.get("category")
    price = int(request.form.get("price", 0))

    images = []
    image_file = request.files.get("image")

    if image_file and image_file.filename:
        os.makedirs(THEME_UPLOAD_FOLDER, exist_ok=True)
        filename = f"{uuid.uuid4().hex}_{image_file.filename}"
        path = os.path.join(THEME_UPLOAD_FOLDER, filename)
        image_file.save(path)
        images.append(f"uploads/themes/{filename}")

    theme = Theme(
        id=f"theme-{uuid.uuid4().hex[:8]}",
        name=name,
        category=category,
        price=price,
        images=images,
        inclusions={},
        addons={}
    )

    db.session.add(theme)
    db.session.commit()
    return jsonify({"ok": True})

@admin_bp.route("/api/admin/themes/<theme_id>", methods=["PUT"])
def admin_update_theme(theme_id):
    theme = Theme.query.get_or_404(theme_id)

    theme.name = request.form.get("name", theme.name)
    theme.category = request.form.get("category", theme.category)
    theme.price = int(request.form.get("price", theme.price))

    image_file = request.files.get("image")
    if image_file and image_file.filename:
        os.makedirs(THEME_UPLOAD_FOLDER, exist_ok=True)
        filename = f"{uuid.uuid4().hex}_{image_file.filename}"
        path = os.path.join(THEME_UPLOAD_FOLDER, filename)
        image_file.save(path)
        theme.images = [f"uploads/themes/{filename}"]

    db.session.commit()
    return jsonify({"ok": True})

@admin_bp.route("/api/admin/themes/<theme_id>", methods=["DELETE"])
def admin_delete_theme(theme_id):
    theme = Theme.query.filter_by(id=theme_id).first_or_404()
    db.session.delete(theme)
    db.session.commit()
    return jsonify({"ok": True})

# =====================================================
# ➕ ADDONS CRUD
# =====================================================
@admin_bp.route("/admin/add-on-content")
def admin_addon_content():
    return render_template("add_on_content.html")

@admin_bp.route("/api/admin/addons")
def admin_get_addons():
    addons = Addon.query.order_by(Addon.category).all()
    return jsonify([
        {
            "id": a.id,
            "name": a.name,
            "category": a.category,
            "price": a.price,
            "image": a.image or "default.jpg"
        } for a in addons
    ])

@admin_bp.route("/api/admin/addons", methods=["POST"])
def admin_add_addon():
    name = request.form.get("name")
    category = request.form.get("category")
    price = int(request.form.get("price", 0))

    image_file = request.files.get("image")
    image_path = None

    if image_file and image_file.filename:
        os.makedirs(ADDON_UPLOAD_FOLDER, exist_ok=True)
        filename = f"{uuid.uuid4().hex}_{image_file.filename}"
        path = os.path.join(ADDON_UPLOAD_FOLDER, filename)
        image_file.save(path)
        image_path = f"uploads/addons/{filename}"

    addon = Addon(
        id=f"addon-{uuid.uuid4().hex[:8]}",
        name=name,
        category=category,
        price=price,
        image=image_path
    )

    db.session.add(addon)
    db.session.commit()
    return jsonify({"ok": True})

@admin_bp.route("/api/admin/addons/<addon_id>", methods=["PUT"])
def admin_update_addon(addon_id):
    addon = Addon.query.get_or_404(addon_id)

    addon.name = request.form.get("name", addon.name)
    addon.category = request.form.get("category", addon.category)
    addon.price = int(request.form.get("price", addon.price))

    image_file = request.files.get("image")
    if image_file and image_file.filename:
        os.makedirs(ADDON_UPLOAD_FOLDER, exist_ok=True)
        filename = f"{uuid.uuid4().hex}_{image_file.filename}"
        path = os.path.join(ADDON_UPLOAD_FOLDER, filename)
        image_file.save(path)
        addon.image = f"uploads/addons/{filename}"

    db.session.commit()
    return jsonify({"ok": True})

@admin_bp.route("/api/admin/addons/<addon_id>", methods=["DELETE"])
def admin_delete_addon(addon_id):
    addon = Addon.query.get_or_404(addon_id)
    db.session.delete(addon)
    db.session.commit()
    return jsonify({"ok": True})

# =====================================================
# 🎯 ADDONS FOR THEME (USER SIDE)
# =====================================================
@admin_bp.route("/api/theme/<theme_id>/addons")
def get_theme_addons(theme_id):
    addons = Addon.query.all()
    grouped = {}

    for a in addons:
        grouped.setdefault(a.category, []).append({
            "id": a.id,
            "name": a.name,
            "price": a.price,
            "image": a.image or "default.jpg"
        })

    return jsonify(grouped)

# =====================================================
# 🎫 SUPPORT / CONCERN SYSTEM
# =====================================================

# 🔹 Generate Concern ID (MMH-2026-000001 format)
def generate_concern_id():
    conn = get_connection()
    cur = conn.cursor()

    year = datetime.datetime.now().year

    cur.execute("""
        SELECT COUNT(*) FROM concerns 
        WHERE YEAR(created_at)=%s
    """, (year,))
    count = cur.fetchone()[0] + 1

    concern_id = f"MMH-{year}-{str(count).zfill(6)}"

    cur.close()
    conn.close()
    return concern_id

# =====================================================
# ➕ SUBMIT CONCERN
# =====================================================
@admin_bp.route("/api/concerns", methods=["POST"])
def submit_concern():

    if "user" not in session:
        return jsonify({"error": "Login required"}), 401

    user_id = session["user"]["id"]

    data = request.json

    conn = get_connection()
    cur = conn.cursor()

    row_id = uuid.uuid4().hex[:24]
    year = datetime.now().year
    short_code = uuid.uuid4().hex[:6].upper()
    concern_id = f"MMH-{year}-{short_code}"

    cur.execute("""
        INSERT INTO concerns
        (id, user_id, concern_id, name, phone,
         booking_id, category, sub_category, description)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        row_id,
        user_id,
        concern_id,
        data.get("name"),
        data.get("phone"),
        data.get("booking_id"),
        data.get("category"),
        data.get("sub_category"),
        data.get("description")
    ))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"concern_id": concern_id})


@admin_bp.route("/api/my-concerns")
def get_my_concerns():

    if "user" not in session:
        return jsonify({"error": "Login required"}), 401

    user_id = session["user"]["id"]

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
    SELECT 
        concern_id,
        status,
        admin_reply,
        created_at,
        updated_at
    FROM concerns
    WHERE user_id=%s
    ORDER BY created_at DESC
""", (user_id,))


    data = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify(data)

# =====================================================
# 👨‍💼 ADMIN VIEW ALL CONCERNS
# =====================================================
@admin_bp.route("/api/admin/concerns")
def get_all_concerns():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT id, concern_id, name, phone,
               booking_id, category, sub_category,
               description, status, admin_reply,
               created_at, updated_at
        FROM concerns
        ORDER BY created_at DESC
    """)

    data = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify(data)


# =====================================================
# 🔄 ADMIN UPDATE STATUS
# =====================================================
@admin_bp.route("/api/admin/concerns/<id>", methods=["PUT"])
def update_concern(id):
    data = request.json

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE concerns
        SET status=%s,
            admin_reply=%s,
            updated_at=NOW()
        WHERE id=%s
    """, (
        data.get("status"),
        data.get("admin_reply"),
        id
    ))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"ok": True})

@admin_bp.route("/api/concerns/reply/<concern_id>", methods=["PUT"])
def user_reply_concern(concern_id):
    data = request.json

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE concerns
        SET description = CONCAT(description, '\n\nUSER FOLLOW-UP:\n', %s),
            status = 'Pending',
            updated_at = NOW()
        WHERE concern_id=%s
    """, (
        data.get("message"),
        concern_id
    ))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"ok": True})

@admin_bp.route("/api/admin/concerns/<id>", methods=["GET"])
def get_single_concern(id):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT id, concern_id, name, phone,
               booking_id, category, sub_category,
               description, status, admin_reply,
               created_at, updated_at
        FROM concerns
        WHERE id=%s
    """, (id,))

    data = cur.fetchone()

    cur.close()
    conn.close()

    if not data:
        return jsonify({"error": "Not found"}), 404

    return jsonify(data)
