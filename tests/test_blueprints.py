"""Integration tests for all blueprint routes via Flask test client."""


class TestCoreBlueprint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200


class TestProductsBlueprint:
    def test_list_products(self, client):
        resp = client.get("/api/products")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_list_with_search(self, client):
        resp = client.get("/api/products?search=Popcorn")
        assert resp.status_code == 200

    def test_list_with_type_filter(self, client):
        resp = client.get("/api/products?type=Snacks")
        assert resp.status_code == 200

    def test_add_product(self, client):
        resp = client.post(
            "/api/products",
            json={
                "type": "Snacks",
                "name": "Test Chips",
                "ean": "12345678",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "id" in data

    def test_add_product_invalid(self, client):
        resp = client.post("/api/products", json={"type": "Snacks"})
        assert resp.status_code == 400

    def test_update_product(self, client):
        # Get an existing product id
        products = client.get("/api/products").get_json()
        pid = products[0]["id"]
        resp = client.put(f"/api/products/{pid}", json={"name": "Updated Name"})
        assert resp.status_code == 200

    def test_update_nonexistent(self, client):
        resp = client.put("/api/products/99999", json={"name": "Test"})
        assert resp.status_code == 404

    def test_delete_product(self, client):
        # Add then delete
        add_resp = client.post(
            "/api/products",
            json={
                "type": "Snacks",
                "name": "ToDelete",
            },
        )
        pid = add_resp.get_json()["id"]
        resp = client.delete(f"/api/products/{pid}")
        assert resp.status_code == 200

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/products/99999")
        assert resp.status_code == 404


class TestImagesBlueprint:
    def test_get_image(self, client):
        products = client.get("/api/products").get_json()
        pid = products[0]["id"]
        resp = client.get(f"/api/products/{pid}/image")
        # May return 200 or 404 depending on whether image exists
        assert resp.status_code in (200, 404)

    def test_set_image(self, client):
        products = client.get("/api/products").get_json()
        pid = products[0]["id"]
        resp = client.put(
            f"/api/products/{pid}/image",
            json={
                "image": "data:image/png;base64,iVBORw0KGgo=",
            },
        )
        assert resp.status_code == 200

    def test_set_image_invalid(self, client):
        products = client.get("/api/products").get_json()
        pid = products[0]["id"]
        resp = client.put(
            f"/api/products/{pid}/image",
            json={
                "image": "invalid-data",
            },
        )
        assert resp.status_code == 400

    def test_delete_image(self, client):
        products = client.get("/api/products").get_json()
        pid = products[0]["id"]
        resp = client.delete(f"/api/products/{pid}/image")
        assert resp.status_code in (200, 404)


class TestCategoriesBlueprint:
    def test_list_categories(self, client):
        resp = client.get("/api/categories")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_add_category(self, client):
        resp = client.post(
            "/api/categories",
            json={
                "name": "Drinks",
                "label": "Drikker",
                "emoji": "🧃",
            },
        )
        assert resp.status_code == 201

    def test_add_duplicate_category(self, client):
        resp = client.post(
            "/api/categories",
            json={
                "name": "Snacks",
                "label": "Snacks",
                "emoji": "🍿",
            },
        )
        assert resp.status_code == 409

    def test_update_category(self, client):
        resp = client.put(
            "/api/categories/Snacks",
            json={
                "label": "Updated Snacks",
                "emoji": "🍕",
            },
        )
        assert resp.status_code == 200

    def test_delete_empty_category(self, client):
        client.post(
            "/api/categories",
            json={
                "name": "EmptyCat",
                "label": "Empty",
                "emoji": "📦",
            },
        )
        resp = client.delete("/api/categories/EmptyCat")
        assert resp.status_code == 200


class TestWeightsBlueprint:
    def test_get_weights(self, client):
        resp = client.get("/api/weights")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_update_weights(self, client):
        resp = client.put(
            "/api/weights",
            json=[
                {
                    "field": "kcal",
                    "enabled": True,
                    "weight": 50,
                    "direction": "lower",
                    "formula": "minmax",
                    "formula_min": 0,
                    "formula_max": 0,
                }
            ],
        )
        assert resp.status_code == 200

    def test_update_weights_invalid(self, client):
        resp = client.put(
            "/api/weights",
            json=[
                {
                    "field": "kcal",
                    "direction": "invalid",
                }
            ],
        )
        assert resp.status_code == 400


class TestProteinQualityBlueprint:
    def test_list_entries(self, client):
        resp = client.get("/api/protein-quality")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_add_entry(self, client):
        resp = client.post(
            "/api/protein-quality",
            json={
                "name": "new_test_source",
                "keywords": ["new", "test"],
                "pdcaas": 0.8,
                "diaas": 0.7,
                "label": "New Test",
            },
        )
        assert resp.status_code == 201

    def test_add_duplicate(self, client):
        resp = client.post(
            "/api/protein-quality",
            json={
                "name": "whey",
                "keywords": ["w"],
                "pdcaas": 1.0,
                "diaas": 1.0,
            },
        )
        assert resp.status_code == 409

    def test_estimate(self, client):
        resp = client.post(
            "/api/estimate-protein-quality",
            json={
                "ingredients": "corn, sunflower oil",
            },
        )
        assert resp.status_code == 200

    def test_estimate_empty(self, client):
        resp = client.post(
            "/api/estimate-protein-quality",
            json={
                "ingredients": "",
            },
        )
        assert resp.status_code == 400


class TestStatsBlueprint:
    def test_get_stats(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total" in data
        assert "types" in data


class TestSettingsBlueprint:
    def test_get_language(self, client):
        resp = client.get("/api/settings/language")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "language" in data

    def test_set_language(self, client):
        resp = client.put("/api/settings/language", json={"language": "en"})
        assert resp.status_code == 200

    def test_set_invalid_language(self, client):
        resp = client.put("/api/settings/language", json={"language": "xx"})
        assert resp.status_code == 400


class TestTranslationsBlueprint:
    def test_get_languages(self, client):
        resp = client.get("/api/languages")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_get_translations(self, client):
        resp = client.get("/api/translations/no")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)

    def test_get_translations_invalid(self, client):
        resp = client.get("/api/translations/xx")
        assert resp.status_code == 404


class TestBackupBlueprint:
    def test_backup(self, client):
        resp = client.get("/api/backup")
        assert resp.status_code == 200

    def test_restore(self, client):
        # Get backup first
        backup = client.get("/api/backup").get_json()
        resp = client.post("/api/restore", json=backup)
        assert resp.status_code == 200

    def test_restore_invalid(self, client):
        resp = client.post("/api/restore", json={})
        assert resp.status_code == 400

    def test_import(self, client):
        resp = client.post(
            "/api/import",
            json={
                "products": [{"type": "Snacks", "name": "Imported"}],
            },
        )
        assert resp.status_code == 200


class TestProxyBlueprint:
    def test_missing_url(self, client):
        resp = client.get("/api/proxy-image")
        assert resp.status_code == 400

    def test_disallowed_domain(self, client):
        resp = client.get("/api/proxy-image?url=https://evil.com/img.jpg")
        assert resp.status_code == 403


class TestCheckDuplicateBlueprint:
    def test_check_duplicate_returns_match(self, client):
        products = client.get("/api/products").get_json()
        pid = products[0]["id"]
        # Add another product to be found as duplicate
        add_resp = client.post(
            "/api/products",
            json={"type": "Snacks", "name": "Another Product", "ean": "8000000000099"},
        )
        other_id = add_resp.get_json()["id"]
        resp = client.post(
            f"/api/products/{other_id}/check-duplicate",
            json={"ean": products[0]["ean"], "name": ""},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["duplicate"] is not None
        assert data["duplicate"]["id"] == pid

    def test_check_duplicate_returns_null(self, client):
        products = client.get("/api/products").get_json()
        pid = products[0]["id"]
        resp = client.post(
            f"/api/products/{pid}/check-duplicate",
            json={"ean": "9999999999999", "name": "Nonexistent"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["duplicate"] is None


class TestMergeBlueprint:
    def test_merge_products(self, client):
        target_resp = client.post(
            "/api/products",
            json={"type": "Snacks", "name": "Merge Target", "ean": "8000000000001"},
        )
        source_resp = client.post(
            "/api/products",
            json={"type": "Snacks", "name": "Merge Source", "ean": "8000000000002", "brand": "SourceBrand"},
        )
        target_id = target_resp.get_json()["id"]
        source_id = source_resp.get_json()["id"]
        resp = client.post(
            f"/api/products/{target_id}/merge",
            json={"source_id": source_id},
        )
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_merge_source_not_found(self, client):
        products = client.get("/api/products").get_json()
        pid = products[0]["id"]
        resp = client.post(
            f"/api/products/{pid}/merge",
            json={"source_id": 99999},
        )
        assert resp.status_code == 404

    def test_merge_missing_source_id(self, client):
        products = client.get("/api/products").get_json()
        pid = products[0]["id"]
        resp = client.post(
            f"/api/products/{pid}/merge",
            json={},
        )
        assert resp.status_code == 400


class TestOffBlueprint:
    def test_missing_json(self, client):
        resp = client.post("/api/off/add-product")
        assert resp.status_code == 400
