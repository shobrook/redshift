# Standard library
import json

# Third party
from saplings.abstract import Tool

# Local
try:
    from redshift.shared.serializers import serialize_call_args
except ImportError:
    from shared.serializers import serialize_call_args


######
# MAIN
######


class PrintArgsTool(Tool):
    def __init__(self, pdb):
        # Base attributes
        self.name = "args"
        self.description = "Prints the argument list of the current function. Equivalent to the pdb 'a' command."
        self.parameters = {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }
        self.is_terminal = False

        # Additional attributes
        self.pdb = pdb

    def format_output(self, output: dict[str, str]) -> str:
        output_str = ""
        for arg_name, arg_val in output.items():
            output_str += f"{arg_name} = {arg_val}\n"

        return output_str

    async def run(self, **kwargs) -> dict[str, str]:
        f_code = self.pdb.curframe.f_code
        f_locals = self.pdb.curframe_locals
        arg_reprs = serialize_call_args(f_code, f_locals)
        arg_reprs = json.loads(arg_reprs)

        return arg_reprs
