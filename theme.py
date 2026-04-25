from flask import Blueprint, render_template, abort
from models import db, Theme

theme_bp = Blueprint("theme_bp", __name__)

# =====================================================
# 🔥 ALL THEMES FROM YOUR GALLERY.HTML
# =====================================================
THEMES = {

    # ================= WEDDING =================
    "wed-1": {"id":"wed-1","name":"Wedding Decoration","category":"wedding","price":12999,"images":["images/wed.jpg"],"inclusions":{},"addons":{}},
    "wed-2": {"id":"wed-2","name":"Wedding Decoration Premium","category":"wedding","price":14999,"images":["images/wed2.jpg"],"inclusions":{},"addons":{}},
    "wed-3": {"id":"wed-3","name":"Royal Wedding Setup","category":"wedding","price":16999,"images":["images/wed3.webp"],"inclusions":{},"addons":{}},
    "wed-5": {"id":"wed-5","name":"Luxury Wedding Decor","category":"wedding","price":21999,"images":["images/wed5.avif"],"inclusions":{},"addons":{}},
    "wed-6": {"id":"wed-6","name":"Wedding Setup (JPEG)","category":"wedding","price":13999,"images":["images/wed5.jpeg"],"inclusions":{},"addons":{}},

    # ================= BIRTHDAY =================
    "birth-1":{"id":"birth-1","name":"Birthday Decoration Basic","category":"birthday","price":3999,"images":["images/birth.webp"],"inclusions":{},"addons":{}},
    "birth-2":{"id":"birth-2","name":"Birthday Decoration Classic","category":"birthday","price":4499,"images":["images/birthday14.jpeg"],"inclusions":{},"addons":{}},
    "birth-3":{"id":"birth-3","name":"Birthday Party Setup Deluxe","category":"birthday","price":4999,"images":["images/birthday.jpeg"],"inclusions":{},"addons":{}},
    "birth-4":{"id":"birth-4","name":"Birthday Theme Decor (Gold)","category":"birthday","price":5499,"images":["images/birthday15.jpg"],"inclusions":{},"addons":{}},
    "birth-5":{"id":"birth-5","name":"Birthday Theme Decor (Pink)","category":"birthday","price":5499,"images":["images/birthday4.jpeg"],"inclusions":{},"addons":{}},
    "birth-6":{"id":"birth-6","name":"Birthday Theme Decor (Kids)","category":"birthday","price":5499,"images":["images/birthday5.webp"],"inclusions":{},"addons":{}},
    "birth-7":{"id":"birth-7","name":"Birthday Theme Decor (Silver)","category":"birthday","price":5499,"images":["images/birthday6.jpeg"],"inclusions":{},"addons":{}},
    "birth-8":{"id":"birth-8","name":"Birthday Theme Decor (Balloon)","category":"birthday","price":5499,"images":["images/birthday12.jpeg"],"inclusions":{},"addons":{}},
    "birth-9":{"id":"birth-9","name":"Grand Birthday Setup","category":"birthday","price":5999,"images":["images/birthday13.jpeg"],"inclusions":{},"addons":{}},

    # ================= ANNIVERSARY =================
    "anni-1":{"id":"anni-1","name":"Anniversary Decoration","category":"anniversary","price":4999,"images":["images/anniversary.webp"],"inclusions":{},"addons":{}},
    "anni2-1":{"id":"anni2-1","name":"Anniversary Decoration Premium","category":"anniversary","price":10999,"images":["images/anniversary4.webp"],"inclusions":{},"addons":{}},
    "anni-3":{"id":"anni-3","name":"Anniversary Decoration","category":"anniversary","price":10999,"images":["images/anniversary3.png"],"inclusions":{},"addons":{}},
    "anni-4":{"id":"anni-4","name":"Anniversary Decoration","category":"anniversary","price":10999,"images":["images/anniversary1.jpeg"],"inclusions":{},"addons":{}},
    "anni-5":{"id":"anni-5","name":"Anniversary Decoration","category":"anniversary","price":10999,"images":["images/anniversary2.webp"],"inclusions":{},"addons":{}},

    # ================= HALDI =================
    "haldi-1":{"id":"haldi-1","name":"Haldi Decoration","category":"haldi","price":8999,"images":["images/haldi.jpg"],"inclusions":{},"addons":{}},
    "haldi-2":{"id":"haldi-2","name":"Haldi Decoration Premium","category":"haldi","price":9999,"images":["images/haldi2.jpg"],"inclusions":{},"addons":{}},
    "haldi-3":{"id":"haldi-3","name":"Haldi Decoration Royal","category":"haldi","price":10999,"images":["images/haldi3.avif"],"inclusions":{},"addons":{}},
    "haldi-4":{"id":"haldi-4","name":"Haldi Decoration (Theme)","category":"haldi","price":8999,"images":["images/haldi4.jpg"],"inclusions":{},"addons":{}},
    "haldi-5":{"id":"haldi-5","name":"Haldi Decoration (Yellow Setup)","category":"haldi","price":9999,"images":["images/haldi5.jpg"],"inclusions":{},"addons":{}},
    "haldi-6":{"id":"haldi-6","name":"Haldi Decoration Grand","category":"haldi","price":11999,"images":["images/haldi6.jpg"],"inclusions":{},"addons":{}},

    # ================= BABY SHOWER =================
    "baby-1":{"id":"baby-1","name":"Baby Shower Decoration","category":"babyshower","price":6999,"images":["images/baby.JPG"],"inclusions":{},"addons":{}},

    # ================= WELCOME BABY =================
    "wb-1":{"id":"wb-1","name":"Welcome Baby Decoration (Setup 1)","category":"welcomebaby","price":7999,"images":["images/wb.jpg"],"inclusions":{},"addons":{}},
    "wb-2":{"id":"wb-2","name":"Welcome Baby Decoration (Setup 2)","category":"welcomebaby","price":8999,"images":["images/wb2.jpg"],"inclusions":{},"addons":{}},
    "wb-3":{"id":"wb-3","name":"Welcome Baby Decoration (Setup 3)","category":"welcomebaby","price":9999,"images":["images/wb3.jpg"],"inclusions":{},"addons":{}},
    "wb-4":{"id":"wb-4","name":"Welcome Baby Decoration (Setup 4)","category":"welcomebaby","price":10999,"images":["images/wb4.jpg"],"inclusions":{},"addons":{}},
    "wb-5":{"id":"wb-5","name":"Welcome Baby Decoration (Setup 5)","category":"welcomebaby","price":11999,"images":["images/wb5.avif"],"inclusions":{},"addons":{}},
    "wb-6":{"id":"wb-6","name":"Welcome Baby Decoration (Setup 6)","category":"welcomebaby","price":12999,"images":["images/wb7.webp"],"inclusions":{},"addons":{}},

    # ================= NAMING CEREMONY =================
    "nc-1":{"id":"nc-1","name":"Naming Ceremony Decoration (Setup 1)","category":"nc","price":4999,"images":["images/nc.webp"],"inclusions":{},"addons":{}},
    "nc-2":{"id":"nc-2","name":"Naming Ceremony Decoration (Setup 2)","category":"nc","price":5999,"images":["images/nc2.jpg"],"inclusions":{},"addons":{}},
    "nc-3":{"id":"nc-3","name":"Naming Ceremony Decoration (Setup 3)","category":"nc","price":6999,"images":["images/nc3.jpg"],"inclusions":{},"addons":{}},
    "nc-4":{"id":"nc-4","name":"Naming Ceremony Decoration (Setup 4)","category":"nc","price":7999,"images":["images/nc4.webp"],"inclusions":{},"addons":{}},
    "nc-5":{"id":"nc-5","name":"Naming Ceremony Decoration (Setup 5)","category":"nc","price":8999,"images":["images/nc5.jpg"],"inclusions":{},"addons":{}},
    "nc-6":{"id":"nc-6","name":"Naming Ceremony Decoration (Setup 6)","category":"nc","price":9999,"images":["images/nc6.webp"],"inclusions":{},"addons":{}},
    "nc-7":{"id":"nc-7","name":"Naming Ceremony Decoration (Setup 7)","category":"nc","price":10999,"images":["images/nc7.webp"],"inclusions":{},"addons":{}},

    # ================= FESTIVAL =================
    "fest-gc-1":{"id":"fest-gc-1","name":"Ganesh Chaturthi Decoration (Setup 1)","category":"festival","price":6999,"images":["images/gc3.webp"],"inclusions":{},"addons":{}},
    "fest-christmas-1":{"id":"fest-christmas-1","name":"Christmas Decoration (Setup 1)","category":"festival","price":6499,"images":["images/christmas.jpg"],"inclusions":{},"addons":{}},
    "fest-newyear-1":{"id":"fest-newyear-1","name":"New Year Decoration (Setup 1)","category":"festival","price":6499,"images":["images/newyear1.webp"],"inclusions":{},"addons":{}},
}

# ================= AUTO SAVE TO DB =================
def seed_themes():
    for t in THEMES.values():
        exists = Theme.query.filter_by(id=t["id"]).first()
        if not exists:
            theme = Theme(
                id=t["id"],
                name=t["name"],
                category=t["category"],
                price=t["price"],
                images=t.get("images", []),
                inclusions=t.get("inclusions", {}),
                addons=t.get("addons", {})
            )
            db.session.add(theme)

    db.session.commit()
    print("✅ All themes synced to database")

# ================= SIMILAR (ONLY 4) =================
def get_related_themes(current_id, category):
    return Theme.query.filter(Theme.category==category, Theme.id!=current_id).limit(4).all()

# ================= THEME PAGE =================
@theme_bp.route("/theme/<theme_id>")
def theme_detail(theme_id):
    seed_themes()
    theme = Theme.query.filter_by(id=theme_id).first()
    if not theme:
        abort(404)
    related = get_related_themes(theme.id, theme.category)
    return render_template("theme_detail.html", theme=theme, related=related)


# ================= BOOKING PAGE =================
import json
from flask import session, redirect, url_for, request

@theme_bp.route("/booking/<theme_id>")
def booking_page(theme_id):

    if "user" not in session:
        return redirect(url_for("login_page", next=request.url))

    seed_themes()
    theme = Theme.query.filter_by(id=theme_id).first_or_404()


    addons = []
    addon_total = 0

    addons_raw = request.args.get("addons_data")

    if addons_raw:
        try:
            decoded = json.loads(addons_raw)
            for a in decoded:
                addon = {
                    "id": a.get("id"),
                    "name": a.get("name"),
                    "price": int(a.get("price", 0)),
                    "qty": int(a.get("qty", 1)),
                    "image": a.get("image") or a.get("img") 
                }
                addon_total += addon["price"] * addon["qty"]
                addons.append(addon)
        except Exception as e:
            print("Addon parse error:", e)

    return render_template(
        "booking_form.html",
        theme=theme,
        addons=addons,
        addon_total=addon_total
    )
