import base64

URL = "/api/v1/company"
PNG_1PX = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def test_empty_profile_by_default(client, cashier_headers):
    assert client.get(URL, headers=cashier_headers).json() == {
        "name": None, "description": None, "logo": None, "currency": "USD",
    }


def test_admin_updates_profile(client, admin_headers, cashier_headers):
    response = client.patch(
        URL,
        json={"name": "  Demir Hırdavat ", "description": "Since 1998", "logo": PNG_1PX},
        headers=admin_headers,
    )
    assert response.status_code == 200

    profile = client.get(URL, headers=cashier_headers).json()
    assert profile == {"name": "Demir Hırdavat", "description": "Since 1998", "logo": PNG_1PX, "currency": "USD"}


def test_partial_update_and_clearing(client, admin_headers):
    client.patch(URL, json={"name": "Shop", "logo": PNG_1PX}, headers=admin_headers)

    profile = client.patch(URL, json={"description": "New"}, headers=admin_headers).json()
    assert profile["name"] == "Shop" and profile["logo"] == PNG_1PX

    profile = client.patch(URL, json={"logo": None, "name": ""}, headers=admin_headers).json()
    assert profile["logo"] is None
    assert profile["name"] is None


def test_cashier_cannot_update(client, cashier_headers):
    assert client.patch(URL, json={"name": "X"}, headers=cashier_headers).status_code == 403


def test_invalid_logos_rejected(client, admin_headers):
    too_big = "data:image/png;base64," + base64.b64encode(b"0" * (301 * 1024)).decode()
    for logo in ["https://example.com/logo.png", "data:text/html;base64,PGgxPg==", too_big]:
        assert client.patch(URL, json={"logo": logo}, headers=admin_headers).status_code == 422


def test_currency(client, admin_headers, cashier_headers):
    assert client.patch(URL, json={"currency": "EUR"}, headers=admin_headers).json()["currency"] == "EUR"
    assert client.get(URL, headers=cashier_headers).json()["currency"] == "EUR"

    # Can't be cleared, and only supported currencies are accepted.
    assert client.patch(URL, json={"currency": None}, headers=admin_headers).json()["currency"] == "EUR"
    assert client.patch(URL, json={"currency": "GBP"}, headers=admin_headers).status_code == 422
