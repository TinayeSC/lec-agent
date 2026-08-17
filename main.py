
from agent import Agent
from validator import validate_task,log_task_event,save_processed_ids,load_processed_ids
from pathlib import Path
import tools
import docs
import json



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
        "/load    Opens a dialogue to load a session memory.",
        "/set     Opens dialogue to load processed ids.",
        "/help    Displays available commands.",
        "/exit    Exit the agent.",
    ]
)

warehouse = {
    "APPLES": {"quantity": 100, "expiry": "2026-08-20"},
    "BANANAS": {"quantity": 50, "expiry": "2026-08-18"},
    
}




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
        outcome, attempt = False, 0
        for attempt in range(1, 3):
            outcome = agent.run(task["action"])
            if outcome:
                break
            print(f"  ↻ retry {attempt}/2 — {task['id']}")
        processed_ids.append(task["id"])
        log_task_event("EXECUTED" if outcome else "ESCALATED", task, "", attempt)

    save_processed_ids(processed_ids)
    print(f"\n  Poll complete — {len(processed_ids)} task(s) processed to date\n")

agent = Agent("Bob")
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
        elif prompt.lower() in {"/load"}:
                    path = input("\033[36m" + "Enter A Filename To Load a Previous Session Memory→ "+ "\033[0m").strip()
                    with open(path,"r") as f:
                         print(" ")
        elif prompt.lower() in {"/set"}:
                            path = input("\033[36m" + "Enter Numbers Seperated by space (e.g 17 18 19) to add to processed IDs→ "+ "\033[0m").strip()
                            with open(path,"r") as f:
                                 print(" ")

        
        
        else:
            for attempt in range(0,2):
                result = agent.run(prompt)
                if result:
                    break
                else:
                    print(f"Attempt {attempt+1}/3")

         

       