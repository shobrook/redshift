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
                "reason": {
                    "type": "string",
                    "description": "Reason for moving the frame. Keep this brief and to the point.",
                },
                "direction": {
                    "type": "string",
                    "enum": ["up", "down"],
                    "description": "Direction to move in the stack trace. 'up' moves to an older frame, 'down' moves to a newer frame.",
                },
            },
            "required": ["reason", "direction"],
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
        # TODO: Experiment with:
        # - Showing the code snapshot
        # - Not showing anything

        if not output.error_message:
            frame_above = self._get_nearest_frame("up")
            frame_below = self._get_nearest_frame("down")

            frame_above = self._format_frame(frame_above)
            curr_frame = self._format_frame(self.pdb.curindex, prefix="> ")
            frame_below = self._format_frame(frame_below)

            output_str = f"{frame_above}\n" if frame_above else ""
            output_str += curr_frame
            output_str += f"\n{frame_below}" if frame_below else ""

            self.printer.tool_call(
                self.name, curr_frame.splitlines(), arg=output.direction
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
        # TODO: Skip external frames

        newframe = None
        if direction == "up":
            if self.pdb.curindex == 0:
                return MoveFrameResult(
                    direction=direction,
                    frame_index=self.pdb.curindex,
                    new_frame_index=self.pdb.curindex,
                    error_message="Already at oldest frame. Cannot move up.",
                )

            newframe = max(0, self.pdb.curindex - 1)
        elif direction == "down":
            if self.pdb.curindex == len(self.pdb.stack) - 1:
                return MoveFrameResult(
                    direction=direction,
                    frame_index=self.pdb.curindex,
                    new_frame_index=self.pdb.curindex,
                    error_message="Already at newest frame. Cannot move down.",
                )

            newframe = self.pdb.curindex + 1

        if newframe is None:
            return MoveFrameResult(
                direction=direction,
                frame_index=self.pdb.curindex,
                new_frame_index=self.pdb.curindex,
                error_message="Invalid direction. Use 'up' or 'down'.",
            )

        old_index = self.pdb.curindex
        self._select_frame(newframe)

        return MoveFrameResult(
            direction=direction,
            frame_index=old_index,
            new_frame_index=self.pdb.curindex,
            error_message="",
        )
