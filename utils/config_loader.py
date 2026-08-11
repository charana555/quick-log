import json
import os
import shutil

CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'config')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'settings.json')
CONFIG_TEMPLATE_PATH = os.path.join(CONFIG_DIR, 'settings.template.json')

URL_KEYS = {
    "elasticsearch_url", "kibana_url",
    "elasticsearch_url_internal", "elasticsearch_url_external",
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


def _ensure_config_exists(config_path=CONFIG_PATH, template_path=CONFIG_TEMPLATE_PATH):
    if os.path.exists(config_path):
        return

    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    shutil.copyfile(template_path, config_path)


def load_config():
    _ensure_config_exists()
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    config = _migrate_config(config)
    return config


def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


def _self_check():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        config_path = os.path.join(tmp, 'settings.json')
        template_path = os.path.join(tmp, 'settings.template.json')
        expected = {"features": {}}

        with open(template_path, 'w') as f:
            json.dump(expected, f)

        _ensure_config_exists(config_path, template_path)

        with open(config_path, 'r') as f:
            assert json.load(f) == expected


if __name__ == '__main__':
    _self_check()
