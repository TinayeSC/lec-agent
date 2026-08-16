#This is where we feed the prompt assembly into the llm 
import ollama
from ollama import chat
from ollama import ChatResponse
from urllib import request
import urllib.request
import psutil 
import json


#The Following functions have been taken and (marginally) adapted from Rashka's Building a LLM from Scratch
def check_if_running(process_name):
    running = False
    for proc in psutil.process_iter(["name"]):
        if process_name in proc.info["name"]:
            running = True
            break
    return running 




def query_model(prompt,model="llama3", url="http://localhost:11434/api/chat"):
    ollama_running = check_if_running("ollama")

    if not ollama_running:
                print("Ollama running:", check_if_running("ollama"))
                raise RuntimeError("Ollama is not running. Launch ollama (ollama run llama3) before proceeding.")

    data = {
        "model":model,
        "seed":123,
        "temperature":0,
        "messages": [
            {"role": "user", "content": prompt} #"stream":True
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



if __name__ == "__main__":
    print("Running...") 
    llama = "llama3"
    result = query_model("What do Llamas eat?", llama)
    print(result)
