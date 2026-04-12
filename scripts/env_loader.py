import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)

ENV_CANDIDATES = [
    os.path.join(SKILL_DIR, "config", ".env"),
    os.path.join(SKILL_DIR, ".env"),
]


def load_env_file():
    for path in ENV_CANDIDATES:
        if not os.path.exists(path):
            continue

        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                if not key:
                    continue

                if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                    value = value[1:-1]

                os.environ.setdefault(key, value)
        return path

    return None