import json
from datetime import datetime, timezone


def log_event(event, **fields):
    payload = {
        "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "event": event,
    }

    for key, value in fields.items():
        if value is None:
            continue
        payload[key] = value

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))