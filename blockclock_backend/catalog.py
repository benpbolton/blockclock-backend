"""Tag catalog exposed to the Blockclock menus."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .bitcoin import BitcoinSnapshot, BitcoinSource, DataSourceError
from .pricing import PriceSource
from .render import DisplayValue, error, numeric, text


@dataclass
class ClientPreferences:
    timezone: str = "UTC"
    swap_separators: bool = False
    hours24: bool = False


Renderer = Callable[[str, "Catalog", ClientPreferences], Awaitable[DisplayValue]]


@dataclass(frozen=True)
class Tag:
    name: str
    label: str
    group: str
    renderer: Renderer


async def _height(tag: str, catalog: "Catalog", _: ClientPreferences) -> DisplayValue:
    snapshot = await catalog.bitcoin.snapshot()
    label = "Electrum Block Height" if tag.startswith("electrum.") else "Bitcoin Block Height"
    return numeric(tag, label, snapshot.height)


async def _difficulty(tag: str, catalog: "Catalog", _: ClientPreferences) -> DisplayValue:
    snapshot = await catalog.bitcoin.snapshot()
    if snapshot.difficulty is None:
        raise DataSourceError("difficulty is unavailable from this node source")
    return numeric(tag, "Bitcoin Difficulty", snapshot.difficulty)


async def _last_block_time(tag: str, catalog: "Catalog", _: ClientPreferences) -> DisplayValue:
    snapshot = await catalog.bitcoin.snapshot()
    if snapshot.block_time is None:
        raise DataSourceError("last block time is unavailable")
    value = dt.datetime.fromtimestamp(snapshot.block_time, tz=dt.timezone.utc).strftime("%H:%M")
    return text(tag, "Last Block Time (UTC)", value)


async def _merkle_root(tag: str, catalog: "Catalog", _: ClientPreferences) -> DisplayValue:
    snapshot = await catalog.bitcoin.snapshot()
    if not snapshot.merkle_root:
        raise DataSourceError("Merkle root is unavailable")
    return text(tag, "Latest Merkle Root", snapshot.merkle_root)


async def _nonce(tag: str, catalog: "Catalog", _: ClientPreferences) -> DisplayValue:
    snapshot = await catalog.bitcoin.snapshot()
    if snapshot.nonce is None:
        raise DataSourceError("block nonce is unavailable")
    return numeric(tag, "Latest Block Nonce", snapshot.nonce)


async def _previous_hash(tag: str, catalog: "Catalog", _: ClientPreferences) -> DisplayValue:
    snapshot = await catalog.bitcoin.snapshot()
    if not snapshot.previous_hash:
        raise DataSourceError("previous block hash is unavailable")
    return text(tag, "Previous Block Hash", snapshot.previous_hash)


async def _mempool_count(tag: str, catalog: "Catalog", _: ClientPreferences) -> DisplayValue:
    snapshot = await catalog.bitcoin.snapshot()
    if snapshot.mempool_transactions is None:
        raise DataSourceError("mempool data requires Bitcoin Core RPC")
    return numeric(tag, "Mempool Transactions", snapshot.mempool_transactions)


async def _mempool_vsize(tag: str, catalog: "Catalog", _: ClientPreferences) -> DisplayValue:
    snapshot = await catalog.bitcoin.snapshot()
    if snapshot.mempool_vsize is None:
        raise DataSourceError("mempool data requires Bitcoin Core RPC")
    return numeric(tag, "Mempool Virtual Bytes", snapshot.mempool_vsize)


async def _hashrate(tag: str, catalog: "Catalog", _: ClientPreferences) -> DisplayValue:
    snapshot = await catalog.bitcoin.snapshot()
    if snapshot.network_hashrate is None:
        raise DataSourceError("network hashrate requires Bitcoin Core RPC")
    return numeric(tag, "Network Hashrate (EH/s)", snapshot.network_hashrate / 1e18, decimals=2)


async def _blocks_to_retarget(tag: str, catalog: "Catalog", _: ClientPreferences) -> DisplayValue:
    snapshot = await catalog.bitcoin.snapshot()
    blocks = 2016 - (snapshot.height % 2016)
    return numeric(tag, "Blocks Until Retarget", blocks)


async def _time_since_block(tag: str, catalog: "Catalog", _: ClientPreferences) -> DisplayValue:
    snapshot = await catalog.bitcoin.snapshot()
    if snapshot.block_time is None:
        raise DataSourceError("last block time is unavailable")
    minutes = max(0, int((dt.datetime.now(dt.timezone.utc).timestamp() - snapshot.block_time) / 60))
    return numeric(tag, "Minutes Since Last Block", minutes, br_text="minutes")


async def _next_block_median_fee(tag: str, catalog: "Catalog", _: ClientPreferences) -> DisplayValue:
    snapshot = await catalog.bitcoin.snapshot()
    if snapshot.next_block_fee_sats_vb is None:
        raise DataSourceError("next-block fee estimate is unavailable from this source")
    fee = snapshot.next_block_fee_sats_vb
    # Match Coinkite: integer sat/vB when >= 1, else keep a little precision.
    display = round(fee) if fee >= 1 else round(fee, 2)
    return numeric(
        tag,
        "Median fee rate predicted for next block",
        display,
        pair=("SAT", "VB"),
    )


async def _price(tag: str, catalog: "Catalog", _: ClientPreferences) -> DisplayValue:
    price = await catalog.price.price_usd()
    return numeric(
        tag,
        "Market price of Bitcoin",
        price,
        pair=("BTC", "USD"),
        symbol="$",
        decimals=0 if price >= 1000 else 2,
    )


async def _coinbase_spot(tag: str, catalog: "Catalog", _: ClientPreferences) -> DisplayValue:
    price = await catalog.price.coinbase_spot_usd()
    return numeric(
        tag,
        "Coinbase BTC-USD Spot",
        price,
        pair=("BTC", "USD"),
        symbol="$",
        decimals=0 if price >= 1000 else 2,
    )


async def _sats_per_dollar(tag: str, catalog: "Catalog", _: ClientPreferences) -> DisplayValue:
    price = await catalog.price.price_usd()
    return numeric(tag, "Sats per Dollar", round(100_000_000 / price), pair=("SAT", "USD"))


async def _clock(tag: str, _: "Catalog", preferences: ClientPreferences) -> DisplayValue:
    try:
        zone = ZoneInfo(preferences.timezone or "UTC")
    except ZoneInfoNotFoundError:
        zone = dt.timezone.utc
    now = dt.datetime.now(zone)
    value = now.strftime("%H:%M" if preferences.hours24 else "%I:%M").lstrip("0")
    return text(tag, f"Time in {preferences.timezone or 'UTC'}", value)


class Catalog:
    GROUPS = [
        ["common", "Common", "Self-hosted essentials"],
        ["blockchain", "Blockchain", "Values from your Bitcoin node"],
        ["datetime", "Date/Time", "Time and date values"],
        ["price", "Fiat Price", "BTC/USD from public spots or config"],
    ]

    def __init__(self, bitcoin: BitcoinSource, price: PriceSource):
        self.bitcoin = bitcoin
        self.price = price
        definitions = [
            Tag("electrum.BTC.block_height", "Electrum Block Height", "blockchain", _height),
            Tag("cm.blockchain.block_height", "Bitcoin Block Height", "blockchain", _height),
            Tag("bitcoin.BTC.block_height", "Bitcoin Block Height", "blockchain", _height),
            Tag("electrum.BTC.difficulty", "Bitcoin Difficulty", "blockchain", _difficulty),
            Tag("electrum.BTC.last_block_time", "Last Block Time", "blockchain", _last_block_time),
            Tag("electrum.BTC.merkle_root", "Latest Merkle Root", "blockchain", _merkle_root),
            Tag("electrum.BTC.nonce", "Latest Block Nonce", "blockchain", _nonce),
            Tag("electrum.BTC.prev_block_hash", "Previous Block Hash", "blockchain", _previous_hash),
            Tag("cm.mempool.transactions", "Mempool Transactions", "blockchain", _mempool_count),
            Tag("bitcoin.mempool.vsize", "Mempool Virtual Bytes", "blockchain", _mempool_vsize),
            Tag("bitcoin.network.hashrate", "Network Hashrate", "blockchain", _hashrate),
            Tag("cm.retarget.blocks_to_retarget", "Blocks Until Retarget", "blockchain", _blocks_to_retarget),
            Tag("cm.mempool.time_since_last_block", "Time Since Last Block", "blockchain", _time_since_block),
            Tag(
                "cm.nextblock.median_fee",
                "Median fee rate predicted for next block",
                "blockchain",
                _next_block_median_fee,
            ),
            Tag("cm.markets.price", "Market price of Bitcoin", "price", _price),
            Tag("coinbase.BTC-USD.spot", "Coinbase BTC-USD Spot", "price", _coinbase_spot),
            Tag("cm.markets.sats_per_dollar", "Sats per Dollar", "price", _sats_per_dollar),
            Tag("memes.moscow_time", "Moscow Time", "price", _sats_per_dollar),
            Tag("datetime.world.a", "Local Time", "datetime", _clock),
            Tag("datetime.world.b", "Local Time", "datetime", _clock),
            Tag("datetime.UTC.time", "UTC Time", "datetime", _clock),
        ]
        self.tags = {tag.name: tag for tag in definitions}

    @property
    def common_tags(self) -> list[str]:
        return [
            "electrum.BTC.block_height",
            "cm.markets.price",
            "cm.markets.sats_per_dollar",
            "memes.moscow_time",
            "datetime.world.a",
        ]

    def group(self, name: str) -> list[str]:
        if name == "common":
            return self.common_tags
        return [tag.name for tag in self.tags.values() if tag.group == name]

    def search(self, query: str) -> list[str]:
        words = [word.lower() for word in query.split() if word]
        matches = []
        for tag in self.tags.values():
            haystack = f"{tag.name} {tag.label}".lower()
            if all(word in haystack for word in words):
                matches.append(tag.name)
        return matches[:50]

    async def render(self, name: str, preferences: ClientPreferences) -> DisplayValue:
        tag = self.tags.get(name)
        if tag is None:
            return error(name, "Unknown Tag", f"unsupported tag: {name}")
        try:
            return await tag.renderer(name, self, preferences)
        except (DataSourceError, OSError, ValueError) as exc:
            return error(name, tag.label, str(exc))
