import streamlit as st
from typing import Dict
from utils.features import get_feature_config
from utils.prerequisites import check_prerequisites


def validate_feature(feature_key: str, app_config: Dict) -> Dict:
    """Validate a feature and return user-friendly report."""
    feature_def = get_feature_config(feature_key)
    if not feature_def:
        return {"valid": False, "errors": ["Feature definition not found"]}

    prereqs = feature_def.prerequisites
    status = check_prerequisites(prereqs, app_config)
    
    errors = []
    warnings = []
    actions = []

    for prereq, res in status["results"].items():
        if prereq == "docker" and not res["running"]:
            errors.append("Docker/Colima is not running. ELK stack services require a container runtime.")
            actions.append({"label": "View Setup Guide", "type": "setup_guide"})

    return {
        "valid": status["all_met"],
        "errors": errors,
        "warnings": warnings,
        "actions": actions,
        "results": status["results"]
    }


def render_feature_error(feature_key: str, validation_result: Dict):
    """Standardized error display for feature pages."""
    if validation_result["valid"]:
        return

    st.error(f"⚠️ {feature_key.replace('_', ' ').title()} Unavailable")
    
    for error in validation_result["errors"]:
        st.markdown(f"- {error}")

    if validation_result["actions"]:
        st.divider()
        for action in validation_result["actions"]:
            if action["type"] == "setup_guide":
                st.info("💡 See the **Setup Guide** in the Settings page.")

    st.divider()
    if st.button("🏠 Back to Home", key=f"back_{feature_key}"):
        st.switch_page("pages/log_uploader.py")


def require_feature(feature_key: str):
    """Decorator-like function to protect feature pages.
    
    Note: ELK is always enabled, so we just validate prerequisites.
    """
    from utils.config_loader import load_config
    config = load_config()
    
    validation = validate_feature(feature_key, config)
    if not validation["valid"]:
        render_feature_error(feature_key, validation)
        st.stop()
    
    return config
