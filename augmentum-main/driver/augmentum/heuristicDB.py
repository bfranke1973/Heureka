# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import pathlib
from typing import Dict, Iterable, Optional, Set

import sqlalchemy as db
from augmentum.paths import Path
from augmentum.priors import Prior, PriorResult, ProbeResult
from sqlalchemy import (
    Boolean,
    Column,
    Enum,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
)
from sqlalchemy.sql.sqltypes import Float

from augmentum.benchmarks import ExecutionResult


class HeuristicDB:
    PATH_HEURISTIC_TBL = "path_heuristics"
    PROBE_TBL = "probe_log"
    PRIOR_TBL = "prior_results"

    def __init__(self, url: str):
        self.engine = db.create_engine(url, connect_args={"timeout": 60})
        self.connection = self.engine.connect()
        self.metadata = MetaData(self.engine)

        # path heuristic table
        self.pheu_tbl = Table(
            HeuristicDB.PATH_HEURISTIC_TBL,
            self.metadata,
            Column("module", String, primary_key=True, nullable=False),
            Column("function", String, primary_key=True, nullable=False),
            Column("path", String, primary_key=True, nullable=False),
            Column(
                "prior_success", String, nullable=False
            ),  # working prior found (other than NullPrior)
            Column("obj_improvement", Boolean, nullable=False),  # obj improvement found
            Column(
                "test_coverage", Integer, nullable=True
            ),  # number of tests covering this entry
        )

        # probe log table
        self.probe_tbl = Table(
            HeuristicDB.PROBE_TBL,
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True, nullable=False),
            Column(
                "module",
                String,
                ForeignKey(f"{HeuristicDB.PATH_HEURISTIC_TBL}.module"),
                nullable=False,
            ),
            Column(
                "function",
                String,
                ForeignKey(f"{HeuristicDB.PATH_HEURISTIC_TBL}.function"),
                nullable=False,
            ),
            Column(
                "path",
                String,
                ForeignKey(f"{HeuristicDB.PATH_HEURISTIC_TBL}.path"),
                nullable=False,
            ),
            Column("case", String, nullable=False),
            Column("prior", String, nullable=False),
            Column("value", String, nullable=True),
            Column("compile", Enum(ExecutionResult), nullable=False),
            Column("run", Enum(ExecutionResult), nullable=False),
            Column("verify", Enum(ExecutionResult), nullable=False),
            Column("compile_t", Float, nullable=True),
            Column("run_t", Float, nullable=True),
            Column("objective", String, nullable=True),
            Column("rel_objective", String, nullable=True),
            Column("objective_supp", String, nullable=True),
            Column("ext_path", String, nullable=True),
            Column("exec_log", String, nullable=False),
        )

        # prior result table
        self.prior_tbl = Table(
            HeuristicDB.PRIOR_TBL,
            self.metadata,
            Column(
                "module",
                String,
                ForeignKey(f"{HeuristicDB.PATH_HEURISTIC_TBL}.module"),
                primary_key=True,
                nullable=False,
            ),
            Column(
                "function",
                String,
                ForeignKey(f"{HeuristicDB.PATH_HEURISTIC_TBL}.function"),
                primary_key=True,
                nullable=False,
            ),
            Column(
                "path",
                String,
                ForeignKey(f"{HeuristicDB.PATH_HEURISTIC_TBL}.path"),
                primary_key=True,
                nullable=False,
            ),
            Column("prior", String, primary_key=True, nullable=False),
            Column("success", Boolean, nullable=False),
            Column("data", String, nullable=False),
        )

        self.metadata.create_all(self.engine, checkfirst=True)

    def get_all_tables(self) -> Dict[str, Table]:
        return {
            HeuristicDB.PATH_HEURISTIC_TBL: self.pheu_tbl,
            HeuristicDB.PROBE_TBL: self.probe_tbl,
            HeuristicDB.PRIOR_TBL: self.prior_tbl,
        }

    def add_path_heuristic(
        self,
        m_name: str,
        fn_name: str,
        path: Path,
        presult: Optional[PriorResult],
        obj_improvement: bool,
        test_coverage: int,
    ):
        """Add function path entry or update if already exists"""
        prior_success = None
        if presult is not None:
            prior_success = presult.success
        self.add_path_heuristic_entry(
            m_name, fn_name, str(path), prior_success, obj_improvement, test_coverage
        )

    def add_path_heuristic_entry(
        self,
        m_name: str,
        fn_name: str,
        path: str,
        prior_success: Optional[bool],
        obj_improvement: bool,
        test_coverage: int,
    ) -> bool:
        """Add function path entry.
        Function parameters correspond with table columns.
        Return True if entry already exists and was updated.
        """

        query = db.select([self.pheu_tbl]).where(
            (self.pheu_tbl.c["module"] == m_name)
            & (self.pheu_tbl.c["function"] == fn_name)
            & (self.pheu_tbl.c["path"] == f"{path}")
        )
        resultProxy = self.connection.execute(query)
        resultSet = resultProxy.fetchall()

        if len(resultSet) == 0:
            # nothing found, insert new entry
            query = db.insert(self.pheu_tbl).values(
                module=m_name,
                function=fn_name,
                path=path,
                prior_success=prior_success if prior_success is not None else "NA",
                obj_improvement=obj_improvement,
                test_coverage=test_coverage,
            )
            _ = self.connection.execute(query)
            return False
        else:
            # found existing entry, update with new values
            query = db.update(self.pheu_tbl).values(
                prior_success=prior_success if prior_success is not None else "NA",
                obj_improvement=obj_improvement,
                test_coverage=test_coverage,
            )
            query = query.where(
                (self.pheu_tbl.c["module"] == m_name)
                & (self.pheu_tbl.c["function"] == fn_name)
                & (self.pheu_tbl.c["path"] == path)
            )
            _ = self.connection.execute(query)
            return True

    def add_probelog(
        self,
        module: str,
        function: str,
        path: Path,
        probe_log: Iterable[ProbeResult],
        record_exec_log: bool = False,
    ):
        """Add probe results from given prior to database."""
        for probe_result in probe_log:
            probe_log = (
                "#".join([",".join(log) for log in probe_result.exec_log])
                if record_exec_log
                else None
            )

            obj_supp = None
            if probe_result.objective is not None:
                obj_supp = "#".join(
                    "=".join((k, str(v)))
                    for (k, v) in probe_result.objective.supplementary.items()
                )

            self.add_probelog_entry(
                module,
                function,
                f"{path}",
                str(probe_result.test_case),
                str(probe_result.probe.priorId),
                str(probe_result.probe.get_probe_value())
                if probe_result.probe.get_probe_value() is not None
                else None,
                probe_result.compile_ok,
                probe_result.run_ok,
                probe_result.verify_ok,
                probe_result.compile_time,
                probe_result.run_time,
                str(probe_result.objective.score)
                if probe_result.objective is not None
                else None,
                str(probe_result.rel_objective)
                if probe_result.rel_objective is not None
                else None,
                obj_supp,
                probe_result.ext_path,
                probe_log,
            )

    def add_probelog_entry(
        self,
        module: str,
        function: str,
        path: str,
        case: str,
        prior: str,
        value: Optional[str],
        compile_ok: ExecutionResult,
        run_ok: ExecutionResult,
        verify_ok: ExecutionResult,
        compile_t: Optional[float],
        run_t: Optional[float],
        objective: Optional[str],
        rel_objective: Optional[str],
        objective_supp: Optional[str],
        ext_path: Optional[pathlib.Path],
        exec_log: Optional[str],
    ) -> bool:
        """Add probe results to database.
        Function parameter order corresponds with table columns.
        Always returns False because entries are unique.
        """
        query = db.insert(self.probe_tbl).values(
            # id auto update
            module=module,
            function=function,
            path=path,
            case=case,
            prior=prior,
            value=value if value is not None else "NA",
            compile=compile_ok,
            run=run_ok,
            verify=verify_ok,
            compile_t=compile_t,
            run_t=run_t,
            objective=objective if objective is not None else "NA",
            rel_objective=rel_objective if rel_objective is not None else "NA",
            objective_supp=objective_supp if objective_supp is not None else "NA",
            ext_path=str(ext_path) if ext_path is not None else "NA",
            exec_log=exec_log if exec_log is not None else "NA",
        )
        _ = self.connection.execute(query)
        return False

    def add_prior_results(
        self, m_name: str, fn_name: str, path: Path, priors: Iterable[Prior]
    ):
        """Add prior results from given sequence of priors to database."""
        for p in priors:
            presult = p.prior_result()
            if presult is not None:
                self.add_prior_results_entry(
                    m_name,
                    fn_name,
                    str(path),
                    str(p),
                    presult.success,
                    str(presult.result_data),
                )

    def add_prior_results_entry(
        self,
        m_name: str,
        fn_name: str,
        path: str,
        prior: str,
        prior_success: bool,
        prior_data: str,
    ):
        """Add prior result to database.
        Function parameter order corresponds with table columns.
        Return True if entry already exists and was updated.
        """

        query = db.select([self.prior_tbl]).where(
            (self.prior_tbl.c["module"] == m_name)
            & (self.prior_tbl.c["function"] == fn_name)
            & (self.prior_tbl.c["path"] == path)
            & (self.prior_tbl.c["prior"] == prior)
        )
        resultProxy = self.connection.execute(query)
        resultSet = resultProxy.fetchall()

        if len(resultSet) == 0:
            # nothing found, insert new entry
            query = db.insert(self.prior_tbl).values(
                module=m_name,
                function=fn_name,
                path=path,
                prior=prior,
                success=prior_success,
                data=prior_data,
            )
            _ = self.connection.execute(query)
            return False
        else:
            # found existing entry, update with new values
            query = db.update(self.prior_tbl).values(
                success=prior_success, data=prior_data
            )
            query = query.where(
                (self.prior_tbl.c["module"] == m_name)
                & (self.prior_tbl.c["function"] == fn_name)
                & (self.prior_tbl.c["path"] == path)
                & (self.prior_tbl.c["prior"] == prior)
            )
            _ = self.connection.execute(query)
            return True

    def path_is_evaluated(self, m_name: str, fn_name: str, path: Path) -> bool:
        """Check if this path has been evaluated already."""
        # find entries with module, function and given path
        # where result is not NOT_EVALUATED
        query = (
            db.select([self.pheu_tbl])
            .where(
                (self.pheu_tbl.c["module"] == m_name)
                & (self.pheu_tbl.c["function"] == fn_name)
                & (self.pheu_tbl.c["path"] == f"{path}")
            )
            .where(self.pheu_tbl.c["prior_success"] != "NA")
        )
        resultProxy = self.connection.execute(query)
        resultSet = resultProxy.fetchall()
        return len(resultSet) == 1

    def get_lookup_string(self, m_name: str, fn_name: str, path: Path) -> str:
        """Return a lookup string for a function path target."""
        return f"{m_name}_{fn_name}_{path}"

    def get_evaluated_paths(self) -> Set[str]:
        """Return a lookup table for all evaluated paths in the database."""

        # find entries with processed functions
        query = db.select([self.pheu_tbl]).where(
            self.pheu_tbl.c["prior_success"] != "NA"
        )
        resultProxy = self.connection.execute(query)
        resultSet = resultProxy.fetchall()

        # map result set to lookup set
        return {self.get_lookup_string(e[0], e[1], e[2]) for e in resultSet}
