# Quick Log

A developer-friendly log analytics tool. Upload static log files or stream live terminal output into Elasticsearch, then visualize and filter in Kibana.

## What it does

- **Log Uploader** — Drag-and-drop CSV/TXT/JSON log files. Files are parsed, enriched, and bulk-indexed to Elasticsearch. View in Kibana.
- **Live Stream** — Pipe terminal output (or tail a log file) directly into Elasticsearch via the `ql` CLI. Logs appear in Kibana in near-real-time, tagged with a session ID so you can filter out the noise.

## Prerequisites

- **Docker** (or Colima on macOS with at least 4GB memory, 8GB recommended)
- **Python 3.8+** (only needed for the `ql` CLI on the host; the Streamlit app runs in Docker)
- **docker-compose**

## Quick start

### 1. Start the stack

```bash
./manage_stack.sh start
```

This starts Elasticsearch, Kibana, and the Quick Log Streamlit app. Elasticsearch is internal-only (not exposed to the host).

| Service        | URL                          |
|----------------|------------------------------|
| Quick Log UI   | http://localhost:8501        |
| Kibana         | http://localhost:5601        |

### 2. Upload log files

Open http://localhost:8501, drag and drop your log files (CSV, TXT, JSON up to 500MB). Files are converted to NDJSON, enriched, and indexed to the `athena-logs` Elasticsearch index. Click "Open Kibana" to visualize.

### 3. Stop the stack

```bash
./manage_stack.sh stop
```

## Live streaming

Live streaming lets you pipe terminal output or tail log files directly into Elasticsearch while you develop. This requires exposing Elasticsearch on `localhost:9200` and installing the `ql` CLI.

### One-time setup

```bash
./manage_stack.sh start-live
```

This does three things:
1. Starts the full stack with Elasticsearch exposed on `127.0.0.1:9200`
2. Installs the `ql` CLI to `~/.local/bin` (adds it to your `PATH`)
3. Makes `ql` executable

If `~/.local/bin` is not on your `PATH`, the script will tell you. Add this to your shell profile (`~/.zshrc`, `~/.bashrc`):

```bash
export PATH="$HOME/.local/bin:$PATH"
```

You can also install the CLI separately at any time:

```bash
./manage_stack.sh install-cli
```

### Streaming terminal output

Pipe any application's stdout/stderr into `ql`:

```bash
# Node.js
node server.js 2>&1 | ql stream --tag my-node-app

# Python
python app.py 2>&1 | ql stream --tag my-python-app

# Go
./myapp 2>&1 | ql stream --tag my-go-app

# With nodemon / ts-node
nodemon server.js 2>&1 | ql stream --tag dev-session
```

`2>&1` merges stderr into stdout so you capture both `console.log` and `console.error`.

### Tailing a log file

If your application writes logs to a file (Winston, pino, Log4j, etc.):

```bash
# Follow a log file (like tail -f)
ql tail -f logs/app.log --tag my-app

# Read a log file once (no following)
ql tail logs/app.log --tag my-app
```

### CLI reference

```
ql - Quick Log CLI

Usage:
    ql stream [options]           Stream stdin to Elasticsearch
    ql tail [options] <file>      Read or tail a log file
    ql --selftest                 Run self-test

Options:
    --tag <name>    Stream tag for Kibana filtering (default: auto-generated session ID)
    --app <name>    Application name (optional)
    --es <url>      Elasticsearch URL (default: http://localhost:9200)

tail-specific:
    -f, --follow    Follow the file for new lines (like tail -f)
```

### How live docs are tagged

Every document streamed via `ql` gets these fields so you can filter in Kibana:

| Field         | Value                                      |
|---------------|--------------------------------------------|
| `source`      | `"live"` (distinguishes from uploaded logs)|
| `stream_tag`  | Your `--tag` value or an auto session ID   |
| `host`        | Your machine's hostname                     |
| `app`         | Your `--app` value (only if provided)       |
| `@timestamp`  | ISO 8601 with millisecond precision         |

### Filtering in Kibana

In Kibana Discover, use KQL to filter:

```
source:live                          # all live-streamed logs
source:live AND stream_tag:my-app   # a specific session
source:live AND host:my-laptop      # logs from a specific machine
source:live AND app:my-node-app     # logs from a specific app
```

### Structured vs plain text logs

`ql` handles both:

- **JSON lines** (pino, winston JSON, Logstash format) — each line is parsed as JSON. All fields become searchable in Kibana (`level`, `requestId`, `userId`, etc.).
- **Plain text** (`console.log("Server started")`) — wrapped as `{"message": "Server started"}`. The full message is still searchable, but without structured fields.

For the best experience, configure your logger to output JSON lines. With pino (Node.js):

```js
const pino = require('pino')
const logger = pino({ level: 'info' })
logger.info({ requestId: 'abc', userId: 123 }, 'Request received')
// → {"level":30,"requestId":"abc","userId":123,"msg":"Request received"}
```

Pipe that through `ql stream` and every field is filterable in Kibana.

### Stopping live mode

```bash
./manage_stack.sh stop
```

This stops all services and removes the port exposure. Use `./manage_stack.sh start` to restart without exposing Elasticsearch.

## Stack manager reference

```
./manage_stack.sh [command]

Commands:
  start       Start all services (ES internal-only)
  start-live  Start with ES exposed on localhost:9200 + install ql CLI
  stop        Stop all services
  restart     Restart all services
  status      Check service status
  logs        View logs from all services
  rebuild     Rebuild containers and restart
  install-cli Install ql CLI to ~/.local/bin (on PATH)
```

## Configuration

Application settings (upload directory, max file size) can be configured via the **Configuration Settings** page in the UI at http://localhost:8501.

Settings are stored in `config/settings.json` (gitignored). A template is provided at `config/settings.template.json`.

## Architecture

```
                    ┌──────────────┐
                    │  Streamlit   │
                    │  Quick Log   │──── http://localhost:8501
                    │  (uploader)  │
                    └──────┬───────┘
                           │ bulk index
                           ▼
┌──────────┐  bulk   ┌──────────────┐         ┌──────────────┐
│   ql     │────────▶│Elasticsearch │◀────────│   Kibana     │
│  (CLI)   │  API    │  :9200       │  query  │  :5601       │
└──────────┘         └──────────────┘         └──────────────┘
   host                   docker                   docker
```

- **Elasticsearch 7.17.15** — stores and indexes logs in the `athena-logs` index
- **Kibana 7.17.15** — visualization and search
- **Streamlit app** — file upload UI, runs in Docker
- **ql CLI** — stdlib-only Python script, runs on the host, posts to ES bulk API

### Index template

The Elasticsearch index template (`elk/es_template.json`) defines mappings for the `athena-logs*` index pattern. The `ql` CLI loads this template on startup. Key fields:

- `@timestamp` — date, ISO 8601
- `value` — object, dynamic
- `label` — text
- `messageNumber` — integer
- `parsed_message` — object, dynamic (parsed from JSON `message` field)
- All other strings — keyword (via dynamic template)

## Project structure

```
quick-log/
├── main.py                    # Streamlit entry point, page registration
├── ql                         # Live stream CLI (stdlib-only, executable)
├── pages/
│   ├── log_uploader.py        # File upload UI
│   ├── live_stream.py         # Live stream instructions + stats UI
│   └── settings.py           # Configuration + diagnostics
├── utils/
│   ├── uploader_helper.py     # Core: parse, enrich, bulk index to ES
│   ├── config_loader.py       # Settings load/save
│   ├── features.py            # Feature registry
│   ├── prerequisites.py       # Docker/Colima detection
│   ├── styles.py              # UI CSS + helpers
│   ├── urls.py                # Internal/external URL helpers
│   └── validation.py          # Feature prerequisite checks
├── elk/
│   ├── es_template.json       # Elasticsearch index template
│   └── kibana.yml             # Kibana config
├── config/
│   └── settings.template.json # Config template
├── docker-compose.yml         # Base stack (ES internal-only)
├── docker-compose.live.yml    # Override: exposes ES on localhost:9200
├── manage_stack.sh            # Stack manager + CLI installer
└── Dockerfile                 # Streamlit app container
```

## Troubleshooting

**`ql: cannot reach Elasticsearch at http://localhost:9200`**
The stack isn't running in live mode. Start it with:
```bash
./manage_stack.sh start-live
```

**`ql: command not found`**
The CLI isn't on your PATH. Either run `./manage_stack.sh install-cli`, or use the full path: `python /path/to/quick-log/ql stream`.

**`~/.local/bin is not on your PATH`**
Add this to your shell profile and restart your terminal:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

**Elasticsearch health check fails on start**
Ensure Docker/Colima has at least 4GB memory (8GB recommended). On macOS:
```bash
colima stop
colima start --memory 8 --cpu 4
```

**Logs not appearing in Kibana**
- Verify the stack is healthy: `./manage_stack.sh status`
- Check the index exists: `curl http://localhost:9200/_cat/indices/athena-logs*`
- Verify your tag: `ql stream` prints the tag on startup. Filter Kibana with `stream_tag:<your-tag>`.
- For uploads, check the Processing Queue in the UI for errors.

**File upload fails**
- Check the file is under 500MB (configurable in Settings)
- Ensure the format is CSV, TXT, or JSON
- Check if the file is already uploaded (deduplication by content hash)
