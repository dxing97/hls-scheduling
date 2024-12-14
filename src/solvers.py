import pulp as plp
import networkx as nx
from typing import Optional
import itertools
from pathlib import Path

def solver(dfg: nx.digraph, opcount: int, Lmax: Optional[int], Mmax: Optional[int],
           alpha: Optional[float],
           objfun: str, memory_model: str, lp_file_path: Path):
    # assert not (Lmax is None and Mmax is None and alpha is None)
    if Lmax is None:
        L = plp.LpVariable('L', lowBound=0, cat=plp.LpInteger)
        Lmax = opcount  # worst case latency: every operation is scheduled into its own clock cycle
    else:
        L = Lmax
    if Mmax is None:
        M = plp.LpVariable('M', lowBound=0, cat=plp.LpInteger)
    else:
        M = Mmax

    problem = plp.LpProblem(name='scheduling')
    if objfun == 'memory':
        problem += M
    elif objfun == 'latency':
        problem += L
    elif objfun == 'linearization':
        problem += alpha * L + ((1-alpha))*M
    else:
        pass

    # variable: operation schedules
    t = plp.LpVariable.dict('t', range(opcount), lowBound=0, upBound=Lmax, cat=plp.LpInteger, )

    # contraint 1: enforce data dependencies
    # assume dfg nodes are labeled using integers starting from 0
    for (o,p) in nx.edges(dfg):
        problem += t[o] - t[p] <= -1

    # constraint 2: schedule latency
    for o in range(opcount):
        problem += t[o] <= L

    ol = list(itertools.product(range(opcount), range(Lmax)))
    # ol = tuple(f'{o},{t}' for o, t in ol)

    x = plp.LpVariable.dicts('x', ol, lowBound=0, upBound=1, cat=plp.LpInteger)
    y = plp.LpVariable.dicts('y', ol, lowBound=0, upBound=1, cat=plp.LpInteger)
    for o, _t in itertools.product(range(opcount), range(Lmax)):
        problem += _t - t[o] + 1 <= Lmax * x[o, _t]
        problem += t[o] - _t <= Lmax * y[o, _t]

    z_indices = list((o,p,_t) for (o,p) in nx.edges(dfg) for _t in range(Lmax))
    z = plp.LpVariable.dicts('z', z_indices, lowBound=0, upBound=1, cat=plp.LpInteger)

    for o, p, _t in z_indices:
        problem += x[o,_t] + y[p, _t] - 1 <= z[o,p,_t]
        problem += z[o,p,_t] <= x[o,_t]
        problem += z[o,p,_t] <= y[p, _t]

    if memory_model == 'pessimistic':
        for _t in range(Lmax):
            problem += plp.lpSum(dfg.edges[o, p]['weight'] * z[o, p, _t] for (o, p) in nx.edges(dfg)) <= M
    elif memory_model == 'optimistic':
        # may need to constrain to only include ops with descendants
        m = plp.LpVariable.dicts('m', itertools.product(range(opcount), range(Lmax)), lowBound=0, upBound=None, cat=plp.LpInteger)
        for o,p,_t in z_indices:
            problem += dfg.edges[o, p]['weight'] * z[o,p,_t] <= m[o, _t]
        for _t in range(Lmax):
            problem += plp.lpSum(m[o, _t] for o in range(opcount)) <= M

    print(f"Writing LP file to {lp_file_path}")
    problem.writeLP(lp_file_path)
    print(f"Solving ILP...")
    problem.solve(solver=plp.GUROBI(timeLimit=60))
    # problem.solve(solver=plp.PULP_CBC_CMD(timeLimit=60))
    print(f"Status: {plp.LpStatus[problem.status]}")

    return plp.LpStatus[problem.status], plp.value(M), plp.value(L), lp_file_path

