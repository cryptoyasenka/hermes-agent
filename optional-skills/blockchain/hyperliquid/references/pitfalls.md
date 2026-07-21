# Hyperliquid Skill -- Pitfalls & Gotchas

Hard-won details about the read-only `/info` endpoint. All reads are public
(no key, no signing); nothing here mutates state.

## Orders

### 1. `historicalOrders` is not your live order book

The `orders` command sends `{"type": "historicalOrders", "user": ...}`. That
returns recent order *history* -- rows wrapped as `{"order": {...}, "status":
"filled", "statusTimestamp": ...}`, including filled and canceled orders, capped
to a recent window (2000 rows observed). It does **not** tell you what is
resting on the book right now.

For live resting orders, query one of these directly (verified live):

```bash
# rich: includes trigger / TP-SL metadata, flat array of resting orders
curl -s https://api.hyperliquid.xyz/info -H 'Content-Type: application/json' \
  -d '{"type":"frontendOpenOrders","user":"0x..."}'

# lean: coin/side/price/size/oid only
curl -s https://api.hyperliquid.xyz/info -H 'Content-Type: application/json' \
  -d '{"type":"openOrders","user":"0x..."}'
```

`frontendOpenOrders` returns only currently-resting orders and carries no
`status` wrapper. If a user asks "what orders do I have open", `historicalOrders`
(and today's `orders` command) will mislead -- reach for `frontendOpenOrders`.
See `references/api-reference.md` for both shapes.

## Funding

### 2. Funding is hourly, not 8-hourly

Unlike most CEXes, Hyperliquid settles funding **every hour**
(`predictedFundings` reports `fundingIntervalHours: 1` for `HlPerp`;
`fundingHistory` rows are 1 hour apart). Do not compare a Hyperliquid hourly
rate directly against a Binance/Bybit 8-hour rate, and do not annualize with an
8h factor. Full mechanics and the exact formula are in
`references/funding-explained.md`.

### 3. A `0.0000125` funding rate is the quiet-market baseline, not the norm

When the premium is small the funding formula collapses to exactly the interest
baseline `0.0000125` per hour. Seeing that value across many coins means calm
markets, not a data error.

## Rate limits & pagination

### 4. `/info` is rate-limited by weight -- back off on 429

Large or rapid queries can return HTTP 429. Prefer batch types (`allMids`,
`metaAndAssetCtxs`) over many single-coin calls, and retry with backoff. The
bundled client already retries 429 with a short sleep.

### 5. History endpoints are capped rolling windows, not archives

`userFills` / `userFillsByTime`, `historicalOrders`, and `userFunding` each
return a recent capped window (2000, 2000, and 500 rows observed
respectively) -- not full account history. For a wider range, paginate with
later `startTime` values; do not assume a single call is the complete record.

## Data shape

### 6. Every number is a string

Prices, sizes, funding rates, PnL -- all returned as JSON strings by design.
Convert to `float`/`Decimal` before arithmetic, and do not rely on JSON numeric
types.

### 7. Asset-context arrays are positional to `universe`

`metaAndAssetCtxs` and `spotMetaAndAssetCtxs` return `[meta, ctxs]` where
`ctxs[i]` describes `meta.universe[i]`. Join by index, not by a name key -- the
ctx objects do not repeat the coin name.

### 8. `candleSnapshot` params are nested under `req`

Unlike other types, `candleSnapshot` puts its params in a nested object:
`{"type": "candleSnapshot", "req": {"coin": ..., "interval": ..., "startTime":
..., "endTime": ...}}`. Top-level params are silently ignored.

## Identifiers

### 9. Spot aliases and HIP-3 prefixes are valid identifiers

Spot pairs may appear as a friendly name (`PURR/USDC`) or an alias (`@1`,
`@107`); both are valid. HIP-3 / builder markets prefix the coin with the DEX
name, e.g. `mydex:BTC`. `allMids` also exposes builder ids like `#5100`.

### 10. `perpDexs[0]` is `null`

The first element of the `perpDexs` array is `null` -- that slot is the native
first-party perp DEX. Builder-deployed DEXs are the later, non-null elements.
Do not treat the leading `null` as an error.

### 11. Position size `szi` is signed

In `clearinghouseState.assetPositions[].position`, `szi` is negative for shorts
and positive for longs. Per-position accrued funding is under the same
object's `cumFunding`.

## Endpoint & snapshots

### 12. Testnet is a different host

Mainnet is `https://api.hyperliquid.xyz/info`; testnet is
`https://api.hyperliquid-testnet.xyz/info`. Same protocol, different data. The
client honors `HYPERLIQUID_API_URL` for this.

### 13. `l2Book` is a point-in-time snapshot

The order book response is a single instant (`levels[0]` bids, `levels[1]`
asks), not a stream or time series. Re-request for a fresh snapshot; do not
diff two snapshots as if they were a continuous feed.

## CLI-specific

### 14. `review` is heuristic; `export` is not a backtester

The `review` command infers fee drag, concentration, and counter-trend losses
from fills alone -- it cannot reconstruct true intent, order-placement quality,
or real slippage. The `export` command writes a normalized candle+funding
dataset, not a fill/slippage model; you still supply your own execution
assumptions.
