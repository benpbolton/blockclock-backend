# Security policy

## Report a vulnerability

Report security issues privately. Do not open a public GitHub issue for a
new vulnerability.

- Prefer GitHub Security Advisories on this repository when available.
- Otherwise contact the maintainer through the GitHub profile linked from the
  repository.

Include steps to reproduce, affected versions or commit, and impact. Allow
reasonable time for a fix before public disclosure.

## Design boundary (not novel bugs)

These properties are intentional or inherited from the Mini firmware protocol.
Do not report them as vulnerabilities in this project alone:

- Cleartext CBOR/TCP on port 21021; server replies are not signed
- Handshake is not per-device access control; any client that can reach the
  port can complete the session shape and pull display tags
- Health HTTP is a local status surface, not an authenticated admin API

Operator risk: expose TCP 21021 only to the Mini or a trusted network path.
Prefer a private LAN, IoT VLAN, or VPN. Do not publish 21021 on the public
Internet.

## Credentials

- Never commit `.env`, RPC cookies, or passwords
- Prefer a dedicated read-only Bitcoin Core `rpcauth` user over sharing the
  node cookie
- Do not log passwords, cookie contents, or full environment dumps

## Scope

This software is a display data backend. It is not a wallet and does not hold
private keys. Opendime balance and broadcast URLs on the Mini are separate
from this service.
