# Standard library
import types
import inspect
from collections import namedtuple

# Third party
from saplings.abstract import Tool


SourceResult = namedtuple(
    "SourceResult", ["filename", "lineno", "lines", "frame_index"]
)


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

    def format_output(self, output: SourceResult | str, **kwargs) -> str:
        if isinstance(output, str):  # Error
            return output

        # TODO: Token truncation
        output_str = ""
        for lineno, line in enumerate(output.lines, start=output.lineno):
            s = str(lineno).rjust(3)
            s += " "
            if len(s) < 4:
                s += " "

            output_str += f"{s}\t{line.rstrip()}\n"
        output_str = output_str.rstrip()
        output_str = (
            f"<file>\n{output.filename}\n</file>\n<code>\n{output_str}\n</code>"
        )

        return output_str

    async def run(self, object: str, **kwargs) -> SourceResult | str:
        self.pdb.message(f"\033[31m├──\033[0m Retrieving source code for: {object}")

        # TODO: Try using pdir2 or pydoc as well
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

            return SourceResult(
                filename=filename,
                lineno=lineno,
                lines=lines,
                frame_index=self.pdb.curindex,
            )
        except (OSError, TypeError) as err:
            return f"Could not retrieve source code for `{object}`: {err}"
