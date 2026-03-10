"""配置管理"""
import os
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # 环境变量覆盖敏感配置
    wechat_token = os.environ.get("WECHAT_TOKEN", "")
    if wechat_token:
        cfg.setdefault("notify", {}).setdefault("wechat", {})["token"] = wechat_token

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        cfg.setdefault("ai_reflection", {})["api_key"] = anthropic_key

    return cfg


# 尝试加载 .env 文件（简单实现，不依赖 python-dotenv）
def _load_dotenv():
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()
