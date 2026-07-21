# How Hyperliquid Perp Funding Works

Funding is the periodic cash transfer between longs and shorts that keeps a
perpetual's mark price tethered to its oracle price. The single most common
mistake when reasoning about Hyperliquid funding is assuming the 8-hour cadence
most CEXes use. **Hyperliquid charges funding every hour.**

Verified live on 2026-07-21 against `api.hyperliquid.xyz/info`. Sources of
truth used: the `predictedFundings`, `metaAndAssetCtxs`, and `fundingHistory`
responses, cross-checked against the Hyperliquid funding docs.

## Interval: hourly, not 8-hourly

- `predictedFundings` reports `"fundingIntervalHours": 1` for the `HlPerp`
  venue on every coin, versus `4` or `8` for `BinPerp`/`BybitPerp` (varies by
  coin) in the same response. Hyperliquid's own venue settles hourly.
- `fundingHistory` returns one row per hour -- consecutive `time` values sit
  about 3_600_000 ms (one hour) apart.
- Each hour, one-eighth of the computed 8-hour-equivalent rate is applied.

Consequence: a Hyperliquid hourly rate is **not** comparable head-to-head with
a CEX 8-hour rate. Multiply the Hyperliquid rate by 8 (or the CEX rate by 1/8)
before comparing, and remember it compounds 24 times a day.

## The formula

```
F_8h   = P_avg + clamp(interest_rate - P_avg, -0.0005, 0.0005)
F_hour = F_8h / 8
```

The formula computes an **8-hour** rate; Hyperliquid then settles every hour,
charging one eighth of it. The `funding` value the API returns is already the
hourly figure (`F_8h / 8`), which is why calm coins read `0.0000125`.

- `P_avg` -- the **average premium** over the hour. The premium is
  `impact_price_difference / oracle_price`, sampled every 5 seconds from the
  impact bid/ask (the average execution price for a standard notional) and
  averaged across the hour.
- `interest_rate` -- a fixed constant: **0.01% per 8 hours = `0.0001`** as an
  8-hour fraction. Positive by convention, so with a flat premium longs pay
  shorts (about 11.6% APR to the short side).
- `clamp(..., -0.0005, 0.0005)` -- the premium-vs-interest term is bounded to
  +/-0.05% over the 8-hour basis.
- A final cap limits total funding to **+/-4% per hour**.

`F_hour` is a per-hour fraction of position notional (the 8-hour `F` divided by
8). It is charged on the position value at each hourly settlement, independent
of your leverage.

## Why so many assets sit at exactly 0.0000125

When the premium is small, the clamp does not bind and the `P_avg` terms
cancel:

```
F_8h   = P_avg + (interest_rate - P_avg) = interest_rate = 0.0001
F_hour = 0.0001 / 8 = 0.0000125
```

So a calm market collapses to exactly the interest baseline. This showed up
live: **ETH** funding read `0.0000125` (premium near zero, the calm-market
baseline), while the `HlPerp` predicted rate across coins was likewise
`0.0000125`.

When the hourly-average premium runs negative enough (below about `-0.0004`),
the `interest_rate - P_avg` term hits the upper `+0.0005` clamp, so `F_8h =
P_avg + 0.0005` and the settled rate drops **below** the `0.0000125` baseline.
Live **BTC** read `funding = 0.0000090784`; **SOL** read `0.0000012413` under a
stronger negative premium. (The `premium` in a ctx snapshot is an instantaneous
sample, not the hour's average that fed the settled rate, so one reading won't
reconcile to the last digit.) All three are consistent with the formula above.

## Where to read it live

- **Current hourly rate per asset:** `metaAndAssetCtxs` -> element 1 ->
  `ctx.funding` (positional to the `universe`). The `premium`, `markPx`, and
  `oraclePx` in the same ctx show the inputs.
- **Next-hour prediction, cross-venue:** `predictedFundings` -- compare
  `HlPerp` against `BinPerp`/`BybitPerp` for the same coin, mindful that the
  other venues quote a longer interval (`fundingIntervalHours`).
- **Realized history for a coin:** `fundingHistory` -- one `{fundingRate,
  premium, time}` row per hour.
- **What a specific account actually paid:** `userFunding` -- one row per
  hourly settlement per position, with the signed `usdc` delta, the position
  `szi`, and the `fundingRate` applied (see `references/api-reference.md`).

## Practical notes

- The sign convention: positive `F` means longs pay shorts. A position's
  accrued funding is also visible per-position as `cumFunding` inside
  `clearinghouseState.assetPositions[].position`.
- Because funding is hourly and small, a position held through a trend pays it
  many times -- funding drag over a multi-day hold is easy to underestimate.
- Do not annualize by multiplying an hourly rate by the CEX 8-hour factor;
  annualize hourly rates by ~8760 hours, and treat `0.0000125` as the
  quiet-market baseline rather than the typical rate.
