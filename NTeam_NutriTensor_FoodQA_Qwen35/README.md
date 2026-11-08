> **New:** Local Qwen3.5-4B meal-scoped food-only Q&A. See [FOOD_ONLY_QWEN_QA_GUIDE.md](FOOD_ONLY_QWEN_QA_GUIDE.md).

# NTeam NutriTensor v2

**Upgrading an existing copy?** Read [docs/PATCH_V2.md](docs/PATCH_V2.md). Use the existing project root; do not scaffold a second Vite project.

A local nutrition workspace with a camera-first React interface, an optional Three.js food illustration, source-based nutrient arithmetic, and a bounded multi-agent pipeline sharing one Qwen model.

The interface follows the supplied sketch: an immersive camera, menu at the upper left, and a capture button at the bottom. The menu opens the journal, insights, recipes, food catalog, and settings. There are no cloud LLM keys or paid API requirements. বাংলা setup instructions are in [START_HERE_BN.md](START_HERE_BN.md).

## What is implemented

- Full-screen camera capture, image upload, camera switching, separate animated results, and manual food entry.
- Four primary menu choices (Camera, Enter food, Saved meals, Settings); extra tools are collapsed under More tools.
- An optional About illustration using Three.js with bounded pixel ratio and resource disposal; no Three.js in the capture/result flow.
- Five specialist roles: identification, catalog retrieval, calculation, review, and explanation. Roles share one inference gateway; five model copies are never loaded.
- Local Transformers support with NF4, double quantization, SDPA, KV caching, bounded context, cancellation, and one active model call.
- Optional connection to an already-running local OpenAI-compatible endpoint, including a separately configured vision capability.
- Source records, nullable nutrients, portion uncertainty ranges, user confirmation, and transparent assumptions.
- Persistent meal journal, timezone-aware summaries, recipe yield calculation, CSV/JSON export, and account-data deletion.
- Optional Tesseract label OCR, retained-photo expiry, EXIF stripping, image-size limits, and owner-scoped uploads.
- Up to three provisioned local users with private records and revocable sessions. Cookie sessions, scrypt passwords, CSRF checks, rate limits, SQLite WAL storage, SSE replay, health/readiness endpoints, and bounded metrics.
- Backend/frontend tests, CI, deployment templates, model diagnostics, benchmark reports, backup tools, and a separate C++/CUDA profiling exercise.

This is a complete runnable source project and an interactive demo. It has not been certified for production, clinical use, or your exact GPU/checkpoint. See [docs/VALIDATION.md](docs/VALIDATION.md) for the checks actually performed and the remaining hardware/browser checks.

## Choose how to run it

| Mode | What runs | Nutrition data | Model |
|---|---|---|---|
| Hosted or local browser demo | React + Three.js; IndexedDB | 18 clearly labeled illustrative fixtures | None; deterministic explanations |
| Backend demo | FastAPI + SQLite + built frontend | Same illustrative fixtures | None |
| Live local workspace | FastAPI + SQLite + built frontend + inference | Your imported verified catalog | Your configured checkpoint or local endpoint |

The hosted demo cannot access your workstation's GPU. Run the full project on your RTX machine for inference. The demo never claims to recognize an uploaded food photograph and never displays fabricated GPU throughput.

## Quick start: interactive demo

Requirements: Node.js 22 or newer, Python 3.11+; Python 3.12 is the validated backend environment. No GPU is needed for this mode.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -c backend/requirements-tested.txt -e './backend[test]'
npm ci
npm run build
python scripts/serve.py --demo
```

Open `http://localhost:8000`. The browser demo is ready immediately. To exercise the FastAPI demo too, open Menu → Settings → Sign in with username `owner` and an empty URL and password. Backend demo sessions are separate from the persistent browser demo; each new backend demo login gets its own owner.

For frontend/backend development, use `python scripts/dev.py --demo`. This starts Vite on port 4173 and FastAPI on port 8000. The Vite development proxy sends `/api` to the local backend.

## Run your existing Qwen checkpoint

Activate your existing working CUDA Python environment. Keep its PyTorch and drivers. Install the application and check CUDA before adding inference dependencies:

```bash
python -m pip install -c backend/requirements-tested.txt -e ./backend
python scripts/doctor.py --require-cuda
python scripts/install_inference.py --dry-run
python scripts/install_inference.py
python scripts/configure.py --model-path /absolute/path/to/your/qwen-directory
```

The configuration script reads `config.json`, asks for a local password, stores a scrypt hash, and creates a private `.env`. It does not download model weights. The inference installer constrains the already-installed torch/torchvision/torchaudio versions; a dependency conflict stops the install instead of silently choosing another torch version.

The setup installs eight real USDA raw-fruit records when no catalog exists. Provision up to three users, then build and start:

```bash
python scripts/manage_users.py add owner --migrate-owner
python scripts/manage_users.py add user2
python scripts/manage_users.py add user3
```

Then:

```bash
npm ci
npm run build
python scripts/smoke_model.py
python scripts/serve.py
```

Open `http://localhost:8000`, choose Settings → Sign in, leave the URL empty, and enter your username and password. The local workspace stores records in `data/nutritensor.sqlite3`. A valid same-origin live session is restored after reload. Each account has its own persistent records.

### Identify the model correctly

“Qwen 4B” alone does not establish whether the model accepts images. `Qwen3-4B` is text-only, but **`Qwen3.5-4B` is a multimodal image-and-text checkpoint**. The `qwen3_5` architecture is recognized and loaded with the official `AutoModelForMultimodalLM` class using Transformers 5.2+. `Qwen3-VL-4B-Instruct` is another supported vision model. The application checks the checkpoint configuration and rejects image inference for a text-only model. Manual food entry and LLM explanations still work with a text model.

Transformers-format model directories are supported directly. If your existing model is GGUF, start your existing compatible local server yourself and configure its `/v1` endpoint:

```bash
python scripts/configure.py --endpoint http://127.0.0.1:8080/v1 --endpoint-model your-model-name
```

Use `--vision` only if that server and checkpoint really support the image chat format. External inference is disabled unless explicitly enabled in `.env`; localhost is the default. There is no Ollama dependency.

## Import verified nutrition data

Live mode has no fabricated fallback catalog. The setup supplies eight sourced raw-fruit records (see [docs/FRUIT_CATALOG.md](docs/FRUIT_CATALOG.md)); run `python scripts/install_fruit_catalog.py --merge` to add them to an existing catalog. To support more foods, import records from USDA FoodData Central or a reviewed compatible catalog. The importer preserves source IDs, URLs, retrieval dates, units, preparation information, and unknown values.

Using a downloaded official JSON export:

```bash
python scripts/import_fdc.py --json /path/to/selected-official-foods.json --output data/foods.json
```

Using a bounded selection from an extracted official CSV download:

```bash
python scripts/import_fdc.py --csv-dir /path/to/extracted-fdc --contains rice --limit 40 --output data/foods.json
```

Or set a free FoodData Central key as `NTEAM_FDC_API_KEY` and fetch reviewed IDs with `--ids`. Run `python scripts/import_fdc.py --help` for exact options. API import makes an explicit network request; inference and lookup can remain offline afterward. API keys are never included in source URLs or logs.

Review raw versus cooked preparation, edible portions, units, brands, and ingredient composition. An imported food is not automatically a match for a home-cooked mixed dish. Use Recipes for ingredients and measured cooked yield. The database supplies nutrition numbers; the vision model supplies candidate names. Image recognition always starts with 100 g per food, never an inferred exact weight. Exact unambiguous aliases are required for automatic matching. Unrelated questions, non-food outputs and unreliable matches receive `Something went wrong. Try again.`; this application policy does not modify the checkpoint outside the app. Model prose can still be wrong: the source table and confirmed portion arithmetic remain the quantitative record.

## RTX 3060 starting configuration

| Setting | Default | Reason |
|---|---|---|
| Quantization | NF4, double quantization | Reduce weight memory |
| Compute dtype | float16 | Conservative CUDA configuration |
| Attention | SDPA | Avoid a mandatory FlashAttention build |
| Context including output | 4,096 tokens | Bound KV-cache and input memory |
| Maximum output | 384 tokens | Bound latency and retained output |
| PyTorch memory fraction | Target 9 GiB | Leave some device headroom |
| Active model generations | 1 | Prevent duplicate model calls from exhausting VRAM |
| Waiting analysis queue | 4 | Bound queued work |
| Internal thinking | Disabled by default | Keep the initial workload small |

These are starting settings, not measured optimums. Quantization can reduce memory without improving latency. Vision encoders, image tokens, driver/library versions, other GPU applications, and checkpoint details affect fit. The allocator fraction is not a guarantee of total process VRAM use.

Normal scans use one vision call and a deterministic summary (`NTEAM_FAST_SCAN=true`). Source details remain available on the result screen. For advanced API clients, `detailed=true` requests a bounded LLM explanation; `NTEAM_THINKING=true` additionally permits internal thinking for a supporting checkpoint/template. Internal reasoning is discarded; the UI shows completed agent actions and final summaries. If the model exhausts its reasoning budget without a final answer, the app presents a calculation summary with a visible flag.

## Verify and profile

```bash
npm test
npm run build
python -m pytest backend/tests
python scripts/count_lines.py
python scripts/benchmark.py --runs 6 --warmups 2 --tokens 128
```

The benchmark requires live inference and writes actual observations under `reports/`. It separates cold load from warm requests. See [docs/BENCHMARKING.md](docs/BENCHMARKING.md) for Nsight and C++/CUDA commands. No throughput, TTFT, VRAM-fit, or photo-recognition accuracy result is bundled as if measured on your card.

## Project map

| Directory | Responsibility |
|---|---|
| `frontend/src/pages` | Capture, journal, insights, recipes, catalog, settings, about |
| `frontend/src/components` | Camera controls, source review, Three.js scene, dialogs |
| `frontend/src/lib` | API adapters, demo persistence, arithmetic, SSE, exports |
| `backend/nutritensor/api` | Authenticated HTTP contract and request boundaries |
| `backend/nutritensor/agents` | Bounded workflow and specialist roles |
| `backend/nutritensor/inference` | Shared model, provider adapters, output parsing |
| `backend/nutritensor/nutrition` | Catalog, source normalization, deterministic calculations |
| `backend/nutritensor/storage` | SQLite transactions and durable job events |
| `scripts` | Setup, imports, diagnostics, serving, backups, profiling, packaging |
| `cuda` | Optional isolated normalization benchmark and CPU reference |
| `deploy` | Native service, Docker, and HTTPS reverse-proxy templates |
| `docs` | Architecture, API, validation, deployment, and data contracts |

## Data and deployment boundaries

The live backend supports at most three local accounts on one workstation, each with separate data. There is no public signup. Provision accounts with `scripts/manage_users.py`. Run exactly one API process per model/device. Photos are stripped of EXIF and normally deleted after analysis; unprocessed or retained uploads expire under the configured retention window. Food entries, model results, and journal records remain in SQLite until deleted. Backups and exports contain personal data and are not erased by the app's delete action.

Camera access requires localhost or HTTPS and browser permission. A hosted preview embedded in another page may restrict camera/fullscreen access. The local frontend and API should share one origin; strict cookies intentionally make arbitrary cross-site connections unsuitable.

For HTTPS, backups, and deployment requirements, read [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). For the limits of general food logging and label extraction, read [docs/DATA_AND_PRIVACY.md](docs/DATA_AND_PRIVACY.md). The app does not infer allergy safety or provide disease treatment, insulin dosing, or prescriptive diet targets.

## Source audit and licensing

`scripts/count_lines.py` audits authored Python, TypeScript, TSX, CSS, C++, CUDA, and shell source, including tests and tooling. It reports both physical and nonempty lines, with a default gate of 10,000 nonempty source lines. Dependencies, lockfiles, build output, JSON fixtures, documentation, and model weights are excluded. Comments and braces are counted transparently. The report is in `docs/source-count.json`.

Project code uses the [MIT license](LICENSE). Model weights are not bundled; their license belongs to the checkpoint owner. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [docs/SOURCES.md](docs/SOURCES.md).

To regenerate the source download included with the hosted release after a local build:

```bash
python scripts/package_source.py --output dist/downloads/nteam-nutritensor.zip
```

The portable ZIP includes a SHA-256 manifest and excludes the original hosting identity, model weights, dependencies, secrets, and user data.
