# NTeam NutriTensor v2 — শুরু করুন

এটি আগের project-এর সম্পূর্ণ v2 এবং patch। নতুন করে `npm create vite` চালাবেন না। ZIP extract করে **যে folder-এ `package.json`, `backend/`, `frontend/`, `scripts/` আছে, সেখানেই** terminal খুলুন।

Camera page: উপরে menu, পুরো screen camera, নিচে capture/upload/switch। ছবি তোলার পরে আলাদা result page bubble animation-এ খুলবে। Manual food entry, saved meals ও settings menu-তে। Three.js শুধু About-এর optional illustration-এ আছে।

## ১. শুধু interface/demo চালান

Python 3.12 এবং Node.js 22+ ব্যবহার করুন:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -c backend/requirements-tested.txt -e './backend[test]'
npm ci
npm run build
python scripts/serve.py --demo
```

`http://localhost:8000` খুলুন। **Menu → Enter food** থেকে example food নির্বাচন করে gram লিখুন → See nutrition → Confirm & save। Browser demo-তে record এই browser-এই থাকে। এটি কোনো photo চিনতে পারে না; photo দিলে fixed retry message আসবে।

FastAPI demo পরীক্ষা করতে Menu → Settings → Sign in; username `owner`, password ও server URL খালি রাখুন। নতুন backend-demo login নতুন demo owner তৈরি করে।

## ২. আপনার downloaded model যাচাই করুন

আপনার যে Python/conda environment-এ PyTorch CUDA চলে, সেটি activate করুন। এই project-এর জন্য driver বদলানোর প্রয়োজন ধরে নেওয়া হয়নি।

```bash
python -m pip install -c backend/requirements-tested.txt -e ./backend
python scripts/doctor.py --require-cuda
python scripts/inspect_model.py /absolute/path/to/your/model
python scripts/install_inference.py --dry-run
python scripts/install_inference.py
python scripts/configure.py --model-path /absolute/path/to/your/model
```

শেষের path-গুলো আপনার আসল directory দিয়ে বদলাবেন। সেখানে `config.json` থাকতে হবে। `.env` আগে থেকেই থাকলে configure script সেটি overwrite করে না; পুরোনো project upgrade করলে নিচের patch নির্দেশনা অনুসরণ করুন।

**Official `Qwen/Qwen3-4B` text-only; কিন্তু `Qwen/Qwen3.5-4B` image + text multimodal model। `Qwen/Qwen3-VL-4B-Instruct`-ও image + text model।** Model-এর নাম আন্দাজ করে নয়, config-এর architecture দেখে capability নির্ধারণ হয়। Text-only checkpoint দিয়ে এই app-এ Enter food ব্যবহার করা যাবে; photo recognition-এর জন্য supported vision checkpoint লাগবে।

Official model cards:

- https://huggingface.co/Qwen/Qwen3.5-4B
- https://huggingface.co/Qwen/Qwen3-4B
- https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct

Configure script একটি private `.env`, password hash এবং catalog না থাকলে আটটি বাস্তব USDA raw-fruit record তৈরি করে। Apple, banana, orange, tangerine, mango, strawberry, avocado ও pineapple দিয়ে শুরু করা যাবে। Calorie/nutrients database থেকে আসে; LLM শুধু food name প্রস্তাব করে।

## ৩. সর্বোচ্চ তিনটি local account তৈরি করুন

```bash
python scripts/manage_users.py add owner --migrate-owner
python scripts/manage_users.py add user2
python scripts/manage_users.py add user3
python scripts/manage_users.py list
```

প্রতিটি command আলাদা password চাইবে—কমপক্ষে ১২ character। আগের owner's journal প্রথম account-এ থাকবে। চতুর্থ user তৈরি হবে না। একই GPU/model সবাই share করবে, কিন্তু journal/private data আলাদা। এক account-এর একটির বেশি pending scan থাকবে না।

Password reset/removal:

```bash
python scripts/manage_users.py reset-password user2
python scripts/manage_users.py remove user3
```

Password reset বা removal-এর পরে পুরোনো sessions বাতিল হয়। Removal পুরোনো meal records মুছে দেয় না। আবার একই username তৈরি করলে নতুন owner ID হবে। `data/users.json` এবং `.env` অন্যকে দেবেন না; private backup রাখুন।

## ৪. Live app চালান

```bash
npm ci
npm run build
python scripts/smoke_model.py
python scripts/serve.py
```

`http://localhost:8000` → Menu → Settings → username/password দিয়ে Sign in। URL খালি রাখুন। একই origin-এ valid session থাকলে reload-এর পরে reconnect হয়। প্রথম vision request-এ model load হওয়ায় সময় বেশি লাগতে পারে। `smoke_model.py --help`-এ actual image test-এর option দেখুন।

Camera → Capture → nutrition result। ছবির পরিমাণ মাপা যায় না: result প্রথমে **প্রতি food ১০০ g** দেখায়। নাম এবং edible weight ঠিক করুন; ওজন মেপে থাকলে checkbox দিন; Confirm & save চাপুন। ভুল food হলে Edit foods থেকে বদলান। Camera permission না দিলে upload ব্যবহার করা যায়।

ছবিতে খাবার না পাওয়া, low-confidence result, catalog match না পাওয়া বা unrelated question হলে: **Something went wrong. Try again.** App-এর বাইরে সরাসরি checkpoint-কে প্রশ্ন করলে তার সাধারণ ক্ষমতা আগের মতোই থাকবে—এই project model-কে retrain করে না।

## ৫. আরও food যোগ করুন

Bundled eight-fruit catalog offline কাজ করে। পুরোনো project-এর catalog-এ এই fruit records যোগ করতে:

```bash
python scripts/install_fruit_catalog.py --merge
```

নিজের reviewed USDA JSON থাকলে:

```bash
python scripts/import_fdc.py --json /path/to/official-foods.json --output data/foods.json --merge
```

Raw/cooked preparation এবং edible portion মিলিয়ে নিন। Automatic vision matching-এর জন্য প্রতিটি food-এর সঠিক common name `aliases`-এ রাখুন; একই alias একাধিক preparation-এ দিলে automatic match প্রত্যাখ্যান হবে। Catalog বদলানোর পরে server restart করুন। `docs/FRUIT_CATALOG.md`-এ source provenance আছে।

## ৬. পুরোনো ZIP-এ patch বসান

Server বন্ধ করুন। পুরোনো project, `.env`, `data/`-এর backup রাখুন। তারপর মূল project directory-তে:

```bash
python scripts/backup.py --output backups/before-v2.sqlite3
git apply --check /path/to/NTeam_NutriTensor_v2.patch
git apply /path/to/NTeam_NutriTensor_v2.patch
python -m pip install -c backend/requirements-tested.txt -e ./backend
npm ci
npm run build
```

Patch path বদলে আপনার download path দিন। Conflict হলে জোর করে apply করবেন না; সম্পূর্ণ v2 ZIP আলাদা folder-এ extract করে backup নেওয়া `.env`/`data/` সেখানে আনুন। Models আগের directory-তেই থাকবে। `docs/PATCH_V2.md`-এ migration-এর পুরো নিয়ম আছে।

## ৭. তিন user-এর phone access

একই workstation-এ `localhost` চলে। Phone থেকে plain LAN HTTP-তে camera permission সাধারণত চলে না। Trusted HTTPS hostname ব্যবহার করুন এবং `docs/DEPLOYMENT.md` অনুযায়ী Caddy, exact allowed origins/hosts ও secure cookie সেট করুন। Backend loopback-এ, এক worker-এ রাখুন; inference endpoint publicly খুলবেন না।

## ৮. RTX 3060 ও verification

Default: NF4, float16, SDPA, ৪০৯৬ context, ৩৮৪ output token, একবারে একটি model generation, 9 GiB allocator target। এটি 12 GB desktop 3060-এর starting configuration; কম VRAM হলে ছোট budget/model লাগবে। Actual speed/VRAM fit আপনার machine-এ মাপতে হবে। Normal scan-এ দ্বিতীয় LLM explanation call হয় না।

```bash
python -m pytest backend/tests
npm test
python scripts/benchmark.py --runs 6 --warmups 2 --tokens 128
```

`docs/VALIDATION.md`-এ automated checks এবং না-হওয়া hardware/browser checks স্পষ্ট আছে। এই environment-এ আপনার actual model, RTX, phone camera বা production TLS পরীক্ষা করা হয়নি।
