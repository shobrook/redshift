# Standard library
import linecache

# Third party
import json_repair
from saplings.abstract import Tool
from litellm import completion, encode, decode


#########
# HELPERS
#########


MAX_MERGE_DISTANCE = 10
MAX_FILE_TOKENS = 60000

# TODO: Bias towards returning more smaller chunks rather than less larger chunks?
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

        # TODO: Truncate chunks that are too large (from the end not the start)

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


class ReadFileTool(Tool):
    def __init__(self, pdb, model: str):
        # Base attributes
        self.name = "file"
        self.description = "Searches the content of the current file semantically. Returns the most relevant code snippets from the file."
        self.parameters = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query. Should consist of keywords, e.g. 'auth handler', 'database connection', 'error handling functions', etc.",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        }
        self.is_terminal = False

        # Additional attributes
        self.pdb = pdb
        self.model = model

    def format_output(self, output: list[tuple[int, int]], **kwargs) -> str:
        if not output:
            return "No relevant code found."

        filename = self.pdb.curframe.f_code.co_filename
        lines = linecache.getlines(filename, self.pdb.curframe.f_globals)
        breaklist = self.pdb.get_file_breaks(filename)

        output_str = ""
        for chunk in output:
            first, last = chunk
            chunk = self.pdb.format_lines(
                lines[first - 1 : last], first, breaklist, self.pdb.curframe
            )
            chunk_str = f"<file>{filename}</file>\n<code>\n{chunk}\n</code>"
            output_str += chunk_str + "\n\n"

        output_str = output_str.rstrip()
        return output_str

    async def run(self, query: str, **kwargs) -> list[tuple[int, int]]:
        filename = self.pdb.curframe.f_code.co_filename
        self.pdb.message(f"Searching {filename} for: {query}")

        lines = linecache.getlines(filename, self.pdb.curframe.f_globals)
        file_content = "\n".join(lines)
        last_lineno = len(lines)

        chunks = extract_chunks(filename, file_content, query, self.model)
        chunks = clamp_chunks(chunks, last_lineno)
        chunks = merge_chunks(chunks)
        chunks = [(chunk["first"], chunk["last"]) for chunk in chunks]

        # TODO: Token truncation

        return chunks
