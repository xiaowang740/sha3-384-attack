"""Incremental SAT solving for path enumeration."""

from __future__ import annotations


class IncrementalSatSolver:
    """Keep one CryptoMiniSat instance alive while enumerating models."""

    def __init__(
        self,
        solver_command: str,
        variable_count: int,
        clauses: list[str],
        threads: int | None = None,
        external_options: list[str] | None = None,
    ) -> None:
        self.variable_count = variable_count
        try:
            import pycryptosat
        except ImportError as exc:
            raise RuntimeError(
                "pycryptosat is required for incremental enumeration. "
                "Install it into the Python environment used to run this script."
            ) from exc

        self._solver = (
            pycryptosat.Solver(threads=threads)
            if threads is not None
            else pycryptosat.Solver()
        )
        for clause in clauses:
            self.add_clause(self._parse_clause(clause))

    @staticmethod
    def _parse_clause(clause: str) -> list[int]:
        values = [int(value) for value in clause.split()]
        if not values or values[-1] != 0:
            raise ValueError(f"invalid CNF clause: {clause!r}")
        return values[:-1]

    def add_clause(self, clause: list[int]) -> None:
        self._solver.add_clause(clause)

    def solve(self) -> tuple[bool, dict[int, bool], str]:
        result = self._solver.solve()
        if not result[0]:
            return False, {}, "s UNSATISFIABLE\n"
        values = result[1]
        model = {
            variable: bool(values[variable])
            for variable in range(1, self.variable_count + 1)
            if values[variable] is not None
        }
        output = "s SATISFIABLE\nv "
        output += " ".join(
            str(variable if model.get(variable, False) else -variable)
            for variable in range(1, self.variable_count + 1)
        )
        return True, model, output + " 0\n"

    def close(self) -> None:
        return
