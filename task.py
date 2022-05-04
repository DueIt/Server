from datetime import datetime, timedelta

class Task():

    def __init__(self, id, title, total_time, importance, difficulty, due_date, breakable=True):
        self.id = id
        self.title = title
        self.total_time = total_time
        self.due_date = due_date
        self.breakable = breakable
        self.subtasks = []

        self.difficulty = difficulty/2 #range 0 to 2 corresponding to easy, medium, hard
        self.importance = importance/4 #range 0 to 4
        self.time_remaining = total_time
        self.proximity = 0


    def add_subtask(self, subtask):
        # self.subtasks.append(subtask)
        # if len(self.subtasks) == 1:
        #     self.proximity = 1
        #     return

        adjacent = 0
        i = 0
        while i < len(self.subtasks) - 1:
            if self.subtasks[i]["end"] == self.subtasks[i + 1]["start"]:
                self.subtasks[i]["end"] == self.subtasks[i + 1]["end"]
                del self.subtasks[i + 1]
            else:
                i += 1
        
        # self.proximity = adjacent / (len(self.subtasks) - 1.0)
        self.subtasks.append(subtask)
        good = 0
        for task in self.subtasks:
            time_length = task["end"] - task["start"]
            if time_length > timedelta(minutes = 30) and time_length < timedelta(minutes = 70):
                good += 1
        self.proximity = good / (len(self.subtasks) * 3)

    def to_json(self):
        res = []
        for subtask in self.subtasks:
            res.append(
                dict({
                    'id': self.id,
                    'title': self.title,
                    'difficulty': self.difficulty,
                    'importance': self.importance,
                    'start': subtask["start"], 
                    'end': subtask["end"],
                })
            )
        return res