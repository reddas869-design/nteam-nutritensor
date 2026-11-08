# HTTP API

Base path: `/api/v1`. The built frontend and API should share an origin. Development-only interactive API docs are at `/api/docs`; production disables them. All routes except health/readiness/login require a valid `nteam_session` cookie. Mutations require the current `X-CSRF-Token` and an allowed browser origin when `Origin` is present.

## Session lifecycle

`POST /session` accepts `{"username":"owner","password":"..."}`. The response contains `username`, `authenticated`, `csrf_token`, `mode`, and `expires_at`; the opaque session cookie is HTTP-only and SameSite Strict. Live mode verifies one of at most three provisioned accounts; a v1 legacy owner login remains compatible until migration. Backend demo mode accepts an empty password and creates a separate demo owner.

`GET /session` refreshes the CSRF token for the current cookie. Replace any cached token after this call; other tabs using an older token may need to reconnect. `DELETE /session` invalidates the current session. A `401` means authentication is missing/expired. A `403` generally indicates an origin or CSRF mismatch.

Use a cookie-aware client. Never put the session secret, password, or API key in a URL. This small example performs a read-only catalog lookup after login:

```python
import getpass
import httpx

with httpx.Client(base_url="http://127.0.0.1:8000/api/v1/") as client:
    response = client.post("session", json={"username": input("Username: "), "password": getpass.getpass("Workspace password: ")})
    response.raise_for_status()
    csrf = response.json()["csrf_token"]
    foods = client.get("foods", params={"q": "rice", "limit": 5})
    foods.raise_for_status()
    print(foods.json())
    client.delete("session", headers={"X-CSRF-Token": csrf}).raise_for_status()
```

## Routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Process/API liveness and operating mode |
| GET | `/ready` | Catalog readiness and whether a model is loaded |
| POST, GET, DELETE | `/session` | Sign in, rotate CSRF, sign out |
| GET | `/capabilities` | Checkpoint/backend capabilities and catalog version |
| GET | `/foods?q=&category=&limit=` | Search source records; limit at most 50 |
| GET | `/foods/categories` | Catalog category names |
| GET | `/foods/{id}` | Full source record |
| POST | `/images` | Multipart `file` upload |
| GET, DELETE | `/images/{id}` | Read or remove an owned upload |
| POST | `/images/{id}/label` | Optional CPU OCR on an owned upload |
| POST | `/labels/parse` | Extract values from supplied label text |
| POST, GET | `/analyses` | Create a job or list recent jobs |
| GET | `/analyses/{id}` | Job, events, and completed result |
| POST | `/analyses/{id}/cancel` | Cancel queued or running work |
| GET | `/analyses/{id}/events` | Replayable SSE progress |
| POST, GET | `/journal` | Save a confirmed result or list entries |
| PATCH, DELETE | `/journal/{id}` | Edit metadata or delete an entry |
| GET | `/summary?start=&end=&timezone=` | Up to 91 local calendar days |
| GET, PUT | `/preferences` | Validated workspace preferences |
| POST, GET | `/recipes` | Calculate/save recipe or list recipes |
| DELETE | `/recipes/{id}` | Delete a recipe |
| POST | `/chat` | Fixed food FAQ over a required owned analysis; other questions rejected |
| GET | `/export?format=json` | Portable journal, recipes, and preferences |
| GET | `/export?format=csv` | Journal CSV with formula-prefix protection |
| DELETE | `/account` | Erase owned records/uploads and invalidate sessions |
| GET | `/metrics` | Authenticated Prometheus metrics |

`/ready` is not an inference health check. The model loads lazily; a ready catalog can coexist with an unloaded or incompatible checkpoint. Use `scripts/smoke_model.py` for an actual generation check.

## Meal analysis

```json
{
  "description": "",
  "items": [
    {
      "food_id": "your-imported-food-id",
      "grams": 150,
      "portion_source": "weighed",
      "uncertainty_percent": 2
    }
  ],
  "meal_name": "Lunch",
  "meal_type": "lunch",
  "language": "en",
  "detailed": false,
  "confirmed": true
}
```

Replace the food ID with a record returned by `/foods`. Items are optional when exact food names/aliases or an owned image ID is provided. Description prose or unrelated instructions are rejected; `150g banana, apple` is supported. Automatic image matches require exact unambiguous aliases. Confirmed requests must include selected food items. Accepted meal types are breakfast/lunch/dinner/snack; explanation languages are en/bn. There are at most 30 selected foods and 3,000 description characters.

Send an optional `Idempotency-Key` header for safe submission retries. A successful creation returns `202` with a job ID. Poll the job or stream `/events`. Events named `progress` contain workflow activity; `finished` terminates the stream. A result includes source-linked portions, totals, lower/upper ranges, coverage, flags, evidence, explanation, and runtime stats.

Initial image/description matches need human confirmation. Correct the food identity and portion amounts, submit a confirmed analysis, then save its ID using `POST /journal`. Repeated saves of one analysis return the existing journal entry. The UI exposes this sequence as Confirm & save. The confirmed request uses food IDs/grams and does not need the original image ID, because private uploads normally expire after the initial scan.

## Nutrition and labels

Nutrients use kcal, grams, and sodium milligrams. `null` means unavailable, never zero. If any selected portion lacks a nutrient, that meal's total for the nutrient is null. Coverage identifies the fraction of selected records with known values; it is not a statistical confidence probability.

Label parsing returns a basis (`per_100g`, `per_serving`, or unknown) and requires human verification. It does not automatically add unverified labels to the catalog or journal. Salt is not silently interpreted as sodium. OCR requires Tesseract plus the optional Python dependency.

## Errors and backpressure

Domain errors return a bounded message/code. Validation returns `422`; unknown owned objects return `404`; state/idempotency conflicts return `409`; request size limits return `413`; request/login limits return `429`; unavailable model/catalog/queue conditions use explicit service errors. Do not immediately retry model failures in an unbounded loop.

SSE sends heartbeat comments and supports `Last-Event-ID`. Streamed events describe stages, not individual LLM tokens. Generation rate in a completed result includes prompt processing in the measured model-call duration; it is not decode-only throughput or time-to-first-token.

## Food-only policy and three-user queue

Each account may have only one queued/running analysis. An idempotent retry can still retrieve its existing job. Three accounts share one serialized model instance. Password reset/removal invalidates old sessions. See `PATCH_V2.md` for the fixed allowed FAQ phrases and `contains_food` schema. Unsupported questions return HTTP 422 with `Something went wrong. Try again.`; image jobs with no reliable food identity fail with the same message. The default scan skips secondary LLM explanation generation; advanced `detailed=true` requests remain bounded.
