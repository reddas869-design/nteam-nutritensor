# NTeam NutriTensor v2: Qwen3.5-4B local run guide

The source has been patched to recognize `model_type=qwen3_5` as multimodal, to load the
full Qwen3.5 image-and-text model, to encode local images via `path`, and to request
Transformers 5.2+ instead of the older, incompatible `<5` constraint. This patch
has NOT been tested against your GPU or your checkpoint because neither is here.

## Ubuntu + existing Conda `team2`

```bash
conda activate team2
cd ~/Downloads/NTeam_NutriTensor_Qwen35_Ready
python --version
python -m pip install -c backend/requirements-tested.txt -e './backend[test]'
python scripts/doctor.py --require-cuda
python scripts/install_inference.py --dry-run
python scripts/install_inference.py
python scripts/inspect_model.py /home/aabhi/models/Qwen3.5-4B
python scripts/configure.py --model-path /home/aabhi/models/Qwen3.5-4B
python scripts/manage_users.py add owner --migrate-owner
npm ci
npm run build
python scripts/smoke_model.py
python scripts/serve.py
```

Open `http://localhost:8000`, Settings > Sign in, enter owner credentials,
then Camera > Capture or upload. For image smoke testing use
`python scripts/smoke_model.py --image /absolute/path/to/a/fruit.jpg`.

If your project already has `.env` and `data/`, **back them up and copy them**
to the patched root rather than running `configure.py` again. Never delete your
working `team2` PyTorch CUDA installation to resolve pip conflicts. Check
`python -m pip show transformers torch` and `python scripts/doctor.py`.

The package `backend/requirements-tested.txt` only pins backend/test packages;
it does not install torch or the image-language inference dependencies.

The model's visual ability does not imply accurate calorie estimation. Vision
generates candidate food names, a verified local catalog provides nutrients,
and users confirm weight; other food names require catalog import.

Run the test suite and check software build separately:

```bash
PYTHONPATH=backend python -m pytest backend/tests
npm test
npm run build
```
