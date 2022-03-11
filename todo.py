

class todo():

    def __init__(self, title, total_time, importance, due_date, breakable=True, focus=45):
        self.title = title
        self.time_remaining = total_time
        self.total_time = total_time
        self.importance = importance
        self.due_date = due_date
        self.breakable = breakable
        self.focus = focus

    def get_priority():
        w_i, w_d, w_bp, w_t, w_dd, w_dc = ()

    def get_slots():
        if not breakable:
            return [self.time_remaining]
        else:
            slots = []
            time = self.time_remaining
            while time > 0:
                slot = min(time, self.focus)
                time -= slot
                slots.append(slot)
            return slots