# Agent instructions

This file is for coding agents (OpenCode, Claude Code, Codex, Cursor, and
similar tools). Humans may read it; the primary audience is automated
assistants working in this repository.

## Project facts

- Self-hosted **BLOCKCLOCK mini** pull-protocol backend (Python 3.9+, stdlib only).
- No third-party runtime dependencies. Do not add packages unless the user asks.
- Secrets live in `.env` (gitignored). Never commit credentials, cookies, or keys.
- Prefer small, reviewable changes. Do not commit or push unless the user asks.

## Before you change code

1. Read the relevant modules and tests.
2. Match existing style: no new comments unless asked; type hints where nearby code uses them.
3. After behavior changes, run:

```sh
python3 -m unittest discover -v
```

4. Do not claim hardware or node validation that was not performed.

## Language standard: ASD-STE100

Use **ASD-STE100** (Simplified Technical English) for:

- Git commit messages
- Pull request titles and descriptions
- User-facing status text you add in this repo (errors that operators read, README
  procedural steps you rewrite)

Do **not** force STE100 on:

- Protocol field names, tag names, or wire formats (`get_value`, `new_btc_block`)
- Code identifiers, log format strings already in the codebase, or citations

### STE100 rules for this project

1. **One topic per sentence.** Prefer short sentences. Avoid stacked clauses.
2. **Use approved simple verbs** when you can: *add, remove, change, fix, set,
   start, stop, show, hide, read, write, send, get, make, use, check, verify,
   fail, reject, allow, block, connect, disconnect.*
3. **Use active voice.** Write “The server sends a challenge,” not “A challenge
   is sent by the server.”
4. **Use the same word for the same thing.** Prefer project terms: *backend*,
   *Mini*, *node*, *tag*, *frame*, *handshake*, *RPC*, *Electrum*. Do not mix
   synonyms in one message (e.g. do not switch among “device / clock / unit”).
5. **Do not use slang, hype, or marketing tone** in commits or PRs
   (“awesome”, “just”, “simply”, “robustly”, meme proverbs).
6. **Do not use vague connectors** as the main claim (“improve things”,
   “update stuff”, “fix issues”, “WIP”).
7. **State the technical change, then the reason** when a reason helps review.
8. **Use consistent American English spelling** in new prose (`behavior`,
   not `behaviour`) unless you edit an existing British string on purpose.
9. **Avoid noun clusters longer than three words** when a short phrase works
   (“block notification” not “Bitcoin blockchain tip advance notification event”).
10. **Commands and paths stay literal.** Keep code, flags, and paths in backticks
    in PR bodies.

### Commit messages

Format:

```text
<summary in imperative mood, ~72 characters or less>

Optional body: what changed and why. Short sentences.
Optional footer: Refs, Breaking, etc.
```

Rules:

- Imperative mood: “Add Electrum TLS option,” not “Added” or “Adds.”
- First line = complete summary. No trailing period on the subject line.
- Body wraps near 72 characters. Blank line between subject and body.
- One logical change per commit when practical.
- No AI attribution trailers unless the user asks for them.

**Good**

```text
Add health bind defaults to the Compose file

Set HEALTH_HOST to loopback so the status port is not
exposed on all interfaces by default.
```

```text
Fix CBOR decode of firmware float32 values
```

**Bad**

```text
Updated some stuff and improved robustness :)
```

```text
WIP: various fixes for the thing
```

### Pull requests

- **Title:** same style as a commit subject (imperative, specific, STE100).
- **Body structure:**

```markdown
## Summary
- <fact 1>
- <fact 2>

## Test plan
- [ ] python3 -m unittest discover -v
- [ ] <other checks you ran or the reviewer must run>
```

- Summaries are factual lists. No roadmap essays unless the user asks.
- Call out security-sensitive changes (RPC auth, bind addresses, network mode).
- If the Mini or a live node was not tested, say that clearly.

## Security

- Do not expose examples that bind protocol port 21021 to the public internet.
- Prefer read-only Bitcoin RPC credentials in docs and samples.
- Never log passwords, cookie contents, or full `.env` files.

## Out of scope unless requested

- Force-push, amend of published history, or git config changes
- New dependencies, frameworks, or license changes
- Claiming affiliation with Coinkite
