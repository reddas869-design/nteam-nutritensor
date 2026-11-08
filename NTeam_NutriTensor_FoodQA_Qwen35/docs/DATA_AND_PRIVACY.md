# Nutrition data, uncertainty, and privacy

## Source contract

Each `FoodRecord` has a stable ID, name, aliases, preparation/category metadata, optional serving weights, nullable nutrients, and a source object. The source records the provider, original record ID/title, URL, retrieval date, license, basis, and whether it is illustrative demo data.

Imported USDA nutrients use the published per-100-g `foodNutrients` amounts. The importer does not substitute serving-level label numbers. Energy prefers nutrient 2048, then 2047, then 1008; those fields are alternatives, not additive values. Protein 1003, fat 1004, carbohydrate 1005, fiber 1079, sugars 2000, and sodium 1093 are mapped with explicit units. Unsupported/missing values remain unknown. Branded and survey foods can have different completeness and measurement provenance.

The shipped 18-record catalog contains project-authored illustrative values only. It is labeled in data and UI. Live mode rejects demo catalogs unless the operator explicitly enables a testing override. There is no bundled comprehensive food database and no hidden network retrieval during inference.

## Calculations

For each selected food:

`portion nutrient = source nutrient per 100 g × selected grams ÷ 100`

The lower/upper ranges multiply portion grams by `1 ± uncertainty_percent / 100`. They describe the selected portion uncertainty, not clinical confidence intervals or an error bound on the source itself. Image-estimated portions have a minimum 25% uncertainty floor. This does not imply that a photograph can estimate weight within 25%.

Unknown nutrients propagate to meal totals. Empty days in Insights are missing observations, not zero intake. Daily summaries use the chosen IANA timezone, including daylight-saving boundaries. The dashboard covers logged meals only. Macro share visualization uses 4/4/9 energy factors for its displayed relative composition and does not overwrite source energy.

Recipe totals sum the ingredients. Per-100-g values divide by the operator's measured cooked weight. Per-serving values divide by the entered serving count. Nutrient changes from cooking, absorption, evaporation, discarded liquid, and oil retention are not independently modeled. Review ingredients and edible portions before using the result.

The project is for general food information and journaling. It does not establish allergy safety from photographs or ingredient absence, diagnose conditions, or prescribe medication/diet treatment. There are no default weight-loss calorie targets. Optional target fields are explicitly entered by the user.

## Model output boundaries

The LLM can misidentify foods, return malformed JSON, or produce incorrect prose. Structured outputs are parsed with bounded JSON validation; generated code and tool instructions are never executed. Images, text, and source names are treated as untrusted inputs. Prompt instructions help constrain explanations but do not mathematically guarantee truthful text. Calculated numeric tables are stored separately from prose.

Food candidate confidence is a model/search suggestion, not a calibrated medical confidence score. Human confirmation is required before automatically proposed portions are journaled. The app cannot infer hidden ingredients, oil, salt, exact weight, or allergens reliably from a single photograph.

## What is stored

| Data | Browser demo | Local backend |
|---|---|---|
| Journal and recipe snapshots | IndexedDB | SQLite |
| Preferences | IndexedDB | SQLite |
| Raw photo preview | Temporary object URL | Browser preview plus sanitized server upload |
| Uploaded photo content | Temporary adapter memory | Private local upload directory |
| Text input and analysis result | Browser demo job records | Jobs and journal tables |
| Password | Not used | Scrypt hash in private configuration |
| Session authentication | Not used | HTTP-only cookie; token digest in SQLite |
| Model weights | Never loaded | Existing operator-selected directory |
| Chat questions/answers | Component memory | Process request only; no persistent chat transcript |

The browser demo and local workspace are separate stores; switching modes does not migrate data. Exports contain journal/recipe/preference records, not model weights or live sessions. Model candidate analyses remain in job storage until account erasure; export is not a full database backup.

## Retention and deletion

Backend photos are normalized to RGB JPEG, resized to a bounded edge, and stripped of EXIF before storage. Default behavior removes them when an analysis finishes. Unprocessed and explicitly retained photos expire after the configured retention window (default 24 hours), with hourly cleanup and startup maintenance. Image previews can remain in the browser while the current screen is open.

Account erasure is blocked while the owner has pending analysis work. Cancel and wait, then erase. It removes owned database records and uploads and invalidates sessions. It cannot remove files you previously exported, manual backups, copied photographs, browser screenshots, or records kept by a separately configured inference endpoint. SQLite/WAL deletion is logical deletion, not certified forensic secure erasure; use disk encryption when appropriate to your deployment.

Logs deliberately omit prompts, images, food names, session tokens, and API keys. Infrastructure access logs may still record IP addresses/paths depending on deployment. Metrics use bounded route/stage/outcome labels. The default app does not send analytics to a third-party service.
