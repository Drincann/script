import json
import os
from typing import List

DATA_DIR = os.path.expanduser('~/.worklog_cli')

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def get_file_path(date_str: str) -> str:
    return os.path.join(DATA_DIR, f"{date_str}.json")

def read_tasks(date_str: str) -> List[dict]:
    ensure_data_dir()
    file_path = get_file_path(date_str)
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r') as f:
        return json.load(f)

def write_tasks(date_str: str, tasks: List[dict]):
    ensure_data_dir()
    file_path = get_file_path(date_str)
    with open(file_path, 'w') as f:
        json.dump(tasks, f, indent=2)
