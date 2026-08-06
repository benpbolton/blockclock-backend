"""Async TCP server implementing the Blockclock Mini pull protocol."""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import json
import logging
import secrets
from dataclasses import dataclass
from typing import Any, Optional

from .catalog import Catalog, ClientPreferences
from .protocol import ProtocolError, read_message, write_message

LOG = logging.getLogger(__name__)


@dataclass
class ServerState:
    active_connections: int = 0
    total_connections: int = 0


class ClientSession:
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        catalog: Catalog,
        state: ServerState,
        block_poll_seconds: float,
    ):
        self.reader = reader
        self.writer = writer
        self.catalog = catalog
        self.state = state
        self.block_poll_seconds = max(5.0, block_poll_seconds)
        self.preferences = ClientPreferences()
        self.authenticated = False
        self._write_lock = asyncio.Lock()
        self._notifier: Optional[asyncio.Task[None]] = None

    @property
    def peer(self) -> str:
        peername = self.writer.get_extra_info("peername")
        return str(peername[0]) if peername else "unknown"

    async def send(self, message: dict[str, Any]) -> None:
        async with self._write_lock:
            await write_message(self.writer, message)

    async def _send_greeting(self) -> None:
        challenge = base64.b32encode(secrets.token_bytes(20))
        await self.send({"min_version": [0, 1, 1], "challenge": challenge})

    async def _send_initial_state(self) -> None:
        now = dt.datetime.now(dt.timezone.utc)
        clock = [
            now.year,
            now.month,
            now.day,
            now.isoweekday(),
            now.hour,
            now.minute,
            now.second,
            now.microsecond,
        ]
        await self.send(
            {
                "reqid": 0,
                "set_time": clock,
                "common_tags": self.catalog.common_tags,
                "your_ip": self.peer,
            }
        )

    async def _block_notifier(self) -> None:
        last_height: Optional[int] = None
        while True:
            try:
                snapshot = await self.catalog.bitcoin.snapshot()
                if last_height is not None and snapshot.height != last_height:
                    await self.send({"new_btc_block": snapshot.height})
                last_height = snapshot.height
            except Exception as exc:  # A notifier failure must not drop the display connection.
                LOG.debug("block notifier for %s: %s", self.peer, exc)
            await asyncio.sleep(self.block_poll_seconds)

    async def _dispatch(self, message: Any) -> None:
        if not isinstance(message, dict):
            raise ProtocolError("command must be a CBOR map")
        command = message.get("cmd")
        argument = message.get("arg")
        request_id = message.get("reqid")
        if not isinstance(command, str):
            raise ProtocolError("command name is missing")

        if command == "client":
            if not isinstance(argument, dict):
                raise ProtocolError("invalid client handshake")
            if not isinstance(argument.get("uuid"), str) or not isinstance(
                argument.get("sig"), bytes
            ):
                raise ProtocolError("invalid client identity")
            self.authenticated = True
            await self._send_initial_state()
            if self._notifier is None:
                self._notifier = asyncio.create_task(self._block_notifier())
            return

        if not self.authenticated:
            raise ProtocolError("client handshake required")

        if command == "timezone":
            if isinstance(argument, str) and len(argument) <= 128:
                self.preferences.timezone = argument
            return
        if command == "swap_sep":
            self.preferences.swap_separators = bool(argument)
            return
        if command == "hours24":
            self.preferences.hours24 = bool(argument)
            return
        if command == "get_groups":
            await self.send({"reqid": request_id or 0, "all_groups": self.catalog.GROUPS})
            return
        if command == "get_group":
            group_name = argument if isinstance(argument, str) else ""
            await self.send({"reqid": request_id or 0, "group_info": self.catalog.group(group_name)})
            return
        if command == "get_value":
            tag_name = argument if isinstance(argument, str) else ""
            value = await self.catalog.render(tag_name, self.preferences)
            await self.send({"reqid": request_id or 0, "tag_value": value.as_dict()})
            return
        if command == "search":
            query = argument if isinstance(argument, str) else ""
            await self.send({"reqid": request_id or 0, "found": self.catalog.search(query)})
            return
        if command == "ping":
            await self.send({"reqid": request_id or 0, "pong": argument})
            return

        LOG.info("ignoring unsupported command %r from %s", command, self.peer)
        if request_id is not None:
            await self.send({"reqid": request_id, "error": f"unsupported command: {command}"})

    async def run(self) -> None:
        self.state.active_connections += 1
        self.state.total_connections += 1
        LOG.info("Blockclock connected from %s", self.peer)
        try:
            await self._send_greeting()
            while True:
                await self._dispatch(await read_message(self.reader))
        except asyncio.IncompleteReadError:
            LOG.info("Blockclock disconnected from %s", self.peer)
        except (ProtocolError, ValueError, TypeError) as exc:
            LOG.warning("protocol error from %s: %s", self.peer, exc)
        except (ConnectionError, OSError) as exc:
            LOG.info("connection ended for %s: %s", self.peer, exc)
        finally:
            if self._notifier is not None:
                self._notifier.cancel()
                try:
                    await self._notifier
                except asyncio.CancelledError:
                    pass
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except (ConnectionError, OSError):
                pass
            self.state.active_connections -= 1


class BlockclockServer:
    def __init__(self, catalog: Catalog, state: ServerState, block_poll_seconds: float):
        self.catalog = catalog
        self.state = state
        self.block_poll_seconds = block_poll_seconds

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await ClientSession(
            reader, writer, self.catalog, self.state, self.block_poll_seconds
        ).run()


async def health_handler(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter, state: ServerState
) -> None:
    try:
        request_line = await asyncio.wait_for(reader.readline(), timeout=2)
        path = request_line.decode("ascii", "replace").split(" ")[1]
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=2)
            if line in (b"\r\n", b"\n", b""):
                break
        if path == "/healthz":
            status = "200 OK"
            body = b'{"status":"ok"}\n'
        elif path == "/status":
            status = "200 OK"
            body = (
                json.dumps(
                    {
                        "status": "ok",
                        "active_connections": state.active_connections,
                        "total_connections": state.total_connections,
                    },
                    separators=(",", ":"),
                ).encode()
                + b"\n"
            )
        else:
            status = "404 Not Found"
            body = b'{"error":"not found"}\n'
        writer.write(
            f"HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
            + body
        )
        await writer.drain()
    except (asyncio.TimeoutError, IndexError, OSError):
        pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass

