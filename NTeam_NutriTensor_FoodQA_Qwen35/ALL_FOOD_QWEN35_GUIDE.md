# NTeam NutriTensor: Qwen3.5-4B all-food edition

## What changed

The existing React camera and animated nutrition bubbles are retained. The live camera pipeline accepts diverse recognizable foods, not a fixed list of eight fruits. Food names, visually estimated edible mass, observed quantity, and approximate per-100-g nutrient values come from **the local Qwen3.5-4B model**. No hand-curated food composition catalog or outside nutrition API is used for the live camera flow. Demo and legacy catalog utilities are included solely for backward compatibility with the other pages.

The photo result is **read-only**. There is no grams editor, slider, food addition, or "I weighed these" toggle. "Save AI estimate" saves a completed camera scan directly. Saved records preserve explicit AI attribution and uncertainty flags.

## Important limitations

- Qwen-generated calories/macros are guesses, **not verified nutrition reference data**. Do not rely on them for medical or allergy decisions.
- One photo **cannot measure grams or unseen ingredients**. Where the model cannot estimate mass, the server computes a *100 g reference*, conspicuously labeled as a reference and NOT as an inferred weight. The displayed uncertainty range covers portion estimates only and does not quantify AI nutrient error.
- The model can misidentify a dish or provide invalid JSON. The backend retries malformed food-observation JSON once, validates the schema and numeric ranges, and returns a retry error rather than inventing a match. Non-food photos remain errors.
- Numeric nutrients come from an additional local Qwen text inference call per group of up to 2 foods. This uses more inference than the previous fruit-only version. The first scan loads model weights into GPU memory.
- Real RTX 3060 latency, accuracy and VRAM usage must be validated on the target machine; tests here used simulated providers because GPU weights are not bundled.

## Install over the existing project (safest)

1. Stop the old server with Ctrl+C.
2. Back up your existing project directory, or keep the original directory unchanged.
3. Extract this ZIP to a **new** directory under `~/Desktop/nteam/`.
4. Copy the **existing private** `.env` and `data/` directory from the original project into the new directory. Do not upload these to public GitHub.
5. Ensure `NTEAM_MODE=live`, `NTEAM_MODEL_BACKEND=transformers`, and `NTEAM_MODEL_PATH=/home/aabhi/models/Qwen3.5-4B` in `.env` (adjust the path if yours differs). No `data/foods.json` is required for live camera scans.
6. Use the *existing* conda environment with CUDA-capable PyTorch/Transformers already installed:

```bash
conda activate nteam2
cd ~/Desktop/nteam/NTeam_NutriTensor_AllFood_Qwen35
python -m pip install --no-deps -e ./backend
python -m pytest backend/tests -q
npm ci
npm run build
python scripts/serve.py --access-log
```

Open `http://127.0.0.1:8000`, or with your existing Tailscale Serve proxy, `https://aabhi-pro.tail8b7abc.ts.net/` while connected to the tailnet. You must sign in as a valid local account. Restart Tailscale Serve only if its proxy mapping to `127.0.0.1:8000` is missing.

The `dist/` output is already included, so if you cannot run npm immediately, the Python server can serve the prebuilt React frontend.

## Diagnostics

```bash
python scripts/diagnose_photo.py /home/aabhi/Downloads/apple.jpg
python scripts/diagnose_last_scan.py
curl -i http://127.0.0.1:8000/api/v1/ready
```

Stop the web server before calling `diagnose_photo.py` on the same RTX 3060 to avoid a second model allocation. The raw photo diagnostic exercises the older schema/catalog path and is not an end-to-end test of the all-food API; the FastAPI integration test `backend/tests/test_model_only.py` checks the new all-food path using a deterministic stub.

## Validation on packaging host

- Python test suite: `PYTHONPATH=.:backend pytest -q backend/tests`
- React TypeScript + Vite production build: `npm run build`
- Frontend Vitest: `npm test`
- No model checkpoints, user files, passwords, or uploaded pictures are in this archive.
