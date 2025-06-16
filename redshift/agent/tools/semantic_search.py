# Standard library
import linecache
from collections import namedtuple

# Third party
import json_repair
from saplings.abstract import Tool
from litellm import completion, encode, decode


#########
# HELPERS
#########


MAX_MERGE_DISTANCE = 10
MAX_FILE_TOKENS = 60000

PROMPT = """I want to find all the code in a file that's relevant to a query. \
You'll be given the file content and a query. \
Your job is to return a list of code chunks that are relevant to the query.

Each chunk should be a line range, which is an object with "first" and "last" keys. \
"first" is the first line number of the chunk and "last" is the last line number, both inclusive.

--

Here is the file path and content:

<path>{file_path}</path>
<content>
{file_content}
</content>

And here is the query:

<query>
{query}
</query>"""


def truncate_file_content(file_content: str, model: str) -> str:
    tokens = encode(model=model, text=file_content)[:MAX_FILE_TOKENS]
    truncated_content = decode(model=model, tokens=tokens)
    return truncated_content


def extract_chunks(
    file_path: str, file_content: str, query: str, model: str
) -> list[dict[str, int]]:
    file_content = truncate_file_content(file_content, model)
    messages = [
        {
            "role": "user",
            "content": PROMPT.format(
                file_path=file_path, file_content=file_content, query=query
            ),
        }
    ]
    response = completion(
        model=model,
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "file_chunks_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "chunks": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "first": {
                                        "type": "integer",
                                        "description": "The first line number of the chunk (inclusive).",
                                    },
                                    "last": {
                                        "type": "integer",
                                        "description": "The last line number of the chunk (inclusive).",
                                    },
                                },
                                "required": ["first", "last"],
                                "additionalProperties": False,
                            },
                            "description": "List of code chunks that are relevant to the query. Each chunk should be denoted by a line range.",
                        }
                    },
                    "required": ["chunks"],
                    "additionalProperties": False,
                },
            },
        },
        drop_params=True,
    )
    response = json_repair.loads(response.choices[0].message.content)
    return response["chunks"]


def clamp_chunks(
    chunks: list[dict[str, int]], last_lineno: int
) -> list[dict[str, int]]:
    clamped_chunks = []
    for chunk in chunks:
        first = max(chunk["first"], 1)
        last = min(max(chunk["last"], 1), last_lineno)

        if first > last:
            continue

        clamped_chunks.append({"first": first, "last": last})

    return clamped_chunks


def merge_chunks(chunks: list[dict[str, int]]) -> list[dict[str, int]]:
    merged_chunks = []
    if not chunks:
        return merged_chunks

    chunks.sort(key=lambda chunk: chunk["first"])
    curr_chunk = chunks[0]
    for next_chunk in chunks[1:]:
        curr_lines = set(range(curr_chunk["first"], curr_chunk["last"] + 1))
        next_lines = set(range(next_chunk["first"], next_chunk["last"] + 1))

        is_overlap = bool(curr_lines & next_lines)
        is_within_distance = (
            0 < next_chunk["first"] - curr_chunk["last"] <= MAX_MERGE_DISTANCE
            or 0 < curr_chunk["first"] - next_chunk["last"] <= MAX_MERGE_DISTANCE
        )

        if is_overlap or is_within_distance:
            curr_chunk["first"] = min(curr_chunk["first"], next_chunk["first"])
            curr_chunk["last"] = max(curr_chunk["last"], next_chunk["last"])
        else:
            merged_chunks.append(curr_chunk)
            curr_chunk = next_chunk

    merged_chunks.append(curr_chunk)
    return merged_chunks


######
# MAIN
######


SemanticSearchResult = namedtuple(
    "SemanticSearchResult", ["chunks", "filename", "frame_index"]
)


class SemanticSearchTool(Tool):
    def __init__(self, pdb, printer, model: str):
        # Base attributes
        self.name = "semantic"
        self.description = "Searches the content of the current file semantically. Returns the most relevant code snippets from the file."
        self.parameters = {
            "type": "object",
            "properties": {
                "explanation": {
                    "type": "string",
                    "description": "One sentence explanation as to why this tool is being used, and how it contributes to the goal.",
                },
                "query": {
                    "type": "string",
                    "description": "The search query. Should consist of keywords, e.g. 'auth handler', 'database connection', 'error handling functions', etc.",
                },
            },
            "required": ["explanation", "query"],
            "additionalProperties": False,
        }
        self.is_terminal = False

        # Additional attributes
        self.pdb = pdb
        self.printer = printer
        self.model = model

    def format_output(self, output: SemanticSearchResult, **kwargs) -> str:
        if not output.chunks:
            return "No relevant code found."

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

    async def run(self, query: str, **kwargs) -> SemanticSearchResult:
        filename = self.pdb.curframe.f_code.co_filename
        self.printer.tool_call(self.name, query, arg=filename)

        lines = linecache.getlines(filename, self.pdb.curframe.f_globals)
        file_content = "\n".join(lines)
        last_lineno = len(lines)

        chunks = extract_chunks(filename, file_content, query, self.model)
        chunks = clamp_chunks(chunks, last_lineno)
        chunks = merge_chunks(chunks)
        chunks = [(chunk["first"], chunk["last"]) for chunk in chunks]

        return SemanticSearchResult(
            chunks=chunks, filename=filename, frame_index=self.pdb.curindex
        )


# TODO: Maybe replace this tool with one that lets you grep all files in the stack trace
