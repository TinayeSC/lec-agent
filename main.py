from agent import WorkspaceContext,now
import state 
import llm 
import tools
import validator 
import argparse



warehouse = {
    "APPLES": {"quantity": 100, "expiry": "2026-08-20"},
    "BANANAS": {"quantity": 50, "expiry": "2026-08-18"},
    
}


session = ""
with open("session1.txt","w") as f:
    f.writelines(session)


    while True:
        # print(prompt)
        prompt = input("--> ").strip()
        if not prompt:
            continue 
        if prompt.lower() in {"/exit"}:
            break
        while True: 
            session += f"Timestamp: {now()}\n"
        
            
            reply = llm.query_model(prompt)


            # print(reply)
            result = tools.apply_tool(reply)
            # print(result)

        
            session += f"""
    User task: {prompt}
    Agent decision: {reply}
    Tool result: {result}
                """
            state.set_session_memory(session)
            if result["success"] and "stop" in result:
                if "message" in result:
                    print(result["message"])
                break
            if "display" in result and "message" in result:
                print(result["message"])

            f.writelines(session)

      


f.close()

print("Session History stored in session folder")

   

