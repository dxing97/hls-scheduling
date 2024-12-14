import argparse
from pathlib import Path
import main

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('benchmark_dir', type=Path, help='Directory containing .edgelist benchmark files')
    args = parser.parse_args()
    return args


def get_benchmarks(benchmark_dir: Path) -> list:
    return list(benchmark_dir.glob('*.edgelist'))


if __name__ == '__main__':
    args = parse_args()
    benchmarks = get_benchmarks(args.benchmark_dir)
    for benchmark in benchmarks:
        for memtype in ('optimistic',):
            for pareto_type in ('sweep',):
                main.main(main.parse_args([str(benchmark), '-p', '-mm', memtype, '-pt', pareto_type]))
