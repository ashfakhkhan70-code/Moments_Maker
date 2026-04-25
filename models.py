from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import JSON

db = SQLAlchemy()

# ================= THEME =================
class Theme(db.Model):
    __tablename__ = "themes"

    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(200))
    category = db.Column(db.String(100))
    price = db.Column(db.Integer)
    images = db.Column(JSON)
    inclusions = db.Column(JSON)
    addons = db.Column(JSON)


# ================= BOOKING =================
class Booking(db.Model):
    __tablename__ = "bookings"   # 🔥 THIS TABLE NAME MATTERS

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    theme_id = db.Column(db.String(50))
    amount = db.Column(db.Integer)
    advance_amount = db.Column(db.Integer)
    status = db.Column(db.String(20))


# ================= PAYMENT =================
class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)

    # 🔥 FIXED FOREIGN KEY
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"))

    payment_id = db.Column(db.String(120))
    order_id = db.Column(db.String(120))
    amount = db.Column(db.Integer)
    type = db.Column(db.String(20))  # advance / remaining

class Addon(db.Model):
    __tablename__ = "addons"

    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Integer, default=0)
    image = db.Column(db.String(255))   # single image (theme jaisa)
