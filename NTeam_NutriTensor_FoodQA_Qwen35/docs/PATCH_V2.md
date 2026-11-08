# Camera and food-only patch — v2

This patch upgrades the original NTeam NutriTensor project at commit `1b69818c214e9bc0bc30165da2e5aac651496ade`. Use the complete v2 ZIP for a fresh installation, or the accompanying `NTeam_NutriTensor_v2.patch` against an unchanged v1 checkout.

## Changes

- Full-screen camera with a menu, shutter, upload, and camera switch. Manual entry and other tools live in the menu.
- Separate result screen with short CSS bubble animations, editable foods/grams, source details, and confirm/save. Reduced motion disables the animations.
- Three local accounts maximum, separate owner-scoped data, scrypt hashes, atomic account-file writes, and immediate session revocation on password reset/removal.
- One pending analysis per account, one shared GPU runtime, and one active model call. Default scans use one vision call followed by source-based calculation, without a second explanatory generation.
- Explicit no-food/low-confidence/unknown-food rejection with `Something went wrong. Try again.` No empty successful scan and no unrestricted chat prompt.
- Eight real raw-fruit USDA records with retained source JSON. Existing catalogs are preserved; missing starter IDs can be merged explicitly.
- Checkpoint inspection before image model loading. `qwen3` is text-only; `qwen3_vl` accepts images.

No SQLite table layout changes are required. Existing journals remain compatible. The first account can inherit the v1 `local-owner` data. Existing aliases/preparations remain under operator control. Text descriptions now accept exact catalog names or aliases, optionally comma-separated and prefixed by grams, such as `150g banana, apple`. Arbitrary prose is rejected. The simple UI uses catalog selection instead of free text.

## Upgrade an existing installation

Stop your running application first and keep a rollback copy of the project, `.env`, and `data/`. Use the original project root containing `package.json` and `backend/`; do not create another Vite project inside it.

```bash
python scripts/backup.py --output backups/before-v2.sqlite3
# Adjust the patch path to where you downloaded it.
git apply --check /path/to/NTeam_NutriTensor_v2.patch
git apply /path/to/NTeam_NutriTensor_v2.patch
python -m pip install -c backend/requirements-tested.txt -e ./backend
npm ci
npm run build
```

If `git apply --check` reports conflicts, do not force the patch over your edits. Extract the complete v2 project into a new directory, then copy your existing `.env` and `data/` into it after backing them up. Existing model weights stay at their original path.

Add these settings to your existing `.env`:

```dotenv
NTEAM_FAST_SCAN=true
NTEAM_USERS_PATH=data/users.json
```

Provision accounts interactively; no passwords are placed in command arguments:

```bash
python scripts/manage_users.py add owner --migrate-owner
python scripts/manage_users.py add user2
python scripts/manage_users.py add user3
python scripts/manage_users.py list
python scripts/install_fruit_catalog.py --merge
python scripts/inspect_model.py /absolute/path/to/your/model
python scripts/serve.py
```

The first command assigns the existing owner's records to `owner`. It asks for a new account password. If accounts are already provisioned, use `list` and `reset-password`; do not add them again. A fourth account is rejected. `data/users.json` is private and must be included in your private backups. A removed/recreated username receives a new owner ID and cannot inherit the removed account's data. Account removal does not erase its stored meals.

The legacy password fallback exists only when no account file has been configured. After successful migration you may remove `NTEAM_ADMIN_PASSWORD` and `NTEAM_ADMIN_PASSWORD_HASH` from `.env`; account-file authentication does not need them. Removing an enabled account file while running fails closed. Keep it across restarts.

## Food-only boundary

The application does not fine-tune or rewrite your checkpoint. A direct call to that model outside this application can still answer general questions. Inside the application, no free-form user text reaches identification: image tasks use a fixed prompt; text entries must resolve to exact, unambiguous catalog names. The `/chat` endpoint accepts only four fixed English questions (plus the documented Bengali energy/protein variants), and requires an owned completed analysis:

- `How many calories are in this meal?`
- `How much protein is in this meal?`
- `Explain the portions`
- `Why are some values unknown?`

Other questions receive HTTP 422 with the fixed retry message. Answers to the permitted questions are computed from stored evidence. The main capture/result UI has no chat field.

For vision output, the server requires `contains_food: true`, a structured food list, model-reported confidence of at least 0.75, and exact unambiguous catalog identity. This confidence threshold is a heuristic, not calibrated accuracy. No prompt or schema can guarantee the model will never mistake an object for food. Validate with your own fruit/non-food photos before use. Uncertain, unsupported, or unmapped results fail with the retry message instead of guessed nutrient records.

Photo portions always begin at **100 g per detected food**, clearly labeled. This is a comparison basis, not an estimated plate weight. The user confirms the name and edible grams. Unknown nutrients remain unknown. The saved record is recalculated from the confirmed selections; it does not depend on retaining the original upload.

## Performance and compatibility

`NTEAM_FAST_SCAN=true` skips explanatory LLM generation on ordinary requests. An API request with `detailed=true` can still request a bounded explanation from the shared model; internal thinking additionally requires operator opt-in and model-template support. Raw reasoning is discarded. Three.js is loaded only when the optional About illustration is opened; capture and results use camera/CSS/React.

The RTX defaults target a 12 GB desktop 3060 starting configuration: NF4, float16, SDPA, 4,096 context tokens, 384 output tokens, one model call at a time, and a 9 GiB allocator target. An RTX 3060 with less VRAM needs smaller settings/model and measurement; the target is not a VRAM-fit guarantee. No measured GPU speedup is claimed.

See `VALIDATION.md` for checks performed and remaining GPU/browser acceptance work.
