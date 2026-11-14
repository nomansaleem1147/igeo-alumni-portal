import os
import re
import uuid
import secrets
from datetime import datetime
from pathlib import Path
from functools import wraps

import qrcode
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A6, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__)
app.config.from_object("config.Config")
Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
(BASE_DIR / "database").mkdir(exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "admin_login"
csrf = CSRFProtect(app)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}
EVENT_NAME = os.getenv("EVENT_NAME", "IGEO Alumni Annual Dinner 2026")
FEE = int(os.getenv("REGISTRATION_FEE", "5000"))
CURRENCY = os.getenv("CURRENCY", "PKR")

class Alumni(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(24), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    batch = db.Column(db.String(40), nullable=False)
    registration_number = db.Column(db.String(80), nullable=False, unique=True)
    email = db.Column(db.String(160), nullable=False)
    contact_number = db.Column(db.String(40), nullable=False)
    employment_status = db.Column(db.String(30), nullable=False)
    organization = db.Column(db.String(160))
    designation = db.Column(db.String(120))
    receipt_filename = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default="Pending", nullable=False)
    admin_remarks = db.Column(db.String(500))
    ticket_token = db.Column(db.String(64), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime)

class Admin(UserMixin):
    # Single environment-configured admin account for this starter version.
    id = "admin"

@login_manager.user_loader
def load_user(user_id):
    return Admin() if user_id == "admin" else None

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def admin_credentials():
    return os.getenv("ADMIN_USERNAME", "admin"), os.getenv("ADMIN_PASSWORD", "change-this-admin-password")

def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

def make_ticket_assets(alumni):
    ticket_dir = Path(app.root_path) / "static" / "tickets"
    ticket_dir.mkdir(parents=True, exist_ok=True)
    verify_url = url_for("verify_ticket", token=alumni.ticket_token, _external=True)
    qr_path = ticket_dir / f"{alumni.reference}_qr.png"
    qrcode.make(verify_url).save(qr_path)

    # JPG ticket artwork
    width, height = 1400, 850
    image = Image.new("RGB", (width, height), "#173B65")
    draw = ImageDraw.Draw(image)
    try:
        font_big = ImageFont.truetype("DejaVuSans-Bold.ttf", 54)
        font_mid = ImageFont.truetype("DejaVuSans.ttf", 34)
        font_small = ImageFont.truetype("DejaVuSans.ttf", 24)
    except OSError:
        font_big = font_mid = font_small = ImageFont.load_default()
    draw.rounded_rectangle((35, 35, width-35, height-35), radius=35, outline="#E5BD69", width=6)
    draw.text((85, 85), "IGEO ALUMNI", fill="#FFFFFF", font=font_big)
    draw.text((85, 165), EVENT_NAME, fill="#F2D28B", font=font_mid)
    draw.line((85, 230, width-85, 230), fill="#7892AE", width=3)
    draw.text((85, 285), "OFFICIAL ALUMNI ENTRY PASS", fill="#FFFFFF", font=font_mid)
    draw.text((85, 385), f"Name: {alumni.full_name}", fill="#FFFFFF", font=font_mid)
    draw.text((85, 455), f"Batch: {alumni.batch}", fill="#FFFFFF", font=font_mid)
    draw.text((85, 525), f"Registration: {alumni.registration_number}", fill="#FFFFFF", font=font_small)
    draw.text((85, 600), f"Ticket ID: {alumni.reference}", fill="#F2D28B", font=font_small)
    draw.text((85, 690), "APPROVED • PRESENT THIS QR AT THE ENTRY", fill="#FFFFFF", font=font_small)
    qr = Image.open(qr_path).convert("RGB").resize((300, 300))
    image.paste(qr, (width-400, 300))
    jpg_path = ticket_dir / f"{alumni.reference}.jpg"
    image.save(jpg_path, quality=95)

    pdf_path = ticket_dir / f"{alumni.reference}.pdf"
    page = landscape(A6)
    c = canvas.Canvas(str(pdf_path), pagesize=page)
    pw, ph = page
    c.setFillColorRGB(0.09, 0.23, 0.40)
    c.rect(0, 0, pw, ph, fill=1, stroke=0)
    c.setStrokeColorRGB(0.90, 0.74, 0.41)
    c.setLineWidth(3)
    c.roundRect(12, 12, pw-24, ph-24, 12, fill=0, stroke=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(28, ph-45, "IGEO ALUMNI")
    c.setFillColorRGB(0.95, 0.82, 0.55)
    c.setFont("Helvetica", 10)
    c.drawString(28, ph-63, EVENT_NAME[:75])
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(28, ph-100, "OFFICIAL ALUMNI ENTRY PASS")
    c.setFont("Helvetica", 10)
    c.drawString(28, ph-125, f"Name: {alumni.full_name}")
    c.drawString(28, ph-145, f"Batch: {alumni.batch}")
    c.drawString(28, ph-165, f"Registration: {alumni.registration_number}")
    c.setFillColorRGB(0.95, 0.82, 0.55)
    c.drawString(28, ph-190, f"Ticket ID: {alumni.reference}")
    c.drawImage(ImageReader(str(qr_path)), pw-130, 55, width=95, height=95, preserveAspectRatio=True)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica", 8)
    c.drawString(28, 28, "APPROVED • Present this QR code at the entry")
    c.save()

@app.context_processor
def inject_globals():
    return {"event_name": EVENT_NAME, "registration_fee": FEE, "currency": CURRENCY}

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        required = ["full_name", "batch", "registration_number", "email", "contact_number", "employment_status"]
        if any(not request.form.get(x, "").strip() for x in required):
            flash("Please complete all required fields.", "error")
            return redirect(url_for("register"))
        reg_no = request.form["registration_number"].strip()
        email = request.form["email"].strip().lower()
        if Alumni.query.filter_by(registration_number=reg_no).first():
            flash("This registration number has already been used.", "error")
            return redirect(url_for("register"))
        if Alumni.query.filter_by(email=email, status="Approved").first():
            flash("An approved registration already exists for this email.", "error")
            return redirect(url_for("register"))
        receipt = request.files.get("receipt")
        if not receipt or not receipt.filename or not allowed_file(receipt.filename):
            flash("Upload a receipt in JPG, PNG or PDF format.", "error")
            return redirect(url_for("register"))
        reference = "ALM-" + uuid.uuid4().hex[:10].upper()
        ext = secure_filename(receipt.filename).rsplit(".", 1)[1].lower()
        stored_name = f"{reference}.{ext}"
        receipt.save(Path(app.config["UPLOAD_FOLDER"]) / stored_name)
        status = request.form["employment_status"]
        alumni = Alumni(
            reference=reference,
            full_name=request.form["full_name"].strip(),
            batch=request.form["batch"].strip(),
            registration_number=reg_no,
            email=email,
            contact_number=request.form["contact_number"].strip(),
            employment_status=status,
            organization=request.form.get("organization", "").strip(),
            designation=request.form.get("designation", "").strip(),
            receipt_filename=stored_name
        )
        db.session.add(alumni)
        db.session.commit()
        return render_template("submitted.html", alumni=alumni)
    return render_template("registration.html",
        account_title=os.getenv("ACCOUNT_TITLE", "Add account title in .env"),
        bank_name=os.getenv("BANK_NAME", "Add bank / wallet name in .env"),
        account_number=os.getenv("ACCOUNT_NUMBER", "Add account number in .env"),
        payment_instructions=os.getenv("PAYMENT_INSTRUCTIONS", "Transfer the fee and upload your receipt."),
        qr_image=os.getenv("PAYMENT_QR_IMAGE", "payment_qr.png"))

@app.route("/status", methods=["GET", "POST"])
def status():
    alumni = None
    if request.method == "POST":
        reference = request.form.get("reference", "").strip().upper()
        email = request.form.get("email", "").strip().lower()
        alumni = Alumni.query.filter_by(reference=reference, email=email).first()
        if not alumni:
            flash("No matching application was found. Check your reference and email.", "error")
    return render_template("status.html", alumni=alumni)

@app.route("/ticket/<token>")
def ticket(token):
    alumni = Alumni.query.filter_by(ticket_token=token, status="Approved").first_or_404()
 make_ticket_assets(alumni)
    return render_template("ticket.html", alumni=alumni)

@app.route("/ticket/<token>/download/<kind>")
def download_ticket(token, kind):
    alumni = Alumni.query.filter_by(ticket_token=token, status="Approved").first_or_404()
    if kind not in {"pdf", "jpg"}:
        abort(404)
    make_ticket_assets(alumni)
    path = Path(app.root_path) / "static" / "tickets" / f"{alumni.reference}.{kind}"
    return send_file(path, as_attachment=True, download_name=f"{alumni.reference}.{kind}")

@app.route("/verify/<token>")
def verify_ticket(token):
    alumni = Alumni.query.filter_by(ticket_token=token, status="Approved").first_or_404()
    return render_template("verify.html", alumni=alumni)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username, password = admin_credentials()
        if secrets.compare_digest(request.form.get("username", ""), username) and secrets.compare_digest(request.form.get("password", ""), password):
            login_user(Admin())
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials.", "error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for("home"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    query = Alumni.query
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(db.or_(Alumni.full_name.ilike(like), Alumni.registration_number.ilike(like), Alumni.batch.ilike(like), Alumni.reference.ilike(like)))
    if status_filter in {"Pending", "Approved", "Rejected"}:
        query = query.filter_by(status=status_filter)
    records = query.order_by(Alumni.created_at.desc()).all()
    counts = {
        "total": Alumni.query.count(),
        "pending": Alumni.query.filter_by(status="Pending").count(),
        "approved": Alumni.query.filter_by(status="Approved").count(),
        "rejected": Alumni.query.filter_by(status="Rejected").count()
    }
    return render_template("admin_dashboard.html", records=records, counts=counts, search=search, status_filter=status_filter)

@app.route("/admin/receipt/<int:alumni_id>")
@admin_required
def admin_receipt(alumni_id):
    alumni = Alumni.query.get_or_404(alumni_id)
    path = Path(app.config["UPLOAD_FOLDER"]) / alumni.receipt_filename
    if not path.exists():
        abort(404)
    return send_file(path)

@app.route("/admin/review/<int:alumni_id>", methods=["POST"])
@admin_required
def review(alumni_id):
    alumni = Alumni.query.get_or_404(alumni_id)
    action = request.form.get("action")
    remarks = request.form.get("remarks", "").strip()
    if action == "approve":
        alumni.status = "Approved"
        alumni.admin_remarks = remarks
        alumni.ticket_token = secrets.token_urlsafe(32)
        alumni.approved_at = datetime.utcnow()
        db.session.commit()
        make_ticket_assets(alumni)
        flash(f"Approved. Ticket generated for {alumni.full_name}.", "success")
    elif action == "reject":
        alumni.status = "Rejected"
        alumni.admin_remarks = remarks or "Payment could not be verified."
        alumni.ticket_token = None
        db.session.commit()
        flash(f"Registration rejected for {alumni.full_name}.", "success")
    else:
        flash("Invalid review action.", "error")
    return redirect(url_for("admin_dashboard"))

@app.route("/health")
def health():
    return {"status": "ok"}

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
