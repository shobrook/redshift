# Standard library
import types
import inspect
from collections import namedtuple

# Third party
from saplings.abstract import Tool


#########
# HELPERS
#########


SourceCode = namedtuple("SourceCode", ["filename", "lineno", "lines"])


######
# MAIN
######


class ShowSourceTool(Tool):
    def __init__(self, pdb):
        # Base attributes
        self.name = "source"
        self.description = "Returns the source code for an object. This can be a variable, function, class, method, module, field, attribute, etc. Equivalent to the pdb 'source' command."
        self.parameters = {
            "type": "object",
            "properties": {
                "object": {"type": "string", "description": "The name of the object."}
            },
            "required": ["object"],
            "additionalProperties": False,
        }
        self.is_terminal = False

        # Additional attributes
        self.pdb = pdb

    def format_output(self, output: SourceCode | str, **kwargs) -> str:
        if isinstance(output, str):
            return output

        output_str = ""
        for lineno, line in enumerate(output.lines, start=output.lineno):
            s = str(lineno).rjust(3)
            s += " "
            if len(s) < 4:
                s += " "

            output_str += f"{s}\t{line.rstrip()}\n"

        output_str = output_str.rstrip()
        output_str = f"<file>{output.filename}</file>\n<code>\n{output_str}\n</code>"
        return output_str

    async def run(self, object: str, **kwargs) -> SourceCode | str:
        self.pdb.message(f"Retrieving source code for: {object}")

        value = None
        try:
            value = eval(object, self.pdb.curframe.f_globals, self.pdb.curframe_locals)
        except Exception as err:
            return f"Could not retrieve source code for `{object}`: {err}"

        if value is None:
            return f"There is no object named `{object}` in the current frame."

        if isinstance(value, types.BuiltinFunctionType) or isinstance(
            value, types.BuiltinMethodType
        ):
            return f"`{object}` is a built-in function or method."

        try:
            filename = inspect.getfile(value)
            lines, lineno = inspect.getsourcelines(value)
            lineno = max(1, lineno)

            return SourceCode(filename=filename, lineno=lineno, lines=lines)
        except (OSError, TypeError) as err:
            return f"Could not retrieve source code for `{object}`: {err}"

        # TODO: Token truncation


# TODO: Try using pdir2 or pydoc as well
