from flask import Blueprint, jsonify, request
from models import db, Addon
import os, uuid

addon_bp = Blueprint("addon_bp", __name__)

ADDON_UPLOAD_FOLDER = "static/uploads/addons"

# =====================================================
# 🔥 STATIC ADDONS (DB SEED)
# =====================================================
ADDONS = [

    {"id":"wb1","name":"Balloon Pillar Welcome Board","category":"Welcome Board","price":699,"image":"images/welcome-board.jpg"},
    {"id":"wb2","name":"Easel Stand Welcome Board","category":"Welcome Board","price":999,"image":"images/welcome-board2.webp"},
    {"id":"wb3","name":"Balloon Garland Easel Stand Welcome Board","category":"Welcome Board","price":999,"image":"images/welcome-board3.jpg"},
    {"id":"wb4","name":"Premium Baby Photos Welcome Board","category":"Welcome Board","price":1199,"image":"images/welcome-board4.jpg"},
    {"id":"wb5","name":"Premium Theme Welcome Easel Stand","category":"Welcome Board","price":1399,"image":"images/welcome-board5.jpg"},
    {"id":"wb6","name":"Welcome Board Premium","category":"Welcome Board","price":999,"image":"images/welcome-board6.jpg"},

    {"id":"ea1","name":"Entrance Arch 1","category":"Entrance Arch","price":999,"image":"images/entrance-arch1.webp"},
    {"id":"ea2","name":"Entrance Arch 2","category":"Entrance Arch","price":999,"image":"images/entrance-arch2.avif"},
    {"id":"ea3","name":"Entrance Arch 3","category":"Entrance Arch","price":1199,"image":"images/entrance-arch3.webp"},
    {"id":"ea4","name":"Entrance Arch 4","category":"Entrance Arch","price":1299,"image":"images/entrance-arch4.webp"},
    {"id":"ea5","name":"Entrance Arch 5","category":"Entrance Arch","price":1499,"image":"images/entrance-arch5.webp"},

    {"id":"nl1","name":"Neon Light 1","category":"Neon Lights","price":899,"image":"images/neon-light1.webp"},
    {"id":"nl2","name":"Neon Light 2","category":"Neon Lights","price":899,"image":"images/neon-light2.avif"},
    {"id":"nl3","name":"Neon Light 3","category":"Neon Lights","price":999,"image":"images/neon-light3.avif"},
    {"id":"nl4","name":"Neon Light 4","category":"Neon Lights","price":1099,"image":"images/neon-light4.webp"},
    {"id":"nl5","name":"Neon Light 5","category":"Neon Lights","price":1199,"image":"images/neon-light5.jpg"},

    {"id":"fl1","name":"Flower Bouquet 1","category":"Flower Bouquet","price":399,"image":"images/flower1.webp"},
    {"id":"fl2","name":"Flower Bouquet 2","category":"Flower Bouquet","price":499,"image":"images/flower2.webp"},
    {"id":"fl3","name":"Flower Bouquet 3","category":"Flower Bouquet","price":599,"image":"images/flower3.webp"},
    {"id":"fl4","name":"Flower Bouquet 4","category":"Flower Bouquet","price":699,"image":"images/flower4.png"},
]

# =====================================================
# 🔥 SEED ADDONS
# =====================================================
def seed_addons():
    for a in ADDONS:
        if not Addon.query.get(a["id"]):
            db.session.add(Addon(**a))
    db.session.commit()

# =====================================================
# 🔥 SHARED GROUP FUNCTION (VERY IMPORTANT)
# =====================================================
def get_grouped_addons():
    addons = Addon.query.all()
    grouped = {}

    for a in addons:
        grouped.setdefault(a.category, []).append({
            "id": a.id,
            "name": a.name,
            "price": a.price,
            "image": a.image
        })

    return grouped

# =====================================================
# 🔥 ADMIN – GET ALL ADDONS
# =====================================================
@addon_bp.route("/api/admin/addons")
def admin_addons():
    data = []
    grouped = get_grouped_addons()

    for cat, items in grouped.items():
        for a in items:
            a["category"] = cat
            data.append(a)

    return jsonify(data)

# =====================================================
# ➕ ADMIN – ADD ADDON
# =====================================================
@addon_bp.route("/api/admin/addons", methods=["POST"])
def add_addon():
    image_path = None
    image_file = request.files.get("image")

    if image_file and image_file.filename:
        os.makedirs(ADDON_UPLOAD_FOLDER, exist_ok=True)
        filename = f"{uuid.uuid4().hex}_{image_file.filename}"
        image_file.save(os.path.join(ADDON_UPLOAD_FOLDER, filename))
        image_path = f"uploads/addons/{filename}"

    addon = Addon(
        id=f"addon-{uuid.uuid4().hex[:8]}",
        name=request.form.get("name"),
        category=request.form.get("category"),
        price=int(request.form.get("price", 0)),
        image=image_path
    )

    db.session.add(addon)
    db.session.commit()
    return jsonify({"ok": True})

# =====================================================
# ✏️ ADMIN – UPDATE ADDON
# =====================================================
@addon_bp.route("/api/admin/addons/<addon_id>", methods=["PUT"])
def update_addon(addon_id):
    addon = Addon.query.get_or_404(addon_id)

    addon.name = request.form.get("name")
    addon.category = request.form.get("category")
    addon.price = int(request.form.get("price", addon.price))

    image_file = request.files.get("image")
    if image_file and image_file.filename:
        os.makedirs(ADDON_UPLOAD_FOLDER, exist_ok=True)
        filename = f"{uuid.uuid4().hex}_{image_file.filename}"
        image_file.save(os.path.join(ADDON_UPLOAD_FOLDER, filename))
        addon.image = f"uploads/addons/{filename}"

    db.session.commit()
    return jsonify({"ok": True})

# =====================================================
# 🗑️ ADMIN – DELETE ADDON
# =====================================================
@addon_bp.route("/api/admin/addons/<addon_id>", methods=["DELETE"])
def delete_addon(addon_id):
    addon = Addon.query.get_or_404(addon_id)
    db.session.delete(addon)
    db.session.commit()
    return jsonify({"ok": True})

# =====================================================
# 🔥 USER – THEME → ADDONS
# =====================================================
@addon_bp.route("/api/theme/<theme_id>/addons")
def theme_addons(theme_id):
    return jsonify(get_grouped_addons())
