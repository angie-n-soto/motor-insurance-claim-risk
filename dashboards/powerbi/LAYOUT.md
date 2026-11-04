# Layout sketch

16:9 canvas (1280 × 720). One accent colour for claim rate throughout; grey for exposure.

## Page 1: Portfolio overview

```
+----------------------------------------------------------------------------------+
| Motor portfolio 2022-2024                              [ 2022 ][ 2023 ][ 2024 ]  |
+-----------------+-----------------+-----------------+----------------------------+
|   Policies      |  Exposure years |   Claim rate    |  Claim rate YoY (pts)      |
|   (card)        |  (card)         |   (card)        |  (card)                    |
+-----------------+-----------------+-----------------+----------------------------+
|                                            |                                     |
|  Exposure (columns) and claim rate (line)  |  Claim rate by last year's claim    |
|  by year                                   |  history: yes / no / no_history     |
|  (line and clustered column chart)         |  (bar chart)                        |
|                                            |                                     |
|                                            +-------------------------------------+
|                                            |  Retention next year (card)         |
+--------------------------------------------+-------------------------------------+
```

## Page 2: Segment risk

```
+----------------------------------------------------------------------------------+
| Segment risk     [year v]   [policy type v]   [fuel type v]                       |
+--------------------------------------------+-------------------------------------+
|  Claim rate heatmap                        |  Lift vs average by brand group     |
|  rows: policy type                         |  (bar chart, sorted, line at 1.0)   |
|  cols: payment frequency                   |                                     |
|  (matrix, background colour)               |                                     |
+--------------------------------------------+-------------------------------------+
|  Price index (x) vs risk index (y)         |  Claim frequency by driver-age band |
|  bubble = policy type, colour = bonus,     |  (line chart)                       |
|  size = exposure; lines at 1.0             |                                     |
|  (scatter)                                 |                                     |
+--------------------------------------------+-------------------------------------+
```

## Page 3: Model decile lift

```
+----------------------------------------------------------------------------------+
| Model decile lift: XGBoost on the unseen 2024 test year (decile 10 = riskiest)    |
+----------------+----------------+----------------+-------------------------------+
| Top decile     | Bottom decile  | Top vs bottom  |                               |
| claim rate     | claim rate     | (x times)      |                               |
+----------------+----------------+----------------+                               |
|                                                  |  Decile table                 |
|  Actual claim rate (columns) and mean predicted  |  decile | policies | mean     |
|  probability (line) by decile 1..10              |  predicted | claim rate |     |
|  (line and clustered column chart)               |  lift                         |
|                                                  |                               |
+--------------------------------------------------+-------------------------------+
```
