# Standard library
import sys
import traceback
import linecache

# Third party
from saplings.abstract import Tool


#########
# HELPERS
#########


def error_message() -> str:
    exc = sys.exception()
    message = traceback.format_exception_only(exc)[-1].strip()
    message = f"***\n{message}"
    return message


######
# MAIN
######


class ReadFileTool(Tool):
    def __init__(self, pdb):
        # Base attributes
        self.name = "list"
        self.description = "Lists source code for the current file. Equivalent to the pdb 'list' command."
        self.parameters = {
            "type": "object",
            "properties": {
                "first": {
                    "type": "integer",
                    "description": "Optional starting line number. If not provided, defaults to the current line.",
                },
                "last": {
                    "type": "integer",
                    "description": "Optional ending line number. If -1, lists all lines in the file. If less than the first line, lists that many lines around the first line. If not provided, lists 11 lines around the first line.",
                },
            },
            "required": [],
            "additionalProperties": False,
        }
        self.is_terminal = False

        # Additional attributes
        self.pdb = pdb

    def format_output(self, output) -> str:
        pass

    async def run(self, first: int | None = None, last: int | None = None, **kwargs):
        if last == -1:
            first = 1
        elif first and last:
            first = max(1, first)
            last = abs(last)
            if last < first:
                incr = max(2, last) // 2
                first = max(1, first - incr)
                last = first + (2 * incr)
        elif first and not last:
            first = max(1, first - 5)
            last = first + 10
        elif not first and last:
            # (Not in prompt) Lists `last` lines around the current line
            incr = max(2, abs(last)) // 2
            first = max(1, self.pdb.curframe.f_lineno - incr)
            last = first + (2 * incr)
        else:
            first = max(1, self.pdb.curframe.f_lineno - 5)
            last = first + 10

        filename = self.pdb.curframe.f_code.co_filename
        lines = linecache.getlines(filename, self.pdb.curframe.f_globals)
        breaklist = self.pdb.get_breaks(filename)

        curr_lineno = self.pdb.curframe.f_lineno
        exc_lineno = self.pdb.tb_lineno.get(self.pdb.curframe, -1)
        lines = lines[first - 1 : last]

        output_str = ""
        for lineno, line in enumerate(lines, first):
            s = str(lineno).rjust(3)
            if len(s) < 4:
                s += " "
            if lineno in breaklist:
                s += "B"
            else:
                s += " "
            if lineno == curr_lineno:
                s += "->"
            elif lineno == exc_lineno:
                s += ">>"

            output_str += f"{s}\t{line.rstrip()}\n"

        output_str = output_str.rstrip()

        # Optionally indicate which lines have breakpoints
