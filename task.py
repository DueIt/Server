
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
        self.subtasks.append(subtask)
        if len(self.subtasks) == 1:
            self.proximity = 1
            return

        adjacent = 0
        for i in range(1, len(self.subtasks)):
            if self.subtasks[i - 1]["end"] == self.subtasks[i]["start"]:
                adjacent += 1
        
        self.proximity = adjacent / (len(self.subtasks) - 1.0)

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