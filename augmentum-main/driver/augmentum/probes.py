# Copyright (c) 2021, Björn Franke
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
from abc import ABC, abstractmethod
from collections import deque
from numbers import Number
from pathlib import Path
from typing import Dict, Generic, Iterable, Optional, Protocol, Set, Tuple, TypeVar

import augmentum.paths
from augmentum.function import Function
from augmentum.paths import ResultPath
from augmentum.type_descs import (
    ArrayTypeDesc,
    FunctionTypeDesc,
    IntTypeDesc,
    PointerTypeDesc,
    PrimitiveTypeDesc,
    RealTypeDesc,
    StructTypeDesc,
    TypeDesc,
    UnknownTypeDesc,
)

logger = logging.getLogger(__name__)


STRUCT_NAME_REX = r"^(?P<kind>class|struct|union)\.(?P<type>.+)"

PROBE_LOG_DELIMITER = ";"

T = TypeVar("T")


class GenerateBodyCall(Protocol):
    """Callable type definition for a call generating a function body"""

    def __call__(
        self,
        return_type: str,
        arg_vals: str,
        path_code: str,
        probed_type: str,
        null_check_id: Optional[str],
        value_op: Optional[str],
    ) -> str:
        ...


def generate_register_extension_point(
    sys_prog_src: str,
    mod_name: str,
    fn_name: str,
    orig_type: str,
    orig_identifier: str,
    mod_identifier: str,
) -> str:
    return f"""
        if (pt.get_module_name() == "{sys_prog_src}/{mod_name}" &&
            pt.get_name() == "{fn_name}") {{
            if (pt.is_replaced()) {{
                throw std::runtime_error("Attempt to register more than one extension point.");
            }}

            pt.replace((Fn) &{mod_identifier});
            {orig_identifier} = ({orig_type}) pt.original_direct();
        }}
    """


def generate_modified_function(
    function: Function,
    orig_type: str,
    orig_id: str,
    mod_id: str,
    path_code: str,
    probed_type: str,
    null_check_id: Optional[str],
    generate_body: GenerateBodyCall,
    value_op: Optional[str],
) -> str:
    return_type = function.type.return_type.get_cpp_type().get_type_string()

    arg_vals = type_descs_to_cpp_arg_vals(function.type.arg_types)
    arg_types = type_descs_to_cpp_arg_types(function.type.arg_types)
    args = type_descs_to_cpp_args(function.type.arg_types)

    function_body = generate_body(
        return_type,
        arg_vals,
        path_code,
        probed_type.get_cpp_type().get_type_string(),
        null_check_id,
        value_op,
    )

    return f"""
// {function.module} {function}
typedef {return_type} (*{orig_type})({arg_types});
{orig_type} {orig_id};

{return_type} {mod_id}({args}) {{
    {function_body}
}}
"""


def fill_extension_template(
    mname: str,
    fname: str,
    log_file: str,
    sys_prog_src: str,
    probe_type: str,
    forward_decl: str,
    modified_fn: str,
) -> str:
    return f"""
#include <cstdint>
#include <stdexcept>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <unordered_map>
#include "augmentum.h"

using namespace augmentum;

{forward_decl}

template <typename A, typename B>
struct std::hash<std::pair<A,B>> {{
    size_t operator()(const std::pair<A,B>& p) const {{
        size_t h1 = std::hash<A>()(p.first);
        size_t h2 = std::hash<B>()(p.second);
        return h1 ^ (h2 << 1);
    }}
}};

// remember which functions you have seen already
std::unordered_map<std::pair<{probe_type},{probe_type}>,size_t> cache;
std::mutex log_mutex;  // protects cache and disc write

void write_probe_log({probe_type} original_value, {probe_type} probed, size_t freq) {{
    std::filesystem::path outputFile = "{log_file}";
    std::ofstream out(outputFile.c_str(), std::ios::out | std::ios::app);
    if (out.good()) {{
        out << original_value << "{PROBE_LOG_DELIMITER}" << probed << "{PROBE_LOG_DELIMITER}" << freq << std::endl;
    }} else {{
        throw std::runtime_error("Writing probe log to file failed: " + outputFile.string());
    }}
    out.close();
}}

void log_entry({probe_type} original_value, {probe_type} probed) {{
    const std::lock_guard<std::mutex> lock(log_mutex);
    auto p = std::make_pair(original_value, probed);
    if (cache.find(p) == cache.end()) {{
        cache[p] = 0;
    }}
    cache[p] += 1;
}}

{modified_fn}

struct ProbeListener: Listener {{
    void on_extension_point_register(FnExtensionPoint& pt) {{
{generate_register_extension_point(sys_prog_src, mname, fname, 'original_t', 'original_function', 'modified_function')}
    }}

    void on_extension_point_unregister(FnExtensionPoint& pt) {{
        if (pt.is_replaced()) {{
            pt.reset();

            // whenever an extension point is unregistered, empty cache to file
            const std::lock_guard<std::mutex> lock(log_mutex);
            if (cache.size() > 0) {{
                for (auto&[k,v] : cache) {{
                    write_probe_log(k.first, k.second, v);
                }}
                cache.clear();
            }}

        }}
    }}
}};
ListenerLifeCycle<ProbeListener> probeListener;
"""


def add_null_check(null_check_id: Optional[str], code: str) -> str:
    """Add null check if clause around given code if id is set"""
    if null_check_id is not None:
        return f"""
    if ({null_check_id} != nullptr) {{
        {code}
    }}
"""
    return code


def type_descs_to_cpp_arg_types(arg_types: Tuple[TypeDesc]) -> str:
    return ", ".join([t.get_cpp_type().get_type_string() for t in arg_types])


def type_descs_to_cpp_arg_vals(arg_types: Tuple[TypeDesc]) -> str:
    return ", ".join([f"a{i}" for i in range(len(arg_types))])


def type_descs_to_cpp_args(arg_types: Tuple[TypeDesc]) -> str:
    result = []
    for i, t in enumerate(arg_types):
        arg_id = f"a{i}"
        result.append(f"{t.get_cpp_type().get_type_string(identifier=arg_id)}")
    return ", ".join(result)


class StructEntry:
    """
    Used for topological sort while generating struct dependencies of functions.
    """

    def __init__(self, td: StructTypeDesc, deep_traversal: bool):
        self.td = td
        self.deep_traversal = deep_traversal
        self.dependencies: Iterable[StructTypeDesc] = []  # structs this type needs
        self.dependents: Iterable[StructTypeDesc] = []  # structs needing this type
        self.forward_decls: Iterable[
            StructTypeDesc
        ] = []  # forward declarations needed for this type
        self.indegree = 0  # indicate the number of dependencies for topological sort

    def add_dependency(self, dependency: StructTypeDesc):
        """
        Add given type as dependency and increase indegree if
        this is not a self reference
        """
        if dependency != self.td:
            self.dependencies.append(dependency)
            self.indegree += 1

    def add_dependent(self, dependent: StructTypeDesc):
        """
        Add dependent to my list of dependents.
        """
        self.dependents.append(dependent)

    def add_forward_decl(self, decl_type: StructTypeDesc):
        """
        Add type needed as forward declaration for this struct.
        """
        self.forward_decls.append(decl_type)

    def __str__(self):
        dependencies = ",".join([str(d) for d in self.dependencies])
        dependents = ",".join([str(d) for d in self.dependents])
        return (
            f"{self.td} - [{dependencies}] - [{dependents}]"
            f" - go deep {self.deep_traversal} - in {self.indegree}"
        )


def debug_print_graph(struct_graph: Dict[StructTypeDesc, StructEntry]):
    graph_str = ""
    for stype, sentry in struct_graph.items():
        graph_str += f"{stype}\n{sentry}\n\n"

    logger.debug(f"Struct graph nodes:\n{graph_str}")


def build_struct_dependency_graph(
    td: TypeDesc, struct_graph: Dict[StructTypeDesc, StructEntry], deep_traversal: bool
) -> Optional[StructTypeDesc]:
    """
    Iterate through struct dependency graph and collect required structs.

    deep_traversal indicates if pointers should be dereferenced or not.
    """
    if isinstance(td, StructTypeDesc):
        # insert if we don't have this struct definition yet
        # or
        # if we have it but as a dereffed version in which case prefer the not dereffed one
        if td not in struct_graph or (
            td in struct_graph
            and deep_traversal
            and not struct_graph[td].deep_traversal
        ):
            # if it is a struct, iterate all its elements
            # and collect dependencies if any of them are structs
            if td in struct_graph:
                struct_graph[td].deep_traversal = deep_traversal
            else:
                struct_graph[td] = StructEntry(td, deep_traversal)
            for elem in td.elem_types:
                dependency = build_struct_dependency_graph(
                    elem, struct_graph, deep_traversal
                )
                if dependency is not None:
                    # add forward declaration and for dependency and don't add as dependency
                    # so you can handle circular dependencies
                    if isinstance(elem, PointerTypeDesc):
                        struct_graph[td].add_forward_decl(dependency)
                    else:
                        struct_graph[td].add_dependency(dependency)
                    struct_graph[dependency].add_dependent(td)
            return td
        else:
            # we have handled this struct already, just return it as dependency
            return td

    if isinstance(td, PointerTypeDesc):
        # if deep traversal is active and we dereference a pointer
        # deactivate deep traversal to not dereference again down the dependency tree
        if deep_traversal:
            return build_struct_dependency_graph(
                td.pointee, struct_graph, deep_traversal=False
            )

    if isinstance(td, ArrayTypeDesc):
        return build_struct_dependency_graph(
            td.contained_type, struct_graph, deep_traversal
        )

    if isinstance(td, FunctionTypeDesc):
        # the initial call is for a function type, so no need to return any
        # structs at this point since they will be top level structs in the dependency tree
        if deep_traversal:
            build_struct_dependency_graph(td.return_type, struct_graph, deep_traversal)
            for arg in td.arg_types:
                build_struct_dependency_graph(arg, struct_graph, deep_traversal)

    if isinstance(td, UnknownTypeDesc):
        logger.warning("Unknown type in struct: " + str(td))

    return None  # no dependency down this recursion


def get_struct_definitions_from_graph(
    struct_graph: Dict[StructTypeDesc, StructEntry]
) -> str:
    """
    Determine struct dependencies of given type dependency graph and
    generate c++ definition code in correct order by using topological sort.
    """
    if len(struct_graph) == 0:
        # no structs found in funtion prototype
        return ""

    zero_indegree: deque[StructTypeDesc] = deque()
    visited: Set[StructTypeDesc] = set()

    # grab structs without dependencies (print those first)
    for stype, sentry in struct_graph.items():
        if sentry.indegree == 0:
            zero_indegree.append(stype)
            visited.add(stype)

    if len(zero_indegree) == 0:
        logger.error("No struct without dependency on other structs found.")
        return ""

    # debug_print_graph(struct_graph)

    definitions: Iterable[str] = []
    while len(zero_indegree) > 0:
        stype = zero_indegree.popleft()
        sentry = struct_graph[stype]

        for forward_decl_td in sentry.forward_decls:
            definitions.append(forward_decl_td.generate_forward_decl_code())

        is_dereffed = not sentry.deep_traversal
        definitions.append(stype.generate_definition_code(is_dereffed))

        for dependent in sentry.dependents:
            if dependent not in visited:
                struct_graph[dependent].indegree -= 1
                if struct_graph[dependent].indegree == 0:
                    zero_indegree.append(dependent)
                    visited.add(dependent)

    cycle = False
    for _, sentry in struct_graph.items():
        if sentry.indegree != 0:
            logger.error(f"Cyclic dependency found for struct {sentry}.")
            cycle = True

    if cycle:
        return ""

    return "\n".join(definitions)


def get_struct_definitions_from_fntype(function_td: FunctionTypeDesc) -> str:
    """
    Determine struct dependencies of given function type and
    generate c++ definition code in correct order by using topological sort.
    """
    struct_graph: Dict[StructTypeDesc, StructEntry] = dict()
    build_struct_dependency_graph(function_td, struct_graph, deep_traversal=True)

    return get_struct_definitions_from_graph(struct_graph)


def generate_path_code(
    path: augmentum.paths.Path, function: Function, path_code_id: str
) -> Tuple[str, TypeDesc, Optional[str]]:
    """
    Generate access extension code for specified path.
    Example:

    const int32_t LEFT = 0;
    const int32_t RIGHT = 1;

    // Z.L.L.R.T
    int8_t* probed = &((int8_t*) &((int16_t*) &((int32_t*) &r)[LEFT])[LEFT])[RIGHT];

    // A0.D.S0.S0.S0.S1.S2.L.R.T
    int16_t* probed = &((int16_t*) &((int32_t*) &a0->e0.e0.e0.e1.e2)[LEFT])[RIGHT]

    // Z.T
    float* probed = &r;
    double* probed = &r;

    // A0.D.L.L.T
    int8_t* probed = &((int8_t*) &((int16_t*) *&a0)[LEFT])[LEFT];

    // Z.T if original type is int32_t can be float
    float* probed = (float*) &r;


    If a dereference is part of the path, a null check should be added for it. Only one dereference can ever
    appear in a path.
    """

    path_elems = str(path).split(".")
    head = "const int32_t LEFT = 0;\n" "const int32_t RIGHT = 1;\n\n"
    call = ""
    path_type = None
    null_check_id = None
    for idx, elem in enumerate(path_elems):
        if elem == "Z":
            path_type = function.type.return_type
            call = "&r"

        elif elem in ["L", "R"]:
            path_type = IntTypeDesc(path_type.bits // 2)
            call = f"&((int{path_type.bits}_t*) {call})[{'RIGHT' if elem == 'R' else 'LEFT'}]"

        elif elem.startswith("T-"):
            cast = ""
            if (
                path_type.get_cpp_type().get_type_string()
                != path.type.get_cpp_type().get_type_string()
            ):
                # should only happen if a float sits in an int32
                assert (
                    isinstance(path_type, IntTypeDesc)
                    and path_type.bits == 32
                    and isinstance(path.type, RealTypeDesc)
                    and path.type.bits == 32
                ), "Unexpected path types!"
                cast = f"({path.type.get_cpp_type().get_type_string()}*) "
                path_type = path.type

            call = f"{path.type.get_cpp_type().get_type_string()}* {path_code_id} = {cast}{call};"

        elif elem == "D":
            if idx == len(path_elems) - 1:
                raise RuntimeError("Invalid path format: " + str(path))

            path_type = path_type.pointee

            if null_check_id is not None:
                raise RuntimeError(f"More than one dereference in Path {path}")

            null_check_id = call[1:]  # ignore the leading &

            if path_elems[idx + 1].startswith("S"):
                call = f"{call}->"
            elif path_elems[idx + 1] in ["L", "R"] or path_elems[idx + 1].startswith(
                "T-"
            ):
                call = f"*{call}"
            else:
                raise RuntimeError(f"Unexpected Path format {path}")

        elif elem.startswith("A"):
            arg_id = int(elem[1:])
            path_type = function.type.arg_types[arg_id]
            call = f"&a{arg_id}"

        elif elem.startswith("S"):
            if idx == 0:
                raise RuntimeError("Invalid path format: " + str(path))

            struct_elem_idx = int(elem[1:])
            path_type = path_type.elem_types[struct_elem_idx]

            access = "" if path_elems[idx - 1] == "D" else "."
            call = f"{call}{access}e{struct_elem_idx}"

        else:
            raise RuntimeError("Unknown path element: " + elem)

    path_code = head + call + "\n"

    assert isinstance(
        path_type, PrimitiveTypeDesc
    ), f"Expected primitive type for final probe type but got: {path_type}"
    return path_code, path_type, null_check_id


def generate_extension_code(
    log_file: Path,
    sys_prog_src: Path,
    function: Function,
    path: Path,
    generate_body: GenerateBodyCall,
    value_op: Optional[str] = None,
    path_code_id: str = "probed",
) -> str:
    path_code, probed_type, null_check_id = generate_path_code(
        path, function, path_code_id
    )
    modified_function = generate_modified_function(
        function,
        "original_t",
        "original_function",
        "modified_function",
        path_code,
        probed_type,
        null_check_id,
        generate_body,
        value_op,
    )

    extension_code = fill_extension_template(
        function.module,
        function.name,
        str(log_file),
        str(sys_prog_src),
        probed_type.get_cpp_type().get_type_string()
        if isinstance(probed_type, RealTypeDesc)
        else "int64_t",
        get_struct_definitions_from_fntype(function.type),
        modified_function,
    )

    return extension_code


class ProbeBase(ABC):
    @abstractmethod
    def extension_code(self, log_file: Path, sys_prog_src: Optional[Path]) -> str:
        """Return extension code required for this probe.
        log_file: specifies path to log output of extension code
        sys_prog_src: specifies path to source location of system program sources
        """

    def get_description(self) -> str:
        """Description for this probe"""
        raise NotImplementedError


class BaselineProbe(ProbeBase):
    """
    Probe used to execute test cases for recording a baseline.
    No extension library is generated or used during system program execution.
    """

    def extension_code(self, log_file: Path, sys_prog_src: Optional[Path]) -> str:
        return ""

    def get_description(self) -> str:
        return "Measure baseline for available test cases"

    def __str__(self) -> str:
        return "Baseline Probe"


class TracerProbe(ProbeBase):
    """
    Probe all available extension points and log
    which functions have been executed.
    """

    def __init__(self, id: str, always_log: bool = False):
        self.id = id
        self.always_log = always_log

    def extension_code(self, log_file: Path, sys_prog_src: Optional[Path]) -> str:
        return f"""
#include <functional>
#include <iostream>
#include <stdexcept>
#include <filesystem>
#include <fstream>

#include <unordered_set>
#include <mutex>
#include <string>

#include "augmentum.h"

using namespace augmentum;

void write_probe_log(std::string mname, std::string fname) {{
    std::filesystem::path outputFile = "{str(log_file)}";
    std::ofstream out(outputFile.c_str(), std::ios::out | std::ios::app);
    if (out.good()) {{
        out << mname << "{PROBE_LOG_DELIMITER}" << fname << std::endl;
    }} else {{
        throw std::runtime_error("Writing probe log to file failed: " + outputFile.string());
    }}
    out.close();
}}

// remember which functions you have seen already
std::unordered_set<FnExtensionPoint*> cache;
std::mutex log_mutex;  // protects cache and disc write

struct ProbeListener: Listener {{
    AfterAdvice log_trace = [this](FnExtensionPoint& pt, RetVal ret_value, ArgVals arg_values) {{
        FnExtensionPoint* key = &pt;
        const std::lock_guard<std::mutex> lock(log_mutex);
        if ({'true' if self.always_log else 'false'} || cache.find(key) == cache.end()) {{
            cache.insert(key);
            write_probe_log(pt.get_module_name(), pt.get_name());
        }}
    }};

    void on_extension_point_register(FnExtensionPoint& pt) {{
        pt.extend_after(log_trace, id);
    }}

    void on_extension_point_unregister(FnExtensionPoint& pt) {{
        pt.remove(id);
    }}

    AdviceId id = get_unique_advice_id();
}};
ListenerLifeCycle<ProbeListener> probeListener;
"""

    def get_description(self) -> str:
        return f"Tracer Probe for {self.id}"

    def __str__(self) -> str:
        return "Function Tracer Probe"


class PriorProbe(ProbeBase, ABC):
    """Probe generated by a prior"""

    def __init__(self, function: Function, path: augmentum.paths.Path, priorId: str):
        self.function = function
        self.path = path
        self.priorId = priorId

    def __str__(self) -> str:
        return f"{self.function} {self.path} -- {self.priorId}"

    def get_probe_value(self) -> Optional[Number]:
        """Return probe value if any"""
        return None


class NullProbe(PriorProbe):
    # Placeholder for value identifier in a path decoding
    ID_TMPL = "%%VALUE_ID%%"

    """Run function without changes for the given path"""

    def __init__(self, function: Function, path: augmentum.paths.Path, priorId: str):
        super().__init__(function, path, priorId)

    def get_extension_body(
        self,
        return_type: str,
        arg_vals: str,
        path_code: str,
        probed_type: str,
        null_check_id: Optional[str],
        _: Optional[str] = None,
    ) -> str:
        if return_type == "void":
            return_stmt, orig_return = "", ""
        else:
            return_stmt = "return r;"
            orig_return = f"{return_type} r = "

        is_r_path = isinstance(self.path, ResultPath)
        before_code = f"""
        {path_code.replace(NullProbe.ID_TMPL, "before")}
        before_value = *before;
"""
        probed_code = f"""
        {path_code.replace(NullProbe.ID_TMPL, "probed")}
        log_entry(before_value, *probed);
"""

        extension_code = f"""
    {probed_type} before_value = 0;
    {"// before not needed" if is_r_path else add_null_check(null_check_id, before_code)}

    {orig_return}original_function({arg_vals});

    {add_null_check(null_check_id, probed_code)}
    {return_stmt}
"""

        return extension_code

    def extension_code(self, log_file: Path, sys_prog_src: Optional[Path]) -> str:
        assert (
            sys_prog_src is not None
        ), "Given system program source path must not be None."

        return generate_extension_code(
            log_file,
            sys_prog_src,
            self.function,
            self.path,
            self.get_extension_body,
            path_code_id=NullProbe.ID_TMPL,
        )

    def get_description(self) -> str:
        return (
            f"Null Probe for function {self.function}"
            + "\n"
            + f"in module {self.function.module} "
            + "\n"
            f"with path {self.path}"
        )


class ParameterProbe(PriorProbe, Generic[T], ABC):
    """Generate extension code which uses a given parameter to modify the output value."""

    def __init__(
        self, function: Function, path: augmentum.paths.Path, priorId: str, value: T
    ):
        super().__init__(function, path, priorId)
        self.value = value

    @abstractmethod
    def get_value_description(self) -> str:
        """Return a description of how the given value is used."""

    def get_extension_body(
        self,
        return_type: str,
        arg_vals: str,
        path_code: str,
        probed_type: str,
        null_check_id: Optional[str],
        value_op: Optional[str] = None,
    ) -> str:
        if return_type == "void":
            return_stmt, orig_return = "", ""
        else:
            return_stmt = "return r;"
            orig_return = f"{return_type} r = "

        if value_op is None:
            calc_probed = f"{self.value}"
        else:
            calc_probed = f"original_value {value_op} {self.value}"

        probed_code = f"""
        {path_code}
        {probed_type} original_value = *probed;
        *probed = {calc_probed};
        log_entry(original_value, *probed);
"""

        extension_code = f"""
    {orig_return}original_function({arg_vals});
    {add_null_check(null_check_id, probed_code)}
    {return_stmt}
"""
        return extension_code

    def get_probe_value(self) -> Optional[Number]:
        """Return probe value if any"""
        return self.value

    def get_description(self) -> str:
        return (
            f"{self.get_value_description()} Probe for function {self.function}"
            + "\n"
            + f"in module {self.function.module} "
            + "\n"
            f"with path {self.path} and value {self.value}"
        )

    def __str__(self) -> str:
        return super().__str__() + f" # {self.get_value_description()} {self.value}"


class StaticProbe(ParameterProbe):
    """Run function and return given value for the given path"""

    def get_value_description(self) -> str:
        return "Static"

    def extension_code(self, log_file: Path, sys_prog_src: Optional[Path]) -> str:
        assert (
            sys_prog_src is not None
        ), "Given system program source path must not be None."

        return generate_extension_code(
            log_file, sys_prog_src, self.function, self.path, self.get_extension_body
        )


class OffsetProbe(StaticProbe, Generic[T]):
    """Run function and return original value offset by given value for the given path"""

    def get_value_description(self) -> str:
        return "Offset"

    def extension_code(self, log_file: Path, sys_prog_src: Optional[Path]) -> str:
        assert (
            sys_prog_src is not None
        ), "Given system program source path must not be None."

        return generate_extension_code(
            log_file,
            sys_prog_src,
            self.function,
            self.path,
            self.get_extension_body,
            value_op="+",
        )


class ScaleProbe(StaticProbe, Generic[T]):
    """Run function and return original value scaled by given value for the given path"""

    def get_value_description(self) -> str:
        return "Scale"

    def extension_code(self, log_file: Path, sys_prog_src: Optional[Path]) -> str:
        assert (
            sys_prog_src is not None
        ), "Given system program source path must not be None."

        return generate_extension_code(
            log_file,
            sys_prog_src,
            self.function,
            self.path,
            self.get_extension_body,
            value_op="*",
        )
