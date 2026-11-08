# NTeam NutriTensor: Qwen3.5-4B Food-Only Questions

This complete source project extends the prior All-Food release and **preserves the existing React design**. Its chat panel now uses the local Qwen3.5-4B, not a hardcoded list of two nutrition questions.

## What the conversation assistant does

1. User signs in, takes/uploads a food photo, and waits for a successful **complete** analysis.
2. Under the analysis result, open **Ask Qwen about this food**.
3. Ask about the foods and fruits in the identified meal. Examples: "How many calories are in this mango?", "What ingredients might this biryani contain?", "এই আপেলে কী ধরনের পুষ্টি থাকতে পারে?", or "How reliable is the estimated weight?".
4. The local Qwen3.5-4B first classifies whether the request is relevant to *this* meal. Only a positive Boolean classification permits a second model call to answer using that meal's stored portion/nutrient data.
5. Unrelated requests, requests without a saved analysis, or unclear topic classifications receive exactly: `cann't help with`.

This is a **best-effort** topic restriction combining deterministic rejection rules and a model classifier. No prompt-based classifier can mathematically guarantee perfect refusal of all adversarial prompts. Inputs are treated as untrusted data. The existing authenticated owner check prevents questioning somebody else's analysis record.

## Install / activate (Ubuntu RTX 3060)

Unzip as a **new sibling project**. Keep your previous project for backup. The archive deliberately excludes `.env`, `data/users.json`, existing meal data, pictures, and GPU model checkpoints.

```bash
conda activate nteam2
cd ~/Desktop/nteam/NTeam_NutriTensor_FoodQA_Qwen35
python -m pip install --no-deps -e ./backend
npm ci
npm run build
python -m pytest backend/tests -q
npm test
```

The updated frontend requires `npm run build` to replace the precompiled frontend. Never run the old project's server simultaneously on port 8000.

To configure live inference, **safely merge** your existing `.env` settings, don't overwrite them or post their contents. These values must be present:

```dotenv
NTEAM_MODE=live
NTEAM_MODEL_BACKEND=transformers
NTEAM_MODEL_PATH=/home/aabhi/models/Qwen3.5-4B
NTEAM_QUANTIZATION=nf4
NTEAM_LOCAL_FILES_ONLY=true
```

Live mode also needs either a valid user registry at `NTEAM_USERS_PATH=data/users.json` or valid legacy administrator credentials; account migration can be performed with `python scripts/manage_users.py add owner --migrate-owner`. Use a strong password, not a placeholder. For the HTTPS Tailscale URL use appropriate allowed hosts and secure cookies.

```bash
python scripts/smoke_model.py --image /home/aabhi/Downloads/apple.jpg
PYTHONUNBUFFERED=1 python scripts/serve.py --access-log
```

Open `https://aabhi-pro.tail8b7abc.ts.net/` from a device connected to the same tailnet, sign in, scan food, and ask a related and an unrelated question.

## Design / cautions

- Food recognition, approximate grams, and nutrition estimates in live photo mode are Qwen-generated. **No fixed food nutrition library** limits photo recognition.
- The photo result does **not** permit editing grams or quantities. A single photo cannot actually measure edible weight.
- Food-only conversation stays tied to a completed analysis; there is no general-purpose uncensored chatbot or internet search.
- Unknown ingredients, allergens, and nutrients must not be presented as facts. Estimates are **not** suitable for clinical nutritional decisions.
- Scope verification and answer generation each use the same model gateway and can add latency on the RTX 3060. One server process avoids multiple redundant GPU loads.
- If the model's JSON scope verdict is missing/malformed/false, chat refuses rather than answering outside its allowed topic.
- Tests in this release use mocked model outputs. Live GPU behavior and accuracy require confirmation on the user's machine.

## Tests

```bash
python -m pytest backend/tests -q
npm run build
npm test
```

The Python test suite covers food question acceptance, unrelated question refusal, malformed scope JSON rejection, cross-user analysis isolation, previous all-food pipeline tests and account/security checks.
