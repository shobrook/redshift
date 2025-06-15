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
        self.description = "Returns the source code for an object. This can be a variable, function, class, method, field, attribute, etc. Equivalent to the pdb 'source' command."
        self.parameters = {
            "type": "object",
            "properties": {
                "explanation": {
                    "type": "string",
                    "description": "One sentence explanation as to why this tool is being used, and how it contributes to the goal.",
                },
                "object": {"type": "string", "description": "The name of the object."},
            },
            "required": ["explanation", "object"],
            "additionalProperties": False,
        }
        self.is_terminal = False

        # Additional attributes
        self.pdb = pdb
        self.printer = printer

    def format_output(self, output: SourceResult | str, **kwargs) -> str:
        stack_entry = self.pdb.format_stack_entry(
            self.pdb.stack[self.pdb.curindex], "\n-> "
        )
        output_str = f"<frame>\n{stack_entry}\n</frame>\n\n"

        if isinstance(output, str):  # Error
            output_str += output
        else:
            # TODO: Token truncation
            breaklist = self.pdb.get_file_breaks(output.filename)
            code = self.pdb.format_lines(output.lines, output.lineno, breaklist)
            output_str += f"Source code for `{output.object}` in the frame above:\n\n"
            output_str += "<source>\n"
            output_str += f"<file>\n{output.filename}\n</file>\n"
            output_str += f"<code>\n{code}\n</code>\n"
            output_str += "</source>"

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
            return f"There is no object named `{object}` in this frame."

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
