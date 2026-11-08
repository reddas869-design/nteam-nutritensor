# NTeam Nsight Report Doctor

এটি CUDA GPU profiler নয়। Nsight report file GUI-তে না খুললে pathname, extension, file size/readability, CSV/SQLite vs native report, উপলব্ধ Nsight executables ও CLI analyzer/import পরীক্ষা করার diagnostic utility। এটি আপনার model, `.env`, accounts বা Nsight reports পরিবর্তন করে না। `--refresh-sqlite` দিলে শুধু Nsight-এর SQLite statistics export update হতে পারে।

## শুরু

```
cd ~/Desktop/nteam/NTeam_NutriTensor_FoodOnly_Qwen35_Full_Project/NTeam_NutriTensor_FoodQA_Qwen35
python ~/Downloads/NTeam_Nsight_Report_Doctor/report_doctor.py reports/nsight/qwen_vision.nsys-rep
```

`--open` দিলে সঠিক viewer চালু করার চেষ্টা করবে।

```
python ~/Downloads/NTeam_Nsight_Report_Doctor/report_doctor.py reports/nsight/qwen_vision.nsys-rep --open
```

যদি SQLite report পুরোনো মনে হয়, `--refresh-sqlite` ব্যবহার করো। এটি original .nsys-rep পরিবর্তন করবে না।

```
python ~/Downloads/NTeam_Nsight_Report_Doctor/report_doctor.py reports/nsight/qwen_vision.nsys-rep --refresh-sqlite
```

Nsight Compute-এর `.ncu-rep` খোলা:

```
python ~/Downloads/NTeam_Nsight_Report_Doctor/report_doctor.py reports/nsight/qwen_4bit_gemm.ncu-rep --open
```

## পার্থক্য

- `nsys-ui`: `.nsys-rep` (Nsight Systems timeline)
- `ncu-ui`: `.ncu-rep` অথবা `.ncu-repz` (Nsight Compute kernel report)
- `.sqlite`: `nsys stats` export; direct timeline GUI report নয়
- `.qdstrm`: incomplete/intermediate, `nsys import` দিয়ে রূপান্তর করতে হবে

নোট: এখানে automated test suite-এ ৬০টি synthetic file/path scenario পরীক্ষা করা হয়েছে; actual RTX 3060 বা user's Nsight report binary এই environment-এ নেই। Genuine compatibility যাচাই CLI diagnostic দিয়ে user computer-এ করতে হবে।
