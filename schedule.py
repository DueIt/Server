import json
from datetime import datetime, timedelta
import time
import copy

from task import Task


class schedule():

    def __init__(self, events, startDate, workHours, days=7):
        self.events = events
        self.startDate = startDate
        self.workHours = workHours
        self.days = days
        self.free_time, self.slot_times = self.find_free_time()

    def calc_workable_windows(self):
        endDate = self.startDate + timedelta(days=self.days)
        workStart = datetime.strptime(self.workHours[0], "%H:%M").time()
        workEnd = datetime.strptime(self.workHours[1], "%H:%M").time()
        newWorkEndTime = self.startDate.replace(hour=workEnd.hour, minute=workEnd.minute)
        newWorkStartTime = self.startDate.replace(hour=workStart.hour, minute=workStart.minute)
        windows = []

        starts = newWorkStartTime > self.startDate

        if starts:
            windows.append((self.startDate, newWorkStartTime))
            newWorkStartTime += timedelta(days=1)
            for i in range(self.days - 1):
                windows.append((newWorkEndTime, newWorkStartTime))
                newWorkEndTime += timedelta(days=1)
                newWorkStartTime += timedelta(days=1)
            windows.append((newWorkEndTime, endDate))
        else:
            for i in range(self.days):
                newWorkStartTime += timedelta(days=1)
                windows.append((newWorkEndTime, newWorkStartTime))
                newWorkEndTime += timedelta(days=1)
        return windows

    def find_free_time(self, locked_time=None):
        # TODO: remove events that are not between start and end dates

        tstart = self.startDate
        tend = tstart + timedelta(days=self.days)

        no_work = self.calc_workable_windows()
        events_work = no_work + self.events

        if locked_time:
            events_work = events_work + locked_time
        
        events_work = sorted(events_work, key=lambda k: k[0])
        tp = [(tstart, tstart)] + events_work
        free_time = []
        tp.append((tend, tend))

        # first combine any overlapping windows
        i = 0
        while i < len(tp) - 1:
            if tp[i][1] > tp[i + 1][0]:
                tp[i] = (tp[i][0], tp[i + 1][1])
                if i + 1 < len(tp):
                    tp.pop(i + 1)
            else:
                i += 1

        # define the freetime as all the gaps between the given windows
        i = 0
        while i < len(tp) - 1:
            free_window = (tp[i][1], tp[i + 1][0])
            free_time.append(free_window)
            i += 1
            
        free_time = sorted(free_time, key=lambda k: k[0])
        slot_times = []
        for start, end in free_time:
            slot = int((end - start).total_seconds() / 60)
            slot -= slot % 10
            slot_times.append(slot)

        #part of the constructor basically
        return (free_time, slot_times)


    def schedule_tasks(self, tasks, locked_time=None):
        if len(tasks) == 0:
            return []

        available_times = None
        temp_slot_times = None

        if locked_time:
            available_times, temp_slot_times = self.find_free_time(locked_time)
        else:
            available_times = self.free_time
            temp_slot_times = self.slot_times.copy()


        scheduled = []
        slot_i = 0
        task_i = 0
        space = True
        new_tasks = copy.deepcopy(tasks)

        while slot_i < len(temp_slot_times) and task_i < len(tasks):
            # consider adding in a random number where it might decide to skip a spot
            if temp_slot_times[slot_i] >= 10:
                if temp_slot_times[slot_i] > new_tasks[task_i].time_remaining:
                    new_task = {
                        "start": (available_times[slot_i][1] - timedelta(minutes=temp_slot_times[slot_i])),
                        "end": (available_times[slot_i][1] - timedelta(minutes=temp_slot_times[slot_i] - new_tasks[task_i].time_remaining)),
                    }
                    temp_slot_times[slot_i] -= new_tasks[task_i].time_remaining
                    new_tasks[task_i].add_subtask(new_task)
                    new_tasks[task_i].time_remaining = 0
                    
                else:
                    new_task = {
                        "start": (available_times[slot_i][1] - timedelta(minutes=temp_slot_times[slot_i])),
                        "end": (available_times[slot_i][1]),
                    }
                    new_tasks[task_i].time_remaining -= temp_slot_times[slot_i]
                    new_tasks[task_i].add_subtask(new_task)
                    temp_slot_times[slot_i] = 0
                    
                if temp_slot_times[slot_i] <= 0:
                    slot_i += 1
                if new_tasks[task_i].time_remaining <= 0:
                    task_i += 1
            else:
                slot_i += 1
        return new_tasks



def datetime_from_utc_to_local(utc_datetime):
    now_timestamp = time.time()
    offset = datetime.fromtimestamp(now_timestamp) - datetime.utcfromtimestamp(now_timestamp)
    return utc_datetime + offset



if __name__ == "__main__":
    f = open('classes.json')
    events = json.load(f)

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
    for start, end in cal.free_time:
        print(datetime_from_utc_to_local(start), datetime_from_utc_to_local(end))