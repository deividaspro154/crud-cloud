from app import app, validate_api_payload


def test_valid_api_payload():
    data = {
        "name": "Keyboard",
        "sku": "KB-001",
        "quantity": 5,
        "price": 49.99,
        "available": True,
        "restock_date": "2026-10-10",
    }
    with app.app_context():
        clean, errors = validate_api_payload(data)
    assert errors == []
    assert clean["quantity"] == 5


def test_invalid_types():
    data = {
        "name": 123,
        "sku": [],
        "quantity": "five",
        "price": "free",
        "available": "yes",
        "restock_date": "tomorrow",
    }
    with app.app_context():
        _, errors = validate_api_payload(data)
    assert len(errors) >= 5
