"""Application entry point."""

from __future__ import annotations

import asyncio
import logging

from .bitcoin import build_bitcoin_source
from .catalog import Catalog
from .config import Config
from .pricing import build_price_source
from .server import BlockclockServer, ServerState, health_handler


async def main() -> None:
    config = Config.from_env()
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    state = ServerState()
    catalog = Catalog(build_bitcoin_source(config), build_price_source(config))
    application = BlockclockServer(catalog, state, config.cache_seconds)
    tcp_server = await asyncio.start_server(
        application.handle,
        config.host,
        config.port,
        limit=256 * 1024 + 4,
    )
    http_server = await asyncio.start_server(
        lambda reader, writer: health_handler(reader, writer, state),
        config.health_host,
        config.health_port,
    )
    logging.getLogger(__name__).info(
        "Blockclock backend listening on %s:%d (health %s:%d, source=%s)",
        config.host,
        config.port,
        config.health_host,
        config.health_port,
        config.bitcoin_source,
    )
    async with tcp_server, http_server:
        await asyncio.gather(tcp_server.serve_forever(), http_server.serve_forever())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
