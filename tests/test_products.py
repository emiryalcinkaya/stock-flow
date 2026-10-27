def test_create_and_list_product(client, admin_headers, make_product):
    product = make_product(name="Coffee", price=4.5, stock=12)

    assert product["price"] == 4.5
    assert product["stock_quantity"] == 12

    listed = client.get("/api/v1/products/", headers=admin_headers).json()
    assert [p["id"] for p in listed] == [product["id"]]


def test_cashier_can_read_but_not_write(client, cashier_headers, make_product):
    product = make_product()

    assert client.get("/api/v1/products/", headers=cashier_headers).status_code == 200

    payload = {"name": "X", "barcode": "X1", "price": 1, "stock_quantity": 1}
    assert client.post("/api/v1/products/", json=payload, headers=cashier_headers).status_code == 403
    assert client.delete(f"/api/v1/products/{product['id']}", headers=cashier_headers).status_code == 403
    assert (
        client.post(
            f"/api/v1/products/{product['id']}/increase-stock",
            json={"quantity": 1},
            headers=cashier_headers,
        ).status_code
        == 403
    )


def test_duplicate_barcode_rejected(client, admin_headers, make_product):
    make_product(barcode="SAME")
    payload = {"name": "Other", "barcode": "SAME", "price": 1, "stock_quantity": 1}

    response = client.post("/api/v1/products/", json=payload, headers=admin_headers)
    assert response.status_code == 400


def test_invalid_values_rejected(client, admin_headers):
    for payload in [
        {"name": "A", "barcode": "B", "price": 0, "stock_quantity": 1},
        {"name": "A", "barcode": "B", "price": 1, "stock_quantity": -1},
        {"name": "  ", "barcode": "B", "price": 1, "stock_quantity": 1},
        {"name": "A", "barcode": "B", "price": 1.234, "stock_quantity": 1},
    ]:
        response = client.post("/api/v1/products/", json=payload, headers=admin_headers)
        assert response.status_code == 422, payload


def test_decrease_stock_cannot_go_negative(client, admin_headers, make_product):
    product = make_product(stock=3)

    response = client.post(
        f"/api/v1/products/{product['id']}/decrease-stock",
        json={"quantity": 4},
        headers=admin_headers,
    )
    assert response.status_code == 400

    response = client.post(
        f"/api/v1/products/{product['id']}/decrease-stock",
        json={"quantity": 3},
        headers=admin_headers,
    )
    assert response.json()["stock_quantity"] == 0


def test_archive_and_restore(client, admin_headers, make_product):
    product = make_product(barcode="ARCH")
    product_url = f"/api/v1/products/{product['id']}"

    assert client.delete(product_url, headers=admin_headers).status_code == 200
    assert client.get(product_url, headers=admin_headers).status_code == 404

    archived = client.get("/api/v1/products/?status=archived", headers=admin_headers).json()
    assert [p["id"] for p in archived] == [product["id"]]

    # The barcode stays reserved by the archived product.
    payload = {"name": "New", "barcode": "ARCH", "price": 1, "stock_quantity": 1}
    response = client.post("/api/v1/products/", json=payload, headers=admin_headers)
    assert response.status_code == 400
    assert "Restore" in response.json()["detail"]

    restored = client.post(f"{product_url}/restore", headers=admin_headers)
    assert restored.status_code == 200
    assert restored.json()["is_active"] is True


def test_cashier_cannot_list_archived(client, cashier_headers):
    response = client.get("/api/v1/products/?status=archived", headers=cashier_headers)
    assert response.status_code == 403


def test_search(client, admin_headers, make_product):
    make_product(name="Green Tea", barcode="TEA-1")
    make_product(name="Coffee", barcode="COF-1")

    names = [p["name"] for p in client.get("/api/v1/products/?search=tea", headers=admin_headers).json()]
    assert names == ["Green Tea"]


def test_stock_movements_are_logged(client, admin_headers, make_product):
    product = make_product(stock=5)
    base = f"/api/v1/products/{product['id']}"

    client.post(f"{base}/increase-stock", json={"quantity": 3}, headers=admin_headers)
    client.post(f"{base}/decrease-stock", json={"quantity": 2}, headers=admin_headers)
    client.patch(base, json={"stock_quantity": 10}, headers=admin_headers)

    movements = client.get(f"{base}/movements", headers=admin_headers).json()
    summary = [(m["reason"], m["change"], m["quantity_after"]) for m in reversed(movements)]

    assert summary == [
        ("initial", 5, 5),
        ("restock", 3, 8),
        ("stock_out", -2, 6),
        ("adjustment", 4, 10),
    ]
    assert all(m["username"] == "admin" for m in movements)
