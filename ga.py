from random import randrange
import random
from schedule import schedule, datetime_from_utc_to_local
import math

class Cluster():

    def __init__(self, tasks):
        self.tasks = tasks

        #positives
        self.proximity_weight = 1
        self.importance_weight = 0.4
        self.difficulty_weight = 0.2

        #negatives
        self.due_weight = 0.4


    def calc_task_fitness(self, task, start_date):
        # degrade value if the item is due in 2 days
        time_left = (task.due_date - start_date).total_seconds()
        time_lost = time_left
        if task.subtasks:
            time_lost = (task.subtasks[-1]["end"] - start_date).total_seconds()
        time_diff = math.tanh((time_left - time_lost) / 172800)

        return self.proximity_weight * task.proximity - \
               self.due_weight * time_diff   


    def calc_fitness(self, start_date):
        total_fitness = 0
        for task in self.tasks:
            total_fitness += self.calc_task_fitness(task, start_date)
        return total_fitness / len(self.tasks)

    
    def swap(self):
        pass


    def move(self):
        pass


    def mutate(self):
        pick = random.randint(0, 2)
        if pick == 0:
            return self.swap()
        return self.move()



class GA():

    def __init__(self, calendar, tasks, cluster_count=20):
        self.cal = calendar
        self.tasks = tasks
        self.cluster_count = cluster_count


    def optimize(self, threshold=0.8, max_iteraions=1):
        clusters = []
        for _ in range(self.cluster_count):
            shuffled = random.sample(self.tasks, len(self.tasks))
            new_cluster = Cluster(self.cal.schedule_tasks(shuffled))
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
                    new_clusters.append(self.make_cluster(seed_cluster))
            clusters = new_clusters
