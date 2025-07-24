# Standard library
from collections import namedtuple

# Third party
from saplings.abstract import Tool


NamesResult = namedtuple("NamesResult", ["locals", "globals", "frame_index"])

TOOL_DESCRIPTION = """Returns all the local and global variable names in the current frame. \
Use this to see what variables, functions, classes, etc. you can inspect the values of."""


class PrintNamesTool(Tool):
    def __init__(self, pdb, printer, truncator, max_tokens: int = 4096):
        # Base attributes
        self.name = "names"
        self.description = TOOL_DESCRIPTION
        self.parameters = {
            "type": "object",
            "properties": {
                "explanation": {
                    "type": "string",
                    "description": "Short, one-sentence explanation of why this tool is being used, and how it contributes to the goal.",
                },
            },
            "required": ["explanation"],
            "additionalProperties": False,
        }
        self.is_terminal = False

        # Additional attributes
        self.pdb = pdb
        self.printer = printer
        self.truncator = truncator
        self.max_tokens = max_tokens

    def format_output(self, output: NamesResult, **kwargs) -> str:
        stack_entry = self.pdb.format_stack_entry(
            self.pdb.stack[self.pdb.curindex], "\n-> "
        )
        output_str = f"<frame>\n{stack_entry}\n</frame>\n\n"

        locals_str = "\n".join(output.locals)
        globals_str = "\n".join(output.globals)

        max_tokens = self.max_tokens // 2
        locals_str = self.truncator.truncate_end(locals_str, max_tokens, type="line")
        globals_str = self.truncator.truncate_end(globals_str, max_tokens, type="line")

        output_str += f"Defined names in the current frame:\n\n"
        output_str += f"<locals>\n{locals_str}\n</locals>\n"
        output_str += f"<globals>\n{globals_str}\n</globals>\n"

        return output_str

    async def run(self, **kwargs) -> NamesResult | str:
        self.printer.tool_call(self.name)

        local_names = list(self.pdb.curframe_locals.keys())
        global_names = list(self.pdb.curframe.f_globals.keys())

        return NamesResult(
            locals=local_names,
            globals=global_names,
            frame_index=self.pdb.curindex,
        )
