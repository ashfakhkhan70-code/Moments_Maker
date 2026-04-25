from flask import Blueprint, render_template, session, redirect, url_for
from db import get_connection
import json
from theme import THEMES

booking_history_bp = Blueprint("booking_history_bp", __name__)

ADDON_IMAGES = {
    "wb1": "images/welcome board.jpg",
    "wb2": "images/welcome board2.webp",
    "wb3": "images/welcome board3.jpg",
    "ea1": "images/entrance arch.webp",
    "ea2": "images/entrance arch2.avif",
    "nl1": "images/neon light.webp",
    "fl1": "images/flowerb.webp",
}

# =========================================================
# 📜 BOOKING HISTORY PAGE
# =========================================================
@booking_history_bp.route("/booking-history")
def booking_history_page():

    if "user" not in session:
        return redirect(url_for("login_page"))

    user_id = session["user"]["id"]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # ============================
    # BOOKINGS
    # ============================
    cursor.execute("""
        SELECT id, booking_code, theme_id, theme_name, theme_image,
               booking_date, event_time, venue_address,
               amount, status, event_details
        FROM bookings
        WHERE user_id=%s
        ORDER BY booking_date DESC
    """, (user_id,))
    bookings = cursor.fetchall()

    booking_ids = [b["id"] for b in bookings]

    # ============================
    # ADDONS
    # ============================
    if booking_ids:
        format_strings = ','.join(['%s'] * len(booking_ids))
        cursor.execute(f"""
            SELECT booking_id, addon_id, addon_name,
                   addon_image, qty, price
            FROM booking_addons
            WHERE booking_id IN ({format_strings})
        """, tuple(booking_ids))
        addons_raw = cursor.fetchall()
    else:
        addons_raw = []

    # ============================
    # PAYMENTS (REAL CALCULATION)
    # ============================
    payment_map = {}

    if booking_ids:
        format_strings = ','.join(['%s'] * len(booking_ids))
        cursor.execute(f"""
            SELECT booking_id, IFNULL(SUM(amount),0) AS paid
            FROM payments
            WHERE booking_id IN ({format_strings})
            GROUP BY booking_id
        """, tuple(booking_ids))

        for row in cursor.fetchall():
            payment_map[row["booking_id"]] = float(row["paid"])

    cursor.close()
    conn.close()

    # ============================
    # MAP ADDONS
    # ============================
    addon_map = {}
    for a in addons_raw:
        addon_map.setdefault(a["booking_id"], []).append(a)

    # ============================
    # PROCESS BOOKINGS
    # ============================
    for b in bookings:

        # Booking Code fallback
        if not b.get("booking_code"):
            b["booking_code"] = f"MM-{str(b['id']).zfill(6)}"

        # Theme fallback
        if not b.get("theme_name"):
            theme_data = THEMES.get(b["theme_id"])
            if theme_data:
                b["theme_name"] = theme_data["name"]
                b["theme_image"] = theme_data["images"][0]
            else:
                b["theme_name"] = "Theme"
                b["theme_image"] = "images/logo2.jpeg"

        # Attach addons
        b["addons"] = addon_map.get(b["id"], [])

        for a in b["addons"]:
            a["addon_name"] = a.get("addon_name") or a.get("addon_id", "Addon")
            a["addon_image"] = (
                a.get("addon_image")
                or ADDON_IMAGES.get(a["addon_id"], "images/logo2.jpeg")
            )

        # ============================
        # 💰 PAYMENT LOGIC
        # ============================
        total_paid = payment_map.get(b["id"], 0)
        remaining = max(float(b["amount"]) - total_paid, 0)

        b["total_paid"] = total_paid
        b["remaining"] = remaining

        # ============================
        # 🎯 STATUS ADJUSTMENT
        # ============================

        if b["status"] == "cancelled":
            b["display_status"] = "Cancelled"

        elif b["status"] == "completed":
            b["display_status"] = "Completed"

        elif total_paid > 0:
             b["display_status"] = "Advance Paid"
             b["status"] = "pending"   # 👈 important

        else:
             b["display_status"] = "Pending"
             b["status"] = "pending"

        # ============================
        # 🎛 BUTTON CONTROL
        # ============================
        b["can_pay_remaining"] = (
            b["status"] == "completed" and remaining > 0
        )
        b["can_cancel"] = (b["status"] == "pending")

    return render_template("booking_history.html", bookings=bookings)
