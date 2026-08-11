import streamlit as st


GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');

:root {
    --font-mono: 'IBM Plex Mono', 'SFMono-Regular', Consolas, monospace;
    --font-body: 'Source Sans Pro', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── Base resets ── */
[data-testid="stHeader"] {
    background: rgba(14, 17, 23, 0.85) !important;
    backdrop-filter: blur(12px);
}

[data-testid="stSidebar"] {
    background: #12151C !important;
    border-right: 1px solid rgba(255,255,255,0.06);
}

.stApp {
    background: #0E1117 !important;
    font-size: 14.5px;
}

/* ── Headings — IBM Plex Mono ── */
h1, .stTitle {
    font-family: var(--font-mono) !important;
    font-size: 28px !important;
    font-weight: 700 !important;
    letter-spacing: -0.5px;
}

h2, .stHeader {
    font-family: var(--font-mono) !important;
    font-size: 22px !important;
    font-weight: 600 !important;
    letter-spacing: -0.3px;
}

h3 {
    font-family: var(--font-mono) !important;
    font-size: 18px !important;
    font-weight: 600 !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #2D333B; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #444C56; }

/* ── File uploader dropzone ── */
[data-testid="stFileUploader"] {
    border: 2px dashed #2D333B !important;
    border-radius: 12px !important;
    background: rgba(26, 29, 38, 0.5) !important;
    transition: all 0.25s ease;
}

[data-testid="stFileUploader"]:hover {
    border-color: #00D4AA !important;
    background: rgba(0, 212, 170, 0.04) !important;
}

[data-testid="stFileUploaderDropzone"] {
    background: transparent !important;
}

/* ── Status dots ── */
.status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
    vertical-align: middle;
}

.status-dot.green {
    background: #00D4AA;
    box-shadow: 0 0 6px rgba(0, 212, 170, 0.6);
    animation: pulse-green 2s infinite;
}

.status-dot.red {
    background: #F85149;
    box-shadow: 0 0 6px rgba(248, 81, 73, 0.6);
    animation: pulse-red 2s infinite;
}

.status-dot.amber {
    background: #D29922;
    box-shadow: 0 0 6px rgba(210, 153, 34, 0.6);
    animation: pulse-amber 2s infinite;
}

@keyframes pulse-green {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.55; }
}

@keyframes pulse-red {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.55; }
}

@keyframes pulse-amber {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.55; }
}

/* ── Format badge / chip ── */
.format-chip {
    display: inline-block;
    padding: 1px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    font-family: var(--font-mono);
    margin-left: 8px;
    vertical-align: middle;
}

.format-chip.csv { background: rgba(0, 212, 170, 0.15); color: #00D4AA; }
.format-chip.json { background: rgba(121, 192, 255, 0.15); color: #79C0FF; }
.format-chip.txt { background: rgba(210, 153, 34, 0.15); color: #D29922; }

/* ── File card ── */
.file-card {
    background: #1A1D26;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 8px;
    transition: border-color 0.2s ease;
}

.file-card:hover {
    border-color: rgba(255,255,255,0.12);
}

.file-card .file-name {
    font-size: 14px;
    font-weight: 600;
    color: #E1E4E8;
    font-family: var(--font-mono);
}

.file-card .file-meta {
    font-size: 12px;
    color: #7D8590;
    margin-top: 4px;
    font-family: var(--font-mono);
}

/* ── Sidebar logo ── */
[data-testid="stSidebarUserContent"] {
    padding-top: 0 !important;
}
[data-testid="stSidebarHeader"] {
    margin-bottom: 0 !important;
    gap: 8px !important;
    text-align: center;
}
[data-testid="stLogoSpacer"] {
    display: flex !important;
    align-items: center !important;
}
[data-testid="stLogoSpacer"] {
    display: block !important;
    text-align: center;
}
[data-testid="stLogoSpacer"]::before {
    content: "Quick Log";
    font-family: var(--font-mono);
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.5px;
    color: #00D4AA;
    display: block;
}
[data-testid="stLogoSpacer"]::after {
    content: "LOG ANALYTICS";
    font-family: var(--font-mono);
    font-size: 11px;
    color: #7D8590;
    letter-spacing: 1px;
    display: block;
}
[data-testid="stSidebar"] [data-testid="stSidebarNav"] {
    display: none !important;
}

/* ── Danger zone ── */
.danger-zone {
    border: 1px solid rgba(248, 81, 73, 0.2);
    border-radius: 10px;
    padding: 16px;
    background: rgba(248, 81, 73, 0.03);
}

/* ── Empty state ── */
.empty-state {
    text-align: center;
    padding: 48px 24px;
}

.empty-state .empty-icon {
    font-size: 48px;
    color: #2D333B;
    margin-bottom: 16px;
}

.empty-state .empty-title {
    font-size: 18px;
    font-weight: 600;
    color: #7D8590;
    font-family: var(--font-mono);
    margin-bottom: 8px;
}

.empty-state .empty-desc {
    font-size: 13px;
    color: #484F58;
}

/* ── Sidebar health row ── */
.health-row {
    display: flex;
    gap: 16px;
    align-items: center;
    padding: 8px 0;
}

.health-item {
    display: flex;
    align-items: center;
    font-size: 12px;
    color: #7D8590;
    font-family: var(--font-mono);
}

/* ── Sidebar stats — mono for numbers ── */
[data-testid="stSidebar"] p {
    font-family: var(--font-mono);
    font-size: 13px;
}

/* ── Expander tweaks ── */
[data-testid="stExpander"] {
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 10px !important;
    background: #1A1D26 !important;
}

/* ── Button refinements ── */
.stButton > button[kind="secondary"] {
    border-color: rgba(255,255,255,0.1) !important;
}

/* ── Progress bar ── */
[data-testid="stProgressBar"] > div > div > div {
    background: #00D4AA !important;
}

/* ── Divider ── */
[data-testid="stDivider"] {
    border-color: rgba(255,255,255,0.06) !important;
}

/* ── Tab bar ── */
[data-testid="stTabs"] button {
    font-family: var(--font-mono) !important;
    font-size: 13px !important;
}

/* ── Hide Streamlit chrome ── */
#stDecoration, #stStatusWidget, .stDeployButton { display: none !important; }

/* ── Toast ── */
.stToast {
    background: #1A1D26 !important;
    border: 1px solid rgba(0, 212, 170, 0.3) !important;
    font-family: var(--font-mono);
}
</style>
"""


def inject_styles():
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def render_status_dot(label, status):
    color = {"healthy": "green", "down": "red", "warning": "amber"}.get(status, "amber")
    st.markdown(
        f'<div class="health-item">'
        f'<span class="status-dot {color}"></span>'
        f'{label}'
        f'</div>',
        unsafe_allow_html=True
    )


def render_file_card_html(name, size_mb, fmt, entries, upload_date):
    chip_class = {"csv": "csv", "json": "json", "txt": "txt"}.get(fmt, "csv")
    size_str = f"{size_mb:.1f} MB" if size_mb < 1024 else f"{size_mb/1024:.1f} GB"
    entries_str = f"{entries:,} entries" if entries else ""
    date_str = upload_date[:19].replace("T", " ") if upload_date else ""

    meta_parts = [p for p in [size_str, entries_str, date_str] if p]
    meta_line = " &middot; ".join(meta_parts)

    return f"""
    <div class="file-card">
        <div class="file-name">{name}<span class="format-chip {chip_class}">{fmt}</span></div>
        <div class="file-meta">{meta_line}</div>
    </div>
    """


def render_empty_state():
    st.markdown("""
    <div class="empty-state">
        <div class="empty-icon">&#9783;</div>
        <div class="empty-title">No logs uploaded yet</div>
        <div class="empty-desc">Drag and drop CSV, TXT, or JSON log files above to get started</div>
    </div>
    """, unsafe_allow_html=True)


def check_service_health(url, path="/", timeout=2):
    import requests
    try:
        r = requests.get(f"{url}{path}", timeout=timeout)
        if r.status_code == 200:
            return "healthy"
        return "warning"
    except Exception:
        return "down"
