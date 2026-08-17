#warehouse services
import datetime
import json
from pathlib import Path




def now():
    return datetime.datetime.now(datetime.timezone.utc)


# ---- warehouse state ---------------------------------------------------
# This used to be a plain module-level dict literal:
#
#     warehouse = {"APPLES": {"quantity": 100, "expiry": "2026-08-20"}, ...}
#
# which meant inventory reset on every launch while processed_ids.txt kept
# persisting — the two halves of the agent's state disagreed between runs.
# It now lives in warehouse.json, created from warehouse.seed.json on first
# run so a fresh clone works and so the demo can be reset by deleting it.
#
# warehouse.json is validated on load for the same reason the feed is: this
# process is the only writer, but "only we write it" is an assumption, and
# checking the shape costs six lines.

WAREHOUSE_PATH = Path("warehouse.json")        # live state, gitignored
SEED_PATH = Path("warehouse.seed.json")        # committed starting state


def load_warehouse():
    if not WAREHOUSE_PATH.exists():
        WAREHOUSE_PATH.write_text(SEED_PATH.read_text())

    data = json.loads(WAREHOUSE_PATH.read_text())
    if not isinstance(data, dict):
        raise ValueError("warehouse.json is not a JSON object")

    # keys starting with "_" are notes for human readers, not stock
    data = {k: v for k, v in data.items() if not k.startswith("_")}

    for name, item in data.items():
        if not isinstance(item, dict) or set(item) != {"quantity", "expiry"}:
            raise ValueError(f"malformed warehouse entry '{name}': expected exactly quantity and expiry")
        if not isinstance(item["quantity"], int) or isinstance(item["quantity"], bool):
            raise ValueError(f"non-integer quantity for '{name}'")
        if not isinstance(item["expiry"], str):
            raise ValueError(f"non-string expiry for '{name}'")
    return data


def save_warehouse():
    # write-then-rename: a crash mid-write can't leave a half-written warehouse
    tmp = WAREHOUSE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(warehouse, indent=2, sort_keys=True))
    tmp.replace(WAREHOUSE_PATH)


warehouse = load_warehouse()

# ---- output formatting -------------------------------------------------
# Every tool returns the same shape, so the agent loop never has to guess
# whether a result is printable.

WIDTH = 52
NAME_W, QTY_W = 16, 7


def ok(message, stop=False):
    result = {"success": True, "message": message, "display": True}
    if stop:
        result["stop"] = True
    return result


def err(message):
    return {"success": False, "message": message, "display": True}


def block(title, headers, rows, footer=None):
    out = ["", f"  {title.upper()}", "  " + "─" * WIDTH]
    if headers:
        out.append("  " + "".join(h.ljust(w) for h, w in headers))
    if rows:
        out.extend("  " + r for r in rows)
    else:
        out.append("  (none)")
    out.append("  " + "─" * WIDTH)
    if footer:
        out.append(f"  {footer}")
    return "\n".join(out) + "\n"

def check_inventory_for_item(name):
    if name not in warehouse:
        return err(f"{name} is not in the warehouse.")
    d = warehouse[name]
    return ok(block(f"Item · {name}", None, [
        f"{'Quantity'.ljust(NAME_W)}{d['quantity']}",
        f"{'Expiry'.ljust(NAME_W)}{d['expiry']}",
    ]))


def check_inventory():
    rows = [f"{n.ljust(NAME_W)}{str(d['quantity']).rjust(QTY_W)}   {d['expiry']}"
            for n, d in sorted(warehouse.items())]
    return ok(block("Warehouse inventory",
                    [("ITEM", NAME_W), ("QTY".rjust(QTY_W), QTY_W + 3), ("EXPIRES", 0)],
                    rows, f"{len(rows)} item(s)"))


def close_to_expiry(days=3):
    today, rows = now(), []
    for n, d in sorted(warehouse.items()):
        exp = datetime.datetime.fromisoformat(d["expiry"]).replace(tzinfo=datetime.timezone.utc)
        left = (exp - today).days
        if left <= days:
            note = "EXPIRED" if left < 0 else ("today" if left == 0 else f"{left} day(s)")
            rows.append(f"{n.ljust(NAME_W)}{d['expiry'].ljust(14)}{note}")
    return ok(block(f"Expiring within {days} days",
                    [("ITEM", NAME_W), ("EXPIRES", 14), ("IN", 0)],
                    rows, f"{len(rows)} item(s) need attention"))


def remove_stale_stock():
    today = now()
    # list() first — popping while iterating warehouse.items() raises RuntimeError
    stale = [(n, d) for n, d in sorted(warehouse.items())
             if (datetime.datetime.fromisoformat(d["expiry"])
                 .replace(tzinfo=datetime.timezone.utc) - today).days <= 0]
    for name, _ in stale:
        warehouse.pop(name)
    if stale:
        save_warehouse()
    rows = [f"{n.ljust(NAME_W)}{str(d['quantity']).rjust(QTY_W)}   expired {d['expiry']}"
            for n, d in stale]
    return ok(block("Removed expired stock",
                    [("ITEM", NAME_W), ("QTY".rjust(QTY_W), QTY_W + 3), ("REASON", 0)],
                    rows, f"{len(rows)} item(s) removed"))



def remove_item(name):
    if name not in warehouse:
        return err(f"Cannot remove {name} — it is not in the warehouse.")
    warehouse.pop(name)
    save_warehouse()
    return ok(f"Removed {name} from the warehouse.")


def add_item(name, quantity, expiry):
    if not name or quantity is None or not expiry or str(expiry).strip() in ("", "undefined"):
        return err("add_item needs a name, a quantity and a real expiry date.")
    if name in warehouse:
        return err(f"{name} already exists — use increase_stock or update_item instead.")
    warehouse[name] = {"quantity": quantity, "expiry": str(expiry)}
    save_warehouse()
    return ok(f"Added {name} — {quantity} unit(s), expires {expiry}.")


def task_complete(summary):
    return ok(f"\n  ✓ {summary}\n", stop=True)


def undefined_task(summary):
    # Deliberately NOT success: a task we cannot do must not be logged as EXECUTED.
    return {"success": False, "message": f"\n  ⚠ {summary}\n", "display": True, "stop": True}







tool_descriptions = {
    "remove_stale_stock":{
        "description": (
                    "Remove ALL items that are past their expiry date "
                    "Use this when the user asks to remove ALL expired warehouse stock "
                   
                ),
                "parameters": {
                   
                },
                "example_input": {
                }

    },
    "check_inventory_for_item": {
        "description": (
            "Check the current inventory information for ONE specific item. "
            "Use this when the user asks about the quantity or expiry information "
            "of a particular item."
        ),
        "parameters": {
            "name": {
                "type": "string",
                "required": True,
                "description": "The item name in uppercase, e.g. 'APPLES'."
            }
        },
        "example_input": {
            "name": "APPLES"
        }
    },

    "check_inventory": {
        "description": (
            "Return the entire current warehouse inventory. "
            "Use this when the user asks to see, inspect, or list the entire inventory."
        ),
        "parameters": {},
        "example_input": {}
    },

    "close_to_expiry": {
        "description": (
            "Find warehouse items that are close to their expiry date. "
            "Use this when the user asks which products are expiring soon "
            "or need attention because of their expiry date."
        ),
        "parameters": {},
        "example_input": {}
    },

    "remove_item": {
        "description": (
            "Permanently remove an existing item from the warehouse inventory. "
            "Use this ONLY when the user explicitly asks to remove or delete "
            "an item from inventory."
        ),
        "parameters": {
            "name": {
                "type": "string",
                "required": True,
                "description": "The existing item name in uppercase, e.g. 'APPLES'."
            }
        },
        "example_input": {
            "name": "APPLES"
        }
    },

    "add_item": {
        "description": (
            "Add a NEW product to the warehouse inventory. "
            "This tool is ONLY for adding new items and must not be used "
            "to update the quantity or expiry of an existing item."
        ),
        "parameters": {
            "name": {
                "type": "string",
                "required": True,
                "description": "The new item name in uppercase, e.g. 'ORANGES'."
            },
            "quantity": {
                "type": "integer",
                "required": True,
                "description": "The quantity to add. Must be greater than 0."
            },
            "expiry": {
                "type": "string",
                "required": True,
                "description": (
                    "The expiry date. Do not invent this value. "
                    "Do not use an empty string, null, or 'undefined'."
                )
            }
        },
        "example_input": {
            "name": "ORANGES",
            "quantity": 50,
            "expiry": "2026-09-20"
        }
    },

    "task_complete": {
        "description": (
            "Tell the user that their requested task has been successfully completed. "
            "Use this ONLY after the requested operation has actually succeeded."
        ),
        "parameters": {
            "summary": {
                "type": "string",
                "required": True,
                "description": "A short summary explaining what was successfully done."
            }
        },
        "example_input": {
            "summary": "Successfully added 50 ORANGES to the warehouse."
        }
    },

    "undefined_task": {
        "description": (
            "Tell the user that their task cannot safely or completely be performed. "
            "Use this when required information is missing, the requested operation "
            "is unsupported, or the task cannot be completed with the available tools."
        ),
        "parameters": {
            "summary": {
                "type": "string",
                "required": True,
                "description": (
                    "A short explanation of what information is missing "
                    "or why the task cannot be completed."
                )
            }
        },
        "example_input": {
            "summary": "I need an expiry date before I can add the oranges."
        }
    },
    "update_item": {
    "description": (
        "Update the quantity and/or expiry date of an EXISTING warehouse item. "
        "This OVERWRITES the given field(s) with the new value(s) — it does not "
        "add to or subtract from the current quantity. Do NOT use this to add a "
        "brand-new item (use add_item) or to increase/decrease stock by an amount "
        "(use increase_stock / decrease_stock)."
    ),
    "parameters": {
        "name": {
            "type": "string",
            "required": True,
            "description": "The existing item name in uppercase, e.g. 'APPLES'."
        },
        "quantity": {
            "type": "integer",
            "required": False,
            "description": "The new absolute quantity. Only include if the task specifies an exact new quantity, not an amount to add/remove."
        },
        "expiry": {
            "type": "string",
            "required": False,
            "description": "The new expiry date. Only include if the task specifies a new date."
        }
    },
    "example_input": {
        "name": "APPLES",
        "quantity": 120,
        "expiry": "2026-10-01"
    }
},

"decrease_stock": {
    "description": (
        "Reduce the quantity of an EXISTING item by a given amount, without "
        "removing the item entirely. Use this when stock is sold, used, or "
        "partially removed. This is DIFFERENT from remove_item, which deletes "
        "the item completely regardless of quantity. Fails if the amount "
        "requested exceeds current stock."
    ),
    "parameters": {
        "name": {
            "type": "string",
            "required": True,
            "description": "The existing item name in uppercase, e.g. 'BANANAS'."
        },
        "quantity": {
            "type": "integer",
            "required": True,
            "description": "The amount to subtract from current stock. Must be greater than 0."
        }
    },
    "example_input": {
        "name": "BANANAS",
        "quantity": 10
    }
},

"increase_stock": {
    "description": (
        "Increase the quantity of an EXISTING item by a given amount, e.g. when "
        "new stock arrives for a product already in the warehouse. This ADDS to "
        "the current quantity — it does not set an absolute new value (use "
        "update_item for that) and does not create a new item (use add_item for "
        "that, which also requires an expiry date)."
    ),
    "parameters": {
        "name": {
            "type": "string",
            "required": True,
            "description": "The existing item name in uppercase, e.g. 'APPLES'."
        },
        "quantity": {
            "type": "integer",
            "required": True,
            "description": "The amount to add to current stock. Must be greater than 0."
        }
    },
    "example_input": {
        "name": "APPLES",
        "quantity": 25
    }
},

"find_low_stock": {
    "description": (
        "Find all warehouse items whose quantity is at or below a given "
        "threshold. Use this when asked which items are running low or need "
        "reordering."
    ),
    "parameters": {
        "threshold": {
            "type": "integer",
            "required": True,
            "description": "The quantity level to check against. Items with quantity <= threshold are returned."
        }
    },
    "example_input": {
        "threshold": 10
    }
}
}

#----------------------AI WRITTEN FUNCTIONS---------------------------------------------------
def update_item(name, quantity=None, expiry=None):
    if name not in warehouse:
        return err(f"{name} is not in the warehouse.")
    changed = []
    if quantity is not None:
        warehouse[name]["quantity"] = quantity
        changed.append(f"quantity → {quantity}")
    if expiry is not None:
        warehouse[name]["expiry"] = expiry
        changed.append(f"expiry → {expiry}")
    if not changed:
        return err(f"Nothing to update on {name} — give a quantity or an expiry.")
    save_warehouse()
    return ok(f"Updated {name}: {', '.join(changed)}.")


def decrease_stock(name, quantity):
    if name not in warehouse:
        return err(f"{name} is not in the warehouse.")
    have = warehouse[name]["quantity"]
    if quantity > have:
        return err(f"Cannot remove {quantity} {name} — only {have} in stock.")
    warehouse[name]["quantity"] -= quantity
    save_warehouse()
    return ok(f"Removed {quantity} {name}: {have} → {warehouse[name]['quantity']} unit(s).")


def increase_stock(name, quantity):
    if name not in warehouse:
        return err(f"{name} is not in the warehouse.")
    have = warehouse[name]["quantity"]
    warehouse[name]["quantity"] += quantity
    save_warehouse()
    return ok(f"Added {quantity} {name}: {have} → {warehouse[name]['quantity']} unit(s).")


def find_low_stock(threshold):
    rows = [f"{n.ljust(NAME_W)}{str(d['quantity']).rjust(QTY_W)}"
            for n, d in sorted(warehouse.items()) if d["quantity"] <= threshold]
    return ok(block(f"Low stock (<= {threshold})",
                    [("ITEM", NAME_W), ("QTY".rjust(QTY_W), 0)],
                    rows, f"{len(rows)} item(s) at or below {threshold}"))






allow_list = {
    "check_inventory_for_item": check_inventory_for_item,
    "add_item": add_item,
    "remove_item": remove_item,
    "close_to_expiry": close_to_expiry,
    "check_inventory": check_inventory,
    "undefined_task": undefined_task,
    "task_complete": task_complete,
    "update_item": update_item,
    "decrease_stock":decrease_stock,
    "increase_stock": increase_stock,
    "remove_stale_stock":remove_stale_stock,
    "find_low_stock":find_low_stock
}

def apply_tool(response):
  
  
    tool = response["tool"]
    args = response["arguments"]
   
    tool = allow_list[tool]
   
    return tool(**args)