from schedule import schedule, datetime_from_utc_to_local
from task import Task
from ga import Cluster, GA

import json
from datetime import datetime, timedelta
import time

startDate = "2022-02-08T14:00:00.000Z"
days = 7
priorities = ["end-date", "priority"]
workDays = ["weekdays", "weekends", "all"]
workTime = ["14:00", "22:00"]

f = open('classes.json')
events = json.load(f)

f = open('to-do.json')
todos = json.load(f)

def event_string_to_date(windows):
    date_windows = []
    for window in windows:
        date_windows.append(
            (datetime.strptime(window['start'], "%Y-%m-%dT%H:%M:%S.%fZ"),
            datetime.strptime(window['end'], "%Y-%m-%dT%H:%M:%S.%fZ"))
        )
    return date_windows

processed_events = event_string_to_date(events['items'])
startDate = datetime.strptime(startDate, "%Y-%m-%dT%H:%M:%S.%fZ")

cal = schedule(processed_events, startDate, ["14:00", "22:00"])

init_tasks = []
for todo in todos["items"]:
    new_task = Task(
        todo["id"],
        todo["title"],
        todo["time"],
        todo["importance"],
        todo["difficulty"],
        datetime.strptime(todo["due-date"], "%Y-%m-%dT%H:%M:%S.%fZ"),
    )
    init_tasks.append(new_task)

ga = GA(cal, init_tasks)
res = ga.optimize(max_iteraions=1000)

print(res[1])
for task in res[0].tasks:
    for subtask in task.subtasks:
        # print(task.id, datetime_from_utc_to_local(subtask["start"]), datetime_from_utc_to_local(subtask["end"]))
        print(task.id, subtask["start"], subtask["end"])