import json, os

STATE_FILE = "state.json"

DEFAULT = {
    "paused": False
}

def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return DEFAULT.copy()

def save_state(state):
    json.dump(state, open(STATE_FILE, "w"), indent=2)

STATE = load_state()
