# Standard library
import traceback
from collections import namedtuple

# Third party
from saplings.abstract import Tool

# Local
try:
    from redshift.shared.serializers import serialize_val
except ImportError:
    from shared.serializers import serialize_val


ExpressionResult = namedtuple(
    "ExpressionResult", ["expression", "value", "frame_index"]
)


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

    def format_output(self, output: ExpressionResult) -> str:
        # TODO: Token truncation
        return output.value

    async def run(self, expression: str, **kwargs) -> ExpressionResult:
        self.pdb.message(f"\033[31m├──\033[0m Evaluating expression: {expression}")
        # TODO: Use the tree branches to prefix messages
        # TODO: Show user truncated result

        try:
            # TODO: This is unsafe and should be sandboxed, or the expression should
            # be sanitized

            value = eval(
                expression, self.pdb.curframe.f_globals, self.pdb.curframe_locals
            )
            value = serialize_val(value)
            return ExpressionResult(
                expression=expression, value=value, frame_index=self.pdb.curindex
            )
        except Exception as exc:
            message = traceback.format_exception_only(exc)[-1].strip()
            message = f"Failed to retrieve value:\n\n{message}"
            return ExpressionResult(
                expression=expression, value=message, frame_index=self.pdb.curindex
            )
