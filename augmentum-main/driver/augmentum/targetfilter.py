# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Specifies classes to filter evaluation targets according to block and allow list"""

import csv
import re
from typing import Iterable


class FilterEntry:
    """Single filter entry used for matching against an evaluation target"""

    def __init__(
        self,
        module: str,
        function: str,
        path: str,
        description: str,
        use_regex: bool = False,
    ):
        self.use_regex = use_regex
        if self.use_regex:
            self.mod = re.compile(module) if len(module) != 0 else None
            self.fn = re.compile(function) if len(function) != 0 else None
            self.path = re.compile(path) if len(path) != 0 else None
        else:
            self.mod = module if len(module) != 0 else None
            self.fn = function if len(function) != 0 else None
            self.path = path if len(path) != 0 else None

        self.description = description

    def match(self, module: str, function: str, path: str) -> bool:
        """check if the given entry matches"""
        matches = []
        if self.mod is not None:
            if self.use_regex:
                matches.append(re.fullmatch(self.mod, module))
            else:
                matches.append(self.mod == module)

        if self.fn is not None:
            if self.use_regex:
                matches.append(re.fullmatch(self.fn, function))
            else:
                matches.append(self.fn == function)

        if self.path is not None:
            if self.use_regex:
                matches.append(re.fullmatch(self.path, path))
            else:
                matches.append(self.path == path)

        if len(matches) == 0:
            return False
        else:
            return all(matches)

    def __str__(self) -> str:
        return f"{self.description} -- module: {self.mod} -- funtion: {self.fn} -- path {self.path}"

    def __repr__(self) -> str:
        return self.__str__()


class TargetFilter:
    """Filter evaluation targets according to BLOCK and ALLOW specifications."""

    def __init__(self, filter_spec_file: Iterable[str]):
        reader = csv.reader(filter_spec_file, delimiter=";")
        next(reader, None)  # skip the headers

        self.block_list = list()
        self.allow_list = list()

        for row in reader:
            if row[0] == "BLOCK_REX":
                self.block_list.append(FilterEntry(*row[1:], use_regex=True))
            elif row[0] == "ALLOW_REX":
                self.allow_list.append(FilterEntry(*row[1:], use_regex=True))
            elif row[0] == "BLOCK":
                self.block_list.append(FilterEntry(*row[1:]))
            elif row[0] == "ALLOW":
                self.allow_list.append(FilterEntry(*row[1:]))
            else:
                raise ValueError(f"Unknown filter type {row[0]}")

    def should_evaluate(self, module: str, function: str, path: str) -> bool:
        """Determine if given evaluation target is to be blocked or allowed."""

        for b_entry in self.block_list:
            if b_entry.match(module, function, path):
                return False

        # if no ALLOW rules are specified, allow everything that is not blocked
        if len(self.allow_list) == 0:
            return True

        for a_entry in self.allow_list:
            if a_entry.match(module, function, path):
                return True

        # if ALLOW rules exist, block everything that is not explicitely allowed
        return False
