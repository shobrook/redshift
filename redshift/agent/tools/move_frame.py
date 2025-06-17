# Standard library
from collections import namedtuple

# Third party
from saplings.dtos import Message
from saplings.abstract import Tool

# Local
try:
    from redshift.shared.is_internal_frame import is_internal_frame
except ImportError:
    from shared.is_internal_frame import is_internal_frame


MoveFrameResult = namedtuple(
    "MoveFrameResult", ["direction", "frame_index", "new_frame_index", "error_message"]
)


class MoveFrameTool(Tool):
    def __init__(self, pdb, printer):
        # Base attributes
        self.name = "move"
        self.description = "Moves the current frame up or down the stack trace. Equivalent to the pdb 'up' or 'down' command."
        self.parameters = {
            "type": "object",
            "properties": {
                "explanation": {
                    "type": "string",
                    "description": "One sentence explanation as to why this tool is being used, and how it contributes to the goal.",
                },
                "direction": {
                    "type": "string",
                    "enum": ["up", "down"],
                    "description": "Direction to move in the stack trace. 'up' moves to an older frame, 'down' moves to a newer frame.",
                },
            },
            "required": ["explanation", "direction"],
            "additionalProperties": False,
        }
        self.is_terminal = False
        # TODO: Add a count parameter to move multiple frames at once

        # Additional attributes
        self.pdb = pdb
        self.printer = printer

    def _select_frame(self, index: int):
        self.pdb.curindex = index
        self.pdb.curframe = self.pdb.stack[self.pdb.curindex][0]
        self.pdb.curframe_locals = self.pdb.curframe.f_locals
        self.pdb.set_convenience_variable(
            self.pdb.curframe, "_frame", self.pdb.curframe
        )
        self.pdb.lineno = None

    def _get_nearest_frame(self, direction: str) -> int | None:
        if direction == "up" and self.pdb.curindex == 0:
            return None
        elif direction == "down" and self.pdb.curindex == len(self.pdb.stack) - 1:
            return None

        indices = (
            range(self.pdb.curindex - 1, -1, -1)
            if direction == "up"
            else range(self.pdb.curindex + 1, len(self.pdb.stack))
        )
        for index in indices:
            frame, _ = self.pdb.stack[index]
            if is_internal_frame(frame):
                return index

        return None

    def _format_frame(self, index: int | None, prefix="  ") -> str:
        if index is None:
            return ""

        frame_lineno = self.pdb.stack[index]
        return prefix + self.pdb.format_stack_entry(frame_lineno, "\n-> ")

    def format_output(self, output: MoveFrameResult) -> str:
        if not output.error_message:
            stack_entry = self._format_frame(self.pdb.curindex, prefix="> ")
            output_str = f"Moved {output.direction} the stack to this frame:\n\n"
            output_str += f"<frame>\n{stack_entry}\n</frame>"

            self.printer.tool_call(
                self.name, stack_entry.splitlines(), arg=output.direction
            )
        else:
            output_str = output.error_message
            self.printer.tool_call(
                self.name, output.error_message, arg=output.direction
            )

        return output_str

    def update_definition(self, trajectory: list[Message] = [], **kwargs):
        # Prevent invalid movements
        if self.pdb.curindex == 0:
            self.parameters["properties"]["direction"]["enum"] = ["down"]
        elif self.pdb.curindex == len(self.pdb.stack) - 1:
            self.parameters["properties"]["direction"]["enum"] = ["up"]

    async def run(self, direction: str, **kwargs) -> MoveFrameResult:
        error_message = ""
        old_index = self.pdb.curindex
        new_index = self._get_nearest_frame(direction)
        if new_index is None:
            if direction == "up":
                error_message = "Already at oldest frame. Cannot move up."
            elif direction == "down":
                error_message = "Already at newest frame. Cannot move down."
        else:
            self._select_frame(new_index)

        return MoveFrameResult(
            direction=direction,
            frame_index=old_index,
            new_frame_index=self.pdb.curindex,
            error_message=error_message,
        )
