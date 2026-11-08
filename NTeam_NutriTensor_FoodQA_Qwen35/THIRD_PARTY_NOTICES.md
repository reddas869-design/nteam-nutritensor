# Third-party components

The repository contains original application code and uses upstream packages through normal dependency installation. Their licenses remain with their respective owners. `package-lock.json`, `backend/pyproject.toml`, and `backend/requirements-tested.txt` identify the dependency set; inspect installed distributions for their complete license text and transitive notices.

Major runtime components include React, Three.js, Lucide icons, Vite, FastAPI, Pydantic, Uvicorn, Pillow, HTTPX, python-dotenv, prometheus-client, and SQLite. Optional inference uses PyTorch, Hugging Face Transformers/Accelerate, bitsandbytes, and safetensors. Optional OCR uses pytesseract and a separately installed Tesseract executable. Test/build tools include TypeScript, Vitest, pytest, Prettier, CMake, and a CUDA toolkit for the optional lab.

Model weights and tokenizers are supplied by the operator. Review the exact checkpoint's license and acceptable-use terms before distribution or deployment. This project does not transfer a license for any checkpoint or include its weights.

USDA FoodData Central data is public domain/CC0 according to its API guide; attribution is requested by USDA. No complete USDA dataset is bundled. The demo nutrition fixtures are project-authored illustrative values, explicitly marked as demo rather than attributed to a USDA record.

The camera reference sketch was supplied by the user. It informed the layout but is not included in the distributed source. The food bowl scene is procedural Three.js geometry, not downloaded photography. Docker images and NVIDIA tools have their own distribution terms and are not included in the archive.

## Bundled starter fruit records

The eight raw-fruit source records in `backend/nutritensor/resources/` are USDA FoodData Central data, public domain / CC0. Attribution: U.S. Department of Agriculture, Agricultural Research Service, FoodData Central. Retrieved 2026-10-18. See `docs/FRUIT_CATALOG.md` for FDC IDs and mapping notes. This does not imply USDA endorsement.
