# Self-hosted BLOCKCLOCK mini backend

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> **Don't trust. Verify.**

Independent, self-hosted replacement for Coinkite's
`na.blockclockmini.com:21021` data backend. It speaks the Mini's undocumented
cleartext CBOR/TCP **pull** protocol, preserves the normal group/tag menus, and
reads blockchain data from **your own** Bitcoin Core or Electrum server.

The point is simple: stop asking someone else's server what the timechain says.
**Run your own node.** This service just puts that truth on the Mini.

The implementation is dependency-free Python (stdlib only, 3.9+) and ships with
a hardened, read-only Docker Compose service.

> **Not affiliated with Coinkite.** BLOCKCLOCK is a Coinkite product. This
> project is a community reimplementation of the on-the-wire pull protocol
> observed against firmware 1.2.3. No Coinkite source code is included.
>
> **Status:** unit-tested protocol/server paths; hardware and node validation
> still required before relying on it. Don't trust this README alone.

## Rationale

Coinkite does not open-source the BLOCKCLOCK mini pull backend, so every Mini
depends on their cloud for menus, tags, and block notifications. This project
exists so you can run that path on your own node—and so the device stays useful
if vendor cloud or company continuity changes (vendor risk is not theoretical;
see e.g. the [COLDCARD seed-generation advisory](https://blog.coinkite.com/coldcard-mk3-seed-generation-warning/)).

## What works

- Firmware 1.2.3 authentication handshake and `0xbc + 24-bit length` framing
- Groups, tag search, and seven-cell rendered values
- Bitcoin block notifications for the Mini's "Bitcoin Block" update mode
- Bitcoin Core RPC using username/password or a mounted cookie
- Electrum `blockchain.headers.subscribe`, including parsed header fields
- BTC/USD from configurable public spots (average) or static/JSON override
- Local health and connection-status HTTP endpoints

Compatible tag names include the Mini's existing
`electrum.BTC.block_height`, `cm.blockchain.block_height`,
`cm.markets.price`, `coinbase.BTC-USD.spot`, and `cm.markets.sats_per_dollar`,
so common saved display selections continue to make sense.

## Quick start with Bitcoin Core

*Your node, your rules.* Copy the example configuration and fill in a
dedicated, read-only RPC login:

```sh
cp .env.example .env
docker compose up -d --build
docker compose logs -f blockclock-backend
```

The Compose file uses host networking because it is intended to run directly
on a Linux Bitcoin node. Core can remain bound to `127.0.0.1:8332`; the
Blockclock service listens on TCP 21021. The health endpoint remains local at
`http://127.0.0.1:8080/healthz`.

> **Note:** Docker host networking is a Linux feature. On macOS/Windows Docker
> Desktop, either run the service with bare Python (see [Development](#development-and-verification))
> or change `network_mode` and publish ports / point RPC at a reachable host address.

For a Core cookie instead of an RPC username/password, add a read-only mount
to the service in `compose.yaml`:

```yaml
volumes:
  - /path/to/bitcoin/.cookie:/run/bitcoin/.cookie:ro
environment:
  BITCOIN_RPC_COOKIE_FILE: /run/bitcoin/.cookie
```

The container runs as UID 10001, so that user must be able to read the mounted
cookie. A dedicated `rpcauth` login is often simpler and avoids sharing the
node's cookie. Prefer least privilege: this backend only needs to **read**
chain state.

## Electrum instead of Core

Prefer a full node when you can. Electrum is a lighter option—useful, but you
are trusting that server's view of the chain more than your own validation.

Set these values in `.env`:

```dotenv
BITCOIN_SOURCE=electrum
ELECTRUM_HOST=127.0.0.1
ELECTRUM_PORT=50001
ELECTRUM_TLS=false
```

Use port 50002 and `ELECTRUM_TLS=true` for a certificate-validating TLS
Electrum endpoint. Electrum supplies block/header tags and next-block fee
estimates (`blockchain.estimatefee`). Mempool count/vsize and network hashrate
tags require Core RPC and will show an offline/error value.

## Price data

Fiat price is not consensus. Block height is.

Venue URLs live in `.env` only (copy `.env.example`). `cm.markets.price`
averages every venue with a non-empty URL. Comment out a block or set
`PRICE_*_URL=` empty to exclude it. Failed venues are omitted from the average
and logged once until they recover. Results cache for `PRICE_CACHE_SECONDS`
(default 30).

`coinbase.BTC-USD.spot` uses only `PRICE_COINBASE_URL`.

Optional overrides:

```dotenv
BITCOIN_PRICE_USD=64520
```

```dotenv
PRICE_URL=http://127.0.0.1:3000/api/price
PRICE_JSON_PATH=data.usd
```

`PRICE_JSON_PATH` is a dot-separated path. Numeric path components index JSON
arrays—for example, `result.XXBTZUSD.c.0`. Static price wins over `PRICE_URL`;
`PRICE_URL` replaces the multi-venue average when set.

## Point the Mini at it

The cleanest route is the Mini's local admin page:

1. Open the Mini's IP address in a browser.
2. Open **Preferences**.
3. Set **Data Backend** to `your-backend-host`.
4. Use **Test Connection**, save, and reboot if needed.

Alternatively, override local DNS for `na.blockclockmini.com` and resolve it to
this server. The firmware's default port is already 21021.

Run this command on the backend computer to see Mini connection counts:

```sh
curl http://127.0.0.1:8080/status
```

### Health checks

| Path | What it shows |
|------|---------------|
| `/healthz` | `{"status":"ok"}` when the health HTTP server can answer |
| `/status` | Current Mini connections and total connections since the backend started |

These pages show whether the backend can answer an HTTP request. They do not
check the Bitcoin node, price sources, or data on the Mini.

With Compose, these pages are available only on the backend computer at
`http://127.0.0.1:8080` by default. When you run Python directly, the health
HTTP server uses all IPv4 network addresses (`0.0.0.0`) on port 8080. Set
`HEALTH_HOST=127.0.0.1` to keep those pages on the backend computer.

Set `HEALTH_PORT` to change the port. For example, use `HEALTH_PORT=18080` if
another service uses port 8080. Set `HEALTH_PORT=0` or `HEALTH_PORT=` to turn
off the health HTTP server. If you leave the setting out, the port is 8080.

Docker runs `python -m blockclock_backend.healthcheck` every 30 seconds. The
check requests `/healthz` at the address and port in `HEALTH_HOST` and
`HEALTH_PORT`. It connects directly, without an HTTP proxy. For `0.0.0.0` or
an empty host, it connects to `127.0.0.1`. For `::`, it connects to `::1`.
These addresses point back to the computer that runs the backend.

When you turn off the health HTTP server, the check passes without sending
a request. In this case, Docker's `healthy` label does not mean the backend
was checked. This also keeps the check from using another service on port
8080 when the container shares the host's network.

## Supported tags

Chain tags depend on a single `BITCOIN_SOURCE` (`rpc`, `electrum`, or `mock`).
You cannot enable Core and Electrum together in one process. If you run a full
node, prefer `rpc`. Use `electrum` when you only have an Electrum server.
Price and clock tags do **not** use `BITCOIN_SOURCE`.

### By `BITCOIN_SOURCE` (chain / mempool)

| Tag | `rpc` | `electrum` | `mock` |
|-----|:-----:|:----------:|:------:|
| `electrum.BTC.block_height` | yes | yes | yes |
| `cm.blockchain.block_height` | yes | yes | yes |
| `bitcoin.BTC.block_height` | yes | yes | yes |
| `electrum.BTC.difficulty` | yes | yes | yes |
| `electrum.BTC.last_block_time` | yes | yes | yes |
| `electrum.BTC.merkle_root` | yes | yes | yes |
| `electrum.BTC.nonce` | yes | yes | yes |
| `electrum.BTC.prev_block_hash` | yes | yes | yes |
| `cm.retarget.blocks_to_retarget` | yes | yes | yes |
| `cm.mempool.time_since_last_block` | yes | yes | yes |
| `cm.nextblock.median_fee` | yes (`estimatesmartfee`) | yes (`estimatefee`) | yes |
| `cm.mempool.transactions` | yes | no | yes |
| `bitcoin.mempool.vsize` | yes | no | yes |
| `bitcoin.network.hashrate` | yes | no | yes |

Unavailable chain values render as seven-cell `ERROR` with `br_text: offline`.

### Price (independent of `BITCOIN_SOURCE`)

All market tags use `.env` venue URLs or overrides (`BITCOIN_PRICE_USD` /
`PRICE_URL`). They work the same under `rpc`, `electrum`, or `mock`.

| Tag | Group | Needs |
|-----|-------|-------|
| `cm.markets.price` | price / common | venue URLs or override |
| `coinbase.BTC-USD.spot` | price | `PRICE_COINBASE_URL` or override |
| `cm.markets.sats_per_dollar` | price / common | same as `cm.markets.price` |
| `memes.moscow_time` | price / common | same as `cm.markets.price` |

### Date/time (local clock)

| Tag | Group |
|-----|-------|
| `datetime.world.a` | datetime / common |
| `datetime.world.b` | datetime |
| `datetime.UTC.time` | datetime |

### Not yet implemented

Coinkite’s cloud serves more tags than this backend. Examples not yet
implemented (forks welcome):

- Other `cm.nextblock.*` (transactions, reward, fees vs reward, …)
- Most Clark Moody / treasury / exchange-specific tags beyond the price set above
- Mempool count, vsize, and hashrate via Electrum (need Core RPC today)
- Dual `rpc` + `electrum` in one process

Menu groups exposed to the Mini: **Common**, **Blockchain**, **Date/Time**,
**Fiat Price**.

## Configuration reference

All settings are environment variables. See `.env.example` for a starter file.
Copy it, edit locally, and **never commit `.env`**.

| Variable | Default | Description |
|----------|---------|-------------|
| `BLOCKCLOCK_HOST` | `0.0.0.0` | Mini protocol bind address |
| `BLOCKCLOCK_PORT` | `21021` | Mini protocol TCP port |
| `HEALTH_HOST` | `0.0.0.0` (`127.0.0.1` in Compose) | Network address for the health HTTP server |
| `HEALTH_PORT` | `8080` | Port for the health HTTP server; `0` or an empty value turns it off |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `CACHE_SECONDS` | `15` | Bitcoin/price cache TTL; also min block-notify poll interval (floor 5s) |
| `REQUEST_TIMEOUT` | `8` | Seconds for RPC, Electrum, and price HTTP calls |
| `BITCOIN_SOURCE` | `rpc` | `rpc`, `electrum`, or `mock` |
| `BITCOIN_RPC_URL` | `http://127.0.0.1:8332` | Bitcoin Core JSON-RPC URL |
| `BITCOIN_RPC_USER` | _(empty)_ | RPC username |
| `BITCOIN_RPC_PASSWORD` | _(empty)_ | RPC password |
| `BITCOIN_RPC_COOKIE_FILE` | _(empty)_ | Path to Core `.cookie` (alternative to user/pass) |
| `ELECTRUM_HOST` | `127.0.0.1` | Electrum server host |
| `ELECTRUM_PORT` | `50001` | Electrum server port |
| `ELECTRUM_TLS` | `false` | Use TLS (`true`/`1`/`yes`/`on`) |
| `BITCOIN_PRICE_USD` | _(unset)_ | Fixed BTC/USD price (wins over all feeds) |
| `PRICE_URL` | _(empty)_ | Single JSON feed; replaces venue average |
| `PRICE_JSON_PATH` | _(empty)_ | Dot path into the `PRICE_URL` JSON body |
| `PRICE_CACHE_SECONDS` | `30` | Price feed cache TTL |
| `PRICE_COINBASE_URL` | _(from `.env.example`)_ | Empty/unset skips venue |
| `PRICE_COINBASE_JSON_PATH` | `data.amount` | JSON path for Coinbase body |
| `PRICE_KRAKEN_URL` | _(from `.env.example`)_ | Empty/unset skips venue |
| `PRICE_KRAKEN_JSON_PATH` | `result.XXBTZUSD.c.0` | JSON path for Kraken body |
| `PRICE_BITSTAMP_URL` | _(from `.env.example`)_ | Empty/unset skips venue |
| `PRICE_BITSTAMP_JSON_PATH` | `last` | JSON path for Bitstamp body |
| `PRICE_GEMINI_URL` | _(from `.env.example`)_ | Empty/unset skips venue |
| `PRICE_GEMINI_JSON_PATH` | `last` | JSON path for Gemini body |
| `MOCK_BLOCK_HEIGHT` | `840000` | Height used when `BITCOIN_SOURCE=mock` |

## Security boundary

The firmware protocol is unencrypted and server replies are unsigned. The
client handshake uses a fleet-wide firmware key, so it is not meaningful
per-device authorization: **any host that can reach TCP 21021 can complete the
handshake and pull tags.** You probably don't want to expose TCP 21021
broadly—firewall it to the Mini/VPN, keep the device on an IoT VLAN, and
prefer a private DNS/VPN route to a public Internet listener.

See [SECURITY.md](SECURITY.md) for reporting and design-boundary notes.

This is a display feed, not a wallet. Still apply the same instincts:
minimize attack surface, don't share more credentials than needed, and assume
anything on a cleartext LAN hop can be observed.

Compose hardening defaults:

- `read_only: true` root filesystem with a small `/tmp` tmpfs
- `cap_drop: ALL` and `no-new-privileges`
- Non-root UID `10001` inside the image
- Health HTTP bound to loopback in Compose

This replaces only the normal data backend. Opendime balance lookups and
transaction broadcasting use the separately configured Esplora-compatible
URLs in the Mini—**not your keys, not your coins** still applies: point those
at explorers or services *you* trust, or don't use the Blockclock Mini for checking them.

## Project layout

```
blockclock_backend/
  __main__.py   # entry point: TCP + health servers
  config.py     # environment → Config
  protocol.py   # 0xbc framing
  cbor.py       # minimal CBOR codec
  server.py     # session, commands, health HTTP
  healthcheck.py # container health check (HEALTH_HOST/HEALTH_PORT)
  catalog.py    # groups, tags, renderers
  bitcoin.py    # Core RPC / Electrum / mock sources
  pricing.py    # static or JSON price
  render.py     # seven-cell display values
tests/          # unittest suite
compose.yaml    # hardened host-network service
Dockerfile
```

## Development and verification

Requires Python 3.9+. No third-party packages. Read the code—**verify**, then
run it.

Run locally without a node:

```sh
BITCOIN_SOURCE=mock BITCOIN_PRICE_USD=64520 python3 -m blockclock_backend
```

Optional install in editable mode:

```sh
python3 -m pip install -e .
```

Run the test suite:

```sh
python3 -m unittest discover -v
```

The tests include a captured firmware-compatible greeting frame, CBOR codec
round trips, exact seven-cell block/price render shapes, and a full async
client/server exchange. Green tests are necessary, not sufficient—confirm
against your Mini and node before you rely on it.

## Protocol summary

Every message is a four-byte big-endian header followed by one CBOR object.
The high header byte is `0xbc`; the remaining 24 bits are the payload length.
The server sends a challenge, then accepts the firmware's `client` message.
Commands used by firmware 1.2.3 are `timezone`, `swap_sep`, `hours24`,
`get_groups`, `get_group`, `get_value`, `get_html`, `search`, and `ping`.

`get_html` is an **admin UI preview** only: the Mini local portal asks for a
tag name and the backend returns `{tag_html: ...}` — a small HTML table that
mimics the seven digit cells (`be-preview`). It is not a firmware check, not
a notice channel, and not the tag catalog. This server mocks Coinkite's shape
from the same `DisplayValue` used by `get_value`.

After handshake the server may push `{"new_btc_block": <height>}` when the
polled chain tip advances (interval ≈ `CACHE_SECONDS`, minimum 5s).

The protocol was reverse-engineered from the published 1.2.3 firmware behavior
and the live Coinkite backend (observed August 2026). No Coinkite source code
is included. Re-check against firmware and wire captures as releases move—
the timechain is slow; vendor firmware is not.

## Related work

Most community tools use Coinkite's **documented local push API**
([blockclockmini.com/api](https://blockclockmini.com/api.html)) instead of
replacing the pull backend:

- [Umbrel-Blockclock-Adapter](https://github.com/billerickson/Umbrel-Blockclock-Adapter) —
  push values from an Umbrel node; air-gap friendly
- [blockpilot](https://github.com/w3bbd3v/blockpilot) — web control plane and
  scheduled push commands

This project is different: the Mini keeps its menus, tag search, and
Bitcoin-block update mode by talking to you as if you were Coinkite's backend.
Same goal, different trust model—pick the path you can actually verify.

## License

MIT. Free software: study it, fork it, run it. See [LICENSE](LICENSE).

*Tick tock, next block.*
