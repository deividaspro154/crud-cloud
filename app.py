import os
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from flask import (
    Flask, abort, flash, jsonify, redirect, render_template,
    request, url_for
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import select
from werkzeug.utils import secure_filename

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB

database_url = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'products.db'}")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    sku = db.Column(db.String(30), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    available = db.Column(db.Boolean, nullable=False, default=True)
    restock_date = db.Column(db.Date, nullable=True)

    image_url = db.Column(db.String(500), nullable=True)
    image_public_id = db.Column(db.String(255), nullable=True)
    storage_provider = db.Column(db.String(30), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "sku": self.sku,
            "description": self.description,
            "quantity": self.quantity,
            "price": float(self.price),
            "available": self.available,
            "restock_date": self.restock_date.isoformat() if self.restock_date else None,
            "image_url": self.image_url,
            "storage_provider": self.storage_provider,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
        }


class BackgroundEvent(db.Model):
    __tablename__ = "background_events"

    id = db.Column(db.Integer, primary_key=True)
    ran_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    changed_count = db.Column(db.Integer, nullable=False, default=0)
    message = db.Column(db.String(255), nullable=False)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def cloudinary_enabled():
    return bool(os.getenv("CLOUDINARY_URL"))


def save_image(file_storage):
    """Store an uploaded image in Cloudinary when configured, otherwise locally."""
    if not file_storage or not file_storage.filename:
        return None, None, None

    if not allowed_file(file_storage.filename):
        raise ValueError("Image must be PNG, JPG, JPEG, GIF or WEBP.")

    if cloudinary_enabled():
        import cloudinary.uploader

        result = cloudinary.uploader.upload(
            file_storage,
            folder="product-manager-crud",
            resource_type="image",
        )
        return result["secure_url"], result["public_id"], "cloudinary"

    safe_name = secure_filename(file_storage.filename)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    path = UPLOAD_DIR / unique_name
    file_storage.save(path)
    return url_for("static", filename=f"uploads/{unique_name}"), unique_name, "local"


def delete_image(product):
    if not product.image_public_id:
        return

    if product.storage_provider == "cloudinary" and cloudinary_enabled():
        import cloudinary.uploader

        cloudinary.uploader.destroy(product.image_public_id)
    elif product.storage_provider == "local":
        path = UPLOAD_DIR / product.image_public_id
        if path.exists():
            path.unlink()


def parse_html_product_form(form):
    """Validate 5 different data types from the web form."""
    errors = []

    # 1. STRING
    name = form.get("name", "").strip()
    if not (2 <= len(name) <= 80):
        errors.append("Name must contain 2-80 characters.")

    sku = form.get("sku", "").strip().upper()
    if not (2 <= len(sku) <= 30):
        errors.append("SKU must contain 2-30 characters.")

    description = form.get("description", "").strip() or None

    # 2. INTEGER
    try:
        quantity = int(form.get("quantity", ""))
        if quantity < 0:
            raise ValueError
    except (ValueError, TypeError):
        errors.append("Quantity must be a non-negative integer.")
        quantity = 0

    # 3. DECIMAL / FLOAT-LIKE NUMBER
    try:
        price = Decimal(form.get("price", ""))
        if price < 0:
            raise InvalidOperation
        price = price.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        errors.append("Price must be a non-negative number.")
        price = Decimal("0.00")

    # 4. BOOLEAN
    available = form.get("available") == "on"

    # 5. DATE
    restock_date_raw = form.get("restock_date", "").strip()
    restock_date = None
    if restock_date_raw:
        try:
            restock_date = datetime.strptime(restock_date_raw, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Restock date must use YYYY-MM-DD format.")

    return {
        "name": name,
        "sku": sku,
        "description": description,
        "quantity": quantity,
        "price": price,
        "available": available,
        "restock_date": restock_date,
    }, errors


def validate_api_payload(data, partial=False):
    """Validate JSON values for public API create/update operations."""
    if not isinstance(data, dict):
        return {}, ["JSON object expected."]

    errors = []
    clean = {}

    required = ["name", "sku", "quantity", "price", "available", "restock_date"]
    if not partial:
        for field in required:
            if field not in data:
                errors.append(f"Missing field: {field}")

    # STRING
    if "name" in data:
        if not isinstance(data["name"], str) or not (2 <= len(data["name"].strip()) <= 80):
            errors.append("name must be a string containing 2-80 characters.")
        else:
            clean["name"] = data["name"].strip()

    if "sku" in data:
        if not isinstance(data["sku"], str) or not (2 <= len(data["sku"].strip()) <= 30):
            errors.append("sku must be a string containing 2-30 characters.")
        else:
            clean["sku"] = data["sku"].strip().upper()

    if "description" in data:
        if data["description"] is not None and not isinstance(data["description"], str):
            errors.append("description must be a string or null.")
        else:
            clean["description"] = data["description"].strip() if isinstance(data["description"], str) else None

    # INTEGER
    if "quantity" in data:
        if isinstance(data["quantity"], bool) or not isinstance(data["quantity"], int) or data["quantity"] < 0:
            errors.append("quantity must be a non-negative integer.")
        else:
            clean["quantity"] = data["quantity"]

    # FLOAT / NUMBER
    if "price" in data:
        if isinstance(data["price"], bool) or not isinstance(data["price"], (int, float)) or data["price"] < 0:
            errors.append("price must be a non-negative number.")
        else:
            clean["price"] = Decimal(str(data["price"])).quantize(Decimal("0.01"))

    # BOOLEAN
    if "available" in data:
        if not isinstance(data["available"], bool):
            errors.append("available must be true or false.")
        else:
            clean["available"] = data["available"]

    # DATE
    if "restock_date" in data:
        if data["restock_date"] is None:
            clean["restock_date"] = None
        elif isinstance(data["restock_date"], str):
            try:
                clean["restock_date"] = datetime.strptime(data["restock_date"], "%Y-%m-%d").date()
            except ValueError:
                errors.append("restock_date must be YYYY-MM-DD or null.")
        else:
            errors.append("restock_date must be YYYY-MM-DD string or null.")

    return clean, errors


def sku_exists(sku, ignore_product_id=None):
    stmt = select(Product).where(Product.sku == sku)
    if ignore_product_id:
        stmt = stmt.where(Product.id != ignore_product_id)
    return db.session.execute(stmt).scalar_one_or_none() is not None


@app.errorhandler(413)
def file_too_large(_error):
    flash("Image is too large. Maximum size is 5 MB.", "danger")
    return redirect(request.referrer or url_for("index"))


@app.route("/")
def index():
    products = db.session.execute(select(Product).order_by(Product.id.desc())).scalars().all()
    events = db.session.execute(
        select(BackgroundEvent).order_by(BackgroundEvent.ran_at.desc()).limit(5)
    ).scalars().all()
    return render_template("index.html", products=products, events=events)


@app.route("/products/new", methods=["GET", "POST"])
def create_product():
    if request.method == "POST":
        clean, errors = parse_html_product_form(request.form)

        if clean["sku"] and sku_exists(clean["sku"]):
            errors.append("SKU already exists.")

        image_data = (None, None, None)
        image = request.files.get("image")
        if image and image.filename:
            try:
                image_data = save_image(image)
            except ValueError as exc:
                errors.append(str(exc))

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("form.html", product=None, form_data=request.form), 400

        product = Product(**clean)
        product.image_url, product.image_public_id, product.storage_provider = image_data
        db.session.add(product)
        db.session.commit()
        flash("Product created.", "success")
        return redirect(url_for("index"))

    return render_template("form.html", product=None, form_data=None)


@app.route("/products/<int:product_id>")
def product_detail(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)
    return render_template("detail.html", product=product)


@app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def edit_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)

    if request.method == "POST":
        clean, errors = parse_html_product_form(request.form)

        if clean["sku"] and sku_exists(clean["sku"], ignore_product_id=product.id):
            errors.append("SKU already exists.")

        new_image = request.files.get("image")
        new_image_data = None
        if new_image and new_image.filename:
            try:
                new_image_data = save_image(new_image)
            except ValueError as exc:
                errors.append(str(exc))

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("form.html", product=product, form_data=request.form), 400

        if new_image_data:
            delete_image(product)
            product.image_url, product.image_public_id, product.storage_provider = new_image_data

        for key, value in clean.items():
            setattr(product, key, value)

        db.session.commit()
        flash("Product updated.", "success")
        return redirect(url_for("product_detail", product_id=product.id))

    return render_template("form.html", product=product, form_data=None)


@app.route("/products/<int:product_id>/delete", methods=["POST"])
def delete_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)

    delete_image(product)
    db.session.delete(product)
    db.session.commit()
    flash("Product deleted.", "success")
    return redirect(url_for("index"))


@app.route("/api")
def api_docs():
    return render_template("api.html")


# ---------------- PUBLIC REST API ----------------

@app.route("/api/products", methods=["GET"])
def api_list_products():
    products = db.session.execute(select(Product).order_by(Product.id)).scalars().all()
    return jsonify([product.to_dict() for product in products])


@app.route("/api/products/<int:product_id>", methods=["GET"])
def api_get_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"error": "Product not found."}), 404
    return jsonify(product.to_dict())


@app.route("/api/products", methods=["POST"])
def api_create_product():
    data = request.get_json(silent=True)
    clean, errors = validate_api_payload(data, partial=False)

    if clean.get("sku") and sku_exists(clean["sku"]):
        errors.append("sku already exists.")

    if errors:
        return jsonify({"errors": errors}), 400

    product = Product(**clean)
    db.session.add(product)
    db.session.commit()
    return jsonify(product.to_dict()), 201


@app.route("/api/products/<int:product_id>", methods=["PUT", "PATCH"])
def api_update_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"error": "Product not found."}), 404

    data = request.get_json(silent=True)
    clean, errors = validate_api_payload(data, partial=(request.method == "PATCH"))

    if clean.get("sku") and sku_exists(clean["sku"], ignore_product_id=product.id):
        errors.append("sku already exists.")

    if errors:
        return jsonify({"errors": errors}), 400

    for key, value in clean.items():
        setattr(product, key, value)

    db.session.commit()
    return jsonify(product.to_dict())


@app.route("/api/products/<int:product_id>", methods=["DELETE"])
def api_delete_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"error": "Product not found."}), 404

    delete_image(product)
    db.session.delete(product)
    db.session.commit()
    return "", 204


# ---------------- BACKGROUND OPERATION ----------------

def background_stock_check():
    """
    Runs in the background every 60 seconds.
    Products with quantity == 0 are automatically marked unavailable.
    A short execution record is stored in the database for demonstration.
    """
    with app.app_context():
        products = db.session.execute(
            select(Product).where(Product.quantity <= 0, Product.available.is_(True))
        ).scalars().all()

        for product in products:
            product.available = False

        event = BackgroundEvent(
            changed_count=len(products),
            message=f"Stock check finished; {len(products)} product(s) changed.",
        )
        db.session.add(event)
        db.session.commit()

        # Keep only the newest 20 log records.
        old_events = db.session.execute(
            select(BackgroundEvent).order_by(BackgroundEvent.ran_at.desc()).offset(20)
        ).scalars().all()
        for old_event in old_events:
            db.session.delete(old_event)
        if old_events:
            db.session.commit()

        print(f"[BACKGROUND] {event.message}", flush=True)


@app.route("/background/run", methods=["POST"])
def run_background_now():
    """Manual trigger makes the background operation easy to demonstrate."""
    background_stock_check()
    flash("Background stock check executed.", "success")
    return redirect(url_for("index"))


with app.app_context():
    db.create_all()

scheduler = None
if os.getenv("ENABLE_SCHEDULER", "true").lower() == "true":
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        background_stock_check,
        trigger="interval",
        seconds=int(os.getenv("BACKGROUND_INTERVAL_SECONDS", "60")),
        id="stock-check",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        use_reloader=False,
    )
