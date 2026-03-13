# FastAPI App — Architecture Guide

This document explains how all the layers of this application work together,
what each file is responsible for, and how a request flows from the client
to the database and back.

---

## Directory Structure

```
app/
├── main.py                             # Entry point
├── core/
│   └── config.py                       # Environment / settings loader
├── database/
│   └── session.py                      # DB engine, session factory, dependency
├── models/
│   └── task.py                         # SQLAlchemy ORM model (maps to DB table)
├── schemas/
│   └── task_model.py                   # Pydantic schema (request/response shape)
├── repositories/
│   └── task_repository.py              # Raw database queries
├── services/
│   └── task_services.py                # Business logic
└── api/
    └── routes/
        └── task_routes.py              # APIRouter instance + HTTP route definitions
```

---

## Layer Breakdown

### 1. Entry Point — `main.py`
Creates the FastAPI instance and registers the router from `task_routes.py`.
This is the only file that "assembles" the app — it contains no logic, routes,
or database code.

```python
app.include_router(tasks_router, prefix="/api")
```

**Responsibility:** Start the app and wire routers together.

---

### 2. Configuration — `core/config.py` + `.env`
`config.py` defines a `Settings` class using `pydantic-settings`. When the
app starts, it reads the `.env` file and loads environment variables into
typed attributes (e.g. `settings.DATABASE_URL`).

The `.env` file stores sensitive values like the database connection string
outside of the source code.

**Responsibility:** Provide a single, typed source of truth for all
configuration values. Other modules import `settings` from here instead of
reading environment variables directly.

---

### 3. Database Layer — `database/session.py`
Three things live here:

- **`engine`** — The SQLAlchemy connection to the database, created once at
  startup using `settings.DATABASE_URL`.

- **`SessionLocal`** — A session factory produced by `sessionmaker()`. It is
  not a session itself; it is a blueprint for creating sessions on demand.
  `autocommit=False` means you must explicitly call `db.commit()`.
  `autoflush=False` means changes are not automatically sent to the DB before
  every query.

- **`get_db()`** — A FastAPI dependency (a generator function). Every time a
  route needs a database session, FastAPI calls this function, which creates a
  new `SessionLocal()` session, yields it to the route, then closes it in the
  `finally` block — guaranteeing the session is always released even if an
  error occurs.

**Responsibility:** Manage database connections and provide sessions to the
rest of the app in a safe, lifecycle-aware way.

---

### 4. ORM Model — `models/task.py`
Defines the `Task` class that maps directly to the `tasks` table in the database.
Each attribute corresponds to a column:

| Python attribute | DB column | Type         |
|-----------------|-----------|--------------|
| `task`          | task      | varchar(200) |
| `completed`     | completed | boolean      |

> **Note:** `task` is currently the primary key, meaning task titles must be
> unique. A dedicated auto-increment `id` column is the more conventional choice.

`Base = declarative_base()` is the SQLAlchemy base class that all ORM models
must inherit from. `__tablename__` tells SQLAlchemy which table this class
represents.

**Responsibility:** Represent a database row as a Python object. This is the
only place that knows about the database table structure.

---

### 5. Pydantic Schema — `schemas/task_model.py`
Defines the `Task` Pydantic model used for **request validation**. When a
client sends a POST request with a JSON body, FastAPI automatically parses it
into this model and rejects it with a 422 error if the shape is wrong.

```python
class Task(BaseModel):
    title: str
    completed: bool = False
```

This is intentionally separate from the ORM model (`models/task.py`):

| Schema (`schemas/`)          | ORM Model (`models/`)         |
|-----------------------------|-------------------------------|
| Validates incoming JSON     | Maps to a database table      |
| Defines the API contract    | Defines the storage structure |
| Used by routes & services   | Used by the repository        |

**Responsibility:** Define and validate the shape of data entering the API.

---

### 6. Repository — `repositories/task_repository.py`
The only layer that talks directly to the database using the ORM. Each
function receives a `db: Session` and performs a single, focused operation:

- `get_all_tasks(db)` — runs `SELECT * FROM tasks` via `db.query(Task).all()`
- `create_task(db, task_name, completed)` — builds a `Task` ORM object,
  calls `db.add()` to stage it, `db.commit()` to persist it, and
  `db.refresh()` to reload the saved state from the DB before returning it.
- `set_complete(task_name, db)` — queries for the task by name, sets
  `completed = True`, then calls `db.commit()`.

**Responsibility:** Contain all SQL/ORM logic. No business decisions are made
here — only data access.

---

### 7. Service Layer — `services/task_services.py`
Sits between the router and the repository. It receives validated Pydantic
objects from the router, applies any business logic, then calls the repository
with the right arguments.

For example, `create_task` extracts `task.title` (a plain string) from the
Pydantic `Task` object before passing it to the repository, which expects a
`str`, not a schema object.

**Responsibility:** Business logic and data transformation. If rules like
"a task title must be unique" or "completed defaults to False on creation"
exist, they live here — not in the router or repository.

---

### 8. Router — `api/routes/task_routes.py`
Defines the `tasks_router = APIRouter()` instance and all HTTP endpoints.
Each route function uses `Depends(get_db)` to receive a database session
injected by FastAPI's dependency injection system, then passes it to the
service layer.

| Method | Path                | Action                        |
|--------|---------------------|-------------------------------|
| GET    | /api/tasks/get      | Return all tasks              |
| POST   | /api/tasks/create   | Create and save a task        |
| POST   | /api/tasks/complete | Mark an existing task as done |

**Responsibility:** Handle HTTP concerns only (method, path, status codes,
request/response models). No business logic or SQL belongs here.

---

## Request Flow

Below is the full lifecycle of a `POST /api/tasks/create` request:

```
Client
  │
  │  POST /api/tasks/create  { "title": "Buy milk" }
  ▼
api/routes/task_routes.py
  │  FastAPI parses JSON into Task schema (Pydantic validates it)
  │  FastAPI calls get_db() and injects a Session
  │  Calls create_task(db, task)
  ▼
services/task_services.py
  │  Extracts task.title from the Pydantic object
  │  Calls task_repository.create_task(db, task_name="Buy milk", completed=False)
  ▼
repositories/task_repository.py
  │  Creates a Task ORM object
  │  db.add(task) → stages the insert
  │  db.commit()  → writes to the database
  │  db.refresh() → reloads the saved row
  │  Returns the ORM Task object
  ▼
services/task_services.py  →  task_routes.py  →  Client
  │
  │  FastAPI serializes the returned object to JSON
  └─ Response: { "task": "Buy milk", "completed": false }
```

---

## Dependency Injection Summary

FastAPI's `Depends()` system connects the database session to routes without
any route having to manually create or close a session.

```
get_db()  (database/session.py)
    │
    └── Depends(get_db) in task_routes.py
            │
            └── db passed to services/task_services.py
                        │
                        └── db passed to repositories/task_repository.py
```

This keeps each layer unaware of how the session is created — they just
receive it as a parameter, making each layer independently testable.
