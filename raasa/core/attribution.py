from __future__ import annotations

from typing import Any, Mapping

from raasa.core.models import FeatureVector


FEATURE_ATTRIBUTION_FIELDS: tuple[tuple[str, str], ...] = (
    ("cpu", "cpu_signal"),
    ("memory", "memory_signal"),
    ("process", "process_signal"),
    ("network", "network_signal"),
    ("syscall", "syscall_signal"),
    ("syscall_jsd", "syscall_jsd_signal"),
    ("file_entropy", "file_entropy_signal"),
    ("network_entropy", "network_entropy_signal"),
    ("dns_entropy", "dns_entropy_signal"),
)


def linear_shap_attributions(
    feature: FeatureVector,
    weights: Mapping[str, float],
) -> list[dict[str, Any]]:
    """
    Return exact SHAP values for RAASA's zero-baseline additive linear model.

    For a model f(x)=sum(w_i*x_i), the SHAP value from a zero-risk baseline is
    exactly w_i*x_i. This keeps attribution deterministic and dependency-light.
    """

    rows: list[dict[str, Any]] = []
    for feature_name, attribute_name in FEATURE_ATTRIBUTION_FIELDS:
        value = float(getattr(feature, attribute_name, 0.0) or 0.0)
        weight = float(weights.get(feature_name, 0.0) or 0.0)
        contribution = value * weight
        rows.append(
            {
                "feature": feature_name,
                "value": value,
                "weight": weight,
                "shap_value": contribution,
            }
        )
    rows.sort(key=lambda item: abs(float(item["shap_value"])), reverse=True)
    return rows
