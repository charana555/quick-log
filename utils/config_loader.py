import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.json')

URL_KEYS = {
    "elasticsearch_url", "kibana_url", "logstash_url",
    "elasticsearch_url_internal", "elasticsearch_url_external",
    "logstash_url_internal", "logstash_url_external",
    "kibana_url_internal", "kibana_url_external",
}


def _migrate_config(config):
    """Migrate old config keys and strip URL fields (now auto-derived)."""
    feature = config.get("features", {}).get("log_analytics_elk", {})
    cfg = feature.get("config", {})
    if not cfg:
        return config

    changed = False

    old_to_new = {
        "elasticsearch_url": ("elasticsearch_url_internal", "elasticsearch_url_external"),
        "kibana_url": ("kibana_url_internal", "kibana_url_external"),
        "logstash_url": ("logstash_url_internal", "logstash_url_external"),
    }

    for old_key, (int_key, ext_key) in old_to_new.items():
        if old_key in cfg:
            del cfg[old_key]
            changed = True

    for url_key in URL_KEYS:
        if url_key in cfg:
            del cfg[url_key]
            changed = True

    if changed:
        config["features"]["log_analytics_elk"]["config"] = cfg

    return config


def load_config():
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    config = _migrate_config(config)
    return config


def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)
