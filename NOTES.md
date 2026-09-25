# Sanctum Sanctorum - Submission Notes

**Live URL:** https://sanctum-sanctorum-7v4e.onrender.com/

### Demo Accounts
The database automatically seeds on first start. You can test the endpoints using these seeded members:
- `apprentice@example.com` (Apprentice Tier)
- `master@example.com` (Master Tier)
- `supreme@example.com` (Supreme Tier)

---

## 1. What was finished
I completed the full specification. All 202 tests pass, and the application is successfully deployed using Render and Supabase (PostgreSQL).

- **Books:** Creation, listing (with advanced search, pagination, and sorting), partial updates, and ISBN-13 checksum validation.
- **Members:** Registration with exact duplicate email checks.
- **Orders:** Full creation logic (checking restricted status, exact stock limits, and calculating tier/bulk pricing combinations) and order cancellations with stock restoration.
- **Loans:** Borrowing and returning system with tier-based limit enforcement, overdue checks, and date-based late fee calculations.
- **Reports:** Member stats (aggregating spent cents, active/overdue loans, and late fees) and the top-selling books aggregation using SQLAlchemy joins.

---

## 2. Architectural Decisions & Trade-offs

**1. Thin Routers, Fat Services**
I kept the HTTP layer (`routers/`) strictly responsible for request parsing and HTTP responses. All business logic, database queries, and validation were pushed down into the `services/` layer. This makes the code much easier to unit test and re-use.

**2. Database Concurrency (Trade-off)**
In `create_order` and `create_loan`, I check `book.stock` and then decrement it (`book.stock -= 1`). In a high-traffic production environment with PostgreSQL, this read-modify-write pattern could result in a race condition (e.g., two concurrent requests selling the last copy). 
*What I would change with more time:* I would implement optimistic concurrency control (using a version/lock column) or use SQLAlchemy's `with_for_update()` to lock the row during the transaction to ensure stock levels remain perfectly accurate under concurrent load.

**3. Database Portability**
The app was initially built for SQLite. When deploying to a serverless platform (Render), SQLite is insufficient because the ephemeral disk wipes the database on restart. I migrated to PostgreSQL (Supabase) via the `SANCTUM_DATABASE_URL` environment variable. To maintain local test suite compatibility, I adjusted the SQLAlchemy engine configuration in `db.py` to only apply the `check_same_thread: False` argument when the URL explicitly starts with `sqlite`. 

**4. Complex Pricing Logic**
I isolated the `calculate_discount_percent` logic into a pure function in `orders.py`. By keeping it decoupled from the database session, it is trivially easy to unit test every combination of tier and bulk discounts without needing database fixtures.

**5. Redis Caching for Heavy Reports (Add-on)**
The `top_books` report executes a heavy analytical query involving multiple joins and aggregations across `Books`, `Orders`, and `OrderItems`. To ensure the API remains extremely fast under load, I implemented a robust caching layer using Redis (`cache.py`). 
- **Graceful Degradation:** The cache safely falls back to direct database execution if the `REDIS_URL` is missing or the Redis server is unreachable, ensuring no test breaks.
- **Event-Driven Invalidation:** The cache is aggressively invalidated matching the `top_books:*` pattern exactly when `pay_order` is executed, guaranteeing that analytical users never see stale sales data while completely avoiding cache reads during write-heavy traffic.

---

**6. Dockerization (Add-on)**
I containerized the entire stack using a multi-stage `Dockerfile` and `docker-compose.yml`. The Docker setup provisions three services: the FastAPI app, PostgreSQL 16, and Redis 7. Key design choices:
- **Multi-stage build:** The first stage uses `uv` for fast dependency resolution; the second stage copies only the virtual environment and app code into a slim Python image, keeping the final image size minimal.
- **Health checks & dependency ordering:** PostgreSQL and Redis containers include health checks, and the app container waits for both to be healthy before starting, preventing startup race conditions.
- **One command to run everything:** `docker compose up --build` spins up the entire production-like environment locally.

---

**7. GitHub Actions CI/CD (Add-on)**
I added a continuous integration pipeline (`.github/workflows/ci.yml`) that runs automatically on every push and pull request to `main`. The pipeline:
- Installs dependencies using `uv` for reproducible builds.
- Runs the full 202-test suite with `pytest`.
- Boots the app and hits the `/health` endpoint to verify the server starts cleanly.

This ensures no broken code ever reaches the main branch.

---

## 3. AI Usage

I utilized an AI assistant (Google DeepMind's Gemini) during this project as a pair programmer to move quickly and effectively.

**What I used it for:**
- **Debugging Deployment:** I used the AI to help me debug the migration from SQLite to PostgreSQL. When the app crashed on Render with an `invalid connection option "check_same_thread"` error, the AI immediately helped me isolate that this is a SQLite-specific `connect_arg` that PostgreSQL rejects, allowing me to patch `db.py` conditionally.
- **Rubber-Ducking Logic:** I used it to validate my logic for the ISBN-13 checksum mathematical rules and the complex late-fee calculation logic (ensuring edge cases around partial days were handled correctly).
- **Scaffolding:** Generating the boilerplate SQLAlchemy aggregation queries for the `top_books` report.

**Where it was wrong / unhelpful:**
When implementing the `tier_at_least` helper function for checking if a member was authorized for restricted books, the AI initially suggested a strict greater-than comparison (`>`) based on the list indices. I had to manually override and correct this to a greater-than-or-equal-to (`>=`) comparison, because a Master tier user should obviously be allowed to access a book with a minimum requirement of Master! Uncritically accepting the AI's logic would have resulted in failed tests and a broken authorization system.
