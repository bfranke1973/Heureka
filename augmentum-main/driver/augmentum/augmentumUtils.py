# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Utility functions for the augmentum library.
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple
from zipfile import ZipFile

from augmentum.sysUtils import build_path_or_fail
from augmentum.timer import Timer

logger = logging.getLogger(__name__)


def load_evaluation_config(
    raw_config: Iterable[str],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Iterable[Dict[str, Any]]]:
    """Read configuration data from specified configuration file."""
    config = json.load(raw_config)

    g_cfg = config["general"]
    t_cfg = config["tools"]
    s_cfg = config["sys_prog"]["available"][config["sys_prog"]["active"]]
    b_cfgs = [
        config["benchmark"]["available"][b] for b in config["benchmark"]["active"]
    ]

    return g_cfg, t_cfg, s_cfg, b_cfgs


def setup_root_directory(run_id: str, working_dir: Path) -> Path:
    """Setup root working directory"""
    if not working_dir.exists():
        raise RuntimeError("Given working directory path invalid: " + str(working_dir))

    wd_run = working_dir / run_id
    wd_run.mkdir(exist_ok=False)
    return wd_run


def setup_working_directories(
    wd_run: Path, general_cfg: Dict[str, Any], sysprog_cfg: Dict[str, Any]
) -> Tuple[Path, Path, Path]:
    """
    Create the following directory tree
    working_dir
      - run_id
         - wd_workers
         - sys_prog_src
         - sys_prog_bld

    sys_prog and benchmark folders are only created if the copy_sources flag is set
    in config.
    """
    wd_workers = wd_run / "worker_output"
    wd_workers.mkdir()

    sys_prog_src_dir = build_path_or_fail(sysprog_cfg["src_dir"])
    sys_prog_bld_dir = build_path_or_fail(sysprog_cfg["build_dir"])

    if general_cfg["copy_sysprog"]:
        with Timer():
            logger.info("Copying system program sources ...")
            sys_prog_src_dir = wd_run / "sys_prog_src"
            sys_prog_origial = Path(sysprog_cfg["src_dir"])
            if sys_prog_origial.is_dir():
                logger.info(f"Copying directory tree {sys_prog_origial}...")
                shutil.copytree(sys_prog_origial, sys_prog_src_dir, symlinks=True)
            elif sys_prog_origial.is_file() and sys_prog_origial.suffix == ".zip":
                logger.info(f"Copy and unpack {sys_prog_origial}...")
                sys_prog_src_dir.mkdir()
                sys_prog_target_zip = sys_prog_src_dir / sys_prog_origial.name
                shutil.copy2(sys_prog_origial, sys_prog_target_zip)
                with ZipFile(sys_prog_target_zip, "r") as zip_obj:
                    zip_obj.extractall(sys_prog_src_dir)
            else:
                raise ValueError(f"Unknown system program source {sys_prog_origial}")

            sys_prog_bld_dir = wd_run / "sys_prog_bld"
            sys_prog_bld_dir.mkdir()

    return wd_workers, sys_prog_src_dir, sys_prog_bld_dir
