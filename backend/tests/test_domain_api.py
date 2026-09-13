from fastapi.testclient import TestClient


def test_domain_creation_flow(client: TestClient) -> None:
    customer_response = client.post(
        "/customers",
        json={"name": "Ana Torres", "phone": "+57 300 123 4567", "email": "ana@example.com"},
    )
    assert customer_response.status_code == 201
    customer = customer_response.json()

    vehicle_response = client.post(
        "/vehicles",
        json={
            "customer_id": customer["id"],
            "plate": "abc 123",
            "vin": "1HGCM82633A004352",
            "brand": "Honda",
            "model": "Accord",
            "year": 2003,
            "engine": "2.4L",
            "mileage": 120000,
        },
    )
    assert vehicle_response.status_code == 201
    vehicle = vehicle_response.json()
    assert vehicle["plate"] == "ABC 123"

    diagnostic_response = client.post(
        "/diagnostics",
        json={"vehicle_id": vehicle["id"], "reported_symptoms": "El motor vibra al acelerar."},
    )
    assert diagnostic_response.status_code == 201
    diagnostic = diagnostic_response.json()
    assert diagnostic["status"] == "CREATED"

    media_response = client.post(
        f"/diagnostics/{diagnostic['id']}/media",
        json={"type": "PHOTO", "file_url": "https://files.example.com/engine.jpg"},
    )
    assert media_response.status_code == 201
    assert client.get(f"/diagnostics/{diagnostic['id']}/media").json()[0]["type"] == "PHOTO"

    finding_response = client.post(
        f"/diagnostics/{diagnostic['id']}/findings",
        json={"component": "Bujías", "finding": "Desgaste notable", "severity": "MEDIUM", "confidence": 85},
    )
    assert finding_response.status_code == 201

    work_order_response = client.post(
        "/work-orders",
        json={
            "diagnostic_id": diagnostic["id"],
            "description": "Cambiar bujías y revisar bobinas.",
            "estimated_cost": "250000.00",
        },
    )
    assert work_order_response.status_code == 201
    assert work_order_response.json()["status"] == "DRAFT"

    assert len(client.get("/customers").json()) == 1
    assert len(client.get("/vehicles").json()) == 1
    assert len(client.get("/diagnostics").json()) == 1
    assert len(client.get("/work-orders").json()) == 1


def test_domain_rejects_invalid_references_and_values(client: TestClient) -> None:
    assert client.post(
        "/vehicles",
        json={
            "customer_id": 999,
            "plate": "ABC123",
            "brand": "Mazda",
            "model": "3",
            "year": 2020,
            "mileage": 0,
        },
    ).status_code == 404

    assert client.post(
        "/customers",
        json={"name": "A", "phone": "invalid#", "email": "not-an-email"},
    ).status_code == 422

    assert client.get("/vehicles/999").status_code == 404
    assert client.get("/diagnostics/999/media").status_code == 404
