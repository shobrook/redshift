# Standard library
import sys
import traceback

# Third party
from saplings.abstract import Tool

# Local
try:
    from redshift.shared.serializers import serialize_val
except ImportError:
    from shared.serializers import serialize_val


#########
# HELPERS
#########


def error_message(expression: str) -> str:
    exc = sys.exception()
    message = traceback.format_exception_only(exc)[-1].strip()
    message = f"Failed to get the value of `{expression}`:\n\n{message}"
    return message


######
# MAIN
######


class PrintExpressionTool(Tool):
    def __init__(self, pdb):
        # Base attributes
        self.name = "expression"
        self.description = "Returns the value of a variable or expression. Equivalent to the pdb 'print' command."
        self.parameters = {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Variable or expression to print. E.g. 'var_name' or 'self.attribute'.",
                }
            },
            "required": ["expression"],
            "additionalProperties": False,
        }
        self.is_terminal = False

        # Additional attributes
        self.pdb = pdb

    async def run(self, expression: str, **kwargs) -> str:
        self.pdb.message(f"Evaluating expression: {expression}")

        try:
            value = eval(
                expression, self.pdb.curframe.f_globals, self.pdb.curframe_locals
            )
            return serialize_val(value)
        except:
            return error_message(expression)

        # TODO: Token truncation


# TODO: This is unsafe because it's executing code in the program context.
# We should somehow sandbox this or sanitize the input
