# NTeam NutriTensor: Qwen3.5-4B Image Analysis Patch

এই patch আগের project-এর source বদলায়, কিন্তু `.env`, `data/`, model weights, user accounts বা Tailscale configuration বদলায় না।

## কী পরিবর্তন হলো

- ছবি upload-এ HTTP/authentication/validation সমস্যা হলে frontend আসল নিরাপদ error message দেখায়। প্রকৃত non-food বা unsupported input হলে আগের generic retry message বজায় থাকে।
- Qwen-এর identification prompt এখন concise JSON-only output স্পষ্টভাবে চায়। `contains_food=true` এবং একটি বৈধ খাবারের নাম দিলে confidence অনুপস্থিত থাকলেও 0.75 সতর্ক threshold ব্যবহার করে; কিন্তু explicit low-confidence প্রত্যাখ্যান করে।
- ছবি থেকে `red apple`, `fresh banana`, `sliced apple` এর মতো appearance adjective বাদ দিয়ে শুধু যাচাইকৃত, unique **exact** catalog record match করে। `apple pie`, `rice cake`, `fried rice`-এর মতো ভিন্ন খাবার ভুলভাবে মেলায় না।
- ছবির অন্য একটি predicted item catalog-এ না থাকলে বাকি verified item-এর calculation বন্ধ করে না। অনিশ্চিত item-এর nutrition বানিয়ে দেয় না।
- Qwen3.5 non-thinking mode নির্বাচন করার সংকেত আরও নির্ভরযোগ্য। vision encoding-এ pixel tensors অনুপস্থিত থাকলে স্পষ্ট error দেয়; context budget অতিক্রম করলে token count দেখায়।
- Server failure event-এ exception type (`error_code`) যোগ হয়েছে। `NTEAM_DEBUG_TRACEBACK=1` থাকলে local admin terminal-এ traceback আসে; browser-এ নয়।
- `scripts/diagnose_last_scan.py` এবং `scripts/diagnose_photo.py` যোগ হয়েছে।

## Apply targeted patch (existing project)

```
cd ~/Desktop/nteam/NTeam_NutriTensor_Qwen35_Ready
unzip -o ~/Downloads/NTeam_ImageFix_Patch.zip -d /tmp/nteam-imagefix
python /tmp/nteam-imagefix/apply_fix.py .
python -m pytest backend/tests
npm run build
```

`unzip`-এ zip path Downloads-এর সঙ্গে মিলিয়ে দেবে। `apply_fix.py` changed source files-এর timestamped backup রাখে।

## Run and inspect most recent image failures

```
conda activate nteam2
cd ~/Desktop/nteam/NTeam_NutriTensor_Qwen35_Ready
python scripts/diagnose_last_scan.py
```

Last scan-এ `error_code` থাকলে কোন component ব্যর্থ হয়েছে বোঝা যাবে। পুরনো scan-এ code না-ও থাকতে পারে।

**Stop running server** with Ctrl+C, then run local inference diagnosis:

```
python scripts/diagnose_photo.py /home/aabhi/Downloads/apple.jpg
```

`apple.jpg` নিজের valid JPEG/PNG ছবির path দিয়ে বদলাও। server একসঙ্গে চালু রেখো না, কারণ দুটি model load GPU VRAM শেষ করতে পারে। এটি Qwen-এর raw output, structured JSON parse এবং catalog match আলাদা করে পরীক্ষা করে।

## Smaller mobile photos and context budget

যদি terminal দেখায় `Image/prompt requires ... tokens`, শুরুতে একটি কম-resolution image চেষ্টা করো অথবা `.env`-এ `NTEAM_IMAGE_MAX_EDGE=768` সেট করো; আবার server restart করো। Context বাড়ালে VRAM-এর চাহিদাও বাড়তে পারে।

CUDA out-of-memory হলে `nvidia-smi` দিয়ে free GPU VRAM দেখো এবং অন্য GPU process বন্ধ করো। `NTEAM_QUANTIZATION=nf4` রাখো, যদি তোমার installed bitsandbytes-এর সঙ্গে compatible হয়।

## Restart production app

```
NTEAM_DEBUG_TRACEBACK=1 python scripts/serve.py
```

অন্য terminal-এ `tailscale serve status` দেখো। ফোনে আগের HTTPS URL-এ browser refresh করো। এটি private Tailscale HTTPS connection; actual model Ubuntu machine-এ চলে।

### Validation সীমা

এখানে 118টি backend Python test পাস করেছে। বাস্তব Qwen model weights/GPU নেই, তাই তোমার RTX 3060-তে live fruit recognition বা mobile image upload end-to-end যাচাই করা যায়নি। Frontend source change review হয়েছে, কিন্তু এই execution environment-এ `npm ci --offline`-এ registry package cache না থাকায় `npm run build` হয়নি; নিজের PC-তে ওপরের build command অবশ্যই চালাবে।
