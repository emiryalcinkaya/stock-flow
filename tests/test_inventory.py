API = "/api/v1"


def _stock_levels(client, headers, product_id):
    levels = client.get(f"{API}/products/{product_id}/stock-levels", headers=headers).json()
    return {level["warehouse_name"]: level["quantity"] for level in levels}


def _add_warehouse(client, headers, name="Store B"):
    response = client.post(f"{API}/warehouses", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# ----- Units and decimal quantities -----------------------------------------


def test_units_are_listed(client, cashier_headers):
    units = {u["code"]: u["whole"] for u in client.get(f"{API}/units", headers=cashier_headers).json()}
    assert units["pcs"] is True
    assert units["kg"] is False


def test_decimal_quantities_for_weight_units(client, admin_headers, make_product):
    product = make_product(name="Flour", unit="kg", stock=10.5)
    base = f"{API}/products/{product['id']}"

    response = client.post(f"{base}/decrease-stock", json={"quantity": 0.25}, headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["stock_quantity"] == 10.25
    assert response.json()["unit"] == "kg"


def test_whole_units_reject_fractions(client, admin_headers, make_product):
    product = make_product(unit="pcs", stock=5)

    response = client.post(
        f"{API}/products/{product['id']}/decrease-stock",
        json={"quantity": 1.5},
        headers=admin_headers,
    )
    assert response.status_code == 400

    response = client.post(
        f"{API}/products/",
        json={"name": "Bolt", "barcode": "B-1", "unit": "box", "stock_quantity": 2.5},
        headers=admin_headers,
    )
    assert response.status_code == 400


def test_unit_change_blocked_when_stock_is_fractional(client, admin_headers, make_product):
    product = make_product(unit="kg", stock=2.5)

    response = client.patch(f"{API}/products/{product['id']}", json={"unit": "pcs"}, headers=admin_headers)
    assert response.status_code == 400


# ----- Optional price and per-product minimum --------------------------------


def test_product_without_price(client, admin_headers, cashier_headers):
    response = client.post(
        f"{API}/products/",
        json={"name": "Screws", "barcode": "SCR-1", "stock_quantity": 100},
        headers=admin_headers,
    )
    assert response.status_code == 201
    product = response.json()
    assert product["price"] is None

    sale = client.post(
        f"{API}/sales/",
        json={"reason": "consumption", "items": [{"product_id": product["id"], "quantity": 10}]},
        headers=cashier_headers,
    )
    assert sale.status_code == 201
    assert sale.json()["total_price"] == 0


def test_price_and_min_stock_can_be_cleared(client, admin_headers, make_product):
    product = make_product(price=5, min_stock=3)

    response = client.patch(
        f"{API}/products/{product['id']}",
        json={"price": None, "min_stock": None},
        headers=admin_headers,
    )

    assert response.json()["price"] is None
    assert response.json()["min_stock"] is None


def test_per_product_minimum_stock(client, admin_headers, make_product):
    # Global threshold is 5.
    below_own_minimum = make_product(stock=15, min_stock=20)
    above_own_minimum = make_product(stock=2, min_stock=1)
    below_default = make_product(stock=3)

    low = client.get(f"{API}/products/?low_stock=true", headers=admin_headers).json()
    assert {p["id"] for p in low} == {below_own_minimum["id"], below_default["id"]}
    assert above_own_minimum["is_low_stock"] is False

    summary = client.get(f"{API}/dashboard/summary", headers=admin_headers).json()
    assert summary["low_stock"] == 2


def test_stock_value(client, admin_headers, make_product):
    make_product(price=2.5, stock=4)
    make_product(price=None, stock=100)

    summary = client.get(f"{API}/dashboard/summary", headers=admin_headers).json()
    assert summary["stock_value"] == 10


# ----- Categories ------------------------------------------------------------


def test_categories_crud_and_filter(client, admin_headers, cashier_headers, make_product):
    food = client.post(f"{API}/categories", json={"name": "Food"}, headers=admin_headers).json()
    assert client.post(f"{API}/categories", json={"name": "Food"}, headers=admin_headers).status_code == 400
    assert client.post(f"{API}/categories", json={"name": "X"}, headers=cashier_headers).status_code == 403

    rice = make_product(name="Rice", category_id=food["id"])
    make_product(name="Hammer")

    filtered = client.get(f"{API}/products/?category_id={food['id']}", headers=cashier_headers).json()
    assert [p["name"] for p in filtered] == ["Rice"]
    assert filtered[0]["category_name"] == "Food"

    categories = client.get(f"{API}/categories", headers=cashier_headers).json()
    assert categories == [{"id": food["id"], "name": "Food", "product_count": 1}]

    assert client.delete(f"{API}/categories/{food['id']}", headers=admin_headers).status_code == 200
    product = client.get(f"{API}/products/{rice['id']}", headers=admin_headers).json()
    assert product["category_id"] is None


def test_unknown_category_rejected(client, admin_headers):
    response = client.post(
        f"{API}/products/",
        json={"name": "A", "barcode": "A-1", "category_id": 999},
        headers=admin_headers,
    )
    assert response.status_code == 404


# ----- Warehouses and transfers ----------------------------------------------


def test_default_warehouse_is_used_when_none_given(client, admin_headers, make_product):
    product = make_product(stock=7)
    assert _stock_levels(client, admin_headers, product["id"]) == {"Main Warehouse": 7}


def test_stock_is_tracked_per_warehouse(client, admin_headers, cashier_headers, make_product):
    store = _add_warehouse(client, admin_headers)
    product = make_product(stock=5)
    base = f"{API}/products/{product['id']}"

    client.post(f"{base}/increase-stock", json={"quantity": 3, "warehouse_id": store["id"]}, headers=admin_headers)
    assert _stock_levels(client, admin_headers, product["id"]) == {"Main Warehouse": 5, "Store B": 3}

    # Total is 8, but only 3 are in Store B.
    response = client.post(
        f"{API}/sales/",
        json={"warehouse_id": store["id"], "items": [{"product_id": product["id"], "quantity": 4}]},
        headers=cashier_headers,
    )
    assert response.status_code == 400

    stock = client.get(f"{API}/warehouses/{store['id']}/stock", headers=cashier_headers).json()
    assert stock == {str(product["id"]): 3}


def test_transfer_between_warehouses(client, admin_headers, make_product):
    store = _add_warehouse(client, admin_headers)
    main_id = client.get(f"{API}/warehouses", headers=admin_headers).json()[0]["id"]
    product = make_product(unit="kg", stock=10)
    base = f"{API}/products/{product['id']}"

    response = client.post(
        f"{base}/transfer",
        json={"from_warehouse_id": main_id, "to_warehouse_id": store["id"], "quantity": 2.5},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["stock_quantity"] == 10
    assert _stock_levels(client, admin_headers, product["id"]) == {"Main Warehouse": 7.5, "Store B": 2.5}

    too_much = client.post(
        f"{base}/transfer",
        json={"from_warehouse_id": store["id"], "to_warehouse_id": main_id, "quantity": 3},
        headers=admin_headers,
    )
    assert too_much.status_code == 400

    same = client.post(
        f"{base}/transfer",
        json={"from_warehouse_id": main_id, "to_warehouse_id": main_id, "quantity": 1},
        headers=admin_headers,
    )
    assert same.status_code == 422

    reasons = [m["reason"] for m in client.get(f"{base}/movements", headers=admin_headers).json()]
    assert reasons[:2] == ["transfer_in", "transfer_out"]


def test_warehouse_rules(client, admin_headers, make_product):
    store = _add_warehouse(client, admin_headers)
    main = client.get(f"{API}/warehouses", headers=admin_headers).json()[0]
    product = make_product(stock=0)
    client.post(
        f"{API}/products/{product['id']}/increase-stock",
        json={"quantity": 1, "warehouse_id": store["id"]},
        headers=admin_headers,
    )

    # Default can't be deactivated; a warehouse with stock can't be deactivated.
    deactivate = {"is_active": False}
    assert client.patch(f"{API}/warehouses/{main['id']}", json=deactivate, headers=admin_headers).status_code == 400
    assert client.patch(f"{API}/warehouses/{store['id']}", json=deactivate, headers=admin_headers).status_code == 400

    # Switching the default keeps exactly one default.
    client.patch(f"{API}/warehouses/{store['id']}", json={"is_default": True}, headers=admin_headers)
    defaults = [w["name"] for w in client.get(f"{API}/warehouses", headers=admin_headers).json() if w["is_default"]]
    assert defaults == ["Store B"]


def test_cancel_returns_stock_to_the_same_warehouse(client, admin_headers, make_product):
    store = _add_warehouse(client, admin_headers)
    product = make_product(stock=0)
    client.post(
        f"{API}/products/{product['id']}/increase-stock",
        json={"quantity": 4, "warehouse_id": store["id"]},
        headers=admin_headers,
    )
    sale = client.post(
        f"{API}/sales/",
        json={"warehouse_id": store["id"], "items": [{"product_id": product["id"], "quantity": 4}]},
        headers=admin_headers,
    ).json()

    client.post(f"{API}/sales/{sale['id']}/cancel", headers=admin_headers)

    assert _stock_levels(client, admin_headers, product["id"]) == {"Store B": 4}


# ----- Stock-out reasons -----------------------------------------------------


def test_stock_out_reasons(client, admin_headers, cashier_headers, make_product):
    product = make_product(price=10, stock=20)

    for reason in ["sale", "waste", "consumption"]:
        response = client.post(
            f"{API}/sales/",
            json={"reason": reason, "note": f"{reason} note", "items": [{"product_id": product["id"], "quantity": 1}]},
            headers=cashier_headers,
        )
        assert response.status_code == 201
        assert response.json()["reason"] == reason

    waste = client.get(f"{API}/sales/?reason=waste", headers=cashier_headers).json()
    assert len(waste) == 1 and waste[0]["note"] == "waste note"

    movements = client.get(f"{API}/products/{product['id']}/movements", headers=admin_headers).json()
    assert [m["reason"] for m in movements[:3]] == ["consumption", "waste", "sale"]

    # Only real sales count as revenue.
    summary = client.get(f"{API}/dashboard/summary", headers=admin_headers).json()
    assert summary["total_sales"] == 1
    assert summary["revenue"] == 10


def test_invalid_stock_out_reason(client, cashier_headers, make_product):
    product = make_product()
    response = client.post(
        f"{API}/sales/",
        json={"reason": "stolen", "items": [{"product_id": product["id"], "quantity": 1}]},
        headers=cashier_headers,
    )
    assert response.status_code == 422
