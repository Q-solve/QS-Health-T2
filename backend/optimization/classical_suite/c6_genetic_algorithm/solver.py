"""
C6 Genetic Algorithm — local CPU.

Chromosome = facility index per community. Uses DEAP when available.
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Tuple

import numpy as np

from backend.optimization.classical_suite.base import ClassicalSolverBase
from backend.optimization.classical_suite.c3_greedy.solver import GreedyNearestNeighborSolver
from backend.optimization.objective import evaluate_H, scenario_distance_matrix
from backend.scenario.models import CHWDeploymentScenario

try:
    from deap import base, creator, tools

    DEAP_AVAILABLE = True
except ImportError:
    base = creator = tools = None
    DEAP_AVAILABLE = False


def _chrom_to_matrix(chrom: List[int], num_f: int, num_c: int) -> np.ndarray:
    x = np.zeros((num_f, num_c), dtype=float)
    for j, i in enumerate(chrom):
        x[int(i) % num_f, j] = 1.0
    return x


class GeneticAlgorithmSolver(ClassicalSolverBase):
    solver_id = "c6_genetic_algorithm"

    def _optimize(
        self,
        scenario: CHWDeploymentScenario,
        time_budget_sec: float,
        seed: int,
    ) -> Tuple[np.ndarray, str, Dict[str, Any]]:
        rng = random.Random(seed)
        dist = scenario_distance_matrix(scenario)
        num_f = len(scenario.facilities)
        num_c = len(scenario.communities)

        greedy_x, _, _ = GreedyNearestNeighborSolver()._optimize(scenario, time_budget_sec, seed)
        greedy_chrom = [int(np.argmax(greedy_x[:, j])) for j in range(num_c)]

        def fitness(chrom: List[int]) -> float:
            return evaluate_H(_chrom_to_matrix(chrom, num_f, num_c), dist, scenario)

        pop_size = 30
        population = [greedy_chrom[:]]
        while len(population) < pop_size:
            population.append([rng.randrange(num_f) for _ in range(num_c)])

        best = min(population, key=fitness)
        best_h = fitness(best)
        generations = 0
        t0 = time.perf_counter()

        if DEAP_AVAILABLE:
            if not hasattr(creator, "FitnessMin"):
                creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
            if not hasattr(creator, "Individual"):
                creator.create("Individual", list, fitness=creator.FitnessMin)
            toolbox = base.Toolbox()
            toolbox.register("attr_fac", rng.randrange, num_f)
            toolbox.register(
                "individual",
                tools.initRepeat,
                creator.Individual,
                toolbox.attr_fac,
                n=num_c,
            )
            toolbox.register("population", tools.initRepeat, list, toolbox.individual)
            toolbox.register("evaluate", lambda ind: (fitness(list(ind)),))
            toolbox.register("mate", tools.cxTwoPoint)
            toolbox.register("mutate", tools.mutUniformInt, low=0, up=num_f - 1, indpb=0.2)
            toolbox.register("select", tools.selTournament, tournsize=3)

            pop = toolbox.population(n=pop_size)
            pop[0] = creator.Individual(greedy_chrom)
            for ind in pop:
                ind.fitness.values = toolbox.evaluate(ind)

            while time.perf_counter() - t0 < time_budget_sec:
                offspring = toolbox.select(pop, len(pop))
                offspring = list(map(toolbox.clone, offspring))
                for c1, c2 in zip(offspring[::2], offspring[1::2]):
                    if rng.random() < 0.6:
                        toolbox.mate(c1, c2)
                        del c1.fitness.values
                        del c2.fitness.values
                for mut in offspring:
                    if rng.random() < 0.3:
                        toolbox.mutate(mut)
                        del mut.fitness.values
                invalid = [ind for ind in offspring if not ind.fitness.valid]
                for ind in invalid:
                    ind.fitness.values = toolbox.evaluate(ind)
                pop[:] = offspring
                generations += 1
                cur_best = tools.selBest(pop, 1)[0]
                if cur_best.fitness.values[0] < best_h:
                    best = list(cur_best)
                    best_h = cur_best.fitness.values[0]
            backend = "deap"
        else:
            while time.perf_counter() - t0 < time_budget_sec:
                scored = sorted([(fitness(ch), ch) for ch in population], key=lambda t: t[0])
                if scored[0][0] < best_h:
                    best_h, best = scored[0][0], scored[0][1][:]
                survivors = [ch for _, ch in scored[: pop_size // 2]]
                children = []
                while len(survivors) + len(children) < pop_size:
                    p1, p2 = rng.choice(survivors), rng.choice(survivors)
                    cut = rng.randrange(1, max(2, num_c))
                    child = p1[:cut] + p2[cut:]
                    if rng.random() < 0.3:
                        child[rng.randrange(num_c)] = rng.randrange(num_f)
                    children.append(child)
                population = survivors + children
                generations += 1
            backend = "custom_ga"

        return _chrom_to_matrix(best, num_f, num_c), "feasible", {
            "backend": backend,
            "generations": generations,
            "best_objective": best_h,
        }
