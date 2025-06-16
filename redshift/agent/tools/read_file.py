# Standard library
import linecache
from collections import namedtuple

# Third party
from saplings.abstract import Tool
from litellm import completion, encode, decode


FileResult = namedtuple("FileResult", ["chunks", "filename", "frame_index"])


class ReadFileTool(Tool):
    def __init__(self, pdb, printer, model: str, max_tokens: int = 4096):
        # Base attributes
        self.name = "read"
        self.description = "Returns source code for the current file. Similar to the pdb 'list' command, except it returns as many lines as possible."
        self.parameters = {
            "type": "object",
            "properties": {
                "explanation": {
                    "type": "string",
                    "description": "One sentence explanation as to why this tool is being used, and how it contributes to the goal.",
                },
            },
            "required": ["explanation"],
            "additionalProperties": False,
        }
        self.is_terminal = False

        # Additional attributes
        self.pdb = pdb
        self.printer = printer
        self.model = model
        self.max_tokens = max_tokens

    def format_output(self, output: FileResult, **kwargs) -> str:
        lines = linecache.getlines(output.filename, self.pdb.curframe.f_globals)
        breaklist = self.pdb.get_file_breaks(output.filename)

        output_str = ""
        for chunk in output.chunks:
            first, last = chunk
            chunk = self.pdb.format_lines(
                lines[first - 1 : last], first, breaklist, self.pdb.curframe
            )
            chunk_str = f"<file>\n{output.filename}\n</file>\n<code>\n{chunk}\n</code>"
            output_str += chunk_str + "\n\n"
        output_str = output_str.rstrip()

        return output_str

    async def run(self, **kwargs) -> FileResult:
        filename = self.pdb.curframe.f_code.co_filename
        self.printer.tool_call(self.name, filename)

        if filename.startswith("<frozen"):
            tmp = self.pdb.curframe.f_globals.get("__file__")
            if isinstance(tmp, str):
                filename = tmp

        lines = linecache.getlines(filename, self.pdb.curframe.f_globals)
        curr_line = self.pdb.curframe.f_lineno

        start_line, end_line = curr_line, curr_line
        total_tokens = 0

        while (
            start_line > 1 or end_line < len(lines)
        ) and total_tokens < self.max_tokens:
            # Try to add a line before if possible
            if start_line > 1:
                start_line -= 1
                line_tokens = len(encode(model=self.model, text=lines[start_line - 1]))
                if total_tokens + line_tokens <= self.max_tokens:
                    total_tokens += line_tokens
                else:
                    start_line += 1
                    break

            # Try to add a line after if possible
            if end_line < len(lines):
                line_tokens = len(encode(model=self.model, text=lines[end_line - 1]))
                if total_tokens + line_tokens <= self.max_tokens:
                    total_tokens += line_tokens
                    end_line += 1
                else:
                    break

        # NOTE: We use chunks so that in the future we can more intelligently
        # truncate a file (e.g. ensuring certain symbols/lines are included)
        chunks = [(start_line, end_line)]
        return FileResult(
            chunks=chunks, filename=filename, frame_index=self.pdb.curindex
        )
