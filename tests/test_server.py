import asyncio
import unittest

from blockclock_backend.bitcoin import MockBitcoinSource
from blockclock_backend.catalog import Catalog
from blockclock_backend.pricing import ConfiguredPriceSource
from blockclock_backend.protocol import read_message, write_message
from blockclock_backend.server import BlockclockServer, ServerState


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        catalog = Catalog(
            MockBitcoinSource(900001),
            ConfiguredPriceSource(60000.0, "", "", 1, 10),
        )
        self.application = BlockclockServer(catalog, ServerState(), 3600)
        self.server = await asyncio.start_server(self.application.handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    async def connect(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        greeting = await read_message(reader)
        self.assertEqual(greeting["min_version"], [0, 1, 1])
        await write_message(
            writer,
            {"cmd": "client", "arg": {"uuid": "test", "sig": b"x" * 64, "version": "1.2.3"}},
        )
        initial = await read_message(reader)
        self.assertIn("common_tags", initial)
        return reader, writer

    async def test_get_value(self):
        reader, writer = await self.connect()
        await write_message(
            writer,
            {"cmd": "get_value", "arg": "electrum.BTC.block_height", "reqid": 123456},
        )
        response = await read_message(reader)
        self.assertEqual(response["reqid"], 123456)
        self.assertEqual(response["tag_value"]["number"], 900001.0)
        writer.close()
        await writer.wait_closed()

    async def test_groups_and_search(self):
        reader, writer = await self.connect()
        await write_message(writer, {"cmd": "get_groups", "arg": None})
        self.assertIn("all_groups", await read_message(reader))
        await write_message(
            writer, {"cmd": "search", "arg": "block height", "reqid": 111111}
        )
        response = await read_message(reader)
        self.assertIn("electrum.BTC.block_height", response["found"])
        writer.close()
        await writer.wait_closed()

    async def test_get_html_preview(self):
        reader, writer = await self.connect()
        await write_message(
            writer,
            {"cmd": "get_html", "arg": "electrum.BTC.block_height", "reqid": 222222},
        )
        response = await read_message(reader)
        self.assertEqual(response["reqid"], 222222)
        self.assertIn("tag_html", response)
        self.assertIn('class="be-preview"', response["tag_html"])
        self.assertIn("9", response["tag_html"])
        writer.close()
        await writer.wait_closed()

    async def test_nextblock_median_fee(self):
        reader, writer = await self.connect()
        await write_message(
            writer,
            {"cmd": "get_value", "arg": "cm.nextblock.median_fee", "reqid": 333333},
        )
        response = await read_message(reader)
        self.assertEqual(response["reqid"], 333333)
        value = response["tag_value"]
        self.assertFalse(value["is_error"])
        self.assertEqual(value["number"], 6.0)
        self.assertEqual(value["pair"], ["SAT", "VB"])
        self.assertEqual(value["contents"][0], "/SAT/VB")
        writer.close()
        await writer.wait_closed()
