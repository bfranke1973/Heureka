# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from enum import Enum

from augmentum.type_descs import TypeDesc


class Path:
    @property
    def type(self) -> TypeDesc:
        raise NotImplementedError

    def __repr__(self) -> str:
        return self.__str__()


class LeafPath(Path):
    def __init__(self, type: TypeDesc):
        self._type = type

    @property
    def type(self) -> TypeDesc:
        return self._type

    def __str__(self) -> str:
        return f"T-{self.type}"


class InternalPath(Path):
    def __init__(self, path: Path):
        self.path = path

    @property
    def type(self) -> TypeDesc:
        return self.path.type


class ResultPath(InternalPath):
    def __init__(self, path: Path):
        super().__init__(path)

    def __str__(self) -> str:
        return "Z." + str(self.path)


class ArgumentPath(InternalPath):
    def __init__(self, i: int, path: Path):
        super().__init__(path)
        self.i = i

    def __str__(self) -> str:
        return "A" + str(self.i) + "." + str(self.path)


class StructElementPath(InternalPath):
    def __init__(self, i: int, path: Path):
        super().__init__(path)
        self.i = i

    def __str__(self) -> str:
        return "S" + str(self.i) + "." + str(self.path)


class SplitIntLeftPath(InternalPath):
    def __init__(self, path: Path):
        super().__init__(path)

    def __str__(self) -> str:
        return "L." + str(self.path)


class SplitIntRightPath(InternalPath):
    def __init__(self, path: Path):
        super().__init__(path)

    def __str__(self) -> str:
        return "R." + str(self.path)


class DerefPath(InternalPath):
    def __init__(self, path: Path):
        super().__init__(path)

    def __str__(self) -> str:
        return "D." + str(self.path)


class PathContext(Enum):
    FUNCTION = (0,)
    RESULT = (1,)
    ARG = (2,)
    DEREFFED = 3
