#agentic loop (harness ala rashka)
import datetime
from pathlib import Path
import subprocess

import llm 
import tools
import validator 
import argparse
import random
from enum import IntEnum


# from llm import query_model
# from state import update_state
from validator import validate_decision
# from tools import execute_tool 

agent_names = ["Bob", "Dave", "Shane"]


class Outcome(IntEnum):
    """Why a run stopped. The caller uses this to decide whether to retry.

    The distinction that matters is FAILED vs UNDEFINED. A FAILED run might
    succeed on a second attempt — the model produced an unparseable tool call,
    or a tool errored on something that could change. An UNDEFINED run is the
    agent stating the task cannot be done at all, which is a deterministic
    answer: retrying re-asks an identical question and burns an LLM call to
    get an identical reply.
    """

    FAILED = 0        # retry may help
    SUCCEEDED = 1     # done
    UNDEFINED = 3     # cannot be done — never retry


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

class Agent:
    def __init__(self):
        self.session = ""
        self.name = random.choice(agent_names)
        self.session_start = now()

    def run(self,task):
        while True:

            self.session += f"Timestamp: {now()}\n"

            reply = llm.query_model(task,self.session)

            valid, response = validate_decision(reply)
            if not valid:
                  # the model proposed something the allowlist refused. A retry
                  # draws a fresh sample, so this is worth another attempt.
                  if "message" in response:
                        print(response["message"])
                  return Outcome.FAILED

            result = tools.apply_tool(response)

            self.session += f"""

User task: {task}
Agent decision: {reply}
Tool result: {result}

                            """

            self.save_session()

            if "display" in result and "message" in result:
                  print(result["message"])

            # undefined_task is the agent reporting the task is impossible with
            # the tools it has. That answer will not change on a second ask.
            if response["tool"] == "undefined_task":
                  return Outcome.UNDEFINED

            if result.get("success"):
                  return Outcome.SUCCEEDED

            return Outcome.FAILED

            

    def save_session(self):
         # git can't track an empty dir, so a fresh clone has no SessionMemory/
         Path("SessionMemory").mkdir(exist_ok=True)
         with open(f"SessionMemory/{self.name}_session_{self.session_start}.txt","w") as f:
              f.writelines(self.session)

    def load_session(self,filepath):
          session = ""
          with open(filepath,"r") as f:
                for line in f.lines():
                      session += line
          self.session += session
          f.close()

        
    