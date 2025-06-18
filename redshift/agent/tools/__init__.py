try:
    from redshift.agent.tools.move_frame import MoveFrameTool
    from redshift.agent.tools.print_args import PrintArgsTool, ArgsResult
    from redshift.agent.tools.print_expression import (
        PrintExpressionTool,
        ExpressionResult,
    )
    from redshift.agent.tools.print_retval import PrintRetvalTool, RetvalResult
    from redshift.agent.tools.show_source import ShowSourceTool, SourceResult
    from redshift.agent.tools.read_file import ReadFileTool, FileResult
    from redshift.agent.tools.generate_answer import GenerateAnswerTool
except ImportError:
    from agent.tools.move_frame import MoveFrameTool
    from agent.tools.print_args import PrintArgsTool, ArgsResult
    from agent.tools.print_expression import PrintExpressionTool, ExpressionResult
    from agent.tools.print_retval import PrintRetvalTool, RetvalResult
    from agent.tools.show_source import ShowSourceTool, SourceResult
    from agent.tools.read_file import ReadFileTool, FileResult
    from agent.tools.generate_answer import GenerateAnswerTool

# TODO: Add the following tools:
# - Tool that greps across all files in the stack trace
# - Tool that wraps the inspect module
# - Tool that uses dir or pdir2 to show available variables
# - Tool that uses pydoc to show documentation for any object
