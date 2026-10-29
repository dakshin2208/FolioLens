# Loading real market data

All commands run inside the backend (locally: `cd backend`; with Docker:
`docker compose run --rm api <command>`). Check each source's current terms of use before relying on it,
especially for anything commercial.

## 1. Mutual fund master and NAVs (AMFI)

```bash
python -m app.market_data.cli fetch-amfi                  # today's NAVs for all schemes
python -m app.market_data.cli load-amfi data/history.txt  # AMFI historical NAV report, same format
```

AMFI's files are semicolon-separated with category headings such as
`Open Ended Schemes(Equity Scheme - Large Cap Fund)`. The loader creates one instrument per ISIN,
infers the asset class from the category, and marks liquid, overnight and money-market funds as liquid.
For return and risk history, download historical NAV reports for the period you need and load each one.

## 2. Stock master and prices (NSE bhavcopy)

Download the daily equity bhavcopy CSV from NSE and load it. Both the UDiFF layout (`TckrSymb`, `ISIN`,
`ClsPric`, `TradDt`) and the legacy layout (`SYMBOL`, `ISIN`, `CLOSE`, `TIMESTAMP`) are supported.

```bash
python -m app.market_data.cli load-bhavcopy data/BhavCopy_NSE_CM_0_0_0_20261009_F_0000.csv
```

## 3. Benchmark (Nifty 50 TRI)

Export the Total Returns Index history as CSV from niftyindices.com, then:

```bash
python -m app.market_data.cli load-index data/nifty50_tri.csv --symbol NIFTY50TRI \
  --name "Nifty 50 TRI" --date-col Date --value-col "Total Returns Index"
```

`BENCHMARK_SYMBOL` in `.env` selects which index reports use.

## 4. Fund constituents (AMC monthly disclosures)

Each AMC publishes a monthly portfolio file, in its own layout. Convert the equity holdings of the funds
you support into this CSV (weight as a fraction or a percentage):

```csv
fund_isin,stock_isin,weight,as_of
INF179K01XQ0,INE040A01034,9.12,2026-09-30
```

```bash
python -m app.market_data.cli load-constituents data/constituents_2026_09.csv --source "AMC disclosures Sep 2026"
```

## 5. Sector and market-cap classification

```csv
isin,sector,market_cap
INE040A01034,Financials,large
```

```bash
python -m app.market_data.cli load-stock-metadata data/stock_metadata.csv
```

Market-cap buckets follow SEBI's categorisation (top 100 large, 101–250 mid, rest small), published
twice a year by AMFI.

## Order matters

Load instruments (steps 1–2) before constituents and metadata (steps 4–5), which refer to ISINs.
