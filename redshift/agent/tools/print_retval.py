# Standard library
from collections import namedtuple

# Third party
from saplings.dtos import Message
from saplings.abstract import Tool

# Local
try:
    from redshift.shared.serializers import serialize_val
except ImportError:
    from shared.serializers import serialize_val


RetvalResult = namedtuple("RetvalResult", ["value", "frame_index"])


class PrintRetvalTool(Tool):
    def __init__(self, pdb, printer, truncator, max_tokens: int = 4096):
        # Base attributes
        self.name = "retval"
        self.description = "Returns the return value for the last return of the current function. Equivalent to the pdb 'retval' command."
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

    def format_output(self, output: RetvalResult) -> str:
        stack_entry = self.pdb.format_stack_entry(
            self.pdb.stack[self.pdb.curindex], "\n-> "
        )
        output_str = f"<frame>\n{stack_entry}\n</frame>\n\n"

        if output.value is None:
            output_str += "No return value for the function in the frame above."
        else:
            truncated_val = self.truncator.truncate_middle(
                output.value, self.max_tokens, type="char"
            )
            output_str += "Return value for the function in the frame above:\n\n"
            output_str += f"<return_value>\n{truncated_val}\n</return_value>"

        return output_str

    def is_active(self, trajectory: list[Message] = []) -> bool:
        for message in trajectory:
            if not message.raw_output:
                continue

            if isinstance(message.raw_output, RetvalResult):
                if message.raw_output.frame_index == self.pdb.curindex:
                    return False

        return True

    async def run(self, **kwargs) -> RetvalResult:
        fn_name = self.pdb.curframe.f_code.co_name
        self.printer.tool_call(self.name, fn_name)

        if "__return__" not in self.pdb.curframe_locals:
            return RetvalResult(value=None, frame_index=self.pdb.curindex)

        value = serialize_val(self.pdb.curframe_locals["__return__"])
        return RetvalResult(value=value, frame_index=self.pdb.curindex)
