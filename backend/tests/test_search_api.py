import pytest
from fastapi.testclient import TestClient


def _customer(client: TestClient, name: str, email: str, phone: str = "+57 300 000 0000") -> dict:
    response = client.post("/customers", json={"name": name, "phone": phone, "email": email})
    assert response.status_code == 201, response.json()
    return response.json()


def _vehicle(client: TestClient, customer_id: int, plate: str) -> dict:
    response = client.post(
        "/vehicles",
        json={
            "customer_id": customer_id,
            "plate": plate,
            "brand": "Mazda",
            "model": "2",
            "year": 2019,
            "mileage": 50_000,
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()


def _names(response) -> list[str]:
    assert response.status_code == 200, response.json()
    return [customer["name"] for customer in response.json()]


# --- Customers --------------------------------------------------------------------------------


@pytest.fixture()
def customers(client: TestClient) -> None:
    _customer(client, "Ana Ruiz", "ana.ruiz@example.com", "+57 300 111 2222")
    _customer(client, "Bruno Díaz", "bruno@taller.co", "+57 310 555 0000")
    _customer(client, "Carla Anaya", "carla@example.com", "+57 320 999 8888")


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("ana", ["Ana Ruiz", "Carla Anaya"]),  # nombre, parcial y sin distinguir mayúsculas
        ("RUIZ", ["Ana Ruiz"]),
        ("taller.co", ["Bruno Díaz"]),  # email
        ("555", ["Bruno Díaz"]),  # teléfono
        ("zzz", []),
    ],
)
def test_search_customers_by_name_email_or_phone(client, customers, q, expected) -> None:
    assert _names(client.get("/customers", params={"q": q})) == expected


def test_search_customers_trims_the_query(client, customers) -> None:
    assert _names(client.get("/customers", params={"q": "  bruno  "})) == ["Bruno Díaz"]


def test_search_customers_default_and_explicit_limit(client) -> None:
    for i in range(25):
        _customer(client, f"Cliente {i:02d}", f"cliente{i}@example.com")

    assert len(client.get("/customers", params={"q": "cliente"}).json()) == 20
    assert len(client.get("/customers", params={"q": "cliente", "limit": 5}).json()) == 5
    assert len(client.get("/customers", params={"q": "cliente", "limit": 50}).json()) == 25


def test_list_customers_without_parameters_returns_all(client) -> None:
    for i in range(25):
        _customer(client, f"Cliente {i:02d}", f"cliente{i}@example.com")

    body = client.get("/customers").json()

    assert len(body) == 25
    assert [c["id"] for c in body] == sorted(c["id"] for c in body)


def test_list_customers_accepts_limit_without_query(client) -> None:
    for i in range(3):
        _customer(client, f"Cliente {i}", f"cliente{i}@example.com")

    assert len(client.get("/customers", params={"limit": 2}).json()) == 2


def test_search_customers_treats_wildcards_literally(client) -> None:
    _customer(client, "Ana Ruiz", "ana_ruiz@example.com")
    _customer(client, "Ana Ruiz Bis", "anaXruiz@example.com")

    assert _names(client.get("/customers", params={"q": "a_r"})) == ["Ana Ruiz"]
    assert _names(client.get("/customers", params={"q": "%%"})) == []


@pytest.mark.parametrize(
    "params",
    [{"q": "a"}, {"q": "   "}, {"q": "x" * 101}, {"q": "ana", "limit": 0}, {"q": "ana", "limit": 51}],
    ids=["q_corta", "q_en_blanco", "q_larga", "limit_0", "limit_51"],
)
def test_search_customers_validates_parameters(client, params) -> None:
    assert client.get("/customers", params=params).status_code == 422


# --- Vehicles ---------------------------------------------------------------------------------


@pytest.fixture()
def fleet(client: TestClient) -> dict[str, int]:
    ana = _customer(client, "Ana Ruiz", "ana@example.com")["id"]
    bruno = _customer(client, "Bruno Díaz", "bruno@example.com")["id"]
    _vehicle(client, ana, "ABC123")
    _vehicle(client, ana, "XYZ789")
    _vehicle(client, bruno, "ABD456")
    return {"ana": ana, "bruno": bruno}


def _plates(response) -> list[str]:
    assert response.status_code == 200, response.json()
    return [vehicle["plate"] for vehicle in response.json()]


def test_list_vehicles_without_filters_returns_all(client, fleet) -> None:
    assert _plates(client.get("/vehicles")) == ["ABC123", "XYZ789", "ABD456"]


def test_filter_vehicles_by_customer(client, fleet) -> None:
    assert _plates(client.get("/vehicles", params={"customer_id": fleet["ana"]})) == ["ABC123", "XYZ789"]
    assert _plates(client.get("/vehicles", params={"customer_id": 999})) == []


@pytest.mark.parametrize(
    ("plate", "expected"),
    [("abc", ["ABC123"]), ("AB", ["ABC123", "ABD456"]), ("789", ["XYZ789"]), (" c12 ", ["ABC123"])],
)
def test_filter_vehicles_by_partial_plate_case_insensitive(client, fleet, plate, expected) -> None:
    assert _plates(client.get("/vehicles", params={"plate": plate})) == expected


def test_vehicle_filters_combine(client, fleet) -> None:
    params = {"customer_id": fleet["bruno"], "plate": "ab"}

    assert _plates(client.get("/vehicles", params=params)) == ["ABD456"]


def test_filtered_vehicles_default_and_explicit_limit(client) -> None:
    owner = _customer(client, "Flota SAS", "flota@example.com")["id"]
    for i in range(25):
        _vehicle(client, owner, f"FLT{i:03d}")

    assert len(client.get("/vehicles", params={"customer_id": owner}).json()) == 20
    assert len(client.get("/vehicles", params={"customer_id": owner, "limit": 50}).json()) == 25
    assert len(client.get("/vehicles").json()) == 25  # sin filtros: comportamiento anterior


@pytest.mark.parametrize(
    "params",
    [{"customer_id": 0}, {"plate": ""}, {"plate": "   "}, {"plate": "X" * 16}, {"limit": 51}],
    ids=["customer_0", "plate_vacia", "plate_en_blanco", "plate_larga", "limit_51"],
)
def test_filter_vehicles_validates_parameters(client, params) -> None:
    assert client.get("/vehicles", params=params).status_code == 422
