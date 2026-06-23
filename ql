#!/usr/bin/env python3
"""ql - Quick Log CLI. Stream terminal output to Elasticsearch for Kibana.

Usage:
    myapp 2>&1 | ql stream --tag my-session
    ql tail -f /var/log/app.log --tag my-session
    ql --selftest
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import argparse
import json
import socket
import time
import urllib.request
import urllib.error
import signal
import atexit
from datetime import datetime, timezone

from utils.uploader_helper import _enrich_entry

ES_INDEX = "athena-logs"
ES_DEFAULT = "http://localhost:9200"
BATCH_SIZE = 500
FLUSH_INTERVAL = 2.0


def _now_iso():
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _make_entry(raw_line, tag, app, hostname):
    line = raw_line.strip()
    if not line:
        return None
    try:
        parsed = json.loads(line)
        entry = parsed.copy() if isinstance(parsed, dict) else {"message": line}
    except (json.JSONDecodeError, ValueError):
        entry = {"message": line}
    if "message" not in entry:
        entry["message"] = line
    entry = _enrich_entry(entry)
    if "@timestamp" not in entry:
        entry["@timestamp"] = _now_iso()
    entry["source"] = "live"
    entry["stream_tag"] = tag
    entry["host"] = hostname
    if app:
        entry["app"] = app
    return entry


def _send_bulk(es_url, entries):
    if not entries:
        return 0, 0
    body = ""
    for e in entries:
        body += json.dumps({"index": {"_index": ES_INDEX}}) + "\n" + e + "\n"
    try:
        req = urllib.request.Request(
            f"{es_url}/_bulk",
            data=body.encode("utf-8"),
            headers={"Content-Type": "application/x-ndjson"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read().decode("utf-8"))
        items = result.get("items", [])
        ok = sum(1 for i in items if i.get("index", {}).get("status") in (200, 201))
        return ok, len(items) - ok
    except Exception:
        return 0, len(entries)


def _ensure_template(es_url):
    path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "elk", "es_template.json")
    if not os.path.exists(path):
        return
    try:
        with open(path) as f:
            body = json.dumps(json.load(f)).encode("utf-8")
        req = urllib.request.Request(
            f"{es_url}/_index_template/athena-logs",
            data=body,
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def _check_es(es_url):
    try:
        urllib.request.urlopen(f"{es_url}/_cluster/health", timeout=5)
        return True
    except Exception:
        return False


class Streamer:
    def __init__(self, es_url, tag, app, hostname):
        self.es_url = es_url
        self.tag = tag
        self.app = app
        self.hostname = hostname
        self.batch = []
        self.last_flush = time.time()
        self.indexed = 0
        self.failed = 0

    def add(self, raw_line):
        entry = _make_entry(raw_line, self.tag, self.app, self.hostname)
        if entry is None:
            return
        self.batch.append(json.dumps(entry))
        if len(self.batch) >= BATCH_SIZE or (time.time() - self.last_flush) >= FLUSH_INTERVAL:
            self.flush()

    def maybe_flush(self):
        if self.batch and time.time() - self.last_flush >= FLUSH_INTERVAL:
            self.flush()

    def flush(self):
        if not self.batch:
            return
        ok, fail = _send_bulk(self.es_url, self.batch)
        self.indexed += ok
        self.failed += fail
        self.batch = []
        self.last_flush = time.time()


def _print_summary(streamer, label):
    print(f"\nql: {streamer.indexed:,} indexed, {streamer.failed:,} failed | {label}", file=sys.stderr)


def _setup_signals(streamer, label):
    def on_sigint(sig, frame):
        streamer.flush()
        _print_summary(streamer, label)
        sys.exit(0)

    signal.signal(signal.SIGINT, on_sigint)
    atexit.register(streamer.flush)


def cmd_stream(args):
    es_url = args.es
    if not _check_es(es_url):
        print(f"ql: cannot reach Elasticsearch at {es_url}", file=sys.stderr)
        print("  Start the stack with: ./manage_stack.sh start-live", file=sys.stderr)
        sys.exit(1)
    _ensure_template(es_url)
    hostname = socket.gethostname()
    tag = args.tag or f"session-{int(time.time())}"
    streamer = Streamer(es_url, tag, args.app, hostname)
    label = f"tag={tag}"
    _setup_signals(streamer, label)
    print(f"ql stream → {es_url}/{ES_INDEX} | tag={tag} host={hostname}", file=sys.stderr)

    import select

    while True:
        ready, _, _ = select.select([sys.stdin], [], [], FLUSH_INTERVAL)
        if ready:
            line = sys.stdin.readline()
            if not line:
                break
            streamer.add(line)
        else:
            streamer.maybe_flush()

    streamer.flush()
    _print_summary(streamer, label)


def cmd_tail(args):
    es_url = args.es
    if not _check_es(es_url):
        print(f"ql: cannot reach Elasticsearch at {es_url}", file=sys.stderr)
        print("  Start the stack with: ./manage_stack.sh start-live", file=sys.stderr)
        sys.exit(1)
    _ensure_template(es_url)
    hostname = socket.gethostname()
    tag = args.tag or f"session-{int(time.time())}"
    streamer = Streamer(es_url, tag, args.app, hostname)
    label = f"tag={tag}"
    _setup_signals(streamer, label)
    mode = "-f " if args.follow else ""
    print(f"ql tail {mode}{args.file} → {es_url}/{ES_INDEX} | tag={tag} host={hostname}", file=sys.stderr)

    with open(args.file, "r") as f:
        for line in f:
            streamer.add(line)

        if args.follow:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    streamer.add(line)
                else:
                    streamer.maybe_flush()
                    pos = f.tell()
                    f.seek(0, 2)
                    if f.tell() < pos:
                        f.seek(0)
                    time.sleep(0.1)

    streamer.flush()
    _print_summary(streamer, label)


def cmd_selftest():
    entry = _make_entry('{"level":30,"msg":"hello","time":1700000000000}', "test", "myapp", "myhost")
    assert entry is not None, "JSON line should produce entry"
    assert entry["source"] == "live", "source tag missing"
    assert entry["stream_tag"] == "test", "stream_tag missing"
    assert entry["host"] == "myhost", "host missing"
    assert entry["app"] == "myapp", "app missing"
    assert "@timestamp" in entry, "@timestamp missing"
    assert "message" in entry, "message field missing"
    assert "parsed_message" in entry, "parsed_message should be set for JSON lines"

    entry2 = _make_entry("Server started on port 3000", "test", None, "myhost")
    assert entry2["message"] == "Server started on port 3000", "plain text not wrapped"
    assert entry2["source"] == "live", "source tag missing for plain text"
    assert "app" not in entry2, "app should be absent when not provided"

    assert _make_entry("", "test", "myapp", "myhost") is None, "empty line should return None"
    assert _make_entry("   \n", "test", "myapp", "myhost") is None, "whitespace-only line should return None"

    print("✅ selftest passed")


def main():
    parser = argparse.ArgumentParser(
        prog="ql",
        description="Quick Log CLI — stream terminal output to Elasticsearch",
    )
    sub = parser.add_subparsers(dest="command")

    p_stream = sub.add_parser("stream", help="Stream stdin to Elasticsearch")
    p_stream.add_argument("--tag", help="Stream tag for Kibana filtering")
    p_stream.add_argument("--app", help="Application name")
    p_stream.add_argument("--es", default=ES_DEFAULT, help=f"Elasticsearch URL (default: {ES_DEFAULT})")

    p_tail = sub.add_parser("tail", help="Tail a log file to Elasticsearch")
    p_tail.add_argument("file", help="Log file to read")
    p_tail.add_argument("-f", "--follow", action="store_true", help="Follow the file (like tail -f)")
    p_tail.add_argument("--tag", help="Stream tag for Kibana filtering")
    p_tail.add_argument("--app", help="Application name")
    p_tail.add_argument("--es", default=ES_DEFAULT, help=f"Elasticsearch URL (default: {ES_DEFAULT})")

    parser.add_argument("--selftest", action="store_true", help="Run self-test")

    args = parser.parse_args()

    if args.selftest:
        cmd_selftest()
        return

    if args.command == "stream":
        cmd_stream(args)
    elif args.command == "tail":
        cmd_tail(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
