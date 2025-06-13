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
    "ExpressionResult", ["expression", "value", "frame_index", "error"]
)


class PrintExpressionTool(Tool):
    def __init__(self, pdb, printer):
        # Base attributes
        self.name = "expression"
        self.description = "Returns the value of a variable or expression. Equivalent to the pdb 'print' command."
        self.parameters = {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for printing the expression. Keep this brief and to the point.",
                },
                "expression": {
                    "type": "string",
                    "description": "Variable or expression to get the value of. E.g. 'var_name' or 'self.attribute'. Must be within the scope of the current frame.",
                },
            },
            "required": ["reason", "expression"],
            "additionalProperties": False,
        }
        self.is_terminal = False

        # Additional attributes
        self.pdb = pdb
        self.printer = printer

    def format_output(self, output: ExpressionResult) -> str:
        # TODO: Token truncation
        stack_entry = self.pdb.format_stack_entry(
            self.pdb.stack[self.pdb.curindex], "\n-> "
        )
        output_str = f"<frame>\n{stack_entry}\n</frame>\n\n"
        if output.error:
            output_str += output.value
        else:
            output_str += f"{output.expression} = {output.value}"

        return output_str

    async def run(self, expression: str, **kwargs) -> ExpressionResult:
        self.printer.tool_call(self.name, expression)

        try:
            # TODO: This is unsafe and should be sandboxed, or the expression should
            # be sanitized

            value = eval(
                expression, self.pdb.curframe.f_globals, self.pdb.curframe_locals
            )
            value = serialize_val(value)
            return ExpressionResult(
                expression=expression,
                value=value,
                frame_index=self.pdb.curindex,
                error=False,
            )
        except Exception as exc:
            message = traceback.format_exception_only(exc)[-1].strip()
            message = f"Failed to retrieve value:\n\n{message}"
            return ExpressionResult(
                expression=expression,
                value=message,
                frame_index=self.pdb.curindex,
                error=True,
            )


# TODO: Add a dir() tool to check available variables (ignore built-ins)
