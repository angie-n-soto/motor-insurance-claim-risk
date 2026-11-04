# Power BI build guide

Step-by-step for Power BI Desktop (free, Windows). About 3–4 hours the first time.
The page layouts are sketched in [LAYOUT.md](LAYOUT.md) and the DAX is in [MEASURES.md](MEASURES.md).

> **Before you start.** Build on the **real** data so the screenshots show real numbers.
> You can practise on the synthetic export (`data_synthetic/`), but never publish screenshots of it.

## 0. Make the CSVs

From the repo root (PowerShell, `.venv` active):

```powershell
python -m sql.load                     # real CSV -> data/claims.duckdb
python -m sql.export_scores            # 2024 model scores (for page 3)
.venv-dbt\Scripts\activate
cd dbt
$env:MOTOR_CSV_PATH = "../data/raw/motor_portfolio.csv"
dbt build
cd ..
.venv\Scripts\activate
python dashboards/powerbi/export_for_powerbi.py
```

Check `dashboards/powerbi/data/SOURCE.txt` says **real data**. You should have
`fct_policy_year.csv`, `dim_driver.csv`, `dim_policy.csv`, `dim_vehicle.csv`, `dim_year.csv`, `fct_scores.csv`.

## 1. Import

1. Open Power BI Desktop → **Blank report**.
2. **Home → Get data → Text/CSV** → pick `dashboards/powerbi/data/fct_policy_year.csv` → **Transform Data**
   (not *Load*: you want to check the types first).
3. In Power Query, **New Source → Text/CSV** for each of the other five CSVs.
4. For each query, check the column types (click the icon left of each column header):
   - `policy_year_id`, `driver_key`, `policy_key`, `vehicle_key` → **Text**. Power BI often guesses
     *Whole number* for `driver_key`; set it to Text in **every** table, or relationships won't match.
   - `year`, `decile`, `has_claim`, `total_claims`, `driver_age`, `seats` → **Whole number**.
   - `total_exposure`, `total_premium`, `premium_per_exposure`, `predicted_probability`, `vehicle_value`
     → **Decimal number**.
   - If a "Changed Type" step turns decimals into text, check *File → Options → Regional settings*:
     the CSVs use a dot as the decimal mark (set the locale to *English (United States)* for the import).
5. **Close & Apply**.

## 2. Relationships (Model view)

Click the **Model view** icon (left bar, third icon). Delete any relationships Power BI auto-detected,
then drag to create these (all **many-to-one, single direction**, from the fact to the dimension):

| From (many) | To (one) |
|---|---|
| `fct_policy_year[driver_key]` | `dim_driver[driver_key]` |
| `fct_policy_year[policy_key]` | `dim_policy[policy_key]` |
| `fct_policy_year[vehicle_key]` | `dim_vehicle[vehicle_key]` |
| `fct_policy_year[year]` | `dim_year[year]` |
| `fct_scores[policy_year_id]` | `fct_policy_year[policy_year_id]` |

The last one lets page 3 be sliced by policy type, etc. If Power BI proposes *one-to-one*, change it
to **Many to one** with cross-filter direction **Single**.

Arrange the diagram as a star: fact in the middle, dimensions around it. **Screenshot it**
(`model_view.png`): it's good interview material for "explain your data model".

Tidy-up: right-click each key column (`*_key`, `policy_year_id`) → **Hide in report view**.

## 3. Sort and label columns

- `dim_vehicle[value_band]`: add a sort column in Power Query or use the order
  `<10k, 10-20k, 20-30k, 30-50k, 50k+, unknown` via **Column tools → Sort by column**
  (create a small `value_band_order` column with **Add Column → Conditional column**).
- `fct_policy_year[driver_age_band]`: same idea, so 18–24 comes first.
- `dim_year[year]`: **Column tools → Summarization → Don't summarize** (otherwise Power BI sums the years).
  Do the same for `fct_scores[decile]`.

## 4. Measures table

1. **Home → Enter data** → name the table `_Measures`, leave one empty column → **Load**.
2. Create every measure from [MEASURES.md](MEASURES.md) with **Modeling → New measure** while
   `_Measures` is selected.
3. Delete the empty column. Apply the formats in the table at the end of MEASURES.md
   (**Measure tools → Format**).

## 5. Page 1: Portfolio overview

Rename the page (double-click the tab) to **Portfolio overview**. See LAYOUT.md for placement.

1. **Slicer**: `dim_year[year]` → *Format → Slicer settings → Style: Tile*.
2. **Four cards** (Visualizations → *Card*): `Policies`, `Exposure Years`, `Claim Rate`, `Claim Rate YoY Change (pts)`.
3. **Line and clustered column chart**: X-axis `dim_year[year]`, columns `Exposure Years`,
   line `Claim Rate`. Title: "Exposure and claim rate by year".
4. **Clustered bar chart**: Y-axis `fct_policy_year[prev_year_claim]`, X-axis `Claim Rate`.
   Title: "Claim rate by last year's claim history".
5. **Card**: `Retention Next Year` (works when one year is selected in the slicer; 2022 is the
   meaningful one).

## 6. Page 2: Segment risk

New page → **Segment risk**.

1. **Slicers**: `dim_year[year]`, `dim_policy[policy_type_label]`, `dim_vehicle[fuel_type_label]`.
2. **Matrix**: Rows `dim_policy[policy_type_label]`, Columns `dim_policy[payment_frequency_label]`,
   Values `Claim Rate`. *Format → Cell elements → Background color* on, so it reads as a heatmap.
3. **Clustered bar chart**: Y-axis `dim_vehicle[brand_group]`, X-axis `Lift vs Average`, sorted descending.
   Add a constant line at 1.0 (*Analytics pane → Constant line*) labelled "portfolio average".
4. **Scatter chart**: Values `dim_policy[policy_type_label]`, Legend `dim_policy[bonus_score]`,
   X-axis `Price Index`, Y-axis `Risk Index`, Size `Exposure Years`.
   Add constant lines at 1.0 on both axes. Title: "Are segments priced to risk?".
5. **Line chart**: X-axis `fct_policy_year[driver_age_band]`, Y-axis `Claim Frequency`.

## 7. Page 3: Model decile lift

New page → **Model decile lift**.

1. **Text box** at the top: "XGBoost model scored on the unseen 2024 test year. Decile 10 = highest
   predicted risk."
2. **Clustered column chart**: X-axis `fct_scores[decile]` (set *Type: Categorical*), Y-axis
   `Decile Claim Rate`. Add a line `Scored Average Claim Rate` as a constant reference (or use a
   *Line and clustered column chart* with `Mean Predicted Probability` as the line: that's the
   calibration check in one picture).
3. **Cards**: `Top vs Bottom Decile`, `Decile Claim Rate` filtered to decile 10 (drag `decile` into
   the visual's filter pane, choose 10), and the same for decile 1.
4. **Table**: `decile`, `Scored Policies`, `Mean Predicted Probability`, `Decile Claim Rate`, `Decile Lift`.
5. Check the numbers against `sql/results/07_decile_lift.csv`. If they differ, a relationship or a
   type is wrong.

## 8. Finish

- *View → Themes*: pick one and keep it; use one accent colour for "claim rate" everywhere.
- *File → Options → Current file → Data load*: turn off *Auto date/time* (no dates here).
- Save as `dashboards/powerbi/motor_claims.pbix` **locally**. The `.pbix` contains the imported
  rows of the real data, whose license is still TBD, so it is git-ignored. To share the build,
  **File → Export → Power BI template** → `motor_claims.pbit` (a template keeps the model, measures
  and visuals but not the data) and commit that.

## 9. Screenshots to save

Save to `dashboards/screenshots/` (PNG, full-page, 1600 px wide or more) and commit them:

| File | What |
|---|---|
| `01_portfolio_overview.png` | Page 1, all years selected |
| `02_segment_risk.png` | Page 2, all filters cleared |
| `03_model_decile_lift.png` | Page 3 |
| `model_view.png` | The star schema in Model view |
| `dax_measure.png` | (optional) one measure open in the formula bar, e.g. *Lift vs Average* |

Then link them from a `dashboards/README.md` with one sentence per page on what an underwriter
would take from it.
