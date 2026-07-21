---
name: hyperliquid
description: Hyperliquid market data, account history, trade review.
version: 0.1.0
author: Hugo Sequier (Hugo-SEQUIER), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Hyperliquid, Blockchain, Crypto, Trading, Perpetuals, Spot, DeFi]
    related_skills: []
---

# Hyperliquid Skill

Query Hyperliquid market and account data through the public `/info` endpoint.
Read-only — no API key, no signing, no order placement.

12 commands: `dexs`, `markets`, `spots`, `candles`, `funding`, `l2`, `state`,
`spot-balances`, `fills`, `orders`, `review`, `export`. Stdlib only
(`urllib`, `json`, `argparse`).

---

## When to Use

- User asks for Hyperliquid perp or spot market data, candles, funding, or L2 book
- User wants to inspect a wallet's perp positions, spot balances, fills, or orders
- User wants a post-trade review combining recent fills with market context
- User wants to inspect builder-deployed perp dexs or HIP-3 markets
- User wants a normalized JSON export of candles + funding for backtesting prep

---

## Prerequisites

Stdlib only — no external packages, no API key.

The script reads `${HERMES_HOME:-~/.hermes}/.env` for two optional defaults:

- `HYPERLIQUID_API_URL` — defaults to `https://api.hyperliquid.xyz`. Set to
  `https://api.hyperliquid-testnet.xyz` for testnet.
- `HYPERLIQUID_USER_ADDRESS` — default address for `state`, `spot-balances`,
  `fills`, `orders`, and `review`. If unset, pass the address as the first
  positional argument.

A project `.env` in the current working directory is honored as a dev fallback.

Helper script: `~/.hermes/skills/blockchain/hyperliquid/scripts/hyperliquid_client.py`

---

## How to Run

Invoke through the `terminal` tool:

```bash
python3 ~/.hermes/skills/blockchain/hyperliquid/scripts/hyperliquid_client.py <command> [args]
```

Add `--json` to any command for machine-readable output.

---

## Quick Reference

```bash
hyperliquid_client.py dexs
hyperliquid_client.py markets [--dex DEX] [--limit N] [--sort volume|oi|funding_abs|change_abs|name]
hyperliquid_client.py spots [--limit N]
hyperliquid_client.py candles <coin> [--interval 1h] [--hours 24] [--limit N]
hyperliquid_client.py funding <coin> [--hours 72] [--limit N]
hyperliquid_client.py l2 <coin> [--levels N]
hyperliquid_client.py state [address] [--dex DEX]
hyperliquid_client.py spot-balances [address] [--limit N]
hyperliquid_client.py fills [address] [--hours N] [--limit N] [--aggregate-by-time]
hyperliquid_client.py orders [address] [--limit N]
hyperliquid_client.py review [address] [--coin COIN] [--hours N] [--fills N]
hyperliquid_client.py export <coin> [--interval 1h] [--hours N] [--output PATH]
```

For `state`, `spot-balances`, `fills`, `orders`, and `review`, the address is
optional when `HYPERLIQUID_USER_ADDRESS` is set in `${HERMES_HOME:-~/.hermes}/.env`.

Deeper material lives in the reference files (load on demand):

| Reference | Contents |
|-----------|----------|
| `references/api-reference.md` | Every read-only `/info` request type -- bodies, response shapes, and which command wraps each |
| `references/funding-explained.md` | How perp funding works -- hourly cadence, the exact formula, and where to read it live |
| `references/recipes.md` | 7 tested read-only recipes, each a real `/info` call with its captured response |
| `references/pitfalls.md` | Gotchas -- live-vs-historical orders, hourly funding, capped windows, string numbers |

---

## Procedure

Run commands through the `terminal` tool (full invocation and flags are in
Quick Reference above); add `--json` for machine-readable output.

1. **Discover** -- `dexs`, `markets`, `spots` to find markets. `--dex` applies
   to perp endpoints only; HIP-3 markets are addressed as `dex:COIN`, and spot
   pairs may show as `PURR/USDC` or an alias like `@107`.
2. **Market data** -- `candles` and `funding` for history, `l2` for a live
   book snapshot. Time-range endpoints paginate; widen the window with a later
   `startTime` or use `export`.
3. **Account** -- `state` (perp positions), `spot-balances` (spot inventory),
   `fills` and `orders` for recent activity.
4. **Review** -- `review` combines recent fills with market context (realized
   PnL, fees, win/loss counts, per-coin trend and average funding, plus
   heuristics). Start here to find problem coins or windows, then drill down
   with `fills`, `candles`, and `funding`, judging decision quality separately
   from outcome.
5. **Export** -- `export` writes a normalized candle + funding dataset for
   backtest prep; use `--end-time-ms` for a reproducible window.

To go beyond the wrapped commands -- live resting orders
(`frontendOpenOrders`), cross-venue predicted funding (`predictedFundings`),
funding actually paid (`userFunding`), portfolio history, all mids -- POST the
raw `/info` request directly. Bodies, shapes, and tested examples are in
`references/api-reference.md` and `references/recipes.md`.

---

## Pitfalls

- The `orders` command sends `historicalOrders` -- recent order *history*, not
  live resting orders. For open orders POST `frontendOpenOrders` / `openOrders`
  directly (`references/api-reference.md`).
- Funding is charged **hourly**, not every 8h -- never compare a Hyperliquid
  rate head-to-head with a CEX 8h rate (`references/funding-explained.md`).
- Info endpoints are rate-limited; history types (`fills`, `orders`,
  `userFunding`) return capped rolling windows, not full archives -- paginate
  with `startTime`.
- All response numbers are strings; asset-context arrays are positional to
  `universe`; `l2` is a point-in-time snapshot, not a time series.

Full list -- spot aliases, HIP-3 prefixes, `perpDexs[0]` null, `candleSnapshot`
nested params, testnet host, and the `review` / `export` caveats -- is in
`references/pitfalls.md`.

---

## Verification

```bash
python3 ~/.hermes/skills/blockchain/hyperliquid/scripts/hyperliquid_client.py \
  markets --limit 5
```

Should print the top Hyperliquid perp markets by 24h notional volume.
