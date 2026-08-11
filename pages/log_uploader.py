import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from datetime import datetime
from utils.uploader_helper import (
    compute_file_hash,
    preprocess_file_streaming,
    bulk_index_to_es,
    detect_format,
    load_hash_db,
    save_hash_db,
    get_es_count,
    delete_uploaded_file,
    full_reset
)
from utils.validation import require_feature
from utils.styles import (
    inject_styles,
    render_status_dot,
    render_file_card_html,
    render_empty_state,
    check_service_health,
)
from utils.urls import (
    ELASTICSEARCH_INTERNAL,
    KIBANA_INTERNAL,
    get_kibana_external,
)

config = require_feature("log_analytics_elk")

inject_styles()

st.title(":material/upload_file: Quick Log")

features = config.get('features', {})
log_config = features.get('log_analytics_elk', {}).get('config', {})

UPLOAD_DIR = log_config.get('upload_dir', 'uploads')
MAX_FILE_SIZE_MB = log_config.get('max_file_size_mb', 500)
ES_URL = ELASTICSEARCH_INTERNAL
KIBANA_URL = get_kibana_external()
KB_URL_INT = KIBANA_INTERNAL

MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

os.makedirs(UPLOAD_DIR, exist_ok=True)

LOGS_METADATA = load_hash_db(UPLOAD_DIR)

# ──────────────────────────────────────────────────────────────
# Sidebar: Stack Health + Stats + Kibana Link
# ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("### :material/monitoring: Stack Health")
    health_cols = st.columns(2)
    with health_cols[0]:
        es_status = check_service_health(ES_URL, "/_cluster/health")
        render_status_dot("ES", es_status)
    with health_cols[1]:
        kb_status = check_service_health(KB_URL_INT, "/api/status")
        render_status_dot("KB", kb_status)

    st.divider()

    total_files = len([f for f in os.listdir(UPLOAD_DIR) if not f.startswith('.')])
    total_entries = sum(m.get('entries_count', 0) for m in LOGS_METADATA.values())
    doc_count = get_es_count(ES_URL)

    st.markdown("### :material/bar_chart: Upload Stats")
    st.markdown(f"**{total_files}** files queued")
    st.markdown(f"**{total_entries:,}** entries processed")
    st.markdown(f"**{doc_count:,}** docs in Elasticsearch")

    st.divider()

    st.link_button(":material/open_in_new: Open Kibana", KIBANA_URL, use_container_width=True)

# ──────────────────────────────────────────────────────────────
# Main: Upload Area
# ──────────────────────────────────────────────────────────────
st.markdown(
    f"Drag and drop your log files here. Supported formats: **CSV**, **TXT**, **JSON**. "
    f"Files up to **{MAX_FILE_SIZE_MB} MB** are supported."
)

uploaded_files = st.file_uploader(
    f"Choose log files (max {MAX_FILE_SIZE_MB} MB each)",
    type=["csv", "txt", "json"],
    accept_multiple_files=True,
    label_visibility="collapsed",
    help=f"Supported formats: CSV, TXT, JSON. Files larger than {MAX_FILE_SIZE_MB} MB will be rejected"
)

if uploaded_files:
    if 'processed_files' not in st.session_state:
        st.session_state.processed_files = set()

    for file_index, uploaded_file in enumerate(uploaded_files, 1):
        file_key = f"{uploaded_file.name}_{uploaded_file.size}"

        if file_key in st.session_state.processed_files:
            continue

        if uploaded_file.size > MAX_FILE_SIZE_BYTES:
            st.error(f":material/error: **{uploaded_file.name}** — File too large ({uploaded_file.size/1024/1024:.1f} MB > {MAX_FILE_SIZE_MB} MB limit)")
            st.session_state.processed_files.add(file_key)
            continue

        content_hash = compute_file_hash(uploaded_file)

        if uploaded_file.name in LOGS_METADATA and LOGS_METADATA[uploaded_file.name].get('hash') == content_hash:
            output_file = LOGS_METADATA[uploaded_file.name].get('output_file')
            if output_file and os.path.exists(os.path.join(UPLOAD_DIR, output_file)):
                st.info(f":material/skip_next: Skipped (already uploaded): **{uploaded_file.name}**")
                st.session_state.processed_files.add(file_key)
                continue

        with st.expander(f"Processing {uploaded_file.name} ({uploaded_file.size/1024/1024:.1f} MB) [{detect_format(uploaded_file.name).upper()}]", expanded=True):
            progress_bar = st.progress(0, "Starting...")
            status_text = st.empty()

            base_name = os.path.splitext(uploaded_file.name)[0]
            file_path = os.path.join(UPLOAD_DIR, f"{base_name}.jsonl")

            if os.path.exists(file_path):
                os.remove(file_path)
                status_text.text("Removed old version")

            try:
                status_text.text("Converting to NDJSON...")
                lines_written, lines_skipped = preprocess_file_streaming(
                    uploaded_file, file_path, uploaded_file.name, progress_bar, status_text
                )

                progress_bar.progress(0.5, "Converting complete. Indexing to Elasticsearch...")
                status_text.text("Indexing to Elasticsearch...")

                indexed, failed = bulk_index_to_es(ES_URL, file_path, progress_bar, status_text)

                progress_bar.progress(1.0, "Complete!")

                LOGS_METADATA[uploaded_file.name] = {
                    'hash': content_hash,
                    'last_uploaded': datetime.now().isoformat(),
                    'size': uploaded_file.size,
                    'output_file': f"{base_name}.jsonl",
                    'entries_count': lines_written,
                    'skipped_count': lines_skipped,
                    'indexed_count': indexed,
                    'index_failed_count': failed
                }
                save_hash_db(UPLOAD_DIR, LOGS_METADATA)

                msg = f":material/check_circle: **{indexed:,}** entries indexed to Elasticsearch"
                if failed > 0:
                    msg += f" ({failed:,} failed)"
                if lines_skipped > 0:
                    msg += f" | {lines_skipped:,} lines skipped during parsing"
                st.success(msg)

            except Exception as e:
                st.error(f":material/error: Failed to process {uploaded_file.name}: {str(e)}")
                if os.path.exists(file_path):
                    os.remove(file_path)

        st.session_state.processed_files.add(file_key)

    st.divider()

# ──────────────────────────────────────────────────────────────
# File Queue — Rich Cards
# ──────────────────────────────────────────────────────────────
st.subheader(":material/folder: Processing Queue")

files = [f for f in os.listdir(UPLOAD_DIR) if not f.startswith('.')]
if files:
    doc_count = get_es_count(ES_URL)
    st.markdown(f"**:material/bar_chart: {doc_count:,}** documents in Elasticsearch")

    for f in files:
        meta = LOGS_METADATA.get(f, {})
        orig_name = None
        for on, m in LOGS_METADATA.items():
            if m.get('output_file') == f:
                orig_name = on
                meta = m
                break

        fmt = detect_format(f).lower()
        if f.endswith('.jsonl') and orig_name:
            fmt = detect_format(orig_name).lower()
        elif f.endswith('.jsonl'):
            fmt = "json"

        size_mb = meta.get('size', os.path.getsize(os.path.join(UPLOAD_DIR, f))) / (1024 * 1024)
        entries = meta.get('entries_count')
        upload_date = meta.get('last_uploaded', '')

        card_cols = st.columns([10, 1])
        with card_cols[0]:
            st.markdown(
                render_file_card_html(f, size_mb, fmt, entries, upload_date),
                unsafe_allow_html=True
            )
        with card_cols[1]:
            st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)
            if st.button(":material/delete:", key=f"del_{f}", help=f"Delete {f}"):
                if delete_uploaded_file(UPLOAD_DIR, f, LOGS_METADATA):
                    st.toast(f"Deleted {f}", icon=":material/delete:")
                    st.rerun()
else:
    render_empty_state()

st.divider()

# ──────────────────────────────────────────────────────────────
# Danger Zone — Full Reset Only
# ──────────────────────────────────────────────────────────────
st.subheader(":material/warning: Danger Zone")

with st.expander("Reset Options", expanded=False):
    confirm = st.checkbox(
        "I understand this will permanently delete all data",
        key="danger_confirm"
    )

    if confirm:
        if st.button(":material/delete_forever: Full Reset", type="primary",
                     help="Clears ES index, all .jsonl files, and upload tracking"):
            if full_reset(ES_URL, UPLOAD_DIR):
                st.session_state.processed_files = set()
                st.toast("Full reset complete", icon=":material/check_circle:")
                st.rerun()
            else:
                st.error("Failed to reset. Check if Elasticsearch is reachable.")
    else:
        st.caption("Check the box above to enable reset.")

