# Third party
from saplings.abstract import Tool

# Local
try:
    from redshift.shared.serializers import serialize_val
except ImportError:
    from shared.serializers import serialize_val


######
# MAIN
######


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

    def format_output(self, output: str | None) -> str:
        if output is None:
            return "Not yet returned."

        return output

    async def run(self, **kwargs) -> str | None:
        fn_name = self.pdb.curframe.f_code.co_name
        self.pdb.message(f"Getting return value for: {fn_name}")

        if "__return__" not in self.pdb.curframe_locals:
            return None

        return serialize_val(self.pdb.curframe_locals["__return__"])

        # TODO: Token truncation
