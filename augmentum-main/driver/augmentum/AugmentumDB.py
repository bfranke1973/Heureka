# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from sqlite3 import Connection
from typing import Dict, Protocol

from sqlalchemy import Table


class AugmentumDataBase(Protocol):
    connection: Connection

    def get_all_tables(self) -> Dict[str, Table]:
        ...
