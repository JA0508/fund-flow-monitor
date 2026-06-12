from __future__ import annotations

import os
import re
from pathlib import Path


TRUE_VALUES = {"1", "true", "yes", "y", "on"}
FALSE_VALUES = {"0", "false", "no", "n", "off"}
PUBLIC_DEMO_ENV_FLAGS = ("FUND_FLOW_PUBLIC_DEMO", "STREAMLIT_PUBLIC_DEMO")
FORBIDDEN_PHRASES = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "抄底",
    "逃顶",
    "推荐买",
    "推荐卖",
    "建议买",
    "建议卖",
    "建仓",
    "清仓",
    "未来会涨",
    "未来会跌",
    "适合配置",
    "应该调仓",
    "趋势确立",
    "反转确认",
    "强烈看好",
    "明确机会",
    "建议关注",
)


def get_env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return default


def detect_public_demo_profile() -> dict:
    env_flags = {name: get_env_flag(name, False) for name in PUBLIC_DEMO_ENV_FLAGS}
    enabled_by = [name for name, enabled in env_flags.items() if enabled]
    public_demo_enabled = bool(enabled_by)
    cloud_hints = [
        name
        for name in ("STREAMLIT_SERVER_PORT", "STREAMLIT_SHARING_MODE", "HOSTNAME")
        if os.environ.get(name)
    ]
    warnings: list[str] = []
    if cloud_hints and not public_demo_enabled:
        warnings.append("检测到可能的云端运行环境变量；如用于公开演示，可显式设置 FUND_FLOW_PUBLIC_DEMO=1。")
    return {
        "public_demo_enabled": public_demo_enabled,
        "detection_method": ",".join(enabled_by) if enabled_by else "not_enabled",
        "env_flags": env_flags,
        "profile_label": "公开演示安全配置" if public_demo_enabled else "本地默认运行配置",
        "profile_reason": (
            "已通过环境变量显式开启 public demo profile。"
            if public_demo_enabled
            else "未显式开启 public demo profile，保持本地默认运行方式。"
        ),
        "warnings": warnings,
        "errors": [],
    }


def _has_csv(directory: Path) -> bool:
    return directory.exists() and any(directory.glob("*.csv"))


def get_runtime_profile(project_root: str | Path = ".") -> dict:
    root = Path(project_root)
    demo_detection = detect_public_demo_profile()
    public_demo_enabled = bool(demo_detection.get("public_demo_enabled"))
    sample_data_available = _has_csv(root / "sample_data/ticks")
    local_data_available = _has_csv(root / "data/ticks")
    warehouse_available = (root / "data/warehouse/fund_flow.sqlite").exists()
    streamlit_config_available = (root / ".streamlit/config.toml").exists()
    secrets_example_available = (root / ".streamlit/secrets.example.toml").exists()
    warnings = list(demo_detection.get("warnings", []))
    errors: list[str] = []

    if public_demo_enabled and sample_data_available:
        default_data_source_mode = "SAMPLE"
        default_presentation_mode = "作品集演示模式"
        safe_write_mode = "read_only_demo"
        runtime_label = "公开演示安全配置可用"
        runtime_reason = "public demo profile 已开启，默认使用 SAMPLE 合成演示数据和作品集演示模式。"
    elif public_demo_enabled:
        default_data_source_mode = "SAMPLE_UNAVAILABLE"
        default_presentation_mode = "作品集演示模式"
        safe_write_mode = "read_only_demo"
        runtime_label = "公开演示配置缺少 SAMPLE"
        runtime_reason = "public demo profile 已开启，但 sample_data/ticks 中没有可用 CSV。"
        errors.append("公开演示模式需要 sample_data/ticks 中至少包含一个 CSV 文件。")
    else:
        default_data_source_mode = "LOCAL"
        default_presentation_mode = "标准模式"
        safe_write_mode = "local_default"
        runtime_label = "本地默认运行配置"
        runtime_reason = "未开启 public demo profile，保持本地真实数据 / 本地缓存默认体验。"

    return {
        "public_demo_enabled": public_demo_enabled,
        "detection_method": demo_detection.get("detection_method"),
        "env_flags": demo_detection.get("env_flags", {}),
        "sample_data_available": sample_data_available,
        "local_data_available": local_data_available,
        "warehouse_available": warehouse_available,
        "streamlit_config_available": streamlit_config_available,
        "secrets_example_available": secrets_example_available,
        "default_data_source_mode": default_data_source_mode,
        "default_presentation_mode": default_presentation_mode,
        "safe_write_mode": safe_write_mode,
        "runtime_label": runtime_label,
        "runtime_reason": runtime_reason,
        "warnings": warnings,
        "errors": errors,
    }


def build_runtime_profile_notice(profile: dict) -> str:
    if profile.get("public_demo_enabled"):
        if profile.get("sample_data_available"):
            return (
                "当前为公开演示安全配置：默认使用 SAMPLE 合成演示数据和作品集演示模式。"
                "SAMPLE 不代表真实行情；页面不会自动读取真实账户或持仓，也不提供交易建议或预测。"
                "真实数据 / 本地缓存模式仍可在本地环境中手动选择。"
            )
        return (
            "当前已开启公开演示安全配置，但未找到 SAMPLE 合成演示数据。"
            "系统不会生成假数据；请先确认 sample_data/ticks 已提交并可读取。"
        )
    return "当前为本地默认运行配置。公开演示可通过 FUND_FLOW_PUBLIC_DEMO=1 启用 SAMPLE 优先的安全默认值。"


def build_runtime_profile_sidebar_defaults(profile: dict) -> dict:
    public_demo_enabled = bool(profile.get("public_demo_enabled"))
    sample_ready = bool(profile.get("sample_data_available"))
    return {
        "data_source_default": "SAMPLE" if public_demo_enabled and sample_ready else "LOCAL",
        "presentation_default": "作品集演示模式" if public_demo_enabled else "标准模式",
        "enable_live_fetch_default": False if public_demo_enabled else True,
        "enable_sample_default": bool(sample_ready),
        "show_runtime_notice": public_demo_enabled,
        "disable_auto_write": public_demo_enabled,
    }


def validate_runtime_profile_text(text: str) -> list[str]:
    if not text:
        return []
    hits: list[str] = []
    for phrase in FORBIDDEN_PHRASES:
        if phrase in text:
            hits.append(phrase)
    slash_users = "/" + "Users/"
    windows_users = r"[A-Za-z]:\\" + "Users" + r"\\"
    if re.search(re.escape(slash_users) + "|" + windows_users, text):
        hits.append("local_path")
    return sorted(set(hits), key=hits.index)
