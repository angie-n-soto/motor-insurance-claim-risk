# DAX measures

Paste each measure into Power BI Desktop: **Modeling → New measure** (or right-click the
`_Measures` table → *New measure*). Table and column names match the CSVs written by
`export_for_powerbi.py`. Keep all measures in one `_Measures` table (see BUILD-GUIDE step 4).

There is no date column in the data, only `year`, so the measures use `dim_year[year]` directly
instead of Power BI's time-intelligence functions (those need a real date table).

## Core counts

```dax
Policies = COUNTROWS ( fct_policy_year )
```
```dax
Insureds = DISTINCTCOUNT ( fct_policy_year[driver_key] )
```
```dax
Exposure Years = SUM ( fct_policy_year[total_exposure] )
```
```dax
Policies With Claim = SUM ( fct_policy_year[has_claim] )
```
```dax
Claims = SUM ( fct_policy_year[total_claims] )
```
```dax
Earned Premium = SUM ( fct_policy_year[total_premium] )
```

## Rates

**Claim rate**: share of policy-years with at least one claim (the model's target).
```dax
Claim Rate = DIVIDE ( [Policies With Claim], [Policies] )
```

**Exposure-weighted claim rate**: each policy-year counts in proportion to how long it was
insured, so a 1-month policy without a claim no longer counts as much as a full clean year.
```dax
Claim Rate (Exposure-Weighted) =
DIVIDE (
    SUMX ( fct_policy_year, fct_policy_year[has_claim] * fct_policy_year[total_exposure] ),
    [Exposure Years]
)
```

**Claim frequency**: claims per year of cover (the actuarial frequency; can exceed 1 in theory).
```dax
Claim Frequency = DIVIDE ( [Claims], [Exposure Years] )
```

**Premium per exposure year**: annualised price.
```dax
Premium per Exposure Year = DIVIDE ( [Earned Premium], [Exposure Years] )
```

## Compared with the average

**Portfolio claim rate**: the claim rate with every filter removed except the year, so a
segment can be compared with its own year's average.
```dax
Portfolio Claim Rate =
CALCULATE ( [Claim Rate], ALLEXCEPT ( fct_policy_year, dim_year[year] ) )
```
```dax
Lift vs Average = DIVIDE ( [Claim Rate], [Portfolio Claim Rate] )
```
Format *Lift vs Average* as a decimal number with 2 places and read it as "× the average":
1.30 means 30% more likely to claim than the average policy that year.

**Price index vs risk index** (the SQL query 03 view, in DAX):
```dax
Portfolio Premium per Exposure Year =
CALCULATE ( [Premium per Exposure Year], ALLEXCEPT ( fct_policy_year, dim_year[year] ) )
```
```dax
Price Index = DIVIDE ( [Premium per Exposure Year], [Portfolio Premium per Exposure Year] )
```
```dax
Risk Index = [Lift vs Average]
```
```dax
Risk minus Price = [Risk Index] - [Price Index]
```
Positive *Risk minus Price* = the segment claims more often than its price suggests
(premiums also price claim cost, so treat it as a question, not a conclusion).

## Year over year

```dax
Claim Rate PY =
VAR y = SELECTEDVALUE ( dim_year[year] )
RETURN
    IF (
        NOT ISBLANK ( y ),
        CALCULATE ( [Claim Rate], REMOVEFILTERS ( dim_year ), dim_year[year] = y - 1 )
    )
```
```dax
Claim Rate YoY Change (pts) =
VAR py = [Claim Rate PY]
RETURN IF ( NOT ISBLANK ( py ), [Claim Rate] - py )
```
```dax
Claim Rate YoY Change (%) = DIVIDE ( [Claim Rate YoY Change (pts)], [Claim Rate PY] )
```
Format *(pts)* as a percentage with 1 decimal: +1.1% means 14.0% → 15.1%, i.e. 1.1 percentage points.

## Retention

Share of this year's insureds who are still insured next year (needs one year selected).
```dax
Retention Next Year =
VAR y = SELECTEDVALUE ( dim_year[year] )
VAR this_year = VALUES ( fct_policy_year[driver_key] )
VAR next_year =
    CALCULATETABLE (
        VALUES ( fct_policy_year[driver_key] ),
        REMOVEFILTERS ( dim_year ),
        dim_year[year] = y + 1
    )
RETURN
    IF ( NOT ISBLANK ( y ), DIVIDE ( COUNTROWS ( INTERSECT ( this_year, next_year ) ), COUNTROWS ( this_year ) ) )
```
Note: the fact table excludes zero-exposure rows, so this can differ very slightly from SQL query 10,
which counts every row.

## Prior-year claim effect

```dax
Claim Rate after a Claim Year =
CALCULATE ( [Claim Rate], fct_policy_year[prev_year_claim] = "yes" )
```
```dax
Claim Rate after a Clean Year =
CALCULATE ( [Claim Rate], fct_policy_year[prev_year_claim] = "no" )
```

## Model deciles (`fct_scores`, test year 2024)

```dax
Scored Policies = COUNTROWS ( fct_scores )
```
```dax
Mean Predicted Probability = AVERAGE ( fct_scores[predicted_probability] )
```
```dax
Decile Claim Rate = AVERAGE ( fct_scores[has_claim] )
```
```dax
Scored Average Claim Rate = CALCULATE ( [Decile Claim Rate], REMOVEFILTERS ( fct_scores[decile] ) )
```
```dax
Decile Lift = DIVIDE ( [Decile Claim Rate], [Scored Average Claim Rate] )
```
```dax
Top vs Bottom Decile =
DIVIDE (
    CALCULATE ( [Decile Claim Rate], fct_scores[decile] = 10 ),
    CALCULATE ( [Decile Claim Rate], fct_scores[decile] = 1 )
)
```
On the real data, *Decile Claim Rate* for deciles 10 and 1 should match `sql/results/07_decile_lift.csv`
(and roughly the 33.9% vs 2.4% in reports/RESULTS.md).

## Formatting

| Measure | Format |
|---|---|
| Claim Rate, Claim Rate (Exposure-Weighted), Portfolio Claim Rate, Claim Rate PY, YoY (pts), YoY (%), Retention Next Year, Decile Claim Rate, Mean Predicted Probability | Percentage, 1 decimal |
| Lift vs Average, Price Index, Risk Index, Decile Lift, Top vs Bottom Decile | Decimal, 2 places |
| Claim Frequency | Decimal, 3 places |
| Policies, Insureds, Claims, Scored Policies | Whole number, thousands separator |
| Exposure Years | Decimal, 0 places, thousands separator |
| Earned Premium, Premium per Exposure Year | Currency € , 0 places |
