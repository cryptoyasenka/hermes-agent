# Hyperliquid Read-Only Recipes

Practical `/info` reads, each a single POST to
`https://api.hyperliquid.xyz/info` -- no API key, no signing. Every recipe
below was executed live and its response captured as proof; the `Tested`
marker records when. Responses are point-in-time and trimmed to the
load-bearing fields (Hyperliquid encodes numbers as strings).

User-scoped recipes name the public address used. Two appear below:

- `0xdfc24b077bc1425ad1dea75bcb6f8158e10df303` -- the HLP (Hyperliquidity
  Provider) vault, a canonical public address.
- `0xf5d81a135f756ca16544e53c20fc20643ec3ad53` -- an actively-trading address
  taken from the public leaderboard, used where live orders / funding are
  needed (HLP was flat at test time).

---

## Recipe 1: Whole-venue price snapshot

One call for every mid price on the exchange -- cheaper than looping per coin.

```bash
curl -s https://api.hyperliquid.xyz/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"allMids"}'
```

Real response (trimmed; 937 keys total):

```json
{"@1": "14.72", "@10": "0.00007355", "@100": "0.003556", "@101": "0.12763",
 "#5100": "0.933255", "0G": "0.18405", "2Z": "0.064994", "...": "..."}
```

Keys are perp coin names (`BTC`, `ETH`, ...), spot pair aliases (`@1`, `@107`),
and builder/HIP-3 market ids (`#5100`). Values are mid prices.

Tested 2026-07-21 against api.hyperliquid.xyz/info (HTTP 200).

---

## Recipe 2: Compare next-hour funding across venues

Is Hyperliquid's upcoming funding richer or cheaper than Binance/Bybit on the
same coin?

```bash
curl -s https://api.hyperliquid.xyz/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"predictedFundings"}'
```

Real response (trimmed to one coin of ~230):

```json
[["0G", [["BinPerp",   {"fundingRate": "-0.00002477", "fundingIntervalHours": 4}],
         ["HlPerp",    {"fundingRate": "0.0000125",   "fundingIntervalHours": 1}],
         ["BybitPerp", {"fundingRate": "0.00005",     "fundingIntervalHours": 4}]]],
 "..."]
```

`HlPerp` settles hourly (`fundingIntervalHours: 1`); the other venues quote a
4h window. Normalize to a common interval before comparing (see
`references/funding-explained.md`).

Tested 2026-07-21 against api.hyperliquid.xyz/info (HTTP 200).

---

## Recipe 3: Current hourly funding and basis for a coin

Read the live funding rate plus the mark/oracle basis that drives it.

```bash
curl -s https://api.hyperliquid.xyz/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"metaAndAssetCtxs"}'
```

The response is `[meta, ctxs]`; `ctxs[i]` lines up with `meta.universe[i]`.
Real `ctx` for BTC (universe index 0):

```json
{"funding": "0.0000090784", "openInterest": "36562.61434",
 "premium": "-0.0003924528", "oraclePx": "66250.0", "markPx": "66223.0",
 "midPx": "66223.5", "impactPxs": ["66223.0", "66224.0"],
 "dayNtlVlm": "2635485914.32...", "prevDayPx": "64330.0"}
```

`funding` is the current hourly rate; `premium`, `markPx`, and `oraclePx` are
its inputs. ETH read exactly `0.0000125` (the calm-market baseline) at the same
time.

Tested 2026-07-21 against api.hyperliquid.xyz/info (HTTP 200).

---

## Recipe 4: List an account's LIVE resting orders

The orders actually sitting on the book right now -- not order history. Use
`frontendOpenOrders`, which returns only currently-resting orders as a flat
array (with trigger / TP-SL metadata).

```bash
curl -s https://api.hyperliquid.xyz/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"frontendOpenOrders",
       "user":"0xf5d81a135f756ca16544e53c20fc20643ec3ad53"}'
```

Real response (trimmed to first of 44 orders):

```json
[{"coin": "ZEC", "side": "B", "limitPx": "543.2", "sz": "2.44",
  "origSz": "2.44", "oid": 499945281456, "timestamp": 1784633677145,
  "orderType": "Limit", "tif": "Alo", "reduceOnly": false,
  "isTrigger": false, "triggerPx": "0.0", "triggerCondition": "N/A",
  "isPositionTpsl": false, "children": [], "cloid": "0xbba554e9...c"},
 "..."]
```

Contrast: `{"type":"historicalOrders", ...}` for the same address returned 2000
rows wrapped as `{"order": {...}, "status": "filled", "statusTimestamp": ...}`
-- filled/canceled history, not the live book. See
`references/pitfalls.md`. For a leaner payload (no trigger metadata) use
`{"type":"openOrders", ...}`.

Tested 2026-07-21 against api.hyperliquid.xyz/info (HTTP 200), address
`0xf5d81a135f756ca16544e53c20fc20643ec3ad53`.

---

## Recipe 5: See what an account actually paid in funding

Per-settlement funding cash flow for an address.

```bash
curl -s https://api.hyperliquid.xyz/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"userFunding",
       "user":"0xf5d81a135f756ca16544e53c20fc20643ec3ad53",
       "startTime":1783423981746}'
```

Real response (trimmed to first of 500 rows):

```json
[{"time": 1783468800000, "hash": "0x0000...0000",
  "delta": {"type": "funding", "coin": "AAVE", "usdc": "0.890391",
            "szi": "-33.72125", "fundingRate": "0.0000125",
            "nSamples": 24}},
 "..."]
```

One row per hourly settlement per position: `usdc` is the signed cash delta,
`szi` the position size, `fundingRate` the hourly rate applied. Capped rolling
window (500 rows); paginate with `startTime` for more.

Tested 2026-07-21 against api.hyperliquid.xyz/info (HTTP 200), address
`0xf5d81a135f756ca16544e53c20fc20643ec3ad53`.

---

## Recipe 6: Chart an account's equity and PnL over time

Time series of account value, PnL, and volume across standard windows.

```bash
curl -s https://api.hyperliquid.xyz/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"portfolio",
       "user":"0xdfc24b077bc1425ad1dea75bcb6f8158e10df303"}'
```

Real response (trimmed; 8 windows total, each `[name, series]`):

```json
[["day", {"accountValueHistory": [[1784546862762, "249112574.4694469869"],
                                  [1784548454121, "249107533.6866639853"],
                                  "..."],
          "pnlHistory": [["...", "..."]], "vlm": "..."}],
 ["week", {"..."}], ["month", {"..."}], ["allTime", {"..."}], "..."]
```

Windows observed: `day`, `week`, `month`, `allTime`, plus `perp`-prefixed
variants. Each `accountValueHistory` / `pnlHistory` point is `[ms, value]`.

Tested 2026-07-21 against api.hyperliquid.xyz/info (HTTP 200), address
`0xdfc24b077bc1425ad1dea75bcb6f8158e10df303` (HLP vault).

---

## Recipe 7: Check a user's leverage and buying power for a coin

Effective leverage, max tradable size, and available margin for one asset --
returns even with no open position in that coin.

```bash
curl -s https://api.hyperliquid.xyz/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"activeAssetData",
       "user":"0xdfc24b077bc1425ad1dea75bcb6f8158e10df303",
       "coin":"BTC"}'
```

Real response:

```json
{"user": "0xdfc24b077bc1425ad1dea75bcb6f8158e10df303", "coin": "BTC",
 "leverage": {"type": "cross", "value": 20},
 "maxTradeSzs": ["63053.12399", "63053.12399"],
 "availableToTrade": ["208784656.8224869967", "208784656.8224869967"],
 "markPx": "66225.0"}
```

`maxTradeSzs` and `availableToTrade` are `[bid-side, ask-side]` pairs.

Tested 2026-07-21 against api.hyperliquid.xyz/info (HTTP 200), address
`0xdfc24b077bc1425ad1dea75bcb6f8158e10df303` (HLP vault).

---

## Reproducing these

Swap the address for any public wallet (these are read-only). Market-wide
recipes (1-3) need no address. Live-changing data (orders, prices, funding)
will differ from the captures above -- the `Tested` markers fix the point in
time each was verified.
