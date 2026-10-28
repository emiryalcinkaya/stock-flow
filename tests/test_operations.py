from tests.conftest import auth_headers

API = "/api/v1"


def _level(client, headers, product_id):
    levels = client.get(f"{API}/products/{product_id}/stock-levels", headers=headers).json()
    return {level["warehouse_name"]: level["quantity"] for level in levels}


# ----- Suppliers and purchases -------------------------------------------------


def test_suppliers_crud(client, admin_headers, cashier_headers):
    response = client.post(
        f"{API}/suppliers",
        json={"name": " Acme Ltd ", "phone": "555", "email": "Sales@Acme.com"},
        headers=admin_headers,
    )
    assert response.status_code == 201
    supplier = response.json()
    assert supplier["name"] == "Acme Ltd" and supplier["email"] == "sales@acme.com"

    assert client.post(f"{API}/suppliers", json={"name": "Acme Ltd"}, headers=admin_headers).status_code == 400
    assert client.post(f"{API}/suppliers", json={"name": "X"}, headers=cashier_headers).status_code == 403
    bad_email = {"name": "Y", "email": "nope"}
    assert client.post(f"{API}/suppliers", json=bad_email, headers=admin_headers).status_code == 422

    client.patch(f"{API}/suppliers/{supplier['id']}", json={"is_active": False}, headers=admin_headers)
    assert client.get(f"{API}/suppliers", headers=cashier_headers).json() == []
    assert len(client.get(f"{API}/suppliers?include_inactive=true", headers=admin_headers).json()) == 1


def test_stock_in_with_supplier_updates_cost(client, admin_headers, make_product):
    supplier = client.post(f"{API}/suppliers", json={"name": "Acme"}, headers=admin_headers).json()
    product = make_product(price=20, stock=0)

    response = client.post(
        f"{API}/products/{product['id']}/increase-stock",
        json={"quantity": 10, "supplier_id": supplier["id"], "unit_cost": 12.5, "document_no": "INV-7"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["cost_price"] == 12.5

    movement = client.get(f"{API}/products/{product['id']}/movements", headers=admin_headers).json()[0]
    assert movement["supplier_name"] == "Acme"
    assert movement["unit_cost"] == 12.5
    assert movement["document_no"] == "INV-7"

    unknown = client.post(
        f"{API}/products/{product['id']}/increase-stock",
        json={"quantity": 1, "supplier_id": 999},
        headers=admin_headers,
    )
    assert unknown.status_code == 404


# ----- Users -------------------------------------------------------------------


def test_admin_manages_users(client, admin_headers, cashier_headers):
    response = client.post(
        f"{API}/users",
        json={"full_name": "Ayşe", "username": "ayse", "email": "ayse@example.com", "password": "secret123"},
        headers=admin_headers,
    )
    assert response.status_code == 201
    user = response.json()
    assert user["role"] == "cashier" and user["is_active"]

    # The new user can sign in.
    login = client.post(f"{API}/auth/login", json={"username": "ayse", "password": "secret123"})
    assert login.status_code == 200

    duplicate = {"full_name": "A", "username": "AYSE", "email": "x@example.com", "password": "secret123"}
    assert client.post(f"{API}/users", json=duplicate, headers=admin_headers).status_code == 400
    short = {"full_name": "B", "username": "bob", "email": "b@example.com", "password": "short"}
    assert client.post(f"{API}/users", json=short, headers=admin_headers).status_code == 422
    assert client.get(f"{API}/users", headers=cashier_headers).status_code == 403

    promoted = client.patch(f"{API}/users/{user['id']}", json={"role": "admin"}, headers=admin_headers).json()
    assert promoted["role"] == "admin"

    client.post(f"{API}/users/{user['id']}/reset-password", json={"new_password": "another123"}, headers=admin_headers)
    assert client.post(f"{API}/auth/login", json={"username": "ayse", "password": "another123"}).status_code == 200

    client.patch(f"{API}/users/{user['id']}", json={"is_active": False}, headers=admin_headers)
    assert client.post(f"{API}/auth/login", json={"username": "ayse", "password": "another123"}).status_code == 403


def test_last_admin_and_self_are_protected(client, admin_headers):
    users = client.get(f"{API}/users", headers=admin_headers).json()
    admin = next(u for u in users if u["username"] == "admin")

    for change in ({"is_active": False}, {"role": "cashier"}):
        response = client.patch(f"{API}/users/{admin['id']}", json=change, headers=admin_headers)
        assert response.status_code == 400


def test_change_own_password(client):
    headers = auth_headers(client, "cashier")

    wrong = {"current_password": "nope", "new_password": "newpass123"}
    assert client.post(f"{API}/auth/change-password", json=wrong, headers=headers).status_code == 400

    right = {"current_password": "cashier123", "new_password": "newpass123"}
    assert client.post(f"{API}/auth/change-password", json=right, headers=headers).status_code == 200
    assert client.post(f"{API}/auth/login", json={"username": "cashier", "password": "newpass123"}).status_code == 200


# ----- Stock counts ------------------------------------------------------------


def test_stock_count_corrects_stock(client, admin_headers, cashier_headers, make_product):
    apples = make_product(name="Apples", unit="kg", stock=10)
    bolts = make_product(name="Bolts", stock=50)
    untouched = make_product(name="Untouched", stock=7)

    count = client.post(f"{API}/stock-counts", json={"note": "Monthly"}, headers=admin_headers).json()
    assert count["status"] == "open"
    assert {line["product_name"]: line["expected_quantity"] for line in count["lines"]} == {
        "Apples": 10, "Bolts": 50, "Untouched": 7,
    }

    # Only one open count per warehouse.
    assert client.post(f"{API}/stock-counts", json={}, headers=admin_headers).status_code == 400

    # Staff can enter counts; whole-number units reject fractions.
    saved = client.patch(
        f"{API}/stock-counts/{count['id']}",
        json={"lines": [{"product_id": apples["id"], "counted_quantity": 8.5},
                        {"product_id": bolts["id"], "counted_quantity": 52}]},
        headers=cashier_headers,
    )
    assert saved.status_code == 200 and saved.json()["counted_count"] == 2
    bad = client.patch(
        f"{API}/stock-counts/{count['id']}",
        json={"lines": [{"product_id": bolts["id"], "counted_quantity": 1.5}]},
        headers=cashier_headers,
    )
    assert bad.status_code == 400

    # Stock moves while counting: completion compares against the quantity at that moment.
    client.post(f"{API}/products/{bolts['id']}/decrease-stock", json={"quantity": 5}, headers=admin_headers)

    assert client.post(f"{API}/stock-counts/{count['id']}/complete", headers=cashier_headers).status_code == 403
    done = client.post(f"{API}/stock-counts/{count['id']}/complete", headers=admin_headers).json()
    assert done["status"] == "completed"
    differences = {line["product_name"]: line["difference"] for line in done["lines"]}
    assert differences == {"Apples": -1.5, "Bolts": 7, "Untouched": None}

    assert _level(client, admin_headers, apples["id"]) == {"Main Warehouse": 8.5}
    assert _level(client, admin_headers, bolts["id"]) == {"Main Warehouse": 52}
    assert _level(client, admin_headers, untouched["id"]) == {"Main Warehouse": 7}

    movement = client.get(f"{API}/products/{bolts['id']}/movements", headers=admin_headers).json()[0]
    assert movement["reason"] == "count_adjustment" and movement["stock_count_id"] == count["id"]

    # Closed counts can't be edited.
    closed = client.patch(f"{API}/stock-counts/{count['id']}", json={"lines": []}, headers=admin_headers)
    assert closed.status_code == 400


def test_stock_count_by_category_and_cancel(client, admin_headers, make_product):
    food = client.post(f"{API}/categories", json={"name": "Food"}, headers=admin_headers).json()
    make_product(name="Rice", category_id=food["id"])
    make_product(name="Hammer")

    count = client.post(f"{API}/stock-counts", json={"category_id": food["id"]}, headers=admin_headers).json()
    assert [line["product_name"] for line in count["lines"]] == ["Rice"]

    assert client.post(f"{API}/stock-counts/{count['id']}/complete", headers=admin_headers).status_code == 400
    cancelled = client.post(f"{API}/stock-counts/{count['id']}/cancel", headers=admin_headers).json()
    assert cancelled["status"] == "cancelled"

    listing = client.get(f"{API}/stock-counts", headers=admin_headers)
    assert listing.headers["X-Total-Count"] == "1"


# ----- Paging ------------------------------------------------------------------


def test_total_count_header(client, admin_headers, make_product):
    for i in range(5):
        make_product(name=f"P{i}")

    response = client.get(f"{API}/products/?limit=2&skip=2", headers=admin_headers)
    assert response.headers["X-Total-Count"] == "5"
    assert [p["name"] for p in response.json()] == ["P2", "P3"]


# ----- CSV ---------------------------------------------------------------------


def test_csv_export_and_import_roundtrip(client, admin_headers, make_product):
    make_product(name="Çay", barcode="TEA", price=2.5, stock=4)

    export = client.get(f"{API}/products/export.csv?delimiter=semicolon", headers=admin_headers)
    assert export.status_code == 200
    text = export.content.decode("utf-8")
    assert text.startswith("﻿barcode;name;category")
    assert "TEA;Çay;;pcs;2,5;;;4" in text

    csv_text = (
        "barcode;name;category;unit;price;cost_price;min_stock;stock_quantity\n"
        "TEA;Çay Premium;Drinks;pcs;3,75;2;;99\n"
        "NEW-1;Un;Food;kg;1.234,50;;10;12,5\n"
    )
    preview = client.post(f"{API}/products/import", json={"csv": csv_text}, headers=admin_headers).json()
    assert preview["saved"] is False
    assert (preview["created"], preview["updated"], preview["categories_created"]) == (1, 1, 2)
    assert preview["warnings"]  # stock of an existing product is not changed by import
    assert client.get(f"{API}/products/?search=Un", headers=admin_headers).json() == []

    saved = client.post(
        f"{API}/products/import", json={"csv": csv_text, "dry_run": False}, headers=admin_headers
    ).json()
    assert saved["saved"] is True

    products = {p["barcode"]: p for p in client.get(f"{API}/products/", headers=admin_headers).json()}
    assert products["TEA"]["name"] == "Çay Premium" and products["TEA"]["price"] == 3.75
    assert products["TEA"]["stock_quantity"] == 4
    assert products["NEW-1"]["price"] == 1234.5 and products["NEW-1"]["stock_quantity"] == 12.5
    assert products["NEW-1"]["category_name"] == "Food"


def test_csv_import_rejects_bad_rows(client, admin_headers):
    csv_text = (
        "barcode,name,unit,price,stock_quantity\n"
        "A,Good,pcs,1,1\nB,,pcs,1,1\nC,Bad unit,parsec,1,1\nD,Frac,pcs,1,1.5\n"
    )
    result = client.post(
        f"{API}/products/import", json={"csv": csv_text, "dry_run": False}, headers=admin_headers
    ).json()

    assert result["saved"] is False
    assert [e["row"] for e in result["errors"]] == [3, 4, 5]
    # All or nothing: the valid row was not saved either.
    assert client.get(f"{API}/products/", headers=admin_headers).json() == []


def test_movement_and_stock_out_exports(client, admin_headers, cashier_headers, make_product):
    product = make_product(name="Widget", price=10, stock=5)
    client.post(
        f"{API}/sales/", json={"items": [{"product_id": product["id"], "quantity": 2}]}, headers=cashier_headers
    )

    movements = client.get(f"{API}/reports/movements.csv", headers=admin_headers).content.decode()
    assert "Widget" in movements and "initial" in movements and "sale" in movements

    stock_outs = client.get(f"{API}/reports/stock-outs.csv", headers=admin_headers).content.decode()
    assert "Widget" in stock_outs and ",2," in stock_outs


# ----- Reports -----------------------------------------------------------------


def test_report_overview(client, admin_headers, cashier_headers, make_product):
    supplier = client.post(f"{API}/suppliers", json={"name": "Acme"}, headers=admin_headers).json()
    sold = make_product(name="Sold", price=10, stock=0)
    make_product(name="Idle", price=4, stock=3)

    client.post(
        f"{API}/products/{sold['id']}/increase-stock",
        json={"quantity": 10, "supplier_id": supplier["id"], "unit_cost": 6},
        headers=admin_headers,
    )
    client.post(f"{API}/sales/", json={"items": [{"product_id": sold["id"], "quantity": 4}]}, headers=cashier_headers)
    client.post(
        f"{API}/sales/",
        json={"reason": "waste", "items": [{"product_id": sold["id"], "quantity": 1}]},
        headers=cashier_headers,
    )

    report = client.get(f"{API}/reports/overview", headers=admin_headers).json()
    totals = report["totals"]
    assert totals["stock_in_value"] == 60
    assert totals["sales_revenue"] == 40
    assert totals["stock_outs"] == 2
    assert totals["gross_profit"] == 16  # 4 x (10 - 6)

    assert report["top_products"][0]["name"] == "Sold"
    assert report["top_products"][0]["quantity"] == 5
    assert [p["name"] for p in report["slow_movers"]] == ["Idle"]
    assert report["warehouses"][0]["value"] == 5 * 10 + 3 * 4
    assert report["suppliers"] == [{"supplier_id": supplier["id"], "name": "Acme", "deliveries": 1, "value": 60.0}]
    assert len(report["monthly"]) == 6
