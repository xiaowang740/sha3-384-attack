"""Enumerate a3 weighted paths using two solver threads by default."""
from enumerate_keccak_paths_a3_weighted import main as enumerate_paths


def main():
    enumerate_paths(default_threads=2)


if __name__ == '__main__':
    main()
