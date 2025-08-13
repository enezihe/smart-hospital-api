from flask import Flask, request
from flask_cors import CORS
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from marshmallow import Schema, fields, ValidationError, validate
from uuid import uuid4
from typing import Optional
import os

# Load environment variables (if any) from .env
load_dotenv()

# Flask app
app = Flask(__name__)

# --- Database (SQLite for local development) ---
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///hospital.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Allow cross-origin requests during development
CORS(app)

# ---- DEBUG: Log every incoming request (method, path, key headers) ----
@app.before_request
def _log_req():
    print(
        "REQ:", request.method, request.path,
        "| CT:", request.headers.get("Content-Type"),
        "| X-API-Key:", bool(request.headers.get("X-API-Key")),
        "| Idem:", request.headers.get("Idempotency-Key")
    )

# ------------------------- MODELS -------------------------
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
    api_key = db.Column(db.String, nullable=False)  # per-device API key (issued at register)

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

# Prevent duplicate POSTs when clients retry (network flakiness etc.)
class IdempotencyKey(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_id = db.Column(db.String, index=True, nullable=False)
    key = db.Column(db.String, unique=True, index=True, nullable=False)  # device_id:idempotency_key
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ------------------------- SCHEMAS (validation) -------------------------
class BPField(Schema):
    systolic = fields.Integer(required=True, validate=validate.Range(min=0, max=300))
    diastolic = fields.Integer(required=True, validate=validate.Range(min=0, max=200))

class VitalInSchema(Schema):
    timestamp = fields.DateTime(required=True)
    heart_rate = fields.Integer(allow_none=True)
    bp = fields.Nested(BPField, required=False)
    spo2 = fields.Integer(allow_none=True)
    temp = fields.Float(allow_none=True)
    device_id = fields.String(required=True)

class DeviceRegisterSchema(Schema):
    device_id = fields.String(required=True)
    type = fields.String(required=True, validate=validate.OneOf(["hr", "bp", "spo2", "temp", "multi"]))
    patient_id = fields.String(required=True)

# ------------------------- HELPERS / CONFIG -------------------------
DEVICE_MASTER_KEY = os.getenv("DEVICE_MASTER_KEY", "dev-master-key-123")

def uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"

def error(code: str, http: int, message: str, details=None):
    """Uniform error payload shape."""
    payload = {"code": code, "message": message}
    if details is not None:
        payload["details"] = details
    return payload, http

def require_device_api_key():
    """Simple device/master key auth for write operations."""
    supplied = request.headers.get("X-API-Key")
    if not supplied:
        return False, error("missing_api_key", 401, "X-API-Key header required")
    if supplied == DEVICE_MASTER_KEY:
        return True, None
    if Device.query.filter_by(api_key=supplied).first():
        return True, None
    return False, error("invalid_api_key", 401, "Invalid API key")

def parse_dt(s: Optional[str]) -> Optional[datetime]:
    """Parse ISO-8601 strings (supports trailing Z)."""
    if not s:
        return None
    try:
        s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        raise ValueError(f"Invalid datetime: {s}")


def record_idempotency(device_id: str, idem_key: Optional[str]) -> bool:
    """
    Return True if (device_id, idem_key) has NOT been seen before (safe to process).
    Return False if duplicate (should be ignored gracefully).
    If client does not send an idempotency key, treat as new (True).
    """
    if not idem_key:
        return True
    combined = f"{device_id}:{idem_key}"
    if IdempotencyKey.query.filter_by(key=combined).first():
        return False
    db.session.add(IdempotencyKey(device_id=device_id, key=combined))
    db.session.commit()
    return True

# ------------------------- ADMIN (local utilities) -------------------------
@app.get("/admin/routes")
def list_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({"rule": str(rule), "methods": sorted(list(rule.methods))})
    return {"routes": routes}, 200

@app.get("/admin/db-path")
def db_path():
    """Show the resolved SQLite file path for troubleshooting."""
    db_file = db.engine.url.database
    abs_path = os.path.abspath(db_file) if db_file else None
    return {"database_uri": str(db.engine.url), "db_file": db_file, "absolute_path": abs_path}, 200

@app.route("/admin/init-db", methods=["POST", "GET"])
def init_db():
    """
    Initialize tables and seed a demo patient (local only).
    - POST: initialize immediately.
    - GET : requires ?confirm=yes to avoid accidental calls.
    """
    if request.method == "GET" and request.args.get("confirm") != "yes":
        return {"message": "Use POST or call /admin/init-db?confirm=yes (local only)"}, 200
    db.create_all()
    if not Patient.query.get("p_001"):
        db.session.add(Patient(id="p_001", name="Demo Patient"))
        db.session.commit()
    print("SQLite file:", os.path.abspath(db.engine.url.database))
    return {"status": "initialized"}, 201

# ------------------------- REST API -------------------------
@app.post("/api/v1/devices/register")
def register_device():
    """Register a device and issue a per-device API key."""
    ok, resp = require_device_api_key()
    if not ok:
        return resp
    try:
        body = DeviceRegisterSchema().load(request.get_json())
    except ValidationError as e:
        return error("validation_error", 400, "Invalid payload", e.messages)

    patient = Patient.query.get(body["patient_id"])
    if not patient:
        # For local demo, auto-create the patient if missing
        patient = Patient(id=body["patient_id"], name=f"Patient {body['patient_id']}")
        db.session.add(patient)

    api_key = uid("key")
    device = Device(
        id=body["device_id"],
        type=body["type"],
        patient_id=body["patient_id"],
        api_key=api_key
    )
    db.session.add(device)
    db.session.commit()
    return {"device_id": device.id, "api_key": api_key, "status": "registered"}, 201

@app.post("/api/v1/patients/<patient_id>/vitals")
def post_vitals(patient_id):
    """Ingest a vital-sign record; idempotent via Idempotency-Key."""
    ok, resp = require_device_api_key()
    if not ok:
        return resp
    try:
        data = VitalInSchema().load(request.get_json())
    except ValidationError as e:
        return error("validation_error", 400, "Invalid payload", e.messages)

    # Idempotency: prefer header, fallback to body
    idem = request.headers.get("Idempotency-Key") or (request.json or {}).get("idempotency_key")
    if not record_idempotency(data["device_id"], idem):
        return {"status": "duplicate_ignored"}, 200

    v = Vital(
        id=uid("v"),
        patient_id=patient_id,
        timestamp=data["timestamp"],
        heart_rate=data.get("heart_rate"),
        bp_systolic=(data.get("bp") or {}).get("systolic"),
        bp_diastolic=(data.get("bp") or {}).get("diastolic"),
        spo2=data.get("spo2"),
        temp=data.get("temp"),
        device_id=data["device_id"],
    )
    db.session.add(v)
    db.session.commit()
    return {"vital_id": v.id, "status": "stored"}, 201

@app.get("/api/v1/patients/<patient_id>/latest")
def get_latest(patient_id):
    """Return the most recent vital-sign reading for the patient."""
    v = Vital.query.filter_by(patient_id=patient_id).order_by(Vital.timestamp.desc()).first()
    if not v:
        return error("not_found", 404, "No readings for patient")
    bp = None
    if v.bp_systolic is not None and v.bp_diastolic is not None:
        bp = {"systolic": v.bp_systolic, "diastolic": v.bp_diastolic}
    return {
        "timestamp": v.timestamp.isoformat() + "Z",
        "heart_rate": v.heart_rate,
        "bp": bp,
        "spo2": v.spo2,
        "temp": v.temp,
        "device_id": v.device_id
    }, 200

@app.get("/api/v1/patients/<patient_id>/history")
def get_history(patient_id):
    """Paginated historical readings with optional from/to filters."""
    try:
        dt_from = parse_dt(request.args.get("from")) if request.args.get("from") else None
        dt_to   = parse_dt(request.args.get("to")) if request.args.get("to") else None
        page = max(int(request.args.get("page", 1)), 1)
        size = min(max(int(request.args.get("page_size", 100)), 1), 500)

        q = Vital.query.filter_by(patient_id=patient_id)
        if dt_from:
            q = q.filter(Vital.timestamp >= dt_from)
        if dt_to:
            q = q.filter(Vital.timestamp <= dt_to)
        total = q.count()
        q = q.order_by(Vital.timestamp.desc()).offset((page - 1) * size).limit(size)

        items = []
        for v in q.all():
            bp = None
            if v.bp_systolic is not None and v.bp_diastolic is not None:
                bp = {"systolic": v.bp_systolic, "diastolic": v.bp_diastolic}
            items.append({
                "timestamp": v.timestamp.isoformat() + "Z",
                "heart_rate": v.heart_rate,
                "bp": bp,
                "spo2": v.spo2,
                "temp": v.temp,
                "device_id": v.device_id
            })
        return {"results": items, "page": page, "page_size": size, "total": total}, 200
    except Exception as e:
        return error("bad_request", 400, "Invalid query parameters", str(e))

# ------------------------- DEMO & DEBUG -------------------------
@app.get("/")
def home():
    return {
        "api_name": "Smart Hospital API",
        "status": "OK",
        "available_endpoints": [
            "/health",
            "/patients",
            "/admin/init-db",
            "/admin/db-path",
            "/admin/routes",
            "/api/v1/devices/register",
            "/api/v1/patients/{id}/vitals",
            "/api/v1/patients/{id}/latest",
            "/api/v1/patients/{id}/history",
            "/debug/echo"
        ]
    }, 200

@app.get("/health")
def health_check():
    return {"status": "OK"}, 200

@app.get("/patients")
def get_patients():
    return {"patients": [
        {"id": 1, "name": "John Doe", "room": 101},
        {"id": 2, "name": "Jane Smith", "room": 102}
    ]}, 200

@app.route("/debug/echo", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
def echo():
    """Utility endpoint that echoes request method, headers, and JSON body (for debugging)."""
    return {
        "method": request.method,
        "path": request.path,
        "headers": {
            "Content-Type": request.headers.get("Content-Type"),
            "X-API-Key": request.headers.get("X-API-Key"),
            "Idempotency-Key": request.headers.get("Idempotency-Key")
        },
        "body": request.get_json(silent=True)
    }, 200

# ------------------------- ENTRY POINT -------------------------
if __name__ == "__main__":
    print("Starting Smart Hospital API from:", os.path.abspath(__file__))
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
