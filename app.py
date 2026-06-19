import os
import random
import string
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename

from config import Config
from extensions import db
from models import AccountApplication
from ocr_extract import extract_document

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    db.create_all()
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]


def generate_reference_no():
    return "AOF" + datetime.now().strftime("%y%m%d") + "".join(random.choices(string.digits, k=4))


@app.route("/")
def home():
    return render_template("home.html")


# ---------- STEP 1: Upload ID document, auto-extract via Qwen2.5-VL ----------
@app.route("/apply/step1", methods=["GET", "POST"])
def step1():
    if request.method == "POST":
        doc_type = request.form.get("document_type")
        doc_file = request.files.get("document_image")

        if doc_type not in ("Aadhaar", "PAN", "Driving License"):
            flash("Please select a valid document type.")
            return redirect(url_for("step1"))

        if not doc_file or not doc_file.filename or not allowed_file(doc_file.filename):
            flash("Please upload a valid image file (png, jpg, jpeg).")
            return redirect(url_for("step1"))

        fname = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{doc_file.filename}")
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], fname)
        doc_file.save(save_path)

        success, data, raw_text, error_message = extract_document(
            save_path, doc_type,
            app.config["OLLAMA_HOST"], app.config["OLLAMA_MODEL"], app.config["OLLAMA_TIMEOUT_SECONDS"],
        )

        session["document_type"] = doc_type
        session["document_image_filename"] = fname

        if success:
            session["extraction_method"] = "auto"
            session["extracted_raw_json"] = raw_text
            session["full_name"] = data.get("full_name") or ""
            session["dob"] = data.get("dob") or ""
            session["gender"] = data.get("gender") or ""
            session["father_name"] = data.get("father_name") or ""
            session["address"] = data.get("address") or ""
            if doc_type == "Aadhaar":
                session["document_number"] = data.get("aadhaar_number") or ""
            elif doc_type == "PAN":
                session["document_number"] = data.get("pan_number") or ""
            else:
                session["document_number"] = data.get("dl_number") or ""
            flash("Document scanned successfully. Please review the details below.")
        else:
            session["extraction_method"] = "manual"
            session["extracted_raw_json"] = ""
            for key in ["full_name", "dob", "gender", "father_name", "address", "document_number"]:
                session[key] = ""
            flash(f"Auto-scan couldn't complete ({error_message}). Please enter your details manually below.")

        return redirect(url_for("step2"))

    return render_template("step1_upload.html")


# ---------- STEP 2: Review / correct extracted personal details ----------
@app.route("/apply/step2", methods=["GET", "POST"])
def step2():
    if "document_type" not in session:
        return redirect(url_for("step1"))

    if request.method == "POST":
        session["full_name"] = request.form["full_name"]
        session["dob"] = request.form["dob"]
        session["gender"] = request.form.get("gender", "")
        session["father_name"] = request.form.get("father_name", "")
        session["address"] = request.form.get("address", "")
        session["document_number"] = request.form["document_number"]
        session["phone"] = request.form["phone"]
        session["email"] = request.form["email"]
        return redirect(url_for("step3"))

    return render_template("step2_review.html", data=session)


# ---------- STEP 3: Account preferences ----------
@app.route("/apply/step3", methods=["GET", "POST"])
def step3():
    if "phone" not in session:
        return redirect(url_for("step2"))

    if request.method == "POST":
        session["account_type"] = request.form["account_type"]
        session["initial_deposit"] = request.form["initial_deposit"]
        session["nominee_name"] = request.form["nominee_name"]
        session["nominee_relation"] = request.form["nominee_relation"]
        return redirect(url_for("step4"))

    return render_template("step3_account.html", data=session)


# ---------- STEP 4: Review & submit ----------
@app.route("/apply/step4", methods=["GET", "POST"])
def step4():
    if "account_type" not in session:
        return redirect(url_for("step3"))

    if request.method == "POST":
        reference_no = generate_reference_no()
        application = AccountApplication(
            reference_no=reference_no,
            document_type=session["document_type"],
            document_number=session.get("document_number"),
            document_image_filename=session.get("document_image_filename"),
            extracted_raw_json=session.get("extracted_raw_json"),
            extraction_method=session.get("extraction_method", "manual"),
            full_name=session["full_name"],
            dob=session.get("dob"),
            gender=session.get("gender"),
            father_name=session.get("father_name"),
            address=session.get("address"),
            phone=session["phone"],
            email=session["email"],
            account_type=session["account_type"],
            initial_deposit=float(session["initial_deposit"]),
            nominee_name=session["nominee_name"],
            nominee_relation=session["nominee_relation"],
        )
        db.session.add(application)
        db.session.commit()

        for key in ["document_type", "document_number", "document_image_filename", "extracted_raw_json",
                    "extraction_method", "full_name", "dob", "gender", "father_name", "address",
                    "phone", "email", "account_type", "initial_deposit", "nominee_name", "nominee_relation"]:
            session.pop(key, None)

        return redirect(url_for("confirmation", ref=reference_no))

    return render_template("step4_review.html", data=session)


@app.route("/apply/confirmation")
def confirmation():
    ref = request.args.get("ref")
    return render_template("confirmation.html", ref=ref)


# ---------- Admin ----------
@app.route("/admin")
def admin_dashboard():
    applications = AccountApplication.query.order_by(AccountApplication.applied_on.desc()).all()
    return render_template("admin_dashboard.html", applications=applications)


@app.route("/admin/application/<int:app_id>/status", methods=["POST"])
def update_status(app_id):
    application = AccountApplication.query.get_or_404(app_id)
    application.status = request.form["status"]
    db.session.commit()
    flash(f"Status updated for {application.full_name}.")
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)