import threading

from fastapi.testclient import TestClient

from app.main import app


def _stock(client, headers, product_id):
    return client.get(f"/api/v1/products/{product_id}", headers=headers).json()["stock_quantity"]


def test_create_sale_updates_stock_and_totals(client, cashier_headers, make_product):
    a = make_product(name="A", price=19.99, stock=10)
    b = make_product(name="B", price=0.1, stock=10)

    response = client.post(
        "/api/v1/sales/",
        json={"items": [{"product_id": a["id"], "quantity": 3}, {"product_id": b["id"], "quantity": 3}]},
        headers=cashier_headers,
    )

    assert response.status_code == 201, response.text
    sale = response.json()
    # Decimal math: 3 * 19.99 + 3 * 0.10 = 60.27 exactly (float would give 60.269999...).
    assert sale["total_price"] == 60.27
    assert sale["status"] == "completed"
    assert sale["cashier_name"] == "Cashier User"
    assert _stock(client, cashier_headers, a["id"]) == 7


def test_duplicate_lines_cannot_oversell(client, cashier_headers, make_product):
    product = make_product(stock=5)

    response = client.post(
        "/api/v1/sales/",
        json={"items": [{"product_id": product["id"], "quantity": 4}, {"product_id": product["id"], "quantity": 4}]},
        headers=cashier_headers,
    )

    assert response.status_code == 400
    assert _stock(client, cashier_headers, product["id"]) == 5


def test_duplicate_lines_are_merged(client, cashier_headers, make_product):
    product = make_product(stock=5)

    response = client.post(
        "/api/v1/sales/",
        json={"items": [{"product_id": product["id"], "quantity": 2}, {"product_id": product["id"], "quantity": 3}]},
        headers=cashier_headers,
    )

    assert response.status_code == 201
    assert [(i["product_id"], i["quantity"]) for i in response.json()["items"]] == [(product["id"], 5)]
    assert _stock(client, cashier_headers, product["id"]) == 0


def test_failed_sale_is_rolled_back(client, cashier_headers, make_product):
    ok = make_product(stock=5)
    short = make_product(stock=1)

    response = client.post(
        "/api/v1/sales/",
        json={"items": [{"product_id": ok["id"], "quantity": 2}, {"product_id": short["id"], "quantity": 2}]},
        headers=cashier_headers,
    )

    assert response.status_code == 400
    assert _stock(client, cashier_headers, ok["id"]) == 5
    assert client.get("/api/v1/sales/", headers=cashier_headers).json() == []


def test_archived_product_cannot_be_sold(client, admin_headers, cashier_headers, make_product):
    product = make_product()
    client.delete(f"/api/v1/products/{product['id']}", headers=admin_headers)

    response = client.post(
        "/api/v1/sales/",
        json={"items": [{"product_id": product["id"], "quantity": 1}]},
        headers=cashier_headers,
    )
    assert response.status_code == 404


def test_sale_keeps_product_snapshot(client, admin_headers, cashier_headers, make_product):
    product = make_product(name="Old Name", price=5)
    sale = client.post(
        "/api/v1/sales/",
        json={"items": [{"product_id": product["id"], "quantity": 1}]},
        headers=cashier_headers,
    ).json()

    client.patch(
        f"/api/v1/products/{product['id']}",
        json={"name": "New Name", "price": 99},
        headers=admin_headers,
    )

    detail = client.get(f"/api/v1/sales/{sale['id']}", headers=cashier_headers).json()
    assert detail["items"][0]["product_name"] == "Old Name"
    assert detail["items"][0]["unit_price"] == 5


def test_cancel_sale_restocks_and_excluded_from_revenue(client, admin_headers, cashier_headers, make_product):
    product = make_product(price=10, stock=5)
    sale = client.post(
        "/api/v1/sales/",
        json={"items": [{"product_id": product["id"], "quantity": 2}]},
        headers=cashier_headers,
    ).json()

    # Cashiers can't cancel.
    assert client.post(f"/api/v1/sales/{sale['id']}/cancel", headers=cashier_headers).status_code == 403

    response = client.post(f"/api/v1/sales/{sale['id']}/cancel", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert _stock(client, admin_headers, product["id"]) == 5

    # Cancelling twice must not restock twice.
    assert client.post(f"/api/v1/sales/{sale['id']}/cancel", headers=admin_headers).status_code == 400
    assert _stock(client, admin_headers, product["id"]) == 5

    summary = client.get("/api/v1/dashboard/summary", headers=admin_headers).json()
    assert summary["total_sales"] == 0
    assert summary["revenue"] == 0


def test_sales_list_filters_and_pagination(client, cashier_headers, make_product):
    product = make_product(stock=50)
    for _ in range(3):
        client.post(
            "/api/v1/sales/",
            json={"items": [{"product_id": product["id"], "quantity": 1}]},
            headers=cashier_headers,
        )

    assert len(client.get("/api/v1/sales/?limit=2", headers=cashier_headers).json()) == 2
    assert len(client.get("/api/v1/sales/?date_from=2000-01-01", headers=cashier_headers).json()) == 3
    assert client.get("/api/v1/sales/?date_to=2000-01-01", headers=cashier_headers).json() == []


def test_concurrent_sales_never_oversell(make_product, cashier_headers):
    """Many parallel requests for the last units: only the available stock may be sold."""
    product = make_product(stock=3)
    results = []
    barrier = threading.Barrier(8)

    def buy():
        with TestClient(app) as thread_client:
            barrier.wait()
            response = thread_client.post(
                "/api/v1/sales/",
                json={"items": [{"product_id": product["id"], "quantity": 1}]},
                headers=cashier_headers,
            )
            results.append(response.status_code)

    threads = [threading.Thread(target=buy) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == [201, 201, 201, 400, 400, 400, 400, 400]

    with TestClient(app) as check_client:
        assert _stock(check_client, cashier_headers, product["id"]) == 0


def test_dashboard_summary(client, cashier_headers, make_product):
    make_product(stock=2)
    make_product(stock=50)

    summary = client.get("/api/v1/dashboard/summary", headers=cashier_headers).json()

    assert summary["total_products"] == 2
    assert summary["low_stock"] == 1
    assert summary["low_stock_threshold"] == 5
