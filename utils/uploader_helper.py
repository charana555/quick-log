"""
Uploader helper module - Core logic for file upload and processing.
Extracted from the original log-viewer uploader service.
Supports CSV, TXT, and JSON file formats with automatic detection.
All formats are converted to NDJSON (.jsonl) for Logstash ingestion.
"""

import os
import json
import hashlib
from datetime import datetime


SUPPORTED_EXTENSIONS = {"csv", "txt", "json"}


def detect_format(filename):
    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
    if ext in ('csv', 'txt'):
        return 'csv'
    if ext == 'json':
        return 'json'
    return 'csv'


def compute_file_hash(file_obj):
    """Compute MD5 hash of file content for deduplication."""
    hasher = hashlib.md5()
    file_obj.seek(0)
    for chunk in iter(lambda: file_obj.read(8192), b''):
        hasher.update(chunk)
    file_obj.seek(0)
    return hasher.hexdigest()


def truncate_large_fields(entry, max_value_length=50000):
    """Truncate large 'value' fields to prevent memory issues."""
    if not isinstance(entry, dict):
        return entry

    if 'value' in entry and isinstance(entry['value'], str) and len(entry['value']) > max_value_length:
        entry = entry.copy()
        entry['value'] = entry['value'][:max_value_length] + "...[TRUNCATED]"
        entry['_value_truncated'] = True
        entry['_original_value_length'] = len(entry['value']) + len("...[TRUNCATED]") - 1

    return entry


def _write_entry(entry, out):
    entry = truncate_large_fields(entry)
    out.write(json.dumps(entry) + '\n')


def _decode_line(raw_line):
    try:
        return raw_line.decode('utf-8').strip()
    except UnicodeDecodeError:
        return raw_line.decode('utf-8', errors='ignore').strip()


def _update_progress(progress_bar, bytes_processed, total_bytes):
    if progress_bar and total_bytes > 0:
        progress = min(bytes_processed / total_bytes, 1.0)
        progress_bar.progress(progress, f"Processing... {bytes_processed/1024/1024:.1f}MB / {total_bytes/1024/1024:.1f}MB")


def _process_csv_lines(input_file, output_path, progress_bar=None, status_text=None):
    total_bytes = len(input_file.getvalue())
    bytes_processed = 0
    lines_written = 0
    lines_skipped = 0

    with open(output_path, "w", encoding='utf-8') as out:
        header = input_file.readline()
        bytes_processed += len(header)

        line_number = 0
        for raw_line in input_file:
            line_number += 1
            bytes_processed += len(raw_line)

            line = _decode_line(raw_line)
            if not line:
                continue

            if line.startswith('"') and line.endswith('"'):
                line = line[1:-1]
            line = line.replace('""', '"')

            try:
                log_entries = json.loads(line)
                if isinstance(log_entries, list):
                    for entry in log_entries:
                        _write_entry(entry, out)
                        lines_written += 1
                elif isinstance(log_entries, dict):
                    _write_entry(log_entries, out)
                    lines_written += 1
                else:
                    lines_skipped += 1
            except json.JSONDecodeError:
                lines_skipped += 1
                if status_text:
                    status_text.text(f"Warning: Line {line_number} is not valid JSON, skipping")

            if line_number % 10 == 0 or bytes_processed > total_bytes * 0.95:
                _update_progress(progress_bar, bytes_processed, total_bytes)

    return lines_written, lines_skipped


def _process_json_file(input_file, output_path, progress_bar=None, status_text=None):
    total_bytes = len(input_file.getvalue())
    bytes_processed = 0
    lines_written = 0
    lines_skipped = 0

    raw_content = input_file.getvalue()
    bytes_processed = total_bytes

    with open(output_path, "w", encoding='utf-8') as out:
        content = raw_content.decode('utf-8').strip()

        parsed = None
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            pass

        if isinstance(parsed, list):
            for entry in parsed:
                if isinstance(entry, dict):
                    _write_entry(entry, out)
                    lines_written += 1
                else:
                    lines_skipped += 1
            _update_progress(progress_bar, bytes_processed, total_bytes)
            return lines_written, lines_skipped

        if isinstance(parsed, dict):
            _write_entry(parsed, out)
            lines_written += 1
            _update_progress(progress_bar, bytes_processed, total_bytes)
            return lines_written, lines_skipped

        input_file.seek(0)
        line_number = 0
        for raw_line in input_file:
            line_number += 1
            line = _decode_line(raw_line)
            if not line:
                continue

            try:
                entry = json.loads(line)
                if isinstance(entry, dict):
                    _write_entry(entry, out)
                    lines_written += 1
                elif isinstance(entry, list):
                    for item in entry:
                        if isinstance(item, dict):
                            _write_entry(item, out)
                            lines_written += 1
                        else:
                            lines_skipped += 1
                else:
                    lines_skipped += 1
            except json.JSONDecodeError:
                lines_skipped += 1
                if status_text:
                    status_text.text(f"Warning: Line {line_number} is not valid JSON, skipping")

            if line_number % 10 == 0:
                _update_progress(progress_bar, bytes_processed, total_bytes)

    _update_progress(progress_bar, bytes_processed, total_bytes)
    return lines_written, lines_skipped


def preprocess_file_streaming(input_file, output_path, filename, progress_bar=None, status_text=None):
    """
    Preprocess log file and convert to NDJSON format for Logstash.
    Supports CSV, TXT, and JSON formats detected by file extension.
    Returns tuple of (lines_written, lines_skipped).
    """
    fmt = detect_format(filename)

    if fmt == 'json':
        return _process_json_file(input_file, output_path, progress_bar, status_text)

    return _process_csv_lines(input_file, output_path, progress_bar, status_text)


def load_hash_db(upload_dir):
    """Load file hash database for deduplication."""
    hash_db_file = os.path.join(upload_dir, ".file_hashes.json")
    if os.path.exists(hash_db_file):
        try:
            with open(hash_db_file, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_hash_db(upload_dir, hash_db):
    """Save file hash database."""
    hash_db_file = os.path.join(upload_dir, ".file_hashes.json")
    try:
        with open(hash_db_file, 'w') as f:
            json.dump(hash_db, f)
    except:
        pass


def get_es_count(es_url):
    """Get document count from Elasticsearch index."""
    import requests
    try:
        response = requests.get(f"{es_url}/athena-logs/_count")
        if response.status_code == 200:
            return response.json().get("count", 0)
    except:
        pass
    return 0


def delete_uploaded_file(upload_dir, filename, hash_db=None):
    """Delete an uploaded file and remove from hash database if present."""
    file_path = os.path.join(upload_dir, filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            return False
            
        # Also remove from metadata if it's a .jsonl file
        if hash_db:
            base_name = os.path.splitext(filename)[0]
            for orig_name, meta in list(hash_db.items()):
                if meta.get('output_file') == filename:
                    del hash_db[orig_name]
                    save_hash_db(upload_dir, hash_db)
                    break

        # Note: We can't clear Logstash sincedb from inside the container without docker.
        # The file will be re-processed if uploaded again only after:
        # 1. Logstash container is restarted, OR
        # 2. sincedb files are cleared manually via manage_stack.sh on host
        return True
    return False


def _docker_client():
    try:
        import docker
        return docker.from_env()
    except Exception:
        return None


def stop_logstash():
    try:
        client = _docker_client()
        if not client:
            return False
        container = client.containers.get("quick-log-logstash")
        container.stop(timeout=15)
        import time
        time.sleep(2)
        return True
    except Exception:
        return False


def start_logstash():
    try:
        client = _docker_client()
        if not client:
            return False
        container = client.containers.get("quick-log-logstash")
        container.start()
        return True
    except Exception:
        return False


def clear_es_index_only(es_url):
    """Clear only the Elasticsearch index. Preserves tracking files and uploads."""
    import requests
    try:
        response = requests.delete(f"{es_url}/athena-logs")
        return response.status_code in [200, 404]
    except Exception:
        return False


def full_reset(es_url, upload_dir):
    """Full reset: stop Logstash, clear ES index + tracking + files, then start Logstash."""
    import requests
    import time

    logstash_stopped = stop_logstash()

    if logstash_stopped:
        time.sleep(1)

    for name in ["sincedb", "completed_files.log"]:
        path = os.path.join(upload_dir, ".tracking", name)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    hash_db_file = os.path.join(upload_dir, ".file_hashes.json")
    if os.path.exists(hash_db_file):
        try:
            os.remove(hash_db_file)
        except Exception:
            pass

    for f in os.listdir(upload_dir):
        if f.endswith('.jsonl'):
            try:
                os.remove(os.path.join(upload_dir, f))
            except Exception:
                pass

    es_cleared = False
    try:
        response = requests.delete(f"{es_url}/athena-logs")
        es_cleared = response.status_code in [200, 404]
    except Exception:
        pass

    logstash_started = start_logstash()

    return es_cleared, logstash_started
