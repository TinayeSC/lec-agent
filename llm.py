#This is where we feed the prompt assembly into the llm 
import ollama
from ollama import chat
from ollama import ChatResponse
from urllib import request
import urllib.request
import psutil 
import json
from agent import WorkspaceContext
import ast
import state 


#The Following functions have been taken and (marginally) adapted from Rashka's Building a LLM from Scratch
def check_if_running(process_name):
    running = False
    for proc in psutil.process_iter(["name"]):
        if process_name in proc.info["name"]:
            running = True
            break
    return running 

def listTools():
     tools = ""
     with open("tools.py","r") as f:
          tree = ast.parse(f.read())
          for node in ast.walk(tree):
               if isinstance(node,ast.FunctionDef):
                    if node.name != "now" and node.name != "apply_tool":
                         tools += node.name
                         tools+="\n"
     return tools 
                    


def query_model(prompt,model="llama3", url="http://localhost:11434/api/chat"):

    ollama_running = check_if_running("ollama")

    if not ollama_running:
                print("Ollama running:", check_if_running("ollama"))
                raise RuntimeError("Ollama is not running. Launch ollama (ollama run llama3) before proceeding.")

    

    workspace = WorkspaceContext.build(".")
    promptAssembly = """
You are being used as an agent for warehouse operations, below is information to help you decipher what tool to choose.

DECISION RULES:

1. You are trying to complete the ORIGINAL USER PROMPT.
2. Look at SESSION HISTORY to see what has already happened.
3. Do not repeat a tool that has already successfully completed its purpose.
4. If a required argument is missing, use undefined_task.
5. If the original task has been successfully completed, use task_complete.
6. Otherwise, choose exactly one tool needed for the next step.


Only choose one tool at a time.
Respond with ONLY valid JSON, the warehouse is structured as so: 

    warehouse = {
    "APPLES": {"quantity": 7, "expiry": "2026-09-20"},
    "BANANAS": {"quantity": 9, "expiry": "2026-09-18"},
    
}

NOTE: THESE ARE JUST EXAMPLE VALUES 

warehouse items have 3 values (name in all caps, quantity and expiry date)
and the output should be EXACTLY like the structured output

STRUCTURED OUTPUT:
   
  "tool": "{one of the available tools}",
  "arguments": { ... }
}

"""
    promptAssembly +=f"""
ONLY EVER RETURN text formatted like that above.

Workspace Context:  
 {workspace}

Available Tools: 
{listTools()}

Descriptions (Argument names in brackets):
1. check_inventory_for_item
Takes in a singular argument which is the item name in all caps and returns the information about it 
(name)

2. check_inventory
Takes no arguments returns the entire inventory as a string to user's terminal
()

3. close_to_expiry 
Takes no arguments, and iterates through the inventory to see which items are close to expiring
()

4. remove_item
Takes one argument that is the name (i.e "APPLES" )  in all caps and deletes it from the warehouse dict
(name)

5. add_item 
Takes 3 arguments, the name (i.e "APPLES" ) in all caps, quantity, and expiry date. Is not used for updating item
values only for adding new ones. 
(name,quantity,expiry)

6. task_complete
Takes in 1 string argument which is a summary to show the user upon (un) successful completion of a task
(summary)

7. undefined_task 
Takes in 1 string argument (summary) which will be shown to the user, detailing the issue with their prompt i.e missing information 
(summary)

Session History: 
{state.get_session_memory()}

User Prompt:
{prompt}

ONLY REPLY WITH THE JSON FORMATTED OUTPUT
"""
    # print("========== PROMPT ==========")
    # print(promptAssembly)
    # print("============================")
    data = {
        "model":model,
        "seed":123,
        "temperature":0,
        "messages": [
            {"role": "user", "content": promptAssembly} #"stream":True
        ]
    }

    payload = json.dumps(data).encode("utf-8")
    request = urllib.request.Request(url,data=payload,method="POST")
    request.add_header("Content-Type","application/json")

    response_data = ""
    with urllib.request.urlopen(request) as response:
        while True:
            line = response.readline().decode("utf-8")
            if not line:
                break
            response_json = json.loads(line)
            response_data += response_json["message"]["content"]

    return response_data 



session = ""

if __name__ == "__main__":
    tools = listTools()
    print(tools)
    print("Running...") 
    llama = "llama3"
    result = query_model("Delete warehouse", llama)
    print(result)
