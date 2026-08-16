#warehouse services
import datetime 
import json




def now():
    return datetime.datetime.now(datetime.timezone.utc)


warehouse = {
    "APPLES": {"quantity": 100, "expiry": "2026-08-20"},
    "BANANAS": {"quantity": 50, "expiry": "2026-08-18"},
    
}


def check_inventory_for_item(name):
    if name not in warehouse:
            return {
                "success": False,
                "message": f"{name} not a key in warehouse",
                "display": True
            }
    else:
        return {
           "success": True,
           "message": f"Inventory for {name}: {warehouse[name]}",
           "display": True
       }

def check_inventory():
    s = "Item                              Quantity"
    s+= "\n"
    for name,data in warehouse.items():
        s+= f"{name}                              {data["quantity"]}"
        s+= "\n"

    return {
                "success": True,
                "message": f"{s}",
                "display": True
            }
    

def close_to_expiry():
    today = now()
    s = "Item                                                Expires"
    s+="\n"
    for name,data in warehouse.items():
        expiry = datetime.datetime.fromisoformat(data["expiry"]).replace(tzinfo=datetime.timezone.utc)
        if (expiry - today).days <= 3:
            s +=f"{name}                             {expiry} ({(expiry - today).days} days)"
            s+="\n"

    return {
            "success": True,
            "message": f"{s}",
            "display": True
        }



def remove_item(name):
    warehouse.pop(name)
    # print(warehouse.items())
    return {
                "success": True,
                "message": f"Removed {name}",
                "display": True
            }


def add_item(name, quantity, expiry):
    if not expiry or not quantity or not name or expiry == "" or expiry == " " or expiry =="undefined":
        return {
            "success": False,
            "message": "Expiry date is required"
        }
    warehouse[name] = {"quantity":quantity, "expiry":f"{expiry}"}
    return {
        "success": True,
        "message": f"Added {quantity} {name}"
    }


# def update_item(item,quantity):
#     pwarehouse[item].items()
#     warehouse[item] = {"quantity":quantity, "expiry":f"{expiry}"}


def apply_tool(reply):
    response = json.loads(reply)
    tool = response["tool"]
    args = response["arguments"]

    tool = allow_list[tool]
    # print(tool)
    # print(args)
    return tool(**args)

def task_complete(summary):
    return {
            "success": True,
            "message": f"{summary}",
            "stop": True 
        }
    
def undefined_task(summary):
    return task_complete(summary)


allow_list = {
    "check_inventory_for_item": check_inventory_for_item,
    "add_item":add_item,
    "remove_item":remove_item,
    "close_to_expiry": close_to_expiry,
    "check_inventory": check_inventory,
    "undefined_task": undefined_task,
    "task_complete": task_complete
} 


tool_descriptions = """
1. check_inventory_for_item
Takes in a singular argument which is the item name in all caps and returns the information about it 

2. check_inventory
Takes no arguments returns the entire inventory as a string to user's terminal

3. close_to_expiry 
Takes no arguments, and iterates through the inventory to see which items are close to expiring

4. remove_item
Takes one argument that is the item name in all caps and deletes it from the warehouse dict

5. add_item 
Takes 3 arguments, the item name (i.e "APPLES" in all caps), quantity, and expiry date. Is not used for updating item
values only for adding new ones. 

6. task_complete
Takes in 1 string argument which is a summary to show the user upon (un) successful completion of a task

7. undefined_task 
Takes in 1 string argument which will be shown to the user, detailing the issue with their prompt i.e missing information 



"""

