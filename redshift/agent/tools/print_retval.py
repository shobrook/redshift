# Standard library
from collections import namedtuple

# Third party
from saplings.abstract import Tool

# Local
try:
    from redshift.shared.serializers import serialize_val
except ImportError:
    from shared.serializers import serialize_val


RetvalResult = namedtuple("RetvalResult", ["value", "frame_index"])


class PrintRetvalTool(Tool):
    def __init__(self, pdb):
        # Base attributes
        self.name = "retval"
        self.description = "Returns the return value for the last return of the current function. Equivalent to the pdb 'retval' command."
        self.parameters = {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }
        self.is_terminal = False

        # Additional attributes
        self.pdb = pdb

    def format_output(self, output: RetvalResult) -> str:
        if output.value is None:
            return "Not yet returned."

        # TODO: Token truncation
        return output.value

    # TODO: Implement is_active to disallow multiple calls in the same frame

    async def run(self, **kwargs) -> RetvalResult:
        fn_name = self.pdb.curframe.f_code.co_name
        self.pdb.message(f"\033[31m├──\033[0m Getting return value for: {fn_name}")

        if "__return__" not in self.pdb.curframe_locals:
            return RetvalResult(value=None, frame_index=self.pdb.curindex)

        value = serialize_val(self.pdb.curframe_locals["__return__"])
        return RetvalResult(value=value, frame_index=self.pdb.curindex)
