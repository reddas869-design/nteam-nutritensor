# Implementation references

These are official upstream references consulted for model capabilities, data normalization, and deployment assumptions. Links describe upstream behavior; they do not establish that the user's particular checkpoint or deployment has been tested.

| Reference | Used for |
|---|---|
| [Qwen3-4B model card](https://huggingface.co/Qwen/Qwen3-4B) | Text architecture, chat template, optional thinking |
| [Qwen3-VL-4B-Instruct model card](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct) | Separate vision checkpoint and processor |
| [Transformers Qwen3-VL documentation](https://huggingface.co/docs/transformers/model_doc/qwen3_vl) | Integrated multimodal loading and chat-template API |
| [Transformers bitsandbytes documentation](https://huggingface.co/docs/transformers/quantization/bitsandbytes) | NF4, double quantization, dtype and 8-bit configuration |
| [bitsandbytes installation](https://huggingface.co/docs/bitsandbytes/main/en/installation) | CUDA/hardware compatibility boundaries |
| [NVIDIA CUDA GPU capabilities](https://developer.nvidia.com/cuda/gpus) | RTX GPU compute architecture |
| [USDA FoodData Central API guide](https://fdc.nal.usda.gov/api-guide/) | Key-based API, public-domain data terms, per-100-g food data |
| [USDA datasets](https://fdc.nal.usda.gov/download-datasets/) | Offline source downloads |
| [USDA download field descriptions](https://fdc.nal.usda.gov/docs/Download_Field_Descriptions_Oct2020.pdf) | Food/nutrient IDs and CSV joins |
| [USDA Foundation Foods documentation](https://fdc.nal.usda.gov/Foundation_Foods_Documentation/) | Nutrient provenance and energy representation |
| [Official PyTorch images](https://hub.docker.com/r/pytorch/pytorch) | Optional container base family |
| [PyTorch previous versions](https://pytorch.org/get-started/previous-versions/) | Explicit version/CUDA combinations |
| [Docker GPU access](https://docs.docker.com/engine/containers/gpu/) | GPU runtime assumptions |
| [Compose device reservations](https://docs.docker.com/reference/compose-file/deploy/) | NVIDIA device reservation in the GPU template |
| [Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy) | Streaming reverse-proxy configuration |

The exact installed CPU/backend and frontend dependencies are recorded in the constraints file, package lock, and validation report. GPU dependencies are ranges requiring a workstation-specific compatibility check, not a claimed tested GPU lock. No pretrained model weights, USDA bulk database, or external food photography are included in the source archive. Eight selected USDA raw-fruit records and their retained source JSON are bundled; see FRUIT_CATALOG.md.
