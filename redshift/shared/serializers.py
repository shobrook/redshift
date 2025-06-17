# Some methods adapted from: https://github.com/gaogaotiantian/objprint

# Standard library
import re
import json
import inspect
import itertools
import traceback
import collections
from types import FunctionType, ModuleType
from typing import Any, Dict, Generator, List, Set, Tuple, Union


#########
# HELPERS
#########


def filter_builtins(locals_dict: Dict[str, Any]) -> Dict[str, Any]:
    default_locals = {}
    exec("", default_locals)  # Create an empty scope
    default_builtins = default_locals["__builtins__"]

    if "__builtins__" in locals_dict:
        locals_dict["__builtins__"] = {
            k: v
            for k, v in locals_dict["__builtins__"].items()
            if k not in default_builtins or default_builtins[k] is not v
        }
        if not locals_dict["__builtins__"]:
            del locals_dict["__builtins__"]

    # TODO: Might need to do string comparison instead of object comparision (is not)
    return {
        k: v
        for k, v in locals_dict.items()
        if k not in default_locals or default_locals[k] is not v
    }


def get_call_args(f_code, f_locals) -> dict[str, object]:
    n_args = f_code.co_argcount + f_code.co_kwonlyargcount

    if f_code.co_flags & inspect.CO_VARARGS:
        n_args += 1
    if f_code.co_flags & inspect.CO_VARKEYWORDS:
        n_args += 1

    call_args = {}
    for index in range(n_args):
        arg_name = f_code.co_varnames[index]
        if arg_name not in f_locals:
            continue

        call_args[arg_name] = f_locals[arg_name]

    return call_args


def add_indent(
    line: Union[str, List[str]], level: int, indent: int = 2
) -> Union[str, List[str]]:
    if isinstance(line, str):
        return " " * (level * indent) + line

    return [" " * (level * indent) + ll for ll in line]


def get_header_footer(obj: Any) -> Tuple[str, str]:
    indicator_map = {
        list: "[]",
        tuple: "()",
        dict: "{}",
        set: "{}",
    }  # TODO: Handle other built-in types (e.g. defaultdict, OrderedDict, etc.)

    obj_type = type(obj)
    if obj_type in indicator_map:
        indicator = indicator_map[obj_type]
        return indicator[0], indicator[1]

    return f"<{obj_type.__name__} {hex(id(obj))}", ">"


def get_ellipsis_str(obj: Any) -> str:
    header, footer = get_header_footer(obj)
    return f"{header} ... {footer}"


def get_packed_str(
    obj: Any, elements: Generator[str, None, None], level: int, max_elements: int = 20
) -> str:
    header, footer = get_header_footer(obj)

    if max_elements == -1:
        elements = list(elements)
    else:
        first_elements = []
        it = iter(elements)
        try:
            for _ in range(max_elements):
                first_elements.append(next(it))
        except StopIteration:
            pass

        if next(it, None) is not None:
            first_elements.append("...")

        elements = first_elements

    multiline = False
    if len(header) > 1 and len(elements) > 0:  # Not a built-in
        multiline = True
    elif any(("\n" in el for el in elements)):  # Already has newlines
        multiline = True

    if multiline:
        elements = ",\n".join(add_indent(elements, level + 1))
        return f"{header}\n{elements}\n{add_indent('', level)}{footer}"

    elements = ", ".join(elements)
    return f"{header}{elements}{footer}"


def get_custom_object_str(obj: Any, visited: Set[int], level: int) -> str:
    # If it has __str__ or __repr__ overloaded, honor that
    if (
        obj.__class__.__str__ is not object.__str__
        or obj.__class__.__repr__ is not object.__repr__
    ):
        s = str(obj)
        lines = s.split("\n")
        lines[1:] = [add_indent(line, level) for line in lines[1:]]
        return "\n".join(lines)

    def _get_method_line(attr: str) -> str:
        return f"def {attr}{inspect.signature(getattr(obj, attr))}"

    def _get_line(key: str) -> str:
        val = serialize_object(getattr(obj, key), visited, level + 1)
        return f".{key} = {val}"

    attrs, methods = [], []
    for attr in dir(obj):
        if not re.fullmatch(r"(?!_).*", attr):
            continue

        try:
            attr_val = getattr(obj, attr)
        except AttributeError:
            continue

        if inspect.ismethod(attr_val) or inspect.isbuiltin(attr_val):
            methods.append(attr)
        else:
            attrs.append(attr)

    elements = itertools.chain(
        (_get_method_line(attr) for attr in sorted(methods)),
        (_get_line(key) for key in sorted(attrs)),
    )

    return get_packed_str(obj, elements, level)


def serialize_object(obj: object, visited: set[int], level: int) -> str:
    # Handle built-in types
    if isinstance(obj, str):
        return f"'{obj}'"
    elif isinstance(obj, (int, float)) or obj is None:
        return str(obj)
    elif isinstance(obj, FunctionType):
        return f"<function {obj.__qualname__}>"
    elif isinstance(obj, ModuleType):
        return f"<module {obj.__name__}>"

    # TODO: Handle other built-in types

    # Prevent recursion
    if id(obj) in visited:
        return get_ellipsis_str(obj)

    visited = visited.copy()
    visited.add(id(obj))

    # Handle container types
    if isinstance(obj, (list, tuple, set, frozenset)):
        elements = (f"{serialize_object(el, visited, level + 1)}" for el in obj)
        return get_packed_str(obj, elements, level)
    elif isinstance(obj, (dict, collections.abc.Mapping)):
        items = [(key, val) for key, val in obj.items()]
        try:
            items = sorted(items)
        except TypeError:
            pass

        elements = (
            f"{serialize_object(key, visited, level + 1)}: {serialize_object(val, visited, level + 1)}"
            for key, val in items
        )
        return get_packed_str(obj, elements, level)

    # Handle all other objects
    return get_custom_object_str(obj, visited, level)


def default_serialize_object(obj: object) -> str:
    try:
        return repr(obj)
    except Exception as e:
        formatted_exc = traceback.format_exception_only(e)[-1].strip()
        return f"*** repr() failed: {formatted_exc} ***"


######
# MAIN
######


def serialize_val(value: object, use_default: bool = True) -> str:
    if use_default:
        return default_serialize_object(value)

    return serialize_object(value, visited=set(), level=0)


def serialize_vars(vars_dict: dict[str, object], use_default: bool = True) -> str:
    vars_dict = filter_builtins(vars_dict)
    serialized_dict = {
        var_name: serialize_val(var_val, use_default)
        for var_name, var_val in vars_dict.items()
    }
    return json.dumps(serialized_dict)


def serialize_call_args(f_code, f_locals, use_default: bool = True) -> str:
    call_args = get_call_args(f_code, f_locals)
    return serialize_vars(call_args, use_default)


def serialize_retval(value: object, use_default: bool = True) -> str:
    if use_default:
        return default_serialize_object(value)

    return serialize_object(value, visited=set(), level=0)
