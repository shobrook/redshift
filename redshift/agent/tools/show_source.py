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
    def __init__(self, pdb, printer, truncator, max_tokens: int = 4096):
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
                # TODO: Maybe we can make an enum of all available objects (symbols) in the current scope?
            },
            "required": ["explanation", "object"],
            "additionalProperties": False,
        }
        self.is_terminal = False

        # Additional attributes
        self.pdb = pdb
        self.printer = printer
        self.truncator = truncator
        self.max_tokens = max_tokens

    def format_output(self, output: SourceResult | str, **kwargs) -> str:
        stack_entry = self.pdb.format_stack_entry(
            self.pdb.stack[self.pdb.curindex], "\n-> "
        )
        output_str = f"<frame>\n{stack_entry}\n</frame>\n\n"

        if isinstance(output, str):  # Error
            output_str += output
        else:
            breaklist = self.pdb.get_file_breaks(output.filename)
            code = self.pdb.format_lines(output.lines, output.lineno, breaklist)
            code = self.truncator.truncate_end(code, self.max_tokens, type="line")
            output_str += f"Source code for `{output.object}` in the frame above:\n\n"
            output_str += f"<file>\n{output.filename}\n</file>\n"
            output_str += f"<code>\n{code}\n</code>\n"

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
