# Standard library
import linecache
from collections import defaultdict

# Third party
from saplings.dtos import Message
from saplings.abstract import Tool
from litellm import completion, encode


# Local
try:
    from redshift.shared.truncator import Truncator
    from redshift.agent.tools.read_file import FileResult
    from redshift.agent.tools.print_args import ArgsResult
    from redshift.agent.tools.show_source import SourceResult
    from redshift.agent.tools.print_retval import RetvalResult
    from redshift.agent.tools.print_expression import ExpressionResult
except ImportError:
    from shared.truncator import Truncator
    from agent.tools.read_file import FileResult
    from agent.tools.print_args import ArgsResult
    from agent.tools.show_source import SourceResult
    from agent.tools.print_retval import RetvalResult
    from agent.tools.print_expression import ExpressionResult


#########
# HELPERS
#########


class File(object):
    def __init__(self, num_lines: int, filename: str, lines: list[str]):
        self.num_lines = num_lines
        self.filename = filename
        self.lines = lines

    def __hash__(self) -> int:
        return hash(self.filename)


class CodeChunk(object):
    def __init__(self, line_nums: list[int], file: File):
        self.line_nums = line_nums  # 1-indexed
        self.file = file

    def __hash__(self) -> int:
        line_nums_str = ",".join(map(str, self.line_nums))
        return hash(f"{self.file.filename}:{line_nums_str}")

    def __repr__(self) -> str:
        return f"CodeChunk(file={self.file.filename}, line_nums={self.line_nums})"

    def to_string(self, line_nums: bool = True, dots: bool = True) -> str:
        output_str = ""

        use_dots = not (1 in self.line_nums)
        for line_num, line in enumerate(self.file.lines):
            line_num = line_num + 1
            if line_num not in self.line_nums:
                if use_dots and dots:
                    output_str += "⋮...\n"
                    use_dots = False

                continue

            output_str += (
                f"{line_num} {line.rstrip()}\n" if line_nums else f"{line.rstrip()}\n"
            )
            use_dots = True

        return output_str.strip("\n")


MAX_MERGE_DISTANCE = 15
MAX_THINKING_TOKENS = 2048

SYSTEM_PROMPT = """You are an AI assistant called 'redshift' that helps users debug Python code. \
Your task is to answer the user's query about the state of their code at a breakpoint. \
You will have context on the stack trace at the breakpoint, including important frames, variable values, and source code. \
Use this context to answer the user's query.

<response_format>
1. Use markdown formatting to make your response more readable. DO NOT include a title in your response.
2. Focus on addressing the user's specific query. Be as brief as possible.
3. If relevant, cite specific frames, variable/expression values, files, or code blocks.
4. Display citations in an interesting way (e.g. leveraging tables, arrows, etc.) if you can. DO NOT overdo it.
5. Keep a terse and professional tone.
6. Keep your response brief and to the point.
</response_format>

--

{stack_trace}

--

{important_frames}

--

{code_context}

--

Use the stack trace, important frames, and additional code context to answer the user's query."""


def get_tool_results(trajectory: list[Message]) -> list[any]:
    tool_results = []
    for message in trajectory:
        if not message.role == "tool":
            continue

        if isinstance(message.raw_output, (str, int)):  # Error messages
            continue

        tool_results.append(message.raw_output)

    return tool_results


def is_code_result(tool_result: any) -> bool:
    return isinstance(tool_result, (SourceResult, FileResult))


def is_variable_result(tool_result: any) -> bool:
    return isinstance(tool_result, (ArgsResult, ExpressionResult, RetvalResult))


def group_chunks_by_file(chunks: list[CodeChunk]) -> dict[File, list[CodeChunk]]:
    chunks_by_file = defaultdict(list)
    for chunk in chunks:
        chunks_by_file[chunk.file].append(chunk)

    return chunks_by_file


def get_contiguous_subchunks(line_nums: list[int], file: File) -> list[CodeChunk]:
    if not line_nums:
        return []

    groups = []
    curr_group = [line_nums[0]]
    for line_num in line_nums[1:]:
        if line_num == curr_group[-1] + 1:
            curr_group.append(line_num)
        else:
            groups.append(curr_group)
            curr_group = [line_num]

    if curr_group:
        groups.append(curr_group)

    chunks = [CodeChunk(group, file) for group in groups]
    return chunks


def merge_chunks(chunks: list[CodeChunk]) -> list[CodeChunk]:
    chunks_by_file = group_chunks_by_file(chunks)
    merged_chunks = []
    for file, chunks in chunks_by_file.items():
        all_line_nums = {ln for chunk in chunks for ln in chunk.line_nums}
        all_line_nums = list(sorted(all_line_nums))
        merged_chunks += get_contiguous_subchunks(all_line_nums, file)

    return merged_chunks


def normalize_chunks(chunks: list[CodeChunk]) -> list[CodeChunk]:
    chunks_by_file = group_chunks_by_file(chunks)
    norm_chunks = []
    for file, chunks in chunks_by_file.items():
        all_line_nums = {ln for chunk in chunks for ln in chunk.line_nums}
        all_line_nums = list(sorted(all_line_nums))

        norm_line_nums = []
        for index in range(len(all_line_nums)):
            curr_line_num = all_line_nums[index]
            next_line_num = (
                all_line_nums[index + 1] if index + 1 < len(all_line_nums) else None
            )

            norm_line_nums.append(curr_line_num)
            for i in range(1, MAX_MERGE_DISTANCE + 1):
                if not next_line_num:
                    if curr_line_num + i > file.num_lines:
                        break

                if curr_line_num + i == next_line_num:
                    break

                norm_line_nums.append(curr_line_num + i)

        norm_chunks.append(CodeChunk(norm_line_nums, file))

    return norm_chunks


def collapse_chunks(chunks: list[CodeChunk]) -> list[CodeChunk]:
    chunks_by_file = group_chunks_by_file(chunks)
    collapsed_chunks = []
    for file, chunks in chunks_by_file.items():
        line_nums = set()
        for chunk in chunks:
            line_nums.update(chunk.line_nums)

        chunk = CodeChunk(
            line_nums=list(sorted(line_nums)),
            file=file,
        )
        collapsed_chunks.append(chunk)

    return collapsed_chunks


######
# MAIN
######


class GenerateAnswerTool(Tool):
    def __init__(self, pdb, printer, model: str, prompt: str, history: list[Message]):
        # Base attributes
        self.name = "none"
        self.description = (
            "Call this when you have enough information to answer the user's query."
        )
        self.parameters = {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }
        self.is_terminal = True

        # Additional attributes
        self.pdb = pdb
        self.printer = printer
        self.model = model
        self.prompt = prompt
        self.history = [m.to_openai_message() for m in history]
        self.truncator = Truncator(model)

    def _get_visited_frames(self, tool_results: list[any]) -> list[int]:
        frame_indices = {self.pdb._original_curindex}  # Always include original frame
        for tool_result in tool_results:
            if not hasattr(tool_result, "frame_index"):
                continue

            frame_index = tool_result.frame_index
            frame_indices.add(frame_index)

        return list(sorted(frame_indices))

    def _convert_to_chunks(self, tool_results: list[any]) -> list[CodeChunk]:
        # Standardize tool results to CodeChunk objects

        file_map = {}
        chunks = []
        for tool_result in tool_results:
            filename = getattr(tool_result, "filename", None)
            frame_index = getattr(tool_result, "frame_index", None)

            if filename is None or frame_index is None:
                continue

            if filename not in file_map:
                frame, _ = self.pdb.stack[frame_index]
                lines = linecache.getlines(filename, frame.f_globals)
                file_map[filename] = File(
                    num_lines=len(lines),
                    filename=filename,
                    lines=lines,
                )

            if isinstance(tool_result, SourceResult):
                num_lines = len(tool_result.lines)
                chunk = CodeChunk(
                    line_nums=[i + tool_result.lineno for i in range(num_lines)],
                    file=file_map[tool_result.filename],
                )
                chunks.append(chunk)
            elif isinstance(tool_result, FileResult):
                for chunk in tool_result.chunks:
                    first, last = chunk
                    chunk = CodeChunk(
                        line_nums=list(range(first, last + 1)),
                        file=file_map[tool_result.filename],
                    )
                    chunks.append(chunk)

        return chunks

    def _format_stack_trace(self, max_tokens: int = 4096) -> str:
        stack_trace = self.pdb.format_stack_trace()
        rev_stack_trace = "\n".join(stack_trace.splitlines()[::-1])
        rev_stack_trace = self.truncator.truncate_end(
            rev_stack_trace, max_tokens, type="line"
        )
        stack_trace = "\n".join(rev_stack_trace.splitlines()[::-1])

        context_str = "This is the stack trace at the breakpoint (most recent frame at the bottom):\n\n"
        context_str += "<stack_trace>\n"
        context_str += stack_trace
        context_str += "\n</stack_trace>"

        return context_str

    def _format_stack_entry(self, frame_index: int) -> str:
        if frame_index == self.pdb._original_curindex:
            prefix = "> "
        else:
            prefix = "  "
        stack_entry = prefix + self.pdb.format_stack_entry(
            self.pdb.stack[frame_index], "\n-> "
        )
        return f"<stack_entry>\n{stack_entry}\n</stack_entry>"

    def _format_file_context(self, frame_index: int) -> str:
        frame, _ = self.pdb.stack[frame_index]
        filename = frame.f_code.co_filename
        code = self.pdb.format_frame_line(frame)

        context_str = "This is the file associated with the frame. The line of code is highlighted with an arrow (->):\n\n"
        context_str += (
            f"<file>\n<path>\n{filename}\n</path>\n<code>\n{code}\n</code>\n</file>"
        )
        return context_str

    def _format_function_context(
        self, frame_index: int, tool_results: list[any]
    ) -> str:
        frame, _ = self.pdb.stack[frame_index]
        fn_name = frame.f_code.co_name
        fn_name = "<lambda>" if not fn_name else fn_name

        args_result = next(
            (result for result in tool_results if isinstance(result, ArgsResult)),
            None,
        )
        retval_result = next(
            (result for result in tool_results if isinstance(result, RetvalResult)),
            None,
        )

        if not args_result and not retval_result:
            return ""

        context_str = (
            "This is information about the function associated with the frame:\n\n"
        )
        context_str += f"<function>\n<name>\n{fn_name}\n</name>\n"

        if args_result and args_result.name_to_repr:
            context_str += "<args>\n"
            for name, value in args_result.name_to_repr.items():
                context_str += f"{name} = {value}\n"
            context_str += "</args>\n"

        if retval_result and retval_result.value is not None:
            context_str += f"<return_value>\n{retval_result.value}\n</return_value>\n"

        context_str += "</function>"

        return context_str

    def _format_expression_context(
        self, tool_results: list[any], max_tokens: int
    ) -> str:
        expression_results = [
            result for result in tool_results if isinstance(result, ExpressionResult)
        ]

        if not expression_results:
            return ""

        context_str = "These are the values of relevant variables and expressions in the frame:\n\n"
        context_str += "<variables>\n"
        expressions_str = ""
        for expr_result in expression_results:
            if expr_result.error:
                continue

            expressions_str += f"{expr_result.expression} = {expr_result.value}\n"
        expressions_str = self.truncator.truncate_middle(
            expressions_str, max_tokens, type="line"
        )
        expressions_str = expressions_str.rstrip("\n")
        context_str += f"{expressions_str}\n</variables>"

        return context_str

    def _format_frame_context(
        self, tool_results: list[any], frame_index: int, max_tokens: int = 4096
    ) -> str:
        tool_results = [
            result
            for result in tool_results
            if result.frame_index == frame_index and is_variable_result(result)
        ]
        stack_entry = self._format_stack_entry(frame_index)
        file_context = self._format_file_context(frame_index)
        function_context = self._format_function_context(frame_index, tool_results)
        expression_context = self._format_expression_context(tool_results, max_tokens)

        context_str = f"<frame>\n"
        context_str += stack_entry
        context_str += "\n\n"
        context_str += file_context
        context_str += "\n\n" if function_context else ""
        context_str += function_context
        context_str += "\n\n" if expression_context else ""
        context_str += expression_context
        context_str += "\n</frame>"

        return context_str

    def _format_important_frames(
        self, tool_results: list[any], max_tokens: int = 40000
    ) -> str:
        visited_frames = self._get_visited_frames(tool_results)
        if not visited_frames:
            return ""

        max_frame_tokens = max_tokens // len(visited_frames)
        context_str = "These are the most important frames in the stack trace:\n\n"
        context_str += "<important_frames>\n"
        context_str += "\n\n".join(
            self._format_frame_context(tool_results, f_index, max_frame_tokens)
            for f_index in visited_frames
        )
        context_str += "\n</important_frames>"

        return context_str

    def _format_code_context(
        self, tool_results: list[any], max_tokens: int = 20000
    ) -> str:
        chunks = self._convert_to_chunks(tool_results)
        chunks = merge_chunks(chunks)
        chunks = normalize_chunks(chunks)
        chunks = collapse_chunks(chunks)

        if not chunks:
            return ""

        max_chunk_tokens = max_tokens // len(chunks)

        context_str = (
            "This is additional context on the codebase and imported packages:\n\n"
        )
        context_str += "<code_context>\n"
        for chunk in chunks:
            context_str += "<file>\n"
            context_str += f"<path>\n{chunk.file.filename}\n</path>\n"
            chunk_str = self.truncator.truncate_end(
                chunk.to_string(), max_chunk_tokens, type="line"
            )
            context_str += f"<code>\n{chunk_str}\n</code>\n"
            context_str += "</file>\n\n"
        context_str = context_str.rstrip("\n")
        context_str += "\n</code_context>"

        return context_str

    def _build_system_prompt(self, trajectory: list[Message]) -> str:
        tool_results = get_tool_results(trajectory)
        stack_trace = self._format_stack_trace()
        important_frames = self._format_important_frames(tool_results)
        code_context = self._format_code_context(tool_results)

        return SYSTEM_PROMPT.format(
            stack_trace=stack_trace,
            important_frames=important_frames,
            code_context=code_context,
        )

    async def run(self, **kwargs) -> str:
        self.printer.tool_call("none")
        trajectory = kwargs.get("trajectory", [])
        system_message = {
            "role": "system",
            "content": self._build_system_prompt(trajectory),
        }
        user_message = {
            "role": "user",
            "content": self.prompt,
        }
        messages = [system_message] + self.history + [user_message]
        response = completion(
            model=self.model,
            messages=messages,
            thinking={"type": "enabled", "budget_tokens": MAX_THINKING_TOKENS},
            drop_params=True,
        )
        response = response.choices[0].message.content
        self.printer.final_output(response)

        return response
