from random import randrange

class Gene():

    def __init__(self, id, time_remaining, time_until_due, importance=1, difficulty=1, delay=0):
        self.fitness = 0
        self.id = id
        self.time_remaining = time_remaining
        self.time_until_due = time_until_due
        self.importance = importance
        self.difficulty = difficulty
        self.delay = delay


class Chromosome():

    def __init(self, genes):
        self.genes = genes
        fitness = 0
        for i, gene in enumerate(genes):
            pre_neighbor_id = genes[i - 1].id if i > 0 else None
            post_neighbor_id = genes[i + 1].id if i < len(genes) - 1 else None
            fitness += self.calc_fitness(gene, pre_neighbor_id, post_neighbor_id)
        self.fitness /= len(genes)
        
    
    def calc_fitness(self, gene, pre_neighbor_id, post_neighbor_id):
        same_neighbor = int(pre_neighbor_id == self.id) + int(post_neighbor_id == self.id)
        
        # TODO: this is the crux ... gotta make this work

    