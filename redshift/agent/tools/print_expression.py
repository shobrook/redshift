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
    def __init__(self, pdb, printer, truncator, max_tokens: int = 4096):
        # Base attributes
        self.name = "expression"
        self.description = "Returns the value of a variable or expression. Equivalent to the pdb 'print' command."
        self.parameters = {
            "type": "object",
            "properties": {
                "explanation": {
                    "type": "string",
                    "description": "One sentence explanation as to why this tool is being used, and how it contributes to the goal.",
                },
                "expression": {
                    "type": "string",
                    "description": "Variable or expression to get the value of. E.g. 'var_name' or 'self.attribute'. Variables must be within the scope of the current frame.",
                },
            },
            "required": ["explanation", "expression"],
            "additionalProperties": False,
        }
        self.is_terminal = False

        # Additional attributes
        self.pdb = pdb
        self.printer = printer
        self.truncator = truncator
        self.max_tokens = max_tokens

    def format_output(self, output: ExpressionResult) -> str:
        stack_entry = self.pdb.format_stack_entry(
            self.pdb.stack[self.pdb.curindex], "\n-> "
        )
        output_str = f"<frame>\n{stack_entry}\n</frame>\n\n"
        output_str += f"Value of `{output.expression}` in the frame above:\n\n"
        if output.error:
            output_str += output.value
        else:
            truncated_val = self.truncator.truncate_middle(
                output.value, self.max_tokens, type="char"
            )
            output_str += f"<expression_value>\n{truncated_val}\n</expression_value>"

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
