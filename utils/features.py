"""Feature registry and management for Quick Log application."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class FeatureCategory(Enum):
    SETTINGS = "Settings"


@dataclass
class FeatureConfig:
    name: str
    key: str
    description: str
    category: FeatureCategory
    prerequisites: List[str]
    page_file: Optional[str] = None
    config_schema: Dict[str, Any] = field(default_factory=dict)
    requires_config: bool = False


FEATURE_REGISTRY: Dict[str, FeatureConfig] = {
    "log_analytics_elk": FeatureConfig(
        name="Quick Log (ELK Stack)",
        key="log_analytics_elk",
        description="Upload CSV logs and analyze with Elasticsearch + Kibana",
        category=FeatureCategory.SETTINGS,
        prerequisites=["docker"],
        page_file="pages/log_uploader.py",
        requires_config=True,
        config_schema={
            "upload_dir": {"type": "string", "default": "uploads", "label": "Upload Directory"},
            "max_file_size_mb": {"type": "int", "default": 500, "label": "Max File Size (MB)", "min": 10, "max": 2000}
        }
    )
}


def get_feature_config(feature_key: str) -> Optional[FeatureConfig]:
    return FEATURE_REGISTRY.get(feature_key)


__all__ = [
    "FeatureConfig",
    "FeatureCategory",
    "FEATURE_REGISTRY",
    "get_feature_config",
]
