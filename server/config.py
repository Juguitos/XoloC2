import os
import json
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "xolo.json"

def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_config(data: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get(key: str, default=None):
    return load_config().get(key, default)

def set_value(key: str, value):
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)

# JWT settings
JWT_SECRET = get("jwt_secret") or os.urandom(32).hex()
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 180  # 3 hours

# Agent shared secret for beacon auth
AGENT_SECRET = get("agent_secret") or os.urandom(16).hex()

# Persist secrets if not already saved
if not get("jwt_secret"):
    cfg = load_config()
    cfg["jwt_secret"] = JWT_SECRET
    cfg["agent_secret"] = AGENT_SECRET
    save_config(cfg)
