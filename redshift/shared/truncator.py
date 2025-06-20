# Standard library
from typing import Literal

# Third party
from litellm import encode, decode


class Truncator:
    def __init__(self, model: str):
        self.model = model

    def truncate_end(
        self, text: str, max_tokens: int, type: Literal["line", "char"] = "char"
    ) -> str:
        if len(encode(model=self.model, text=text)) <= max_tokens:
            return text

        if type == "line":
            lines = text.splitlines()
            truncated_lines = []
            num_tokens = 0
            for line in lines:
                line_tokens = len(encode(model=self.model, text=line))
                if num_tokens + line_tokens > max_tokens:
                    break

                num_tokens += line_tokens
                truncated_lines.append(line)

            return "\n".join(truncated_lines) + "\n..."
        elif type == "char":
            tokens = encode(model=self.model, text=text)[:max_tokens]
            truncated_text = decode(model=self.model, tokens=tokens)
            return f"{truncated_text} ..."

        return text

    def truncate_middle(
        self, text: str, max_tokens: int, type: Literal["line", "char"] = "char"
    ) -> str:
        if len(encode(model=self.model, text=text)) <= max_tokens:
            return text

        if type == "line":
            # TODO: Implement
            return text
        elif type == "char":
            tokens = encode(model=self.model, text=text)
            keep_tokens = max_tokens - 3  # Reserve 3 tokens for ellipsis
            start_tokens = keep_tokens // 2
            end_tokens = keep_tokens - start_tokens

            start_text = decode(model=self.model, tokens=tokens[:start_tokens])
            end_text = decode(model=self.model, tokens=tokens[-end_tokens:])

            return f"{start_text} ... {end_text}"

    def window_truncate(
        self, lines: list[str], lineno: int, max_tokens: int
    ) -> tuple[int, int]:
        if len(encode(model=self.model, text="\n".join(lines))) <= max_tokens:
            return 1, len(lines)  # 1-indexed, inclusive

        start_line, end_line = lineno, lineno
        total_tokens = 0

        while (start_line > 1 or end_line < len(lines)) and total_tokens < max_tokens:
            # Try to add a line before if possible
            if start_line > 1:
                start_line -= 1
                line_tokens = len(encode(model=self.model, text=lines[start_line - 1]))
                if total_tokens + line_tokens <= max_tokens:
                    total_tokens += line_tokens
                else:
                    start_line += 1
                    break

            # Try to add a line after if possible
            if end_line < len(lines):
                line_tokens = len(encode(model=self.model, text=lines[end_line - 1]))
                if total_tokens + line_tokens <= max_tokens:
                    total_tokens += line_tokens
                    end_line += 1
                else:
                    break

        return start_line, end_line
