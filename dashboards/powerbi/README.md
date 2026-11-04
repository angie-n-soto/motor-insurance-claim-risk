# Power BI dashboard (prep)

Everything needed to build a three-page Power BI report on the dbt star schema. The report itself
is built by hand in Power BI Desktop (Windows), so it isn't in the repo yet.

| File | What |
|---|---|
| [export_for_powerbi.py](export_for_powerbi.py) | Writes the star schema (`fct_policy_year`, `dim_*`) and the 2024 model scores (`fct_scores`, with deciles) as CSVs |
| [BUILD-GUIDE.md](BUILD-GUIDE.md) | Click-by-click: import, types, relationships, measures, the three pages, screenshots |
| [MEASURES.md](MEASURES.md) | DAX: claim rate, exposure-weighted claim rate, frequency, lift vs average, price vs risk index, YoY, retention, decile lift |
| [LAYOUT.md](LAYOUT.md) | Wireframes of the three pages |

```bash
# after `dbt build` (dbt/README.md) and, for page 3, python -m sql.load + python -m sql.export_scores
python dashboards/powerbi/export_for_powerbi.py
```

The CSVs are row-level data, so the output folders (`data/`, and `data_synthetic/` when the dbt
build read the synthetic fixture) are git-ignored, as is any `.pbix`. `SOURCE.txt` in the output
folder says which data the export came from. CI runs the export on the synthetic fixture after `dbt build`.
