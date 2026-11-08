# Running and deploying the local workspace

## Supported operating shape

Use one API process and one GPU model on a trusted workstation. The application permits at most three local accounts with separate owner-scoped data. It has no public registration, third-party security audit, distributed lock, or formal availability guarantee. Provision users with `scripts/manage_users.py`; see `PATCH_V2.md` for owner migration. The private hosted demo serves only static assets and browser-mode data; it is not a hosted GPU service.

Start with the native instructions in the README. Keep the working CUDA/PyTorch environment. Do not install another driver merely because `nvcc --version` and `torch.version.cuda` differ: they describe separate components. `scripts/doctor.py` records both when available.

## Native same-origin service

`python scripts/serve.py` serves built assets and the API from `127.0.0.1:8000`. There is exactly one worker. Files are stored under `data/`; run from the project directory. Settings are read from `.env` without overriding environment variables already supplied by the operator.

`deploy/nutritensor.service` is an editable systemd template. Before using it, create a dedicated service user, move/install the project at the chosen path, change the Python executable path, allow that user to read model weights, and give it ownership of the data directory. `ProtectHome=true` means checkpoints inside a private home directory need a deliberate path/permission adjustment. The template leaves CUDA device access enabled. No system service is installed automatically by this project.

## HTTPS and phone camera access

Localhost is accepted as a secure context by browsers. Accessing a workstation by an ordinary LAN HTTP address generally is not. To use a phone camera against your workstation, expose the app through a properly configured HTTPS hostname trusted by that phone.

`deploy/Caddyfile` is a native Caddy reverse-proxy template for port 8000. Set `NTEAM_DOMAIN` in the Caddy service environment and configure DNS/TLS for that hostname. Then set these application variables to matching exact values:

```dotenv
NTEAM_ENVIRONMENT=production
NTEAM_COOKIE_SECURE=true
NTEAM_ALLOWED_HOSTS=your.actual.hostname,localhost,127.0.0.1
NTEAM_ALLOWED_ORIGINS=https://your.actual.hostname
```

Retain loopback binding for the API. The reverse proxy handles HTTPS and streaming. The app does not trust arbitrary forwarded IP headers, so rate limits behind a single proxy can be shared by clients; this is appropriate for the intended three-user deployment. Do not configure wildcard origins/hosts or expose an unprotected inference endpoint. Keep the frontend/API on the same site because sessions use strict same-site cookies.

The example Caddy content security policy permits React inline styles and local blob camera previews; scripts remain same-origin. If you deliberately configure a separate HTTPS API origin, revise both the exact CORS settings and the CSP. Cross-site strict cookies can still prevent that setup; same-origin is the supported default.

## Optional containers

The templates have not been built or exercised against a GPU in the authoring environment. Verify them in your deployment environment before relying on them. The GPU base is an explicit official PyTorch tag and can be replaced with a driver-compatible tested image through `GPU_BASE_IMAGE`; record the image digest after verification.

Demo container, without GPU dependencies:

```bash
docker compose -f deploy/compose.demo.yaml up --build
```

GPU container:

1. Prepare `.env` and `data/foods.json` using the native setup tools.
2. Configure a working Docker GPU runtime on the host following NVIDIA's official guidance.
3. Set `NTEAM_HOST_MODEL_PATH` to your existing absolute model directory.
4. Ensure the `data` directory and files are writable by container UID/GID 10001. Use a dedicated directory; do not recursively change ownership of unrelated personal files.
5. Run `docker compose up --build` from the project root.

The model mount is read-only. The root filesystem is read-only, writable cache/temp mounts are bounded, Linux capabilities are dropped, and the published API port binds to loopback. Model weights and secrets are excluded from the Docker build context. Only one GPU is reserved. Container creation does not install host drivers.

The CPU Dockerfile also supports an operator-managed compatible inference endpoint if explicitly configured. In a container, `127.0.0.1` means that container; it does not automatically refer to the host or another service. A non-loopback endpoint needs explicit `NTEAM_ALLOW_REMOTE_INFERENCE=true` and an appropriate trusted network.

## Backup and restore

```bash
python scripts/backup.py --output backups/verified-snapshot.sqlite3
```

The tool uses SQLite's online backup API, avoiding an unsafe copy of a live WAL database. It does not include uploads, the nutrition catalog, `data/users.json`, model files, `.env`, or browser IndexedDB. Secure the snapshot and configuration separately. A database backup includes active session digests; rotate the session secret after a restore if those sessions should become invalid.

For restore, stop the application, preserve the current data directory as a rollback copy, restore the chosen SQLite snapshot to the configured path, and ensure stale `-wal`/`-shm` files from a different database are not reused. Restore matching source catalogs/uploads when needed. Check permissions, start the app, and verify journal counts and a sample nutrient result. Exercise this procedure on a disposable copy before a production restore.

## Operations and limits

`/health` proves the process answers; `/ready` proves the catalog is available. Neither proves model inference succeeds. Run the actual checkpoint smoke test and at least one confirmed meal through the UI. Watch queue depth, stage timings, error counts, model latency, and real device memory.

Application request bodies, image pixel counts, generation tokens, queue capacity, label OCR time, and session lifetime are bounded. Storage size and record retention are not subject to per-account quotas. Back up and monitor disk space for a long-running workspace. OCR is optional and CPU-based; install a suitable Tesseract executable and `backend[ocr]` before enabling it.

Before broader deployment, perform browser/mobile checks, GPU load/cancellation tests, dependency/image vulnerability scanning, backup restore validation, and a deployment-specific security review. These are remaining acceptance gates, not claimed completed work.
