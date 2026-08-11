import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
import streamlit as st
from utils.uploader_helper import get_es_count
from utils.styles import inject_styles, check_service_health, render_status_dot
from utils.urls import ELASTICSEARCH_INTERNAL, KIBANA_INTERNAL, get_kibana_external
from utils.validation import require_feature

config = require_feature("log_analytics_elk")
inject_styles()

st.title(":material/stream: Live Stream")

ES_URL = ELASTICSEARCH_INTERNAL
KIBANA_URL = get_kibana_external()
KB_URL_INT = KIBANA_INTERNAL

if "live_tag" not in st.session_state:
    st.session_state.live_tag = uuid.uuid4().hex[:8]

tag = st.session_state.live_tag

with st.sidebar:
    st.markdown("<br><br><br><br>", unsafe_allow_html=True)
    st.markdown("### :material/monitoring: Stack Health")
    health_cols = st.columns(2)
    with health_cols[0]:
        es_status = check_service_health(ES_URL, "/_cluster/health")
        render_status_dot("ES", es_status)
    with health_cols[1]:
        kb_status = check_service_health(KB_URL_INT, "/api/status")
        render_status_dot("KB", kb_status)

    st.divider()

    import requests

    try:
        r = requests.get(
            f"{ES_URL}/athena-logs/_count",
            json={"query": {"match": {"source": "live"}}},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        live_count = r.json().get("count", 0) if r.status_code == 200 else 0
    except Exception:
        live_count = 0

    doc_count = get_es_count(ES_URL)

    st.markdown("### :material/stream: Stream Stats")
    st.markdown(f"**{live_count:,}** live docs")
    st.markdown(f"**{doc_count:,}** total docs")

    st.divider()
    st.link_button(":material/open_in_new: Open Kibana", KIBANA_URL, use_container_width=True)

st.markdown(
    "Pipe terminal output or tail a log file directly into Elasticsearch. "
    "Logs appear in Kibana in near-real-time, filterable by your session tag."
)

st.info(
    "Live streaming requires `./manage_stack.sh start-live` to expose Elasticsearch on `localhost:9200`. "
    "This also installs the `ql` CLI on your PATH."
)

st.divider()

st.subheader(":material/terminal: Quick Start")

st.markdown("**1. Start the stack (one-time, exposes ES + installs ql CLI):**")
st.code("./manage_stack.sh start-live", language="bash")

st.markdown("**2. Generate a session tag:**")
tag_cols = st.columns([4, 1])
with tag_cols[0]:
    st.code(f"Session tag: {tag}")
with tag_cols[1]:
    if st.button(":material/refresh: New", help="Generate a new session tag"):
        st.session_state.live_tag = uuid.uuid4().hex[:8]
        st.rerun()

st.markdown("**3. Pipe your application output:**")
st.code(f"myapp 2>&1 | ql stream --tag {tag}", language="bash")

st.markdown("**Or tail a log file:**")
st.code(f"ql tail -f /var/log/app.log --tag {tag}", language="bash")

st.divider()

st.subheader(":material/filter_list: Kibana Filter")
st.markdown("In Kibana Discover, filter with:")
st.code(f'source:live AND stream_tag:{tag}', language="bash")

kibana_discover = f"{KIBANA_URL}/app/discover#/?_a=(index:'athena-logs*')"
st.link_button(":material/open_in_new: Open Kibana Discover", kibana_discover, use_container_width=True)
