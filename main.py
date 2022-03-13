from schedule import schedule, datetime_from_utc_to_local
from task import task

import json
from datetime import datetime, timedelta
import time

startDate = "2022-02-08T14:30:00.000Z"
days = 7
priorities = ["end-date", "priority"]
workDays = ["weekdays", "weekends", "all"]
workTime = ["14:00", "22:00"] #utc times. Same as 9 to 5
focusTime = 45
breakTime = 15

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
startDate = datetime.strptime("2022-02-08T14:30:00.000Z", "%Y-%m-%dT%H:%M:%S.%fZ")

cal = schedule(processed_events, startDate, ["14:00", "22:00"])
# for start, end in cal.free_time:
#     print(datetime_from_utc_to_local(start), datetime_from_utc_to_local(end))

init_tasks = []
for todo in todos["items"]:
    new_task = task(
        todo["id"],
        todo["title"],
        todo["time"],
        todo["importance"],
        todo["due-date"],
    )
    init_tasks.append(new_task)


tasks = cal.schedule_tasks(init_tasks)
for task in tasks:
    print(task["id"], datetime_from_utc_to_local(task["start"]), datetime_from_utc_to_local(task["end"]))