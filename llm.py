#This is where we feed the prompt assembly into the llm 
import ollama
from ollama import chat
from ollama import ChatResponse
from urllib import request
import urllib.request
import psutil 
import json
import datetime
from pathlib import Path
import subprocess
import tools
import validator 
import argparse
import ast
from tools import tool_descriptions

DOC_NAMES = ("AGENTS.md", "README.md", "pyproject.toml", "package.json")
#-----------------FROM SEBASTIAN RASHKA MINI AGENT--------------------

MAX_TOOL_OUTPUT = 4000
MAX_HISTORY = 12000
IGNORED_PATH_NAMES = {".git", ".mini-coding-agent", "__pycache__", ".pytest_cache", ".ruff_cache", ".venv", "venv"}
##############################
#### 1) Live Repo Context ####
##############################
def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# Supporting helper for component 4 (context reduction and output management).
def clip(text, limit=MAX_TOOL_OUTPUT):
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"


class WorkspaceContext:
    def __init__(self, cwd, repo_root, branch, default_branch, status, recent_commits, project_docs):
        self.cwd = cwd
        self.repo_root = repo_root
        self.branch = branch
        self.default_branch = default_branch
        self.status = status
        self.recent_commits = recent_commits
        self.project_docs = project_docs

    @classmethod
    def build(cls, cwd):
        cwd = Path(cwd).resolve()

        def git(args, fallback=""):
            try:
                result = subprocess.run(
                    ["git", *args],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=5,
                )
                return result.stdout.strip() or fallback
            except Exception:
                return fallback

        repo_root = Path(git(["rev-parse", "--show-toplevel"], str(cwd))).resolve()
        docs = {}
        for base in (repo_root, cwd):
            for name in DOC_NAMES:
                path = base / name
                if not path.exists():
                    continue
                key = str(path.relative_to(repo_root))
                if key in docs:
                    continue
                docs[key] = clip(path.read_text(encoding="utf-8", errors="replace"), 1200)

        return cls(
            cwd=str(cwd),
            repo_root=str(repo_root),
            branch=git(["branch", "--show-current"], "-") or "-",
            default_branch=(git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], "origin/main") or "origin/main").removeprefix("origin/"),
            status=clip(git(["status", "--short"], "clean") or "clean", 1500),
            recent_commits=[line for line in git(["log", "--oneline", "-5"]).splitlines() if line],
            project_docs=docs,
        )

    def text(self):
        commits = "\n".join(f"- {line}" for line in self.recent_commits) or "- none"
        docs = "\n".join(f"- {path}\n{snippet}" for path, snippet in self.project_docs.items()) or "- none"
        return "\n".join([
            "Workspace:",
            f"- cwd: {self.cwd}",
            f"- repo_root: {self.repo_root}",
            f"- branch: {self.branch}",
            f"- default_branch: {self.default_branch}",
            "- status:",
            self.status,
            "- recent_commits:",
            commits,
            "- project_docs:",
            docs,
        ])


#Following functions have been adapted from Rashka's Building a LLM from Scratch
def check_if_running(process_name):
    running = False
    for proc in psutil.process_iter(["name"]):
        if process_name in proc.info["name"]:
            running = True
            break
    return running 

def listTools():
    output = ""

    for name, tool in tool_descriptions.items():

        output += f"""
TOOL: {name}
DESCRIPTION: {tool["description"]}
REQUIRED INPUTS: {", ".join(tool["parameters"].keys())}
"""

        if tool["example_input"]:
            output += f"""
EXAMPLE INPUT VALUES:
{json.dumps(tool["example_input"], indent=2)}
"""

    return output
                    


def query_model(prompt,session,model="qwen3:8b", url="http://localhost:11434/api/chat"):

    ollama_running = check_if_running("ollama")

    if not ollama_running:
                print("Ollama running:", check_if_running("ollama"))
                raise RuntimeError("Ollama is not running. Launch ollama (ollama run llama3) before proceeding.")

    

    workspace = WorkspaceContext.build(".")
    promptAssembly = """
You are an agent for warehouse operations. Use the information below to decide which single tool to call next.

DECISION RULES:
1. FIRST, check: does SESSION HISTORY already contain a successful tool result
   that answers or fulfils the CURRENT TASK? This applies to BOTH mutation
   tools (add_item, update_item, increase_stock, decrease_stock, remove_item)
   AND query/read-only tools (check_inventory, check_inventory_for_item,
   close_to_expiry, find_low_stock) — a single successful result from either
   kind is enough. Never call the same tool again "to confirm" or "to be
   sure". If satisfied, respond with task_complete immediately.
2. If a required argument is missing, use undefined_task. Do not invent values.
3. Only use argument values explicitly present in the CURRENT TASK or SESSION
   HISTORY — never from tool documentation examples, and never calculated,
   estimated, or guessed by you.
4. For a CHANGE described in relative terms ("received X more", "sold X",
   "used X", "X were damaged/lost"), use increase_stock or decrease_stock —
   they apply the change automatically. Do NOT use update_item for this: its
   quantity is an ABSOLUTE replacement value, and you do not know the item's
   current quantity unless a prior tool result in SESSION HISTORY has shown
   it to you. Use update_item ONLY when the task or a prior result gives you
   an exact new value directly.
5. Otherwise, choose exactly one tool needed for the next step.

STRUCTURED OUTPUT FORMAT (the ONLY shape you may return):
{
  "tool": "<one of the available tool names>",
  "arguments": { <actual values, not type descriptions> }
}

Example of a correct response:
{
  "tool": "add_item",
  "arguments": {"name": "ORANGES", "quantity": 50, "expiry": "YYYY-MM-DD"}
}

IMPORTANT:
- "arguments" must contain real values (real item names, real numbers, real dates) — never type descriptions.
- Never output the words "type", "required", or "description" in your response. Those words only appear in the tool documentation below to describe a tool; they are not part of a tool call.
- Respond with ONLY the JSON object above. No explanation, no markdown fences, no extra text.

Example — task already complete (mutation tool):
CURRENT TASK: "Add 40 oranges to inventory with expiry date 2026-08-25"
SESSION HISTORY already shows:
  Agent decision: {"tool": "add_item", "arguments": {"name": "ORANGES", "quantity": 40, "expiry": "2026-08-25"}}
  Tool result: {'success': True, 'message': 'Added 40 ORANGES'}
Correct response:
{"tool": "task_complete", "arguments": {"summary": "Successfully added 40 ORANGES to the warehouse."}}
Do NOT call any other tool — the task is already done.

Example — task already complete (query tool):
CURRENT TASK: "Check whether any products are close to expiry"
SESSION HISTORY already shows:
  Agent decision: {"tool": "close_to_expiry", "arguments": {}}
  Tool result: {'success': True, 'message': 'Item ... Expires ...'}
Correct response:
{"tool": "task_complete", "arguments": {"summary": "Checked items close to expiry."}}
Do NOT call close_to_expiry again — one successful result is enough, even
though the message doesn't say "success" in plain English.

Example — relative stock change:
CURRENT TASK: "We received 25 additional apples from the supplier"
Correct FIRST response:
{"tool": "increase_stock", "arguments": {"name": "APPLES", "quantity": 25}}
NOT update_item — you do not know APPLES' current quantity, so you cannot
supply a correct absolute value yourself. increase_stock adds 25 to whatever
the current quantity already is, without you needing to know or guess it.
"""

    promptAssembly += f"""
Warehouse Structure (for reference — values below are illustrative only):
{{
  "APPLES": {{"quantity": 7, "expiry": "2026-09-20"}},
  "BANANAS": {{"quantity": 9, "expiry": "2026-09-18"}}
}}

Workspace Context:
{workspace}

Available Tools (Follow the specifications for each tool):
{listTools()}

Session History:
{session}

Current Task:
{prompt}

Respond now with ONLY the JSON tool call and nothing else.
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
