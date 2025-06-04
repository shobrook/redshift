# Third party
from saplings.abstract import Tool


######
# MAIN
######


class MoveFrameTool(Tool):
    def __init__(self, pdb):
        # Base attributes
        self.name = "move"
        self.description = "Move the current frame up or down the stack trace. Equivalent to the pdb 'up' and 'down' commands."
        self.parameters = {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down"],
                    "description": "Direction to move in the stack trace. 'up' moves to an older frame, 'down' moves to a newer frame.",
                },
            },
            "required": ["direction"],
            "additionalProperties": False,
        }
        self.is_terminal = False

        # Additional attributes
        self.pdb = pdb

    def _select_frame(self, index: int):
        self.pdb.curindex = index
        self.pdb.curframe = self.pdb.stack[self.pdb.curindex][0]
        self.pdb.curframe_locals = self.pdb.curframe.f_locals
        self.pdb.set_convenience_variable(
            self.pdb.curframe, "_frame", self.pdb.curframe
        )
        self.pdb.lineno = None

    def format_output(self, output: str | None) -> str:
        # No error message, show current stack entry
        if not output:
            frame_lineno = self.pdb.stack[self.pdb.curindex]
            frame, _ = frame_lineno

            if frame is self.pdb.curframe:
                prefix = "> "
            else:
                prefix = "  "

            return prefix + self.pdb.format_stack_entry(frame_lineno, "\n-> ")

        # TODO: Show frame above and below the current one

        # Show error message
        return output

    async def run(self, direction: str, **kwargs) -> str | None:
        self.pdb.message(f"Moving {direction} the call stack")

        # TODO: Skip non-user frames

        newframe = None
        if direction == "up":
            if self.pdb.curindex == 0:
                return "Already at oldest frame. Cannot move up."

            newframe = max(0, self.pdb.curindex - 1)
        elif direction == "down":
            if newframe == len(self.pdb.stack):
                return "Already at newest frame. Cannot move down."

            newframe = self.pdb.curindex + 1

        if newframe is None:
            return "Invalid direction. Use 'up' or 'down'."

        self._select_frame(newframe)
        return None
