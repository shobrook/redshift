try:
    from redshift.agent.tools.move_frame import MoveFrameTool
    from redshift.agent.tools.print_args import PrintArgsTool
    from redshift.agent.tools.print_expression import PrintExpressionTool
    from redshift.agent.tools.print_retval import PrintRetvalTool
    from redshift.agent.tools.read_file import ReadFileTool
    from redshift.agent.tools.show_source import ShowSourceTool
    from redshift.agent.tools.generate_answer import GenerateAnswerTool
except ImportError:
    from agent.tools.move_frame import MoveFrameTool
    from agent.tools.print_args import PrintArgsTool
    from agent.tools.print_expression import PrintExpressionTool
    from agent.tools.print_retval import PrintRetvalTool
    from agent.tools.read_file import ReadFileTool
    from agent.tools.show_source import ShowSourceTool
    from agent.tools.generate_answer import GenerateAnswerTool
