#agentic loop (harness ala rashka)
import datetime
from pathlib import Path
import subprocess

import llm 
import tools
import validator 
import argparse
import random 


# from llm import query_model
# from state import update_state
from validator import validate_decision
# from tools import execute_tool 

agent_names = ["Bob", "Dave", "Shane"]

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

class Agent:
    def __init__(self):
        self.session = ""
        self.name = random.choice(agent_names)
        self.session_start = now()

    def run(self,task):
        task_complete = False
        while True:

            self.session += f"Timestamp: {now()}\n"
                    
                        
            reply = llm.query_model(task,self.session)

           

            valid, response = validate_decision(reply)
            # print("Validator: "
            #             f"{valid}\n"
            #             f"{response}")
            if not valid:
                  return response 
            
            # print(f"Applying tool: {response}")
                        
            result = tools.apply_tool(response)  
            
            self.session += f"""

User task: {task}
Agent decision: {reply}
Tool result: {result}

                            """
            
            self.save_session()

            if result.get("success") and result.get("stop"):
                        if "message" in result:
                            print(result["message"])
                        task_complete = True
                        break

            if "display" in result and "message" in result:
                                    print(result["message"])

            if result.get("stop"):
                  task_complete = False
                  break

            if not result.get("success"):
                   task_complete = False
                   break

            if result.get("success"):
                   task_complete = True
                   break
    
            
       

        return task_complete

            

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

        
    