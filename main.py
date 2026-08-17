
from agent import Agent, Outcome
from validator import validate_task,log_task_event,save_processed_ids,load_processed_ids
from pathlib import Path
import tools
import docs
import json


FAILED = 0 
SUCCEEDED = 1 
UNDEFINED = 3

#Welcome Art Created by Claude
WELCOME_ART = (
      "╔═════════════════════════════════════════════════════════════╗",
      "║                                                             ║",
      "║    █   █  ███  ████  █████ █   █  ███  █   █  ████ █████    ║",
      "║    █   █ █   █ █   █ █     █   █ █   █ █   █ █     █        ║",
      "║    █ █ █ █████ ████  ████  █████ █   █ █   █  ███  ████     ║",
      "║    ██ ██ █   █ █  █  █     █   █ █   █ █   █     █ █        ║",
      "║    █   █ █   █ █   █ █████ █   █  ███   ███  ████  █████    ║",
      "║                                                             ║",
      "║    ┌───┬───┬───┐                                            ║",
      "║    │▓▓▓│▓▓▓│▓▓▓│   A  G  E  N  T                            ║",
      "║    ├───┼───┼───┤   ─────────────────────────────────        ║",
      "║    │▓▓▓│▓▓▓│▓▓▓│   untrusted feed → sanitise → execute      ║",
      "║    └───┴───┴───┘                                            ║",
      "║                                                             ║",
      "╠═════════════════════════════════════════════════════════════╣",
      "║      built for LEC-AI  ·  thank you for the assessment      ║",
      "╚═════════════════════════════════════════════════════════════╝",
)

HELP_DETAILS = "\n".join(
    [
        "Commands:",
        "/feed    Run the untrusted feed through an Agent (Agent won't stop iterating through feed tasks).",
        "/usage   Show a README section. '/usage' lists them, '/usage 4' or '/usage sanitisation' jumps straight there.",
        "/reset   Restore the warehouse from seed and clear processed ids.",
        "/help    Displays available commands.",
        "/exit    Exit the agent.",
    ]
)


def process_feed(feed_path, agent, processed_ids):

    with open(feed_path) as f:
        raw_tasks = json.load(f)

    valid_tasks = []

    for raw_task in raw_tasks:
        result = validate_task(raw_task)

        if result["status"] in ("rejected", "quarantined"):
            log_task_event(result["status"].upper(), raw_task, result["reason"],0)
            continue

        task = result["task"]
        if task["id"] in processed_ids:
            continue  # already handled on a previous poll


        # append the VALIDATED copy, not the raw dict — raw may be missing
        # 'priority', which validate_task defaults to "normal"
        valid_tasks.append(task)

    valid_tasks = sorted(
    valid_tasks,
    key=lambda t: {"high": 0, "normal": 1, "low": 2}[t["priority"]]
    )

    print(f"\n  Polling feed — {len(valid_tasks)} task(s) passed validation\n")
    for task in valid_tasks:
        outcome, attempt = Outcome.FAILED, 0
        for attempt in range(1, 3):
            outcome = agent.run(task["action"])
            # SUCCEEDED is done; UNDEFINED will answer the same way forever
            if outcome in (Outcome.SUCCEEDED, Outcome.UNDEFINED):
                break
            if attempt < 2:
                print(f"  ↻ retry {attempt}/2 — {task['id']}")

        status = {
            Outcome.SUCCEEDED: "EXECUTED",
            Outcome.UNDEFINED: "UNSUPPORTED",
            Outcome.FAILED: "ESCALATED",
        }[outcome]
        processed_ids.append(task["id"])
        log_task_event(status, task, "", attempt)

    save_processed_ids(processed_ids)
    print(f"\n  Poll complete — {len(processed_ids)} task(s) processed to date\n")

agent = Agent()
print("\033[36m" + "\n".join(WELCOME_ART) + "\033[0m")
print("\033[36m" + (HELP_DETAILS) + "\033[0m")
print("\033[36m" + f"Hey I am {agent.name} your Warehouse Agent. What can I help you with? " + "\033[0m")
while True:
        
        prompt = input("\033[36m" + "→ "+ "\033[0m").strip()
        if not prompt:
            continue 
        elif prompt.lower() in {"/exit","/quit","/stop","/bye"} :
            break
        elif prompt.lower() in {"/feed"}:
             ids = load_processed_ids()
             process_feed("feed.json",agent,ids)
             continue
        elif prompt.lower() in {"help"}:
            print("\033[36m" + (HELP_DETAILS) + "\033[0m")
        elif prompt.lower() in {"/reset"}:
             # wipe both halves of persisted state so the demo can be re-run
             for path in (Path("warehouse.json"), Path("processed_ids.txt")):
                 path.unlink(missing_ok=True)
             tools.warehouse = tools.load_warehouse()   # reload from the seed
             print("\n  State reset — warehouse restored from seed, processed ids cleared\n")
             continue
        elif prompt.lower().split()[0] in {"/usage","/help","/docs"}:
             # /usage renders README.md itself, so the help text can never
             # drift from the documentation. "/usage <query>" skips the menu.
             sections = docs.load_sections()
             if not sections:
                 print("\n  README.md not found — nothing to show.\n")
                 continue

             query = prompt.split(maxsplit=1)[1] if len(prompt.split()) > 1 else ""
             if not query:
                 print(docs.list_sections(sections))
                 query = input("\033[36m" + "  section→ " + "\033[0m").strip()
                 if not query:
                     continue

             title, problem = docs.find_section(sections, query)
             if problem:
                 print(f"\n  {problem}\n")
                 continue
             print(docs.render(title, sections[title]))
        elif prompt.lower() in {"/load","/set"}:
             # planned, not built — kept out of HELP_DETAILS so the menu only
             # advertises what actually works
             print("\n  Not implemented yet.\n")
             continue

        
        
        else:
            for attempt in range(1, 3):
                outcome = agent.run(prompt)
                if outcome == Outcome.SUCCEEDED:
                    break
                if outcome == Outcome.UNDEFINED:
                    # a definite "no" — retrying would ask the same question
                    print("  ⚠ Not something I can do with the tools I have — not retrying.\n")
                    break
                if attempt < 2:
                    print(f"  ↻ retry {attempt}/2")
                else:
                    print("  ! Giving up after 2 attempts — escalating.\n")

         

       