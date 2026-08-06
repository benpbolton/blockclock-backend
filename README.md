# Self-hosted BLOCKCLOCK mini backend

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Independent, self-hosted replacement for Coinkite's
`na.blockclockmini.com:21021` data backend. It speaks the Mini's undocumented
cleartext CBOR/TCP **pull** protocol, preserves the normal group/tag menus, and
reads blockchain data from your own Bitcoin Core or Electrum server.

The implementation is dependency-free Python (stdlib only, 3.9+) and ships with
a hardened, read-only Docker Compose service.

> **Not affiliated with Coinkite.** BLOCKCLOCK is a Coinkite product. This
> project is a community reimplementation of the on-the-wire pull protocol
> observed against firmware 1.2.3. No Coinkite source code is included.
>
> **Status:** unit-tested protocol/server paths; end-to-end validation on a
> real Mini is welcome. Treat as experimental until you confirm it with your
> device and node.

## What works

- Firmware 1.2.3 authentication handshake and `0xbc + 24-bit length` framing
- Groups, tag search, and seven-cell rendered values
- Bitcoin block notifications for the Mini's "Bitcoin Block" update mode
- Bitcoin Core RPC using username/password or a mounted cookie
- Electrum `blockchain.headers.subscribe`, including parsed header fields
- Optional static or JSON-fed BTC/USD price
- Local health and connection-status HTTP endpoints

Compatible tag names include the Mini's existing
`electrum.BTC.block_height`, `cm.blockchain.block_height`,
`cm.markets.price`, and `cm.markets.sats_per_dollar`, so common saved display
selections continue to make sense.

## Quick start with Bitcoin Core

Copy the example configuration and fill in a dedicated, read-only RPC login:

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
node's cookie.

## Electrum instead of Core

Set these values in `.env`:

```dotenv
BITCOIN_SOURCE=electrum
ELECTRUM_HOST=127.0.0.1
ELECTRUM_PORT=50001
ELECTRUM_TLS=false
```

Use port 50002 and `ELECTRUM_TLS=true` for a certificate-validating TLS
Electrum endpoint. Electrum supplies block/header tags; mempool and network
hashrate tags require Core RPC and will show an offline/error value.

## Price data is opt-in

No third-party price server is contacted by default. You can set a fixed value:

```dotenv
BITCOIN_PRICE_USD=64520
```

Or point the service at any JSON endpoint, including one you self-host:

```dotenv
PRICE_URL=http://127.0.0.1:3000/api/price
PRICE_JSON_PATH=data.usd
```

`PRICE_JSON_PATH` is a dot-separated path. Numeric path components index JSON
arrays—for example, `result.XXBTZUSD.c.0`. If both are set, `BITCOIN_PRICE_USD`
wins.

## Point the Mini at it

The cleanest route is the Mini's local admin page:

1. Open the Mini's IP address in a browser.
2. Open **Preferences**.
3. Set **Data Backend** to `your-backend-host:21021`.
4. Use **Test Connection**, save, and reboot if needed.

Alternatively, override local DNS for `na.blockclockmini.com` and resolve it to
this server. The firmware's default port is already 21021.

Check connection state locally with:

```sh
curl http://127.0.0.1:8080/status
```

### Health endpoints

| Path       | Purpose                                      |
|------------|----------------------------------------------|
| `/healthz` | Liveness probe (`{"status":"ok"}`)           |
| `/status`  | Active and total Mini connection counts      |

Compose binds health to `127.0.0.1:8080` by default. Bare `python -m` runs bind
health to `0.0.0.0:8080` unless `HEALTH_HOST` is set.

## Supported tags

| Tag | Group | Needs |
|-----|-------|-------|
| `electrum.BTC.block_height` | blockchain / common | any source |
| `cm.blockchain.block_height` | blockchain | any source |
| `bitcoin.BTC.block_height` | blockchain | any source |
| `electrum.BTC.difficulty` | blockchain | any source |
| `electrum.BTC.last_block_time` | blockchain | any source |
| `electrum.BTC.merkle_root` | blockchain | any source |
| `electrum.BTC.nonce` | blockchain | any source |
| `electrum.BTC.prev_block_hash` | blockchain | any source |
| `cm.retarget.blocks_to_retarget` | blockchain | any source |
| `cm.mempool.time_since_last_block` | blockchain | any source |
| `cm.mempool.transactions` | blockchain | Core RPC |
| `bitcoin.mempool.vsize` | blockchain | Core RPC |
| `bitcoin.network.hashrate` | blockchain | Core RPC |
| `cm.markets.price` | price / common | price config |
| `cm.markets.sats_per_dollar` | price / common | price config |
| `memes.moscow_time` | price / common | price config |
| `datetime.world.a` | datetime / common | local clock |
| `datetime.world.b` | datetime | local clock |
| `datetime.UTC.time` | datetime | local clock |

Menu groups: **Common**, **Blockchain**, **Date/Time**, **Fiat Price**.

Unavailable values render as seven-cell `ERROR` with `br_text: offline`.

## Configuration reference

All settings are environment variables. See `.env.example` for a starter file.

| Variable | Default | Description |
|----------|---------|-------------|
| `BLOCKCLOCK_HOST` | `0.0.0.0` | Mini protocol bind address |
| `BLOCKCLOCK_PORT` | `21021` | Mini protocol TCP port |
| `HEALTH_HOST` | `0.0.0.0` (`127.0.0.1` in Compose) | Health HTTP bind address |
| `HEALTH_PORT` | `8080` | Health HTTP port |
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
| `BITCOIN_PRICE_USD` | _(unset)_ | Fixed BTC/USD price |
| `PRICE_URL` | _(empty)_ | JSON price endpoint URL |
| `PRICE_JSON_PATH` | _(empty)_ | Dot path into the price JSON body |
| `MOCK_BLOCK_HEIGHT` | `840000` | Height used when `BITCOIN_SOURCE=mock` |

## Security boundary

The firmware protocol is unencrypted and server replies are unsigned. The
client handshake uses a fleet-wide firmware key, so it is not meaningful
per-device authorization. Do not expose TCP 21021 broadly: firewall it to the
Mini/VPN, keep the device on an IoT VLAN, and prefer a private DNS/VPN route to
a public Internet listener.

Compose hardening defaults:

- `read_only: true` root filesystem with a small `/tmp` tmpfs
- `cap_drop: ALL` and `no-new-privileges`
- Non-root UID `10001` inside the image
- Health HTTP bound to loopback in Compose

This replaces only the normal data backend. Opendime balance lookups and
transaction broadcasting use the separately configured Esplora-compatible
URLs in the Mini and should be pointed at services you trust as well.

## Project layout

```
blockclock_backend/
  __main__.py   # entry point: TCP + health servers
  config.py     # environment → Config
  protocol.py   # 0xbc framing
  cbor.py       # minimal CBOR codec
  server.py     # session, commands, health HTTP
  catalog.py    # groups, tags, renderers
  bitcoin.py    # Core RPC / Electrum / mock sources
  pricing.py    # static or JSON price
  render.py     # seven-cell display values
tests/          # unittest suite
compose.yaml    # hardened host-network service
Dockerfile
```

## Development and verification

Requires Python 3.9+. No third-party packages.

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
client/server exchange.

## Protocol summary

Every message is a four-byte big-endian header followed by one CBOR object.
The high header byte is `0xbc`; the remaining 24 bits are the payload length.
The server sends a challenge, then accepts the firmware's `client` message.
Commands used by firmware 1.2.3 are `timezone`, `swap_sep`, `hours24`,
`get_groups`, `get_group`, `get_value`, `search`, and `ping`.

After handshake the server may push `{"new_btc_block": <height>}` when the
polled chain tip advances (interval ≈ `CACHE_SECONDS`, minimum 5s).

The protocol was reverse-engineered from the published 1.2.3 firmware behavior
and the live Coinkite backend (observed August 2026). No Coinkite source code
is included.

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

## License

MIT. See [LICENSE](LICENSE).
