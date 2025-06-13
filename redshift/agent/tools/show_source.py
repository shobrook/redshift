# Standard library
import types
import inspect
from collections import namedtuple

# Third party
from saplings.abstract import Tool


SourceResult = namedtuple(
    "SourceResult", ["object", "filename", "lineno", "lines", "frame_index"]
)


class ShowSourceTool(Tool):
    def __init__(self, pdb, printer):
        # Base attributes
        self.name = "source"
        self.description = "Returns the source code for an object. This can be a variable, function, class, method, module, field, attribute, etc. Equivalent to the pdb 'source' command."
        self.parameters = {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for printing the source code. Keep this brief and to the point.",
                },
                "object": {"type": "string", "description": "The name of the object."},
            },
            "required": ["reason", "object"],
            "additionalProperties": False,
        }
        self.is_terminal = False

        # Additional attributes
        self.pdb = pdb
        self.printer = printer

    def format_output(self, output: SourceResult | str, **kwargs) -> str:
        output_str = f"<frame>\n{self.pdb.format_stack_entry(self.pdb.stack[self.pdb.curindex], '\n-> ')}\n</frame>\n\n"

        if isinstance(output, str):  # Error
            output_str += output
        else:
            # TODO: Token truncation
            breaklist = self.pdb.get_file_breaks(output.filename)
            code = self.pdb.format_lines(output.lines, output.lineno, breaklist)
            output_str += "Source code for "
            output_str += f"<file>\n{output.filename}\n</file>"
            output_str += f"\n<code>\n{code}\n</code>"

        return output_str

    async def run(self, object: str, **kwargs) -> SourceResult | str:
        self.printer.tool_call(self.name, object)

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
                object=object,
                filename=filename,
                lineno=lineno,
                lines=lines,
                frame_index=self.pdb.curindex,
            )
        except (OSError, TypeError) as err:
            return f"Could not retrieve source code for `{object}`: {err}"


# TODO: Create more tools that leverage the inspect module
