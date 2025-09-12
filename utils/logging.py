import os
import json
from datetime import datetime
from typing import Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
LOG_FILE = os.path.join(PROJECT_ROOT, "agent_log.json")


def _to_serializable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _to_serializable(v) for k, v in obj.items()}
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    if hasattr(obj, "dict"):
        try:
            return obj.dict()  
        except Exception:
            pass
    try:
        return str(obj)
    except Exception:
        return repr(obj)


def log_entry(entry_type: str, content: Any) -> None:
    entry = {
        "type": entry_type,
        "content": _to_serializable(content),
    }
    text = json.dumps(entry, indent=2, default=str)
    print(text)

    # Read existing log entries
    entries = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    # Try to parse as array first, then as single object for backward compatibility
                    try:
                        entries = json.loads(content)
                        if not isinstance(entries, list):
                            entries = [entries]  # Convert single object to array
                    except json.JSONDecodeError:
                        # If not valid JSON, start fresh
                        entries = []
        except Exception:
            entries = []

    # Append new entry
    entries.append(entry)

    # Write all entries back as array
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, default=str, ensure_ascii=False)


def log_input(content: Any) -> None:
    log_entry("input", content)


def log_agent_setup(content: Any) -> None:
    log_entry("agent_setup", content)


def log_invoke_start(content: Any) -> None:
    log_entry("invoke_start", content)


def log_step(content: Any) -> None:
    log_entry("step", content)


def log_error(content: Any) -> None:
    log_entry("error", content)


def write_pretty_json(filename: str, data: Any) -> str:
    print(data)
    path = filename if os.path.isabs(filename) else os.path.join(PROJECT_ROOT, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_to_serializable(data), f, indent=2, ensure_ascii=False)
    return path
