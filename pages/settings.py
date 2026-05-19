import streamlit as st
import os
from utils.config_loader import load_config, save_config
from utils.features import FEATURE_REGISTRY
from utils.prerequisites import check_docker, check_colima_memory
from utils.styles import inject_styles, check_service_health, render_status_dot
from utils.urls import (
    ELASTICSEARCH_INTERNAL,
    LOGSTASH_INTERNAL,
    KIBANA_INTERNAL,
    get_kibana_external,
)

inject_styles()

st.title(":material/settings: Quick Log Settings")

config = load_config()

if "features" not in config:
    config["features"] = {}

feature_key = "log_analytics_elk"
feature_def = FEATURE_REGISTRY[feature_key]
feature_config = config["features"].get(feature_key, {}).get("config", {})

tab_upload, tab_diagnostics = st.tabs([
    ":material/folder: Upload",
    ":material/science: Diagnostics"
])

# ──────────────────────────────────────────────────────────────
# Tab 1: Upload Settings
# ──────────────────────────────────────────────────────────────
with tab_upload:
    upload_settings = {}
    for field_key in ["upload_dir", "max_file_size_mb"]:
        field_def = feature_def.config_schema[field_key]
        label = field_def.get("label", field_key)
        default = field_def.get("default")
        current_val = feature_config.get(field_key, default)

        if field_def["type"] == "string":
            upload_settings[field_key] = st.text_input(label, value=current_val, key=f"cfg_{field_key}")
        elif field_def["type"] == "int":
            upload_settings[field_key] = st.number_input(
                label,
                value=current_val,
                min_value=field_def.get("min"),
                max_value=field_def.get("max"),
                key=f"cfg_{field_key}"
            )

updated_features = {
    feature_key: {
        "enabled": True,
        "config": upload_settings
    }
}

# ──────────────────────────────────────────────────────────────
# Tab 2: Diagnostics
# ──────────────────────────────────────────────────────────────
with tab_diagnostics:
    st.subheader(":material/build: Runtime Status")

    mem_status = check_colima_memory()
    if mem_status["status"] == "insufficient":
        st.error(f":material/warning: {mem_status['message']}")
        st.info("Please restart Colima with more memory to enable this feature.")
        st.code(mem_status["restart_command"], language="bash")
    elif mem_status["status"] == "warning":
        st.warning(f":material/warning: {mem_status['message']}")
        if st.button("How to increase memory?", key="btn_mem_help"):
            st.code(mem_status["restart_command"], language="bash")
    else:
        st.success(f":material/check_circle: {mem_status['message']}")

    docker_status = check_docker()
    if not docker_status["running"]:
        st.warning(":material/warning: Docker/Colima not detected. ELK stack requires a running container runtime.")
        with st.expander("ELK Setup Guide"):
            st.markdown("""
            ### Prerequisites
            1. **Install Colima** (Recommended for Mac)
               ```bash
               brew install colima
               colima start --memory 4 --cpu 2
               ```
            2. **Or Install Docker Desktop**
               https://www.docker.com/products/docker-desktop
            3. **Start the Stack**
               ```bash
               ./manage_stack.sh start
               ```
            """)
    else:
        st.success(f":material/check_circle: Docker ({docker_status['method']}) is running.")

    st.divider()

    st.subheader(":material/link: Service URLs")
    st.caption("URLs are auto-derived from Docker service names and the `QUICK_LOG_HOST` environment variable.")

    url_cols = st.columns(2)
    with url_cols[0]:
        st.markdown("**Internal (Docker network)**")
        st.code(f"Elasticsearch  {ELASTICSEARCH_INTERNAL}", language=None)
        st.code(f"Logstash       {LOGSTASH_INTERNAL}", language=None)
        st.code(f"Kibana         {KIBANA_INTERNAL}", language=None)
    with url_cols[1]:
        st.markdown("**External (Browser)**")
        st.code(f"Kibana         {get_kibana_external()}", language=None)
        st.caption("ES and Logstash are internal-only — not exposed outside Docker.")

    st.divider()

    st.subheader(":material/science: Connection Tests")

    test_cols = st.columns(3)
    with test_cols[0]:
        if st.button("Test Elasticsearch", key="test_es", use_container_width=True):
            import requests
            try:
                r = requests.get(f"{ELASTICSEARCH_INTERNAL}/_cluster/health", timeout=5)
                if r.status_code == 200:
                    st.success(f":material/check_circle: ES: {r.json().get('status', 'unknown')}")
                else:
                    st.error(f":material/error: ES: HTTP {r.status_code}")
            except Exception as e:
                st.error(f":material/error: ES: {str(e)[:60]}")

    with test_cols[1]:
        if st.button("Test Logstash", key="test_ls", use_container_width=True):
            import requests
            try:
                r = requests.get(LOGSTASH_INTERNAL, timeout=5)
                st.success(f":material/check_circle: Logstash: HTTP {r.status_code}")
            except Exception as e:
                st.error(f":material/error: Logstash: {str(e)[:60]}")

    with test_cols[2]:
        if st.button("Test Kibana", key="test_kb", use_container_width=True):
            import requests
            try:
                r = requests.get(f"{KIBANA_INTERNAL}/api/status", timeout=5)
                if r.status_code == 200:
                    st.success(":material/check_circle: Kibana: Running")
                else:
                    st.warning(f":material/warning: Kibana: HTTP {r.status_code}")
            except Exception as e:
                st.error(f":material/error: Kibana: {str(e)[:60]}")

# ──────────────────────────────────────────────────────────────
# Save
# ──────────────────────────────────────────────────────────────
st.divider()

if st.button(":material/save: Save Configuration", type="primary", use_container_width=True):
    try:
        config["features"] = updated_features

        upload_dir = upload_settings.get("upload_dir", "uploads")
        os.makedirs(upload_dir, exist_ok=True)

        save_config(config)
        st.toast("Configuration saved", icon=":material/check_circle:")
    except Exception as e:
        st.error(f"Error saving config: {str(e)}")
