# Validation record

v2 patch validation: 2026-10-19. Unchanged C++/deployment syntax checks were carried forward from the 2026-10-18 v1 run. Results below describe the available Linux build environment, not the user's RTX workstation. Machine-readable results and the source audit are in `verification.json` and `source-count.json`.

## Completed checks

| Check | Result | Scope |
|---|---|---|
| Backend tests | 110 passed | FastAPI integration, source arithmetic, authentication, persistence, image boundaries, queue/cancellation behavior |
| Frontend tests | 37 passed | Nutrition arithmetic, missing values, timezone boundaries, SSE chunking/Unicode, CSV injection protection |
| TypeScript strict compilation | Passed | All React and TypeScript source contracts |
| Vite production build | Passed | Production assets and lazy route/Three.js chunks |
| Python bytecode compilation | Passed | Application modules and scripts |
| C++ CPU reference | Passed | Compiled with g++ 13.3, C++17, `-Wall -Wextra -Werror`; exercised layout/numerical/input checks |
| Deployment YAML | Parsed | Compose and CI syntax; not container execution |
| Shell profiling script | Syntax passed | `bash -n`; no profiling tools executed |
| Source-line audit | Passed 10,000 nonempty-line gate | Authored source, styles, tests, and tools; no dependencies/builds/data/docs |
| Source ZIP | Integrity and per-file manifest checks | No secrets, user records, dependencies, or model weights included |

Backend test cases include a known 393-kcal illustrative two-food calculation, incomplete-nutrient propagation, recipe cooked-yield scaling, USDA energy precedence, unit conversion, minimum uncertainty on image estimates, EXIF stripping, invalid/animated/oversized images, live password/session cookies, CSRF/origin rejection, owner isolation, idempotency conflicts, restart recovery, missing queued uploads, SSE replay, journal confirmation, CSV export, and erasure.

New v2 tests cover three-account limits, private preferences, password reset/removal and session revocation, account-file corruption, strict food input, explicit non-food outputs, confidence rejection, unknown catalog identity, image rejection before text-model load, one model call for an ordinary scan, one pending job per owner, owned food FAQ answers, aborted/timed-out result waiting, and the eight real USDA fruit records. Vision tests use a controlled provider and do not establish actual model accuracy.

The concurrency regression uses a blocking provider to verify that cancelling a caller does not allow a second generation to overlap the still-running first one. It validates scheduling behavior without claiming actual CUDA cancellation was tested. Thinking-output tests ensure tokenizer special-token filtering cannot accidentally expose an unfinished internal reasoning segment.

The latest environment used Python 3.12.14 and Node.js 24.19.0. Exact installed frontend versions are recorded in `package-lock.json`; the CPU backend constraints are in `backend/requirements-tested.txt`. Node 22/Python 3.12 CI configuration is included but has not run on GitHub as part of this delivery.

## Observed non-failing warnings

Starlette's installed TestClient emits a deprecation warning for HTTPX compatibility. All HTTP integration tests pass; the warning is retained rather than suppressed. The Vite build reports the lazy Three.js vendor bundle just above its default 500-kB minified threshold (about 128 kB gzip). It loads only after the About illustration is explicitly opened; no bundle-size threshold was raised to hide the warning.

## Not executed here

- Browser visual, responsive, keyboard/screen-reader, real IndexedDB, webcam, and mobile permission tests. The managed build environment did not expose the supported browser QA capability, so no substitute browser automation or preview server was started.
- Model download, actual checkpoint load, NF4 quantization, vision recognition, thinking quality, GPU memory fit, CUDA performance, or Nsight traces. This environment exposes neither NVIDIA hardware nor nvcc; the user's model files are not present.
- CUDA compilation/execution. Only the independent C++ CPU reference was compiled and run. CMake is not installed here; the CMake recipe itself remains a workstation/CI acceptance check.
- Docker image builds, GPU container startup, systemd installation, Caddy/TLS configuration, remote compatible-server inference, Tesseract execution, or the operator-key USDA import CLI. The bounded one-time public USDA API retrieval for the bundled eight-fruit catalog was performed.
- Long-duration soak/load testing, external penetration testing, medical validation, and backup restoration on the deployment machine.

## Workstation acceptance sequence

1. Run `scripts/doctor.py --require-cuda` in the existing CUDA environment.
2. Run the actual checkpoint smoke test; verify text-only and image-capable behavior match the chosen model.
3. Import/review source data and manually check a confirmed meal against its source arithmetic.
4. Exercise capture permission, upload, food correction, save/reload, journal edit/delete, recipe calculation, export, and account deletion in the real browser, using all three accounts.
5. Check mobile camera switching, secure-context access, narrow layouts, keyboard dialogs, reduced motion and WebGL fallback.
6. Run repeated warm benchmarks with no competing model process and record actual VRAM and completion lengths.
7. Test cancellation, queue saturation, failed model loading, restart recovery, and disk/backup operations in that environment.
8. Complete the HTTPS/deployment-specific review before broader access.

The project provides runnable features and production-oriented controls. It is not labeled “production certified” or “fully optimized” without these deployment-specific results.

The source audit excludes the bundled nutrition JSON from the 10,000-line requirement. The patch is checked against the exact v1 source and compared byte-for-byte against the current source distribution after application. `verification.json` records the final counts and artifact checks.
