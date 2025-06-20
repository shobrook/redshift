# Standard library
import json
from collections import namedtuple

# Third party
from saplings.dtos import Message
from saplings.abstract import Tool

# Local
try:
    from redshift.shared.serializers import serialize_call_args
except ImportError:
    from shared.serializers import serialize_call_args


ArgsResult = namedtuple("ArgsResult", ["name_to_repr", "frame_index"])


class PrintArgsTool(Tool):
    def __init__(self, pdb, printer, truncator, max_tokens: int = 4096):
        # Base attributes
        self.name = "args"
        self.description = "Returns the argument list of the current function. Equivalent to the pdb 'args' command."
        self.parameters = {
            "type": "object",
            "properties": {
                "explanation": {
                    "type": "string",
                    "description": "One sentence explanation as to why this tool is being used, and how it contributes to the goal.",
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

    def format_output(self, output: ArgsResult) -> str:
        stack_entry = self.pdb.format_stack_entry(
            self.pdb.stack[self.pdb.curindex], "\n-> "
        )
        output_str = f"<frame>\n{stack_entry}\n</frame>\n\n"
        output_str += "Arguments for the function in the frame above:\n\n"
        output_str += "<args>\n"
        args_str = ""
        for arg_name, arg_val in output.name_to_repr.items():
            args_str += f"{arg_name} = {arg_val}\n"
        output_str += self.truncator.truncate_middle(
            args_str, self.max_tokens, type="line"
        )
        output_str += "\n</args>"

        return output_str

    def is_active(self, trajectory: list[Message] = [], **kwargs) -> bool:
        # Ensure tool can only be called once per frame

        for message in trajectory:
            if not message.raw_output:
                continue

            if isinstance(message.raw_output, ArgsResult):
                if message.raw_output.frame_index == self.pdb.curindex:
                    return False

        return True

    # TODO: Implement update_prompt to include function name in prompt? Same for
    # other tools (e.g. in `retval`, current file in `file`, etc.)

    async def run(self, **kwargs) -> ArgsResult:
        fn_name = self.pdb.curframe.f_code.co_name
        self.printer.tool_call(self.name, fn_name)

        f_code = self.pdb.curframe.f_code
        f_locals = self.pdb.curframe_locals
        arg_reprs = serialize_call_args(f_code, f_locals)
        arg_reprs = json.loads(arg_reprs)

        return ArgsResult(name_to_repr=arg_reprs, frame_index=self.pdb.curindex)
