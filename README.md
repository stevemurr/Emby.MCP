# Emby.MCP

[![Version](https://img.shields.io/badge/version-0.3.1-blue.svg)](https://github.com/stevemurr/Emby.MCP/releases)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)
[![License: GPL v3](https://img.shields.io/badge/license-GPLv3-green.svg)](LICENSE.txt)
[![Tests](https://img.shields.io/badge/tests-301%20passing-brightgreen.svg)](#development)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)](#development)

A [Model Context Protocol](https://modelcontextprotocol.io/) server that connects an
[Emby media server](https://emby.media/) to any MCP-compatible AI client, letting you browse, search,
queue and play your own media collection in natural language.

Ask Claude to *"find the BBC radio dramas with Bill Nighy in the cast and queue them on the living room
speaker"*, and it will search your library by lyrics metadata, build a playlist, and start playback.

> **Not affiliated with, or endorsed by, [Emby LLC](https://emby.media/).**

## Contents

[Features](#features) · [Requirements](#requirements) · [Installation](#installation) ·
[Configuration](#configuration) · [Connecting an AI client](#connecting-an-ai-client) ·
[CLI reference](#cli-reference) · [Usage tips](#usage-tips) · [Architecture](#architecture) ·
[Development](#development) · [Troubleshooting](#troubleshooting) · [Credits](#credits) · [License](#license)

## Features

- **Library browsing** — list libraries and the genres within them, and scope a session to one library.
- **Rich search** — by title, album, artist, genre, release year, and free text in lyrics or description.
  Results are returned in size-limited chunks so large libraries do not overwhelm the model's context.
- **Playlist management** — create, rename, reorder, add and remove items, and share with other Emby
  users at a chosen access level.
- **Playback control** — list active player sessions, read their play queues, and play, pause, seek,
  skip or transfer a queue to another device.

### MCP tools

The server exposes 20 tools. Names and docstrings are written for model comprehension, so the client
generally picks the right one without being told.

| Area | Tools |
|---|---|
| Users | `retrieve_user_list` |
| Libraries | `retrieve_library_list`, `select_library`, `retrieve_current_library`, `retrieve_genre_list` |
| Search | `search_for_item`, `retrieve_next_search_chunk` |
| Playlists | `create_playlist`, `modify_playlist_name`, `retrieve_playlist_list`, `retrieve_playlist_items`, `add_items_to_playlist`, `remove_items_from_playlist`, `reorder_items_on_playlist` |
| Sharing | `share_playlist_public`, `share_playlist_user_access`, `stop_sharing_playlist` |
| Players | `retrieve_player_list`, `retrieve_player_queue`, `control_media_player` |

## Requirements

| | |
|---|---|
| Python | 3.13 or newer |
| Package manager | [uv](https://docs.astral.sh/uv/) |
| Emby server | A reachable [Emby Media Server](https://emby.media/about.html) with a media library |
| AI client | Any MCP client with **Tools** support — see the [client matrix](https://modelcontextprotocol.io/clients) |

Python dependencies (`mcp[cli]<2`, `embyclient`, `typer`, `dotenv`, `unidecode`) are installed by `uv sync`.

> `mcp` is pinned below 2.x, which removed the `mcp.server.fastmcp` API this server is built on.

## Installation

```bash
git clone https://github.com/stevemurr/Emby.MCP.git
cd Emby.MCP
uv sync
```

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
pip install uv
git clone https://github.com/stevemurr/Emby.MCP.git
cd Emby.MCP
uv sync --link-mode=copy
```

If `uv` is not found afterwards, add `%USERPROFILE%\AppData\Roaming\Python\Python313\Scripts` to your
`Path` via Settings → System → About → Advanced system settings → Environment Variables.
</details>

That is the whole installation — there is no patch step.

### About the SDK corrections

The official [`embyclient`](https://pypi.org/project/embyclient/) SDK has two defects that would
otherwise stop this server working:

- `Configuration.auth_settings()` never defines the `embyauth` scheme that the SDK's own endpoints ask
  for, so authenticated requests go out with no `X-Emby-Token` header.
- `get_users_itemaccess()` rejects the `ItemId` parameter, so per-playlist sharing cannot be read.

`emby_mcp/sdk_patches.py` corrects both in memory when the package is imported. The installed SDK is
never modified, so nothing has to be reapplied after `uv sync` and upgrading `embyclient` cannot
silently revert the fixes.

## Configuration

Create a `.env` file in the project root. It is git-ignored, so your credentials stay local.

```ini
# Required
EMBY_SERVER_URL="http://localhost:8096"
EMBY_USERNAME="user"
EMBY_PASSWORD="pass"

# Optional
EMBY_VERIFY_SSL=True
LLM_MAX_ITEMS=100
```

| Variable | Required | Default | Notes |
|---|---|---|---|
| `EMBY_SERVER_URL` | yes | — | Base URL of your Emby server, including scheme and port |
| `EMBY_USERNAME` | yes | — | Emby account the server logs in as |
| `EMBY_PASSWORD` | yes | — | Password for that account |
| `EMBY_VERIFY_SSL` | no | `True` | Set false for a self-signed certificate. Accepts `true/1/yes/y/on` |
| `LLM_MAX_ITEMS` | no | `100` | Maximum items per search chunk. Must be a positive whole number; anything else falls back to the default |

Any variable already set in the environment can be used instead of the file, and `--env` points any
command at a different file.

> **Tip:** create a dedicated Emby user for this server so you can limit what it can see and do.
> Note that listing Emby users — and therefore per-user playlist sharing — needs an account with
> administrator rights; without them the user list comes back empty.

### Tuning `LLM_MAX_ITEMS`

Items with rich metadata average roughly 1,800 bytes each as JSON. Every model has a per-tool-call
ingestion limit, so this setting trades round trips against the risk of the client refusing an
oversized response. Lower it if searches get truncated or refused.

## Quick start

Verify the installation before wiring up a client:

```bash
uv run emby-mcp test-connection     # authenticate and log out again
uv run emby-mcp list-libraries      # list libraries with their IDs
uv run emby-mcp search "star" -L Movies --limit 5
```

```
Library                        Type            ID
-------------------------------------------------------------------------------------
Movies                         movies          96047
TV Shows                       tvshows         96049
Audiobooks                     audiobooks      16887632
...
✓ Found 11 libraries
```

## Connecting an AI client

The server speaks MCP over stdio. Every client needs the same thing: run `emby-mcp serve` with this
project as the working directory.

### Claude Desktop

Open **Settings → Developer → Edit Config** and add:

```json
{
  "mcpServers": {
    "Emby": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/Emby.MCP", "emby-mcp", "serve"]
    }
  }
}
```

On Windows use `"uv.exe"` and escape path separators as `\\`:

```json
{
  "mcpServers": {
    "Emby": {
      "command": "uv.exe",
      "args": ["run", "--directory", "C:\\path\\to\\Emby.MCP", "emby-mcp", "serve"]
    }
  }
}
```

Fully quit Claude Desktop (File → Exit, not just closing the window) and reopen it. MCP requires a paid
plan; the free tier does not support it.

### VS Code / GitHub Copilot

Requires VS Code 1.102 or newer. Follow
[Add an MCP Server](https://code.visualstudio.com/docs/copilot/chat/mcp-servers#_add-an-mcp-server) and
put the same command in `mcp.json`:

```json
{
  "servers": {
    "Emby": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/Emby.MCP", "emby-mcp", "serve"]
    }
  }
}
```

Then use it from [agent mode](https://code.visualstudio.com/docs/copilot/chat/mcp-servers#_use-mcp-tools-in-agent-mode).

### Any other client

Point it at `uv run --directory /path/to/Emby.MCP emby-mcp serve` over stdio. The server reports itself
as `Emby.MCP` and advertises the 20 tools listed above.

## CLI reference

```
uv run emby-mcp [--env PATH] [--debug] COMMAND
```

| Command | Purpose |
|---|---|
| `serve` | Run the MCP server over stdio. This is what AI clients invoke |
| `test-connection` | Authenticate against Emby and report success or the failure reason |
| `list-libraries` | List libraries with type and ID. `--format json` for machine-readable output |
| `search QUERY` | Search for audio and video items. `--library/-L` to scope, `--limit/-l` to cap results |
| `debug` | Interactive harness that exercises the underlying Emby functions against a live server |
| `version` | Show the version, Python version, and platform |

Global options: `--env/-e` selects a `.env` file, `--debug/-d` enables debug mode.

## Usage tips

The client receives each tool's name, parameters and docstring at startup and reasons about which to
call. That works well, but a few habits help:

- **Name Emby in your first message.** It cues the client to reach for these tools.
- **Select a library early.** It narrows searches and cuts the volume of data the model has to read.
- **Say "lyrics" or "description" explicitly** when you want a free-text search of that metadata,
  otherwise the client will usually search only titles and artists.
- **Be brief and specific.** Vague requests against a large library produce results the model may
  refuse to ingest, even chunked.
- **Approve tools once.** Choose *Allow always* at the first permission prompt for each tool.

A session usually opens like this:

> **list emby libraries**
>
> Your Emby server has several libraries available: **Music**, **Playlists**, **Movies**, **BBC Sounds**.
>
> **select the bbc library**
>
> I've selected the **BBC Sounds** library. What would you like to do next?

## Architecture

```
emby_mcp_server.py        MCP tool definitions, FastMCP instance, lifespan, entry points
emby_mcp/
├── functions.py          Emby API layer — all the real work
├── sdk_patches.py        Runtime corrections to the embyclient SDK
├── config.py             EmbyConfig, reads .env and the environment
├── debug.py              Interactive developer harness
├── server.py             Re-export shim so the server is importable as emby_mcp.server
└── cli/main.py           The emby-mcp Typer CLI
```

**Lifespan and context.** `app_lifespan` runs once at client startup: it logs into Emby and yields a
context dict holding the API client, user ID, cached library list, current library, and search chunking
state. Tools read and write that context through `mcp.get_context()`. When the client exits, the same
function logs out.

**Tools are thin.** Each `@mcp.tool()` function validates arguments, calls into `functions.py`, and
returns a string — either a status message or JSON. The long names and detailed docstrings exist
because the MCP SDK ships them to the model as the tool's entire specification.

**Chunked search.** `search_for_item` fetches a full result set, stores it in the lifespan context, and
returns the first `LLM_MAX_ITEMS` items along with `search_id`, `chunk_number` and
`more_chunks_available`. The client calls `retrieve_next_search_chunk` until the results are exhausted,
at which point the stored set is cleared.

**Emby quirks worth knowing.** The REST API documents `CamelCaseNames` while the SDK uses
`lower_case_names`. Emby also strips leading articles, so searching `"The Life"` and `"Life"` return
identical results, and `"the"` alone matches nothing. Genre filters are sent without a media-type
filter because Emby returns HTTP 500 when the two are combined; the media-type restriction is applied
client-side instead.

## Development

```bash
uv sync --extra dev
uv run pytest                                    # 301 tests
uv run pytest --cov --cov-report=term-missing    # 100% coverage
```

The suite mocks the Emby SDK throughout, so no live server is needed. An autouse fixture blocks `.env`
discovery so a local configuration cannot leak into a test run.

`emby_mcp/debug.py` is excluded from coverage: it is an interactive harness that drives a live server
and selects what to exercise through `if True:` edits. Reach it with `uv run emby-mcp debug`.

To inspect the protocol directly, use the MCP Inspector from the SDK (requires Node.js), or read the
client's log files — the server writes serious errors to stderr, which most clients capture.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Client shows an Emby error at startup | The Emby server was unreachable when the client launched. The client keeps working without these tools; restart it once Emby is up |
| `Fatal error: missing required environment variables` | `.env` is absent or incomplete. Check `EMBY_SERVER_URL`, `EMBY_USERNAME`, `EMBY_PASSWORD` |
| SSL certificate errors | Set `EMBY_VERIFY_SSL=False` if your server uses a self-signed certificate |
| `retrieve_user_list` returns nothing | The account lacks administrator rights, which Emby requires to list users. Per-user playlist sharing needs the same |
| Searches return truncated or refused results | Lower `LLM_MAX_ITEMS` |
| Server fails to start on Windows | Check that `claude_desktop_config.json` escapes path separators as `\\` |

## Credits

Originally created by **Dominic Search** ([angeltek/Emby.MCP](https://github.com/angeltek/Emby.MCP)),
inspired by Yoko Li's [Morse Code MCP server](https://github.com/ykhli/mcp-light-control).
This repository is a fork with a package restructure, a CLI, a test suite, and bug fixes.

### Also see

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Emby Server REST API documentation](https://dev.emby.media/reference/RestAPI.html)
- [Emby REST API Clients documentation](https://dev.emby.media/home/sdk/apiclients/index.html)
- [a16z podcast with MCP co-creator David Soria Parra](https://a16z.com/podcast/mcp-co-creator-on-the-next-wave-of-llm-innovation/)

## License

Copyright (C) 2025 Dominic Search &lt;code@angeltek.co.uk&gt;

This program is free software: you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even
the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
[GNU General Public License](LICENSE.txt) for more details.
