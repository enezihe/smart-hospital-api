import json

def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "OK"}

def test_init_db_and_latest_404(client):
    resp = client.post("/admin/init-db", data=b"")
    assert resp.status_code in (200, 201)
    assert resp.get_json()["status"] == "initialized"

    resp = client.get("/api/v1/patients/p_smoke/latest")
    assert resp.status_code == 404
    assert resp.get_json()["code"] == "not_found"

def test_register_post_vitals_latest_and_idempotency(client):
    payload = {"device_id": "dev-smoke", "type": "multi", "patient_id": "p_smoke"}
    resp = client.post(
        "/api/v1/devices/register",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json", "X-API-Key": "test-master-key"},
    )
    assert resp.status_code in (200, 201)
    reg = resp.get_json()
    assert reg["device_id"] == "dev-smoke"
    assert "api_key" in reg

    vital_body = {
        "timestamp": "2025-08-13T12:00:00Z",
        "heart_rate": 72,
        "bp": {"systolic": 118, "diastolic": 76},
        "spo2": 97,
        "temp": 36.8,
        "device_id": "dev-smoke",
    }
    idem = "reading-2025-08-13T12:00:00Z-dev-smoke"

    r1 = client.post(
        "/api/v1/patients/p_smoke/vitals",
        data=json.dumps(vital_body),
        headers={"Content-Type": "application/json", "X-API-Key": "test-master-key", "Idempotency-Key": idem},
    )
    assert r1.status_code == 201
    assert r1.get_json()["status"] == "stored"

    r2 = client.post(
        "/api/v1/patients/p_smoke/vitals",
        data=json.dumps(vital_body),
        headers={"Content-Type": "application/json", "X-API-Key": "test-master-key", "Idempotency-Key": idem},
    )
    assert r2.status_code == 200
    assert r2.get_json()["status"] == "duplicate_ignored"

    latest = client.get("/api/v1/patients/p_smoke/latest")
    assert latest.status_code == 200
    doc = latest.get_json()
    assert doc["heart_rate"] == 72
    assert doc["bp"] == {"systolic": 118, "diastolic": 76}
    assert doc["spo2"] == 97
    assert doc["temp"] == 36.8
    assert doc["device_id"] == "dev-smoke"
