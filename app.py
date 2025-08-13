from flask import Flask, request
from flask_cors import CORS
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

# Load environment variables from .env file (if available)
load_dotenv()

# Create Flask application instance
app = Flask(__name__)

# --- DB config (SQLite for local) ---
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///hospital.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Enable Cross-Origin Resource Sharing (CORS) for API calls from different domains
CORS(app)

# -------------------------
# Models (for local SQLite)
# -------------------------
class Patient(db.Model):
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, nullable=False)
    dob = db.Column(db.String)
    assigned_doctor_id = db.Column(db.String)

class Device(db.Model):
    id = db.Column(db.String, primary_key=True)
    type = db.Column(db.String, nullable=False)  # hr, bp, spo2, temp, multi
    patient_id = db.Column(db.String, db.ForeignKey("patient.id"))
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String, default="active")
    api_key = db.Column(db.String, nullable=False)  # reserved for later steps

class Vital(db.Model):
    id = db.Column(db.String, primary_key=True)
    patient_id = db.Column(db.String, db.ForeignKey("patient.id"), index=True)
    timestamp = db.Column(db.DateTime, index=True)
    heart_rate = db.Column(db.Integer)
    bp_systolic = db.Column(db.Integer)
    bp_diastolic = db.Column(db.Integer)
    spo2 = db.Column(db.Integer)
    temp = db.Column(db.Float)
    device_id = db.Column(db.String, db.ForeignKey("device.id"))

class Alert(db.Model):
    id = db.Column(db.String, primary_key=True)
    patient_id = db.Column(db.String, index=True)
    type = db.Column(db.String)       # e.g., LOW_SPO2, HIGH_TEMP
    value = db.Column(db.Float)
    threshold = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String, default="NEW")

# -------------------------
# Local-only admin helpers
# -------------------------

@app.route("/admin/db-path", methods=["GET"])
def db_path():
    """
    Show where the SQLite file is expected to be (absolute path).
    Useful when you 'can't see hospital.db'.
    """
    db_file = db.engine.url.database  # may be relative
    abs_path = os.path.abspath(db_file) if db_file else None
    return {"database_uri": str(db.engine.url), "db_file": db_file, "absolute_path": abs_path}, 200


@app.route("/admin/init-db", methods=["POST", "GET"])
def init_db():
    """
    One-shot DB initialization for local development.
    Creates tables and seeds a demo patient 'p_001'.
    - POST: creates immediately
    - GET: requires ?confirm=yes (just for convenience in browser)
    Remove/disable this in production.
    """
    if request.method == "GET" and request.args.get("confirm") != "yes":
        return {"message": "Use POST or call /admin/init-db?confirm=yes (local only)"}, 200

    db.create_all()
    if not Patient.query.get("p_001"):
        db.session.add(Patient(id="p_001", name="Demo Patient"))
        db.session.commit()
    # print path to console too
    try:
        print("SQLite file:", os.path.abspath(db.engine.url.database))
    except Exception:
        pass
    return {"status": "initialized"}, 201

# -------------------------
# Existing demo routes
# -------------------------
@app.route("/", methods=["GET"])
def home():
    return {
        "api_name": "Smart Hospital API",
        "status": "OK",
        "available_endpoints": ["/health", "/patients", "/admin/init-db", "/admin/db-path"]
    }, 200

@app.route("/health", methods=["GET"])
def health_check():
    return {"status": "OK"}, 200

@app.route("/patients", methods=["GET"])
def get_patients():
    patients = [
        {"id": 1, "name": "John Doe", "room": 101},
        {"id": 2, "name": "Jane Smith", "room": 102}
    ]
    return {"patients": patients}, 200

# -------------------------
# Entrypoint (local dev)
# -------------------------
if __name__ == "__main__":
    # Use 8000 by default (5000 might be busy on your machine)
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
