# Hyperliquid `/info` Request Reference

Every read-only Hyperliquid query is a single POST:

```
POST https://api.hyperliquid.xyz/info
Content-Type: application/json
Body: {"type": "<request>", ...}
```

No API key, no signing, no wallet ownership proof -- these are public reads.
Testnet is the same protocol at `https://api.hyperliquid-testnet.xyz/info`.

Two scopes:

- **Market-wide** -- no address. Universe, prices, funding, books, candles.
- **User-scoped** -- add `"user": "0x..."` (any public address; you are only
  reading). Positions, balances, fills, orders, funding paid, portfolio.

All request types below were verified live against `api.hyperliquid.xyz/info`
on 2026-07-21 (HTTP 200). Response shapes are trimmed to the load-bearing
fields; string-encoded numbers are Hyperliquid's own convention (parse as
`float`/`Decimal`). The `CLI` note names the `hyperliquid_client.py` command
that wraps each type, or marks it as not yet wrapped.

---

## Market-Wide Requests

### `meta` -- perp universe + margin tiers

```
Body:     {"type": "meta"}
Response: {"universe": [{"name": "BTC", "szDecimals": 5, "maxLeverage": 40,
                         "marginTableId": 56}, ...],
           "marginTables": [...], "collateralToken": ...}
```

The `universe` order is the asset index used positionally by other endpoints
(asset-context arrays line up with it). `isDelisted: true` marks retired
markets. CLI: folded into `markets`.

### `metaAndAssetCtxs` -- universe + live per-asset context

```
Body:     {"type": "metaAndAssetCtxs"}
Response: [ {universe...},                          # element 0 == meta
            [ {"funding": "0.0000090784",           # element 1, positional
               "openInterest": "36562.61434",
               "premium": "-0.0003924528",
               "oraclePx": "66250.0", "markPx": "66223.0", "midPx": "66223.5",
               "impactPxs": ["66223.0", "66224.0"],
               "dayNtlVlm": "...", "dayBaseVlm": "...", "prevDayPx": "..."},
              ... ] ]
```

`ctxs[i]` describes `universe[i]`. `funding` here is the current **hourly**
rate (see `references/funding-explained.md`). CLI: `markets` sorts/formats this.

### `allMids` -- every mid price in one call

```
Body:     {"type": "allMids"}
Response: {"BTC": "66223.5", "ETH": "1931.5", "@1": "14.72",
           "#5100": "0.933255", ...}   # ~940 keys
```

Keys are perp coin names, spot pair aliases (`@1`, `@107`), and HIP-3 /
builder market ids. One cheap request for a whole-venue price snapshot.
CLI: not yet wrapped (use as a fast price map).

### `predictedFundings` -- next-hour funding across venues

```
Body:     {"type": "predictedFundings"}
Response: [ ["BTC", [ ["HlPerp",    {"fundingRate": "0.0000125",
                                      "nextFundingTime": 1784631600000,
                                      "fundingIntervalHours": 1}],
                      ["BinPerp",   {"fundingRate": "...",
                                      "fundingIntervalHours": 4}],
                      ["BybitPerp", {"fundingRate": "...",
                                      "fundingIntervalHours": 4}] ]],
            ... ]   # ~230 coins
```

`HlPerp` carries `fundingIntervalHours: 1` -- Hyperliquid settles funding
hourly, while `BinPerp`/`BybitPerp` quote 4h/8h. Use this to compare
Hyperliquid's next-hour rate against CEX venues on the same coin. CLI: not
yet wrapped.

### `fundingHistory` -- realized hourly funding for one coin

```
Body:     {"type": "fundingHistory", "coin": "BTC",
           "startTime": <ms> [, "endTime": <ms>]}
Response: [ {"coin": "BTC", "fundingRate": "0.000009516",
             "premium": "-0.0004238717", "time": 1784613600043}, ... ]
```

One row per hour (consecutive `time` values are about 3_600_000 ms apart). CLI:
`funding`.

### `candleSnapshot` -- OHLCV candles

```
Body:     {"type": "candleSnapshot",
           "req": {"coin": "BTC", "interval": "1h",
                   "startTime": <ms>, "endTime": <ms>}}
Response: [ {"t": 1784610000000, "T": 1784613599999, "s": "BTC", "i": "1h",
             "o": "65502.0", "c": "65720.0", "h": "65860.0", "l": "65451.0",
             "v": "1550.49254", "n": 12925}, ... ]
```

`t`/`T` are the candle open/close ms; `n` is trade count. Note the nested
`req` object -- unlike other types the params are not top-level. CLI:
`candles` and `export`.

### `l2Book` -- order-book snapshot

```
Body:     {"type": "l2Book", "coin": "BTC" [, "nSigFigs": N]}
Response: {"coin": "BTC", "time": 1784633876810,
           "levels": [ [ {"px": "66266.0", "sz": "4.30324", "n": 14}, ... ],
                       [ {"px": "66280.0", "sz": "...", "n": ...}, ... ] ]}
```

`levels[0]` = bids (descending), `levels[1]` = asks (ascending); `n` is the
order count at that level. A point-in-time snapshot, not a stream. CLI: `l2`.

### `spotMeta` / `spotMetaAndAssetCtxs` -- spot universe + context

```
Body:     {"type": "spotMeta"}
Response: {"universe": [{"tokens": [1, 0], "name": "PURR/USDC", "index": 0,
                         "isCanonical": true}, ...],
           "tokens": [{...}, ...]}

Body:     {"type": "spotMetaAndAssetCtxs"}
Response: [ {spotMeta...}, [ {ctx per pair}, ... ] ]
```

`name` may be a friendly pair (`PURR/USDC`) or an alias (`@1`, `@107`); both
are valid identifiers. `tokens` maps token indices to metadata. CLI: `spots`.

### `perpDexs` -- builder-deployed perp DEXs (HIP-3)

```
Body:     {"type": "perpDexs"}
Response: [ null, {"name": "...", "full_name": "...", "deployer": "0x...",
                   ...}, ... ]
```

Element 0 is `null` -- that is the native first-party perp DEX. Later
elements are builder-deployed DEXs; their coins are addressed as
`dexname:COIN`. CLI: `dexs`.

---

## User-Scoped Requests

### `clearinghouseState` -- perp positions + margin

```
Body:     {"type": "clearinghouseState", "user": "0x..." [, "dex": "..."]}
Response: {"marginSummary": {"accountValue": "...", "totalNtlPos": "...",
                             "totalRawUsd": "...", "totalMarginUsed": "..."},
           "crossMarginSummary": {...}, "crossMaintenanceMarginUsed": "...",
           "withdrawable": "...", "time": <ms>,
           "assetPositions": [
             {"type": "oneWay",
              "position": {"coin": "BTC", "szi": "-33.23545",
                           "leverage": {"type": "cross", "value": 3},
                           "entryPx": "66202.1", "positionValue": "...",
                           "unrealizedPnl": "...", "liquidationPx": "...",
                           "marginUsed": "...", "maxLeverage": 40,
                           "cumFunding": {"allTime": "...", "sinceOpen": "...",
                                          "sinceChange": "..."}}}, ... ]}
```

`szi` is signed (negative == short). `assetPositions` is empty when the
account is flat. Pass `dex` for a HIP-3 DEX. CLI: `state`.

### `spotClearinghouseState` -- spot balances

```
Body:     {"type": "spotClearinghouseState", "user": "0x..."}
Response: {"balances": [{"coin": "USDC", "token": 0, "total": "0.000019",
                         "hold": "0.0", "entryNtl": "0.0"},
                        {"coin": "HYPE", "token": 150, "total": "...",
                         "hold": "0.0", "entryNtl": "..."}, ...]}
```

`total` includes `hold` (amount locked in resting orders). CLI:
`spot-balances`.

### `userFills` / `userFillsByTime` -- trade fills

```
Body:     {"type": "userFills", "user": "0x..." [, "aggregateByTime": true]}
   or:    {"type": "userFillsByTime", "user": "0x...", "startTime": <ms>
           [, "endTime": <ms>, "aggregateByTime": true]}
Response: [ {"coin": "BTC", "px": "66264.0", "sz": "0.00016", "side": "B",
             "time": <ms>, "startPosition": "-32.06011", "dir": "Close Short",
             "closedPnl": "-0.010352", "hash": "0x...", "oid": ...,
             "crossed": false, "fee": "-0.000212", "tid": ...}, ... ]
```

`side`: `B` buy / `A` ask-sell. `dir` is the human action ("Open Long",
"Close Short"). Both variants cap the response (2000 rows observed) and expose
only a recent rolling window -- **not** full archive history. CLI: `fills`.

### `historicalOrders` -- recent orders WITH status (NOT live)

```
Body:     {"type": "historicalOrders", "user": "0x..."}
Response: [ {"order": {"coin": "ETH", "side": "A", "limitPx": "1931.8",
                       "sz": "0.0", "origSz": "12.0946", "oid": ...,
                       "timestamp": <ms>, "orderType": "Limit", "tif": "Alo",
                       "cloid": "0x..."},
             "status": "filled", "statusTimestamp": <ms>}, ... ]
```

Each row is wrapped as `{order, status, statusTimestamp}` and includes
**terminal** states (`filled`, `canceled`, ...). Capped (2000 rows observed),
recent only. This is order *history*, not the live book -- for currently
resting orders use `frontendOpenOrders` below. CLI: `orders` (see the
`references/pitfalls.md` note on the live-vs-historical gap).

### `frontendOpenOrders` -- live resting orders (rich)

```
Body:     {"type": "frontendOpenOrders", "user": "0x..."}
Response: [ {"coin": "ZEC", "side": "B", "limitPx": "543.2", "sz": "2.44",
             "origSz": "2.44", "oid": 499945281456, "timestamp": <ms>,
             "orderType": "Limit", "tif": "Alo", "reduceOnly": false,
             "isTrigger": false, "triggerPx": "0.0",
             "triggerCondition": "N/A", "isPositionTpsl": false,
             "children": [], "cloid": "0x..."}, ... ]
```

A **flat** array of only the orders currently resting on the book -- no
`status` wrapper, no filled/canceled entries. This is the correct type for
"what orders are live right now", including trigger/TP-SL metadata
(`isTrigger`, `triggerPx`, `reduceOnly`, `children`). CLI: not yet wrapped
(the `orders` command currently sends `historicalOrders`).

### `openOrders` -- live resting orders (lean)

```
Body:     {"type": "openOrders", "user": "0x..."}
Response: [ {"coin": "ZEC", "side": "A", "limitPx": "543.7", "sz": "2.77",
             "origSz": "2.77", "oid": 499946839678, "timestamp": <ms>,
             "cloid": "0x..."}, ... ]
```

Same live resting set as `frontendOpenOrders` but with the trigger/TP-SL
metadata stripped -- lighter payload when you only need coin/side/price/size.
CLI: not yet wrapped.

### `userFunding` -- funding payments received/paid

```
Body:     {"type": "userFunding", "user": "0x...", "startTime": <ms>
           [, "endTime": <ms>]}
Response: [ {"time": 1783468800000, "hash": "0x000...000",
             "delta": {"type": "funding", "coin": "AAVE", "usdc": "0.890391",
                       "szi": "-33.72125", "fundingRate": "0.0000125",
                       "nSamples": 24}}, ... ]
```

One row per hourly funding settlement per position. `usdc` is the signed cash
delta, `szi` the position size at settlement, `fundingRate` the hourly rate
applied. Capped (500 rows observed). CLI: not yet wrapped.

### `portfolio` -- equity / PnL / volume history

```
Body:     {"type": "portfolio", "user": "0x..."}
Response: [ ["day",       {"accountValueHistory": [[<ms>, "249112574.46..."],
                                                   ...],
                           "pnlHistory": [[<ms>, "..."], ...], "vlm": "..."}],
            ["week",       {...}], ["month", {...}], ["allTime", {...}],
            ["perpDay", {...}], ["perpWeek", {...}], ... ]   # 8 windows
```

An array of `[periodName, series]` pairs. Each series has time-stamped
`accountValueHistory` and `pnlHistory` plus a `vlm` total. CLI: not yet
wrapped.

### `activeAssetData` -- per-asset trading context for a user

```
Body:     {"type": "activeAssetData", "user": "0x...", "coin": "BTC"}
Response: {"user": "0x...", "coin": "BTC",
           "leverage": {"type": "cross", "value": 20},
           "maxTradeSzs": ["63053.12399", "63053.12399"],
           "availableToTrade": ["208784656.82...", "208784656.82..."],
           "markPx": "66225.0"}
```

The user's effective leverage, max tradable size, and available margin for one
coin. Returns even when the user holds no position in that coin. CLI: not yet
wrapped.

---

## Notes

- Response numbers are strings by design -- convert before arithmetic.
- Asset-context arrays (`metaAndAssetCtxs`, `spotMetaAndAssetCtxs`) are
  positional to their `universe`; join by index, not by a key.
- The `/info` endpoint is rate-limited by weight. Batch with `allMids` /
  `metaAndAssetCtxs` instead of many single-coin calls where possible, and
  back off on HTTP 429.
- History-bearing types (`userFills*`, `historicalOrders`, `userFunding`) are
  capped rolling windows, not full archives -- paginate with `startTime` for
  wider ranges.
