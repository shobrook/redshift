# Standard library
import json
from collections import namedtuple

# Third party
from saplings.abstract import Tool

# Local
try:
    from redshift.shared.serializers import serialize_call_args
except ImportError:
    from shared.serializers import serialize_call_args


ArgsResult = namedtuple("ArgsResult", ["name_to_repr", "frame_index"])


class PrintArgsTool(Tool):
    def __init__(self, pdb, printer):
        # Base attributes
        self.name = "args"
        self.description = "Returns the argument list of the current function. Equivalent to the pdb 'args' command."
        self.parameters = {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for printing the arguments. Keep this brief and to the point.",
                },
            },
            "required": ["reason"],
            "additionalProperties": False,
        }
        self.is_terminal = False

        # Additional attributes
        self.pdb = pdb
        self.printer = printer

    def format_output(self, output: ArgsResult) -> str:
        # TODO: Token truncation

        output_str = ""
        for arg_name, arg_val in output.name_to_repr.items():
            output_str += f"{arg_name} = {arg_val}\n"
        output_str = output_str.rstrip()

        return output_str

    # TODO: Implement is_active to disallow multiple calls in the same frame
    # TODO: Implement update_prompt to include function name in prompt

    async def run(self, **kwargs) -> ArgsResult:
        fn_name = self.pdb.curframe.f_code.co_name
        self.printer.tool_call(self.name, fn_name)

        f_code = self.pdb.curframe.f_code
        f_locals = self.pdb.curframe_locals
        arg_reprs = serialize_call_args(f_code, f_locals)
        arg_reprs = json.loads(arg_reprs)

        return ArgsResult(name_to_repr=arg_reprs, frame_index=self.pdb.curindex)
