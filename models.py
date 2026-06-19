from datetime import datetime
from extensions import db


class AccountApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference_no = db.Column(db.String(20), unique=True, nullable=False)

    # ID document (extracted via Qwen2.5-VL, or typed manually if extraction failed)
    document_type = db.Column(db.String(30), nullable=False)       # Aadhaar / PAN / Driving License
    document_number = db.Column(db.String(40), nullable=True)      # Aadhaar is stored masked, see ocr_extract.mask_aadhaar
    document_image_filename = db.Column(db.String(200), nullable=True)
    extracted_raw_json = db.Column(db.Text, nullable=True)         # audit trail of what the model returned
    extraction_method = db.Column(db.String(10), default="manual")  # "auto" or "manual"

    # Personal details (auto-filled from document, editable by applicant)
    full_name = db.Column(db.String(120), nullable=False)
    dob = db.Column(db.String(20), nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    father_name = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(300), nullable=True)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)

    # Account preferences
    account_type = db.Column(db.String(20), nullable=False)        # Savings / Current
    initial_deposit = db.Column(db.Float, nullable=False)
    nominee_name = db.Column(db.String(120), nullable=False)
    nominee_relation = db.Column(db.String(40), nullable=False)

    status = db.Column(db.String(20), default="Submitted")
    applied_on = db.Column(db.DateTime, default=datetime.utcnow)