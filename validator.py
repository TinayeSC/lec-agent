# sanitiser.py
import re
import json
import datetime
from pathlib import Path
from tools import tool_descriptions


#input validation as per LEC -AI instructions
ALLOW_LIST = {
    "check_inventory_for_item",
    "add_item",
    "remove_item",
    "close_to_expiry",
    "check_inventory",
    "undefined_task",
    "task_complete",
    "update_item",
    "remove_stale_stock",
    "decrease_stock",
    "increase_stock",
    "find_low_stock"
}

def _reject(message):
    return False, {"success": False, "message": f"\n  ✗ {message}\n", "display": True}


def validate_decision(response):
    try:
        decision = json.loads(response)
    except Exception:
        return _reject(f"Could not parse a JSON tool call. Got: {response}")

    if not isinstance(decision, dict):
        return _reject(f"Decision is not an object. Got: {decision}")

    if set(decision.keys()) != {"tool", "arguments"}:
        return _reject(f"Decision must have exactly 'tool' and 'arguments'. Got: {decision}")

    tool = decision["tool"]
    args = decision["arguments"]

    if tool not in ALLOW_LIST:
        return _reject(f"Tool '{tool}' is not on the allowlist.")

    if not isinstance(args, dict):
        return _reject(f"Arguments must be an object. Got: {args}")

    num_args = len(tool_descriptions[tool]["parameters"])
    if num_args != len(args):
        return _reject(f"'{tool}' takes {num_args} argument(s), got {len(args)}: {sorted(args)}")

    return True, decision



#----------------------CLAUDE CHAT CREATED SKELETON AND REGEX--------------------------------

# --- Layer 1: schema (allowlist) ---

ALLOWED_TASK_FIELDS = {"id", "action", "priority"}
ALLOWED_PRIORITIES = {"low", "normal", "high"}
TASK_ID_PATTERN = re.compile(r"^task-\d+$")
MAX_ACTION_LENGTH = 500


# --- Layer 2: content patterns (defense-in-depth, not primary control) ---

SUSPICIOUS_PATTERNS = [
    re.compile(r"\bignore\s+(all\s+)?(previous|prior|above)\s+instructions?\b", re.I),
    re.compile(r"\byou\s+are\s+now\b", re.I),
    re.compile(r"\bnew\s+instructions?\b", re.I),
    re.compile(r"\b(system|assistant)\s*:", re.I),
    re.compile(r"\b(override|disregard)\b", re.I),
    re.compile(r"\bauthoris(e|ed|ation)|\bauthoriz", re.I),
    re.compile(r"###|\[system\]|<\|.*?\|>"),
    # command-injection-flavoured — see note below
    re.compile(r"[;&|`]"),
    re.compile(r"\$\("),
    re.compile(r"\b(subprocess|os\.system|eval|exec)\s*\(", re.I),
]


def validate_task(raw_task):
    if not isinstance(raw_task, dict):
        return {"status": "rejected", "reason": "task is not a JSON object"}

    extra = set(raw_task.keys()) - ALLOWED_TASK_FIELDS
    if extra:
        return {"status": "rejected", "reason": f"unexpected field(s): {sorted(extra)}"}

    task_id = raw_task.get("id")
    if not isinstance(task_id, str) or not TASK_ID_PATTERN.match(task_id):
        return {"status": "rejected", "reason": "missing or invalid 'id'"}

    action = raw_task.get("action")
    if not isinstance(action, str) or not action.strip():
        return {"status": "rejected", "reason": "missing or invalid 'action'"}
    if len(action) > MAX_ACTION_LENGTH:
        return {"status": "rejected", "reason": "'action' exceeds max length"}

    priority = raw_task.get("priority", "normal")
    if priority not in ALLOWED_PRIORITIES:
        return {"status": "rejected", "reason": f"invalid priority '{priority}'"}

    for pattern in SUSPICIOUS_PATTERNS:
        if pattern.search(action):
            return {
                "status": "quarantined",
                "reason": f"suspicious pattern matched in 'action': {pattern.pattern}",
            }

    return {"status": "valid", "task": {"id": task_id, "action": action, "priority": priority}}


STATUS_MARK = {"EXECUTED": "✓", "REJECTED": "✗", "QUARANTINED": "⚠",
               "ESCALATED": "!", "UNSUPPORTED": "⊘"}


def log_task_event(status, task, reason, attempts=0):
    task_id = task.get("id", "<no id>") if isinstance(task, dict) else "<malformed>"
    with open("task_logs.txt", "a") as f:
        f.write(json.dumps({
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": status,
            "task_id": task_id,
            "task": task,
            "reason": reason if isinstance(reason, str) else str(reason),
            "attempts": attempts,
        }) + "\n")
    print(f"  {STATUS_MARK.get(status, '·')} {status:<12} {task_id:<10} {reason}")


def save_processed_ids(ids):
    with open("processed_ids.txt", "w") as f:
        for task_id in ids:
            f.write(task_id + "\n")


def load_processed_ids():
    path = Path("processed_ids.txt")
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]
