# 🏊 Safe to Swim

**Predicting bacteria risk at King County lakes on the days between official tests.**

Safe to Swim is a web app that estimates swim risk at 30 King County lakes for any date — including tomorrow and the rest of the week. It combines each lake's most recent official bacteria measurement with live weather data, using a machine learning model trained on seven years of King County monitoring records.

---

## The problem

Swimming in lakes makes people sick more often than most people realize. The CDC estimates roughly 5.6 million illnesses a year in the U.S. are linked to recreational water, and its outbreak surveillance found that most reported lake outbreaks happen at **small inland lakes and ponds** — not the large coastal beaches that get national monitoring. Small inland lakes are exactly what King County has.

You might think you could just test the water yourself. But E. coli has to be incubated: the fastest consumer test kits take 24 to 72 hours, and the EPA lab standard is 24 hours. **A test kit tells you Monday whether Saturday's water was safe.** By then you've already swum.

King County has the same limitation at scale. They test each swim beach for bacteria about **once a week**, with results posted days after sampling. But water quality changes fast — especially after rain, when runoff carries pet waste, fertilizer, and bacteria like E. coli into the lakes. King County's own guidance says to stay out of the water for 24 hours after heavy rain.

That leaves a gap: **six days out of seven, nobody knows.** And the EPA's national bloom forecast only covers lakes large enough to be resolved by satellite — it can't see Pine Lake or Beaver Lake at all.

**Every other option measures the past. This one estimates the future** — because you can't collect a water sample from a day that hasn't happened yet.

---

## How it works

```
King County open data API  ──┐
   (4,300 bacteria tests,    │
    30 lakes, 2019–2026)     ├──►  merged on date  ──►  Random Forest  ──►  model.pkl
                             │      (prepare.py)         (train_model.py)
Open-Meteo weather API    ───┘
   (rolling 1/3/7-day
    rainfall totals)

                        ┌──────────────────────────────────┐
User picks lake + date ►│  latest county test              │
                        │  + live weather forecast         ├─► model.pkl ─► 🟢 / 🔴 + explanation
                        │  (app.py)                        │
                        └──────────────────────────────────┘
```

### Model inputs

| Feature | Source |
|---|---|
| `rain_1d` — rainfall, previous day | Open-Meteo (live) |
| `rain_3d` — rainfall, previous 3 days | Open-Meteo (live) |
| `rain_7d` — rainfall, previous 7 days | Open-Meteo (live) |
| `watertempc` — temperature | Open-Meteo (air temp used as proxy — see Limitations) |
| `geomean30d` — 30-day bacteria geometric mean | King County |
| `nsampleshigh30d` — high samples in last 30 days | King County |

**Label:** King County's own `HighToday` flag — whether bacteria exceeded the safe threshold that day. Using the county's official determination rather than a self-defined cutoff keeps the target objective.

---

## Model performance

Random Forest classifier (300 trees, balanced class weights), trained on **3,861 lake-days** containing **496 unsafe days**, across 30 lakes. Evaluated on a held-out 20% test set (773 rows, 96 unsafe).

### Threshold analysis

Unsafe days are rare — roughly 13% of the record — so plain accuracy is misleading: a model that simply predicts "safe" every time scores well while warning nobody. I tested four decision thresholds on held-out data:

| Threshold | Precision | Recall | F1 | Unsafe days missed | False alarms |
|---|---|---|---|---|---|
| **0.20** | 0.35 | **0.97** | 0.52 | **3** of 96 | 169 |
| 0.30 | 0.35 | 0.84 | 0.49 | 15 | 152 |
| 0.40 | 0.37 | 0.76 | 0.50 | 23 | 122 |
| 0.50 | 0.37 | 0.60 | 0.46 | 38 | 97 |

**Chosen threshold: 0.20.** The trade-off here is unusually lopsided. Raising the threshold barely improves precision (0.35 → 0.37) but collapses recall from 97% to 60% — so tightening it would mean giving up danger detection for almost no reduction in false alarms. At 0.20 the model catches 93 of 96 unsafe days.

For a public-health tool, the two errors are not equally costly: missing an unsafe day means someone may swim in contaminated water, while a false alarm means someone skips a swim unnecessarily.

### Effect of expanding the dataset

The first version of this project trained on a truncated download — King County's API returns only 1,000 rows unless `$limit` is specified, which silently cut the dataset to 8 lakes. Fixing that produced a measurable improvement:

| | Truncated (1,000 rows, 8 lakes) | Full (4,300 rows, 30 lakes) |
|---|---|---|
| Training rows | 667 | **3,861** |
| Unsafe examples | 83 | **496** |
| Recall (unsafe) | 0.47 | **0.97** |

### What the model relies on

> **TODO — paste real values.** Add this to the end of `train_model.py` and run it:
> ```python
> for f, i in sorted(zip(features, model.feature_importances_), key=lambda x: -x[1]):
>     print(f"{f:18s} {i:.3f}")
> ```

On the earlier 8-lake model the ranking was: recent high samples (0.44), 30-day bacteria average (0.24), water temperature (0.13), then the three rainfall windows (0.10 / 0.06 / 0.04).

**Key finding:** I hypothesized that rainfall would be the dominant predictor, since runoff is the main mechanism by which bacteria enter lakes. The data disagreed. **Recent contamination history was roughly four times more important than any rainfall feature** — a lake that has recently had high bacteria is likely to have high bacteria again. Rainfall matters, but as a secondary signal.

---

## Data sources

- **Bacteria and water temperature:** [King County Freshwater Swim Beach Data](https://data.kingcounty.gov/Environment-Waste-Management/Freshwater-Swim-Beach-Data/mbzm-4r9y) — weekly monitoring, May–September, 2019–2026. Pulled live via the Socrata API.
- **Rainfall and air temperature:** [Open-Meteo](https://open-meteo.com/) — archive API for historical dates, forecast API for today and future dates.
- **Coverage:** 30 lakes, ~4,300 records.

---

## Limitations

This tool estimates risk; it does not measure water quality.

1. **It over-warns.** At a 0.20 threshold, roughly two-thirds of high-risk warnings are false alarms. This is a deliberate choice for a safety tool, but it means Safe to Swim is a screening aid, not a substitute for official advisories.
2. **Bacteria data is not real-time.** The app pulls King County's most recent published measurement — typically a few weeks old during the season. It cannot know today's actual bacteria level, because nobody does.
3. **Water temperature is a proxy.** Live water temperature isn't published for these lakes, so air temperature from the weather API is used in its place. Air temperature runs warmer than lake water in summer, which is a known source of error.
4. **Swim season only.** King County monitors May–September, so the model has never seen winter conditions.
5. **Precision is flat across thresholds**, which suggests the model separates "clearly safe" from "possibly unsafe" well but struggles to discriminate within the risky group. More features — wind, sunlight, days since last test — might sharpen this.
6. **One weather location.** Rainfall is pulled from a single central King County point rather than per-lake, on the assumption that rainfall varies little across the county.

---

## Running it locally

```bash
pip install -r requirements.txt

python prepare.py        # pulls King County + weather data, builds combine_data.csv
python train_model.py    # trains the model, saves model.pkl
streamlit run app.py     # launches the app
```

### Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit application — map, date picker, prediction, 7-day forecast |
| `prepare.py` | Pulls the King County API, merges weather, builds the training dataset |
| `train_model.py` | Trains and evaluates the Random Forest, saves `model.pkl` |
| `model.pkl` | Trained model |
| `bacteria_backup.csv` | Offline fallback if the King County API is unreachable |
| `combine_data.csv` | Merged training dataset |

---

## Next steps

- Derive water temperature from air temperature using a fitted lag model (`water_temp ≈ a × N-day mean air temp + b`) instead of using air temperature directly
- Add features that may improve precision: wind speed, sunlight, days since the last county test
- Per-lake rainfall rather than a single county-wide weather point
- Validate predictions against held-out historical county results
- Restrict predictions to the May–September monitoring season

---

## Disclaimer

Not affiliated with or endorsed by King County. This tool provides estimates only. Always check official advisories before swimming.
