# Third party
from saplings.abstract import Tool


class MoveFrameTool(Tool):
    def __init__(self, pdb):
        # Base attributes
        self.name = "move"
        self.description = "Moves the current frame up or down the stack trace. Equivalent to the pdb 'up' and 'down' commands."
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
        # TODO: Add a count parameter to move multiple frames at once

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

    def format_output(self, output: str | int) -> str:
        if isinstance(output, int):  # No error
            # TODO: Show frame above and below the current one

            frame_lineno = self.pdb.stack[self.pdb.curindex]
            frame, _ = frame_lineno

            if frame is self.pdb.curframe:
                prefix = "> "
            else:
                prefix = "  "

            output = prefix + self.pdb.format_stack_entry(frame_lineno, "\n-> ")

        return output

    # TODO: Implement update_prompt to protect against invalid moves (e.g.
    # moving down when you're already at the newest frame)

    async def run(self, direction: str, **kwargs) -> str | int:
        self.pdb.message(f"\033[31m├──\033[0m Moving {direction} the call stack")

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

        # TODO: Print the current stack entry underneath the progress message
        # (should be tab-indented and grey, with one frame above/below the current)

        return self.pdb.curindex
