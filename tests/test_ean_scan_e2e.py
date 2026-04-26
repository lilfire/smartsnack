"""E2E integration test: register product with EAN → search/scan by EAN.

This test uses a real test database (no mocks) to verify the full flow:
1. Register a new product via the API
2. Add an EAN barcode to the product
3. Search for that EAN via the products list endpoint
4. Assert the product is found and the response shape matches the real API

This was created as part of LSO-874 to prevent the class of bug where
unit test mocks hide real API issues (LSO-858).
"""

from tests.mock_shape_validator import (
    validate_product_list_response,
    validate_add_ean_response,
    validate_add_product_response,
    validate_ean_list_response,
)


def test_register_product_and_scan_ean(client, app_ctx):
    """Full integration: create product → add EAN → search by EAN → find product."""
    # Step 1: Register a new product
    product_data = {
        "name": "E2E EAN Test Product",
        "type": "Snacks",
        "kcal": 200,
        "fat": 10,
        "saturated_fat": 3,
        "carbs": 25,
        "sugar": 5,
        "protein": 8,
        "fiber": 3,
        "salt": 0.5,
        "smak": 4,
    }
    resp = client.post("/api/products", json=product_data)
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.data}"
    created = resp.get_json()
    validate_add_product_response(created)
    product_id = created["id"]

    # Step 2: Add an EAN barcode to the product
    ean_code = "7038010069307"
    resp = client.post(f"/api/products/{product_id}/eans", json={"ean": ean_code})
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.data}"
    ean_result = resp.get_json()
    validate_add_ean_response(ean_result)
    assert ean_result["ean"] == ean_code
    assert ean_result["is_primary"] is True

    # Step 3: Search for the product by EAN (simulates scanner lookup)
    resp = client.get(f"/api/products?search={ean_code}")
    assert resp.status_code == 200
    search_result = resp.get_json()

    # Step 4: Validate the response shape via the shared validator
    validate_product_list_response(search_result, allow_empty=False)

    # Step 5: Verify the product is actually found
    assert search_result["total"] >= 1, "Should find at least 1 product"
    matching = [p for p in search_result["products"] if p["id"] == product_id]
    assert len(matching) == 1, f"Expected exactly 1 match for product {product_id}"
    assert matching[0]["name"] == "E2E EAN Test Product"

    # Step 6: Validate EAN list endpoint shape
    resp = client.get(f"/api/products/{product_id}/eans")
    assert resp.status_code == 200
    validate_ean_list_response(resp.get_json())


def test_search_by_ean_response_shape(client, app_ctx):
    """Verify the /api/products response shape is always {products: [], total: N}."""
    resp = client.get("/api/products?search=0000000000000")
    assert resp.status_code == 200
    result = resp.get_json()
    validate_product_list_response(result)
    assert result["total"] == 0
    assert result["products"] == []


def test_ean_search_finds_secondary_ean(client, app_ctx):
    """Adding a secondary EAN to a product should also be findable via search."""
    resp = client.post("/api/products", json={
        "name": "Secondary EAN Product",
        "type": "Snacks",
        "kcal": 100, "fat": 5, "saturated_fat": 1,
        "carbs": 15, "sugar": 3, "protein": 4,
        "fiber": 2, "salt": 0.3, "smak": 3,
    })
    assert resp.status_code == 201
    pid = resp.get_json()["id"]

    # Add primary EAN
    resp = client.post(f"/api/products/{pid}/eans", json={"ean": "5901234123457"})
    assert resp.status_code == 201

    # Add secondary EAN
    secondary_ean = "4006381333931"
    resp = client.post(f"/api/products/{pid}/eans", json={"ean": secondary_ean})
    assert resp.status_code == 201
    ean_data = resp.get_json()
    validate_add_ean_response(ean_data)
    assert ean_data["is_primary"] is False

    # Search by secondary EAN
    resp = client.get(f"/api/products?search={secondary_ean}")
    result = resp.get_json()
    validate_product_list_response(result, allow_empty=False)
    matching = [p for p in result["products"] if p["id"] == pid]
    assert len(matching) == 1, "Product should be found by secondary EAN"


def test_product_list_response_has_required_fields(client, app_ctx):
    """Each product in the response must have core fields for the scanner UI."""
    resp = client.post("/api/products", json={
        "name": "Field Check Product",
        "type": "Snacks",
        "kcal": 150, "fat": 7, "saturated_fat": 2,
        "carbs": 20, "sugar": 4, "protein": 6,
        "fiber": 2.5, "salt": 0.4, "smak": 3,
    })
    assert resp.status_code == 201

    resp = client.get("/api/products")
    result = resp.get_json()
    validate_product_list_response(result, allow_empty=False)
