from random import randrange
import random
from schedule import schedule, datetime_from_utc_to_local
import math
import copy

class Cluster():

    def __init__(self, tasks, calendar):
        self.tasks = tasks
        self.cal = calendar

        #positives
        self.proximity_weight = 0.1
        self.importance_weight = 0.3
        # self.difficulty_weight = 0.2
        self.distribution_weight = 0.2
        self.due_weight = 0.4


    def calc_task_fitness(self, task, start_date):
        # degrade value if the item is due in 2 days
        time_left = (task.due_date - start_date).total_seconds()
        time_lost = time_left
        if task.subtasks:
            time_lost = (task.subtasks[-1]["end"] - start_date).total_seconds()
        time_diff = math.tanh((time_left - time_lost) / 172800)
        if time_diff <= 0:
            time_diff = -0.5

        return self.proximity_weight * task.proximity + \
               self.due_weight * time_diff


    def calc_ordered_value(self, arr):
        if len(arr) == 0:
            return 0
        total = 0
        for i, val in enumerate(arr):
            for j in range(i, len(arr)):
                if arr[j] > val:
                    total += 1
        return total


    def calc_time_per_day(self, locked_time=None):
        free_time, _ = self.cal.find_free_time(locked_time=locked_time)
        cur_day = free_time[0][0].day
        time_per_day = [0]
        for period in free_time:
            if period[0].day == cur_day and period[1].day == cur_day:
                time_per_day[-1] += int((period[1] - period[0]).total_seconds() / 60)
            elif period[0].day == cur_day and period[1].day != cur_day:
                eod = period[0].replace(hour=11, minute=59)
                time_per_day[-1] += int((eod - period[0]).total_seconds() / 60)
                new_time = int((period[1] - eod).total_seconds() / 60)
                time_per_day.append(new_time)
                cur_day = period[1].day
            else:
                new_time = int((period[1] - period[0]).total_seconds() / 60)
                time_per_day.append(new_time)
                cur_day = period[1].day
        return time_per_day

    
    def calc_work_distribution(self):
        locked_times = []
        total_task_time = 0
        for task in self.tasks:
            total_task_time += task.total_time
            for subtask in task.subtasks:
                locked_times.append((subtask["start"], subtask["end"]))

        task_tpd = sorted(self.calc_time_per_day(locked_time=locked_times))
        no_task_tpd = sorted(self.calc_time_per_day())

        best_case = no_task_tpd.copy()
        best_case.reverse()
        time_left = total_task_time
        i = 0
        count = 1
        big = best_case[0]
        while i < len(best_case) - 1 and time_left > 0:
            if best_case[i] == best_case[i + 1]:
                count += 1
                i += 1
            else:
                diff = big - best_case[i + 1]
                max_gain = count * diff
                remove_time = min(max_gain, time_left)
                time_left -= remove_time
                big -= int(remove_time / count)
                if time_left != 0:
                    i += 1
        best_case_gap = 0 if i == len(best_case) - 1 else big - best_case[-1]


        worst_case = no_task_tpd
        worst_case_gap = worst_case[-1]
        if sum(worst_case[:-1]) < total_task_time:
            worst_case_gap = sum(worst_case) - total_task_time
        elif worst_case[0] > total_task_time:
            worst_case_gap = worst_case[-1] - worst_case[0] - total_task_time

        actual_gap = task_tpd[-1] - task_tpd[0]
        upper = worst_case_gap - best_case_gap
        real = actual_gap - best_case_gap
        return 1 - ((actual_gap - best_case_gap) / (worst_case_gap - best_case_gap))


    def calc_fitness(self, start_date):
        total_fitness = 0
        total_time = 0
        importance_list = []
        for task in self.tasks:
            # this needs to be adjusted to use end of last subtask
            total_time += task.total_time
            importance_list.append(task.importance)
            total_fitness += self.calc_task_fitness(task, start_date)

        importance_ordered = importance_list
        worst_case = sorted(importance_list)

        total_importance = 1 - (self.calc_ordered_value(importance_ordered) / self.calc_ordered_value(worst_case))
        res_fitness = total_fitness / len(self.tasks)
        res_fitness += self.importance_weight * total_importance

        res_work_distribution = self.calc_work_distribution()
        res_fitness += self.distribution_weight * res_work_distribution
        
        return res_fitness


    def move(self):
        tries = 0
        subtask = None
        task = None
        new_tasks = copy.deepcopy(self.tasks)
        while not subtask and tries < 5:
            tries += 1
            task_pick = random.randint(0, len(self.tasks) - 1)
            task = new_tasks[task_pick]
            if task.subtasks:
                subtask = task.subtasks[0]
                del task.subtasks[0]
        locked_time = [(subtask["start"], subtask["end"])]
        subtask_time = (subtask["end"] - subtask["start"]).total_seconds()
        task.time_remaining += subtask_time / 60

        self.tasks = self.cal.schedule_tasks(new_tasks, locked_time=locked_time)


    def mutate(self):
        pick = random.randint(0, 1)
        if pick == 0:
            self.move()



class GA():

    def __init__(self, calendar, tasks, cluster_count=20):
        self.cal = calendar
        self.tasks = tasks
        self.cluster_count = cluster_count


    def optimize(self, threshold=0.8, max_iteraions=50):
        clusters = []
        for _ in range(self.cluster_count):
            shuffled = random.sample(self.tasks, len(self.tasks))
            new_cluster = Cluster(self.cal.schedule_tasks(shuffled), self.cal)
            clusters.append(new_cluster)

        iterations = 0
        fitnesses = {}
        while iterations < max_iteraions:
            iterations += 1
            
            fitnesses = {}
            for i, cluster in enumerate(clusters):
                fitnesses[i] = cluster.calc_fitness(self.cal.startDate)

            fitnesses = {k: v for k, v in sorted(fitnesses.items(), key=lambda item: item[1], reverse=True)}
            top_fitness = list(fitnesses.values())[0]

            # Bit of a sketchy breakout. Should work though I hope?
            if top_fitness > threshold or max_iteraions == iterations:
                return (clusters[list(fitnesses.keys())[0]], top_fitness)

            top_clusters = list(fitnesses.keys())[0:max(int(self.cluster_count * 0.1), 2)]
            rem_clusters = self.cluster_count - len(top_clusters)
            distribution = [int(rem_clusters / len(top_clusters)) for i in range(len(top_clusters))]
            distribution[-1] = rem_clusters - (int(rem_clusters / len(top_clusters)) * (len(distribution) - 1))

            new_clusters = []
            for i, seed_cluster in enumerate(top_clusters):
                for _ in range(distribution[i]):
                    new_cluster = copy.deepcopy(clusters[seed_cluster])
                    new_cluster.mutate()
                    new_clusters.append(new_cluster)
            clusters = new_clusters
