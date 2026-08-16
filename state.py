#persistence?
from tools import check_inventory
session = "Starting New Session..."

def set_session_memory(state):
    global session
    session = state 

def get_session_memory():
    return session

def get_state():
    return check_inventory()


def apply_tool(response):
    pass