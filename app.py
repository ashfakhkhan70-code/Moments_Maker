from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_connection
from account import account_bp
from theme import theme_bp
from booking import booking_bp
from models import db
from addon import addon_bp
from forget import forget_bp
from flask import make_response
from payment import payment_bp
from booking_history import booking_history_bp
from admin import admin_bp   # ✅ admin
# ❌ notification_bp removed because notification.py now only has email functions

app = Flask(__name__)
app.secret_key = "momentsmaker_secret_key_123"
app.config["SESSION_PERMANENT"] = False

# ================= DATABASE CONFIG =================
app.config["SQLALCHEMY_DATABASE_URI"]="mysql+pymysql://root:tiger@localhost/momentsmaker"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
with app.app_context():
    db.create_all()

    from theme import seed_themes
    from addon import seed_addons
    seed_themes()
    seed_addons()


# ================= BLUEPRINTS =================
app.register_blueprint(account_bp)
app.register_blueprint(theme_bp)
app.register_blueprint(booking_bp)
app.register_blueprint(booking_history_bp)
app.register_blueprint(payment_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(addon_bp)
app.register_blueprint(forget_bp)
# =====================================================
# 🔐 USER SIGNUP
# =====================================================
@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.get_json()
    name = data.get("name")
    email = data.get("email").lower()
    password = data.get("password")

    password_hash = generate_password_hash(password)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
    if cursor.fetchone():
        return jsonify({"ok": False, "message": "Email already registered"}), 409

    cursor.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (%s,%s,%s)",
        (name, email, password_hash)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"ok": True}), 201


# =====================================================
# 🔐 LOGIN (ADMIN + USER)
# =====================================================
@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    email = data.get("email").lower()
    password = data.get("password")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"ok": False, "message": "Invalid credentials"}), 401

    # 🔥 ADMIN LOGIN
    if user.get("is_admin"):
        session["admin"] = {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"]
        }
        return jsonify({"ok": True, "redirect": "/admin"})

    # 👤 NORMAL USER LOGIN
    session["user"] = {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"]
    }
    return jsonify({"ok": True, "redirect": "/home"})


# =====================================================
# 🛡 ADMIN DASHBOARD
# =====================================================
@app.route("/admin")
def admin_dashboard():
    if "admin" not in session:
        return redirect("/login")

    response = make_response(
        render_template("admin.html", admin_name=session["admin"]["name"])
    )

    # Cache disable (VERY IMPORTANT)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response

# =====================================================
# 🚪 LOGOUT
# =====================================================
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/home")

@app.route("/admin-logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/home")
# =====================================================
# 🌐 STATIC PAGES
# =====================================================
@app.route("/")
def root():
    return redirect("/home")

@app.route("/home")
def home_page():
    return render_template("home.html")

@app.route("/gallery")
def gallery_page():
    return render_template("gallery.html")

@app.route("/support")
def support_page():
    return render_template("support.html")

@app.route("/signup")
def signup_page():
    return render_template("signup.html")


@app.route("/about")
def about_page():
    return render_template("about.html")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/payment-success")
def payment_success():
    return render_template("payment_success.html")


@app.route("/account")
def account_page():
    if "user" not in session:
        return redirect("/login")
    return render_template("account.html")


# =====================================================
# 🚀 RUN SERVER
# =====================================================
if __name__ == "__main__":
    app.run(debug=True)
