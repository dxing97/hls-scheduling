import argparse
from pathlib import Path
import solvers
import networkx as nx
import matplotlib.pyplot as plt
from typing import *


def parse_args(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(usage='%(prog)s [options]')
    parser.add_argument('-l', '--latency', metavar='<integer>', dest='L', default=None, required=False, type=int,
                        help='Latency contraint, enables latency constrained memory minimization optimization.')
    parser.add_argument('-m', '--memory', metavar='<integer>', dest='M', default=None, required=False, type=int,
                        help='Memory contraint, enables memory constrained latency minimization.')
    parser.add_argument('-mm', '--memory-model', metavar='<pessimistic|optimistic>', dest='memory_model', default='pessimistic', required=False, type=str,
                        help='Memory model (pessimistic or optimistic), see README.md for more information.')
    parser.add_argument('-p', '--pareto-analysis', default=False, action='store_true', dest='do_pareto',
                        help='Do pareto curve analysis. Default is to sweep over feasible space.')
    parser.add_argument('-pt', '--pareto-type', metavar='<linearization|sweep>',default='sweep', dest='pareto_type', required=False, type=str,
                        help='Pareto front characterization method type: exhausitve sweep or linearization.')

    parser.add_argument(dest='edgelist_path', type=Path,
                        help='Path to .edgelist file.')
    parser.add_argument('-fp', '--figures-path', dest='figure_directory', type=Path, default=Path('../figures'),
                        help='Path to directory to save pareto curve figures to.')
    args = parser.parse_args(args)
    return args


def main(args):

    if args.M is None and args.L is None and args.do_pareto == False:
        raise ValueError('Require at least one argument')

    dfg = nx.read_weighted_edgelist(args.edgelist_path, create_using=nx.DiGraph(), nodetype=int)
    opcount = len(dfg.nodes())
    results = []
    design_points = []
    if args.M is not None:
        status, M, L, lp_path = result = solvers.solver(dfg, opcount, None, args.M, None, 'latency', args.memory_model, Path(f'{args.memory_model}_mclm.lp'))
        results.append(result)
        print(f"Latency optimization final status: {status}\n\tMemory: {M} Latency:{L}")
        if status == 'Optimal':
            design_points.append((M, L))
    if args.L is not None:
        status, M, L, lp_path = result = solvers.solver(dfg, opcount, args.L, None, None, 'memory', args.memory_model, Path(f'{args.memory_model}_lcmm.lp'))
        results.append(result)
        print(f"Memory optimization final status: {status}\n\tMemory: {M} Latency:{L}")
        if status == 'Optimal':
            design_points.append((M, L))
    if args.do_pareto:
        print(f"Performing pareto front analysis")
        # if args.pareto_type == 'sweep':
        # establish lower bounds on memory usage (unobunded memory minimization)
        print(f"Finding lower bound on memory usage")
        Lmax = opcount
        kwargs = {'dfg': dfg,
                  'opcount': opcount,
                  'alpha': None,
                  'memory_model': args.memory_model,
                  'lp_file_path': Path(f'pareto_problem.lp')}
        status, M, L, lp_path = result = solvers.solver(Lmax=opcount, Mmax=None, objfun='memory', **kwargs)
        assert status != 'Infeasible'
        design_points.append((M, L))
        Mmin = int(M)

        # establish lower bounds on latency (unbounded latency minimzation, i.e. ASAP scheduling)
        print(f"Finding lower bound on latency")
        status, M, L, lp_path = result = solvers.solver(Lmax=None, Mmax=None, objfun='latency', **kwargs)
        assert status != 'Infeasible'
        design_points.append((M, L))
        print(design_points)
        Lmin = int(L)

        # find extrema points: lowest memory usage possible at minimal latency
        print(f"Finding extrema on latency")
        status, M, L, lp_path = result = solvers.solver(Lmax=Lmin, Mmax=None, objfun='memory', **kwargs)
        assert status != 'Infeasible'
        design_points.append((int(M), int(L)))
        print(design_points)

        # find extrema points: lowest latency possible at minimal memory usage
        print(f"Finding extrema on memory")
        status, M, L, lp_path = result = solvers.solver(Lmax=None, Mmax=Mmin, objfun='latency', **kwargs)
        assert status != 'Infeasible'
        design_points.append((int(M), int(L)))
        print(design_points)

        # define search space: range of last two design points
        memory_search_range = (Mmin, int(design_points[-2][0]))
        latency_search_range = (Lmin, int(design_points[-1][1]))
        if memory_search_range[0] - memory_search_range[1] == 0 or latency_search_range[0] - latency_search_range[1] == 0:
            # search space is empty, one solution pareto-dominates entire search space!
            print(f"Search space is convex, found best possible solution of M={Mmin}, L={Lmin}")
        else:
            if args.pareto_type == 'sweep':
                print(f"Latency search space: {latency_search_range}")
                for lmax in range(*latency_search_range):
                    status, M, L, lp_path = result = solvers.solver(Lmax=lmax, Mmax=None, objfun='memory', **kwargs)
                    assert status != 'Infeasible'
                    design_points.append((int(M), int(L)))
                    print(design_points)
            elif args.pareto_type == 'linearization':
                arange = 10
                print(f"Alpha search range: {arange}")
                for aratio in range(arange):
                    kwargs['alpha'] = aratio/arange
                    status, M, L, lp_path = result = solvers.solver(Lmax=None, Mmax=None, objfun='linearization', **kwargs)
                    assert status != 'Infeasible'
                    design_points.append((int(M), int(L)))
                    print(design_points)
            else:
                raise ValueError(f'Unknown pareto analysis type {args.pareto_type}')
        print(f"Outputting pareto curve:")
        plt.scatter(list(x[1] for x in design_points), list(x[0] for x in design_points))
        plt.title(f"Pareto Curve for Benchmark {args.edgelist_path.name}")
        plt.xlabel("Latency (clock cycles)")
        plt.ylabel("Memory allocation (arbitrary units)")
        plt.savefig(args.figure_directory/f"{args.edgelist_path.name}_{args.memory_model}_pareto_{args.pareto_type}.jpeg")
        plt.show()


if __name__ == '__main__':
    _args = parse_args()
    main(_args)
