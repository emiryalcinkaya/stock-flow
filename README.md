# StockFlow

[![CI](https://github.com/emiryalcinkaya/stock-flow/actions/workflows/ci.yml/badge.svg)](https://github.com/emiryalcinkaya/stock-flow/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791)

StockFlow is a full-stack inventory and sales management system. It simulates how real-world stock and sales operations should behave: consistent, auditable and safe under concurrent use.

Instead of a plain CRUD app, the project focuses on **how data should behave in a real system**.

## Features

- **Products** – create, edit, search, archive and restore products with unique barcodes
- **Stock control** – stock in / stock out, enforced never to go below zero (API checks *and* a database constraint)
- **Sales** – multi-item sales processed in a single transaction, with row locking so two cashiers can never sell the same last unit
- **Sale snapshots** – each sale line stores the product name, barcode and price at the time of sale, so editing a product never rewrites history
- **Cancellation** – admins can cancel a sale; items go back into stock and the sale is excluded from revenue
- **Audit log** – every stock change (initial, restock, stock out, adjustment, sale, cancellation) is recorded with who did it
- **Roles** – `admin` manages products and sales, `cashier` processes sales; enforced by the API and reflected in the UI
- **Dashboard** – product count, low-stock count, completed sales and revenue

## Design decisions

| Decision | Why |
| --- | --- |
| Products are archived, never deleted | Historical sales keep a valid reference |
| Money stored as `NUMERIC(10,2)` and computed with `Decimal` | No floating point rounding errors in totals |
| `SELECT ... FOR UPDATE` on products during a sale, locked in id order | Prevents overselling and deadlocks under concurrency |
| Duplicate lines in one sale are merged before the stock check | A cart can't bypass the stock limit by splitting a quantity |
| Stock changes go through one service (`app/services/stock.py`) | Every change is validated and logged in one place |
| Schema managed by Alembic migrations | Safe upgrades of existing databases |

## Tech stack

**Backend:** FastAPI · SQLAlchemy 2 · PostgreSQL · Alembic · Pydantic v2 · PyJWT · bcrypt
**Frontend:** Vanilla JavaScript (ES modules) · modular CSS · Lucide icons
**Tooling:** pytest · Ruff · Docker Compose · GitHub Actions

## Project structure

```
stockflow/
├── app/
│   ├── api/
│   │   ├── deps.py              # auth & role dependencies
│   │   └── v1/endpoints/        # auth, products, sales, dashboard
│   ├── core/                    # settings, security (JWT, bcrypt), rate limiting
│   ├── db/
│   │   ├── models/              # SQLAlchemy models
│   │   ├── seed.py              # roles + demo users
│   │   └── session.py
│   ├── schemas/                 # Pydantic request/response models
│   ├── services/stock.py        # stock changes + audit log
│   └── main.py
├── alembic/                     # database migrations
├── frontend/                    # static HTML/CSS/JS client
├── tests/                       # pytest suite (runs against PostgreSQL)
├── docker-compose.yml
└── Dockerfile
```

## Getting started

### Option A – Docker (everything)

```bash
cp .env.example .env          # then set a strong secret_key
docker compose --profile full up --build
```

- Frontend: http://localhost:8080
- API docs: http://localhost:8000/docs

Migrations and the demo users are applied automatically on startup.

### Option B – Local development

Requirements: Python 3.11+, Docker (for PostgreSQL).

```bash
# 1. Database
docker compose up -d db

# 2. Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # then set a strong secret_key

alembic upgrade head          # create / upgrade the schema
python -m app.db.seed         # roles + demo users
uvicorn app.main:app --reload

# 3. Frontend (in another terminal) – ES modules need to be served over HTTP
python -m http.server 5500 --directory frontend
```

Open http://localhost:5500 and sign in.

| Role | Username | Password |
| --- | --- | --- |
| Admin | `admin` | `admin123` |
| Cashier | `cashier` | `cashier123` |

> These are demo credentials. Override them with `SEED_ADMIN_PASSWORD` / `SEED_CASHIER_PASSWORD` before seeding any real environment.

### Upgrading a database created before migrations

If your database was created by the old `create_all` script, mark it as the initial revision once, then upgrade:

```bash
alembic stamp 0001_initial
alembic upgrade head
```

## Configuration

All settings are read from environment variables or `.env` (see [`.env.example`](.env.example)).

| Variable | Default | Description |
| --- | --- | --- |
| `database_url` | – | SQLAlchemy URL for PostgreSQL |
| `secret_key` | – | JWT signing key (min. 16 chars) |
| `access_token_expire_minutes` | `60` | Token lifetime |
| `cors_origins` | localhost:5500 / 8080 | Comma separated allowed frontend origins |
| `low_stock_threshold` | `5` | Stock level considered "low" |
| `login_max_attempts` / `login_lockout_seconds` | `5` / `300` | Failed-login rate limit |

The frontend calls `http://127.0.0.1:8000/api/v1` by default. To change it, define `window.STOCKFLOW_API_URL` before the page scripts load.

## API overview

Interactive docs are available at `/docs` when the API is running.

| Method | Endpoint | Role |
| --- | --- | --- |
| `POST` | `/api/v1/auth/login` | public |
| `GET` | `/api/v1/auth/me` | any |
| `GET` | `/api/v1/products/?search=&status=active\|archived&skip=&limit=` | any (archived: admin) |
| `POST` | `/api/v1/products/` | admin |
| `PATCH` / `DELETE` | `/api/v1/products/{id}` | admin |
| `POST` | `/api/v1/products/{id}/increase-stock` · `/decrease-stock` · `/restore` | admin |
| `GET` | `/api/v1/products/{id}/movements` | admin |
| `GET` / `POST` | `/api/v1/sales/?date_from=&date_to=&status=&skip=&limit=` | any |
| `GET` | `/api/v1/sales/{id}` | any |
| `POST` | `/api/v1/sales/{id}/cancel` | admin |
| `GET` | `/api/v1/dashboard/summary` | any |
| `GET` | `/api/v1/health` | public |

## Running tests

The tests run against a real PostgreSQL database (row locking can't be tested on SQLite).

```bash
docker compose up -d db
docker exec stockflow_db psql -U stockflow_user -d stockflow_db -c "CREATE DATABASE stockflow_test"

pytest          # uses TEST_DATABASE_URL, defaults to the local stockflow_test database
ruff check .
```

The suite covers authentication, permissions, stock rules, sale rollback, snapshots, cancellation and a concurrency test that fires parallel sales at the last units in stock.

## Roadmap

- User management screens (create / deactivate users from the UI)
- Stock movement history view in the frontend
- Reports: daily / monthly revenue and best-selling products
- Shared rate-limit store (e.g. Redis) for multi-worker deployments

## License

[MIT](LICENSE) © Emir Yalçınkaya
