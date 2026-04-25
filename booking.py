from flask import Blueprint, request, session, redirect, url_for
from db import get_connection
from models import Theme
import json

booking_bp = Blueprint("booking_bp", __name__)

@booking_bp.route("/create-order", methods=["POST"])
def create_order():

    if "user" not in session:
        return redirect(url_for("login_page", next=request.url))

    user_id = session["user"]["id"]
    theme_id = request.form.get("theme_id")

    # 📧 BOOKING CONTACT EMAIL
    contact_email = request.form.get("email")

    # 📍 VENUE ADDRESS (FROM FORM FIELDS)
    address_line1 = request.form.get("address_line1")
    address_line2 = request.form.get("address_line2")
    city = request.form.get("city")
    state = request.form.get("state")
    pincode = request.form.get("pincode")

    # 🔗 COMBINE ADDRESS (CLEAN FORMAT)
    venue_address = f"""
{address_line1}
{address_line2 or ''}
{city}, {state} - {pincode}
""".strip()

    # 🎨 THEME SNAPSHOT
    theme = Theme.query.get(theme_id)
    if not theme:
        return "Theme not found", 404

    theme_name = theme.name
    theme_image = theme.images[0] if theme.images else "images/logo2.jpeg"

    total_amount = int(request.form.get("total_amount", 0))
    advance_amount = int(request.form.get("advance_amount", 0))
    event_date = request.form.get("event_date")
    event_time = request.form.get("event_time")

    event_details = {
        "bname": request.form.get("bname"),
        "couple_name": request.form.get("couple_name"),
    }

    conn = get_connection()
    cursor = conn.cursor()

    # 💾 SAVE BOOKING (EMAIL + VENUE ADDRESS)
    cursor.execute("""
        INSERT INTO bookings
        (user_id, theme_id, theme_name, theme_image,
         booking_date, event_time,
         amount, advance_amount, event_details,
         contact_email, venue_address, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending')
    """, (
        user_id,
        theme_id,
        theme_name,
        theme_image,
        event_date,
        event_time,
        total_amount,
        advance_amount,
        json.dumps(event_details),
        contact_email,
        venue_address
    ))

    booking_id = cursor.lastrowid

    # ➕ SAVE ADDONS
    addons_json = request.form.get("addons_json")
    if addons_json:
        addons = json.loads(addons_json)
        for a in addons:
            addon_image = a.get("image") or a.get("img") 
            cursor.execute("""
                INSERT INTO booking_addons
                (booking_id, addon_id, addon_name, addon_image, qty, price)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (
                booking_id,
                a["id"],
                a["name"],
                addon_image,
                a["qty"],
                a["price"]
            ))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(
        url_for("payment_bp.payment_page", booking_id=booking_id, ptype="advance")
    )
