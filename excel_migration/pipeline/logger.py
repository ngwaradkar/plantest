import csv
import traceback
import datetime
import os

LOG_FILE = os.path.join(os.path.dirname(__file__), "run_logs.csv")
HEALTH_FILE = os.path.join(os.path.dirname(__file__), "system_health.txt")

def init_log():
    with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Date/Time", "Process", "Source", "Status", "Message", "Error Details", "Duration"])
    with open(HEALTH_FILE, 'w', encoding='utf-8') as f:
        f.write("GREEN")

def get_health():
    if not os.path.exists(HEALTH_FILE): return "GREEN"
    with open(HEALTH_FILE, 'r', encoding='utf-8') as f:
        return f.read().strip()

def set_health(new_health):
    curr = get_health()
    if curr == "RED": return  # RED cannot be downgraded
    if curr == "YELLOW" and new_health == "GREEN": return
    with open(HEALTH_FILE, 'w', encoding='utf-8') as f:
        f.write(new_health)

def log_event(process, source, status, message, details="", duration=0):
    if not os.path.exists(LOG_FILE):
        init_log()
        
    if status == "Error":
        set_health("YELLOW")
    elif status == "Critical":
        set_health("RED")
        status = "Error"
        
    with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            process,
            source,
            status,
            message,
            str(details).replace('\n', ' | '),
            f"{duration}s"
        ])
