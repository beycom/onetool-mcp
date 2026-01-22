"""Console reporter for progress events during benchmark runs."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from rich import box
from rich.rule import Rule
from rich.table import Table

from ot.config import get_config
from ot.logging import LogSpan

# Patterns to detect in MCP tool responses that indicate LLM retry behavior
TOOL_RESPONSE_ERROR_PATTERNS = [
    r"Code validation failed",
]

if TYPE_CHECKING:
    from rich.console import Console

    from ot_bench.harness.config import HarnessConfig
    from ot_bench.harness.metrics import TaskResult


def _extract_result(response: str) -> str:
    """Extract result from JSON response if present."""
    try:
        parsed = json.loads(response)
        if isinstance(parsed, dict) and "result" in parsed:
            return str(parsed["result"])
    except json.JSONDecodeError:
        pass
    return response


class SpanPrinter:
    """Formats and prints spans to console as name=value pairs.

    Verbose mode:
    - Non-verbose: newlines replaced with \\n, values truncated at compact_max_length
    - Verbose: full content with actual newlines
    """

    def __init__(self, console: Console, verbose: bool = False) -> None:
        self.console = console
        self.verbose = verbose
        self.compact_max_length = get_config().compact_max_length

    def _format_value(self, value: Any) -> str:
        """Format a value for console output based on verbose mode."""
        # Format lists as comma-separated
        if isinstance(value, list):
            result = ", ".join(str(v) for v in value) if value else ""
        else:
            result = str(value)

        # Non-verbose: truncate and replace newlines
        if not self.verbose:
            result = result.replace("\n", "\\n")
            if len(result) > self.compact_max_length:
                result = result[: self.compact_max_length] + "..."

        return result

    def print_span(self, data: dict[str, Any]) -> None:
        """Print all span fields to console.

        Special handling for taskRequest and taskResponse - highlighted in green
        to match evaluation output style.
        """
        self.console.print()
        for key, value in data.items():
            formatted = self._format_value(value)
            # Highlight taskRequest and taskResponse in green (like evaluation)
            if key in ("taskRequest", "taskResponse"):
                self.console.print(f"    [bold green]{key}[/bold green]={formatted}")
            else:
                self.console.print(f"    [cyan]{key}[/cyan]={formatted}")


class ConsoleReporter:
    """Handles progress reporting for benchmark runs.

    Encapsulates all console output logic, supporting verbose mode
    and trace mode for debugging.
    """

    def __init__(
        self,
        console: Console,
        config: HarnessConfig,
        *,
        verbose: bool = False,
        trace: bool = False,
        no_color: bool = False,
    ) -> None:
        """Initialize the reporter.

        Args:
            console: Rich console for output.
            config: Harness configuration (for looking up prompts).
            verbose: Enable verbose output with full content.
            trace: Enable timestamped trace output for debugging.
            no_color: Disable color output.
        """
        self.console = console
        self.config = config
        self.verbose = verbose
        self.trace = trace
        self.no_color = no_color
        self.span_printer = SpanPrinter(console, verbose=verbose)

        # Track LLM call count per task for [call=N] prefix
        self.llm_call_counts: dict[str, int] = {}

        # Track tool call count per task
        self.tool_call_counts: dict[str, int] = {}

        # Track connected servers per task (for inferring server in tool calls)
        self.connected_servers: dict[str, list[str]] = {}

        # Track current task for server connection events
        self.current_task: str | None = None

        # Current tool call LogSpan (captures timing and data)
        self.current_tool_span: LogSpan | None = None

        # Current harness LogSpan (captures timing and data)
        self.current_harness_span: LogSpan | None = None

        # Track code validation errors for summary
        self.validation_errors: list[dict[str, str]] = []

        # Track current scenario name
        self.current_scenario: str | None = None

    def _get_server_for_task(self, task: str | None) -> str:
        """Get the server name for a task.

        Args:
            task: Task name.

        Returns:
            Server name or "mcp" if unknown.
        """
        if task and task in self.connected_servers and self.connected_servers[task]:
            servers = self.connected_servers[task]
            return servers[0] if len(servers) == 1 else ",".join(servers)
        return "mcp"

    def on_event(
        self,
        event: str,
        *,
        scenario: str | None = None,
        task: str | None = None,
        result: TaskResult | None = None,
        server: str | None = None,
        server_status: str | None = None,  # noqa: ARG002 - part of event interface
        tool_count: int | None = None,
        error: str | None = None,
        tool_name: str | None = None,
        tool_args: dict[str, Any] | None = None,
        tool_result: str | None = None,
        llm_request: list[dict[str, Any]] | None = None,
        llm_response: str | None = None,
    ) -> None:
        """Handle a progress event from the runner.

        Args:
            event: Event type (scenario_start, task_start, task_complete, etc.).
            scenario: Scenario name (if applicable).
            task: Task name (if applicable).
            result: TaskResult (for task_complete events).
            server: Server name (for server_* events).
            server_status: Status message (for server_* events).
            tool_count: Number of tools available (for server_connected events).
            error: Error message (for server_failed events).
            tool_name: Name of tool being called (for tool_call/tool_response events).
            tool_args: Arguments passed to tool (for tool_call events).
            tool_result: Result from tool (for tool_response events).
            llm_request: Messages sent to LLM (for llm_request events).
            llm_response: Final LLM response text (for llm_response events).
        """
        if event == "scenario_start":
            self._on_scenario_start(scenario)
        elif event == "task_start":
            self._on_task_start(task)
        elif event == "server_connecting":
            self._on_server_connecting(server)
        elif event == "server_connected":
            self._on_server_connected(task, server, tool_count)
        elif event == "server_failed":
            self._on_server_failed(server, error)
        elif event == "tool_call":
            self._on_tool_call(task, tool_name, tool_args)
        elif event == "tool_response":
            self._on_tool_response(task, tool_name, tool_result)
        elif event == "llm_request":
            self._on_llm_request(task, llm_request)
        elif event == "llm_response":
            self._on_llm_response(task, llm_response)
        elif event == "task_complete":
            self._on_task_complete(task, result)
        elif event == "task_evaluated":
            self._on_task_evaluated(result)

    def _on_scenario_start(self, scenario: str | None) -> None:
        """Handle scenario_start event."""
        self.current_scenario = scenario
        self.console.print(f"\n[yellow]Scenario[/yellow]: {scenario}")

    def _on_task_start(self, task: str | None) -> None:
        """Handle task_start event."""
        if task:
            self.llm_call_counts[task] = 0
            self.tool_call_counts[task] = 0
            self.connected_servers[task] = []
            self.current_task = task

        # Visual separator between tasks
        self.console.print()
        self.console.print(Rule(style="dim"))
        self.console.print(f"  [bold cyan]Task[/bold cyan]: {task}")

    def _on_server_connecting(self, _server: str | None) -> None:
        """Handle server_connecting event."""
        # Server connection logged but not displayed (too noisy)

    def _on_server_connected(
        self,
        task: str | None,
        server: str | None,
        _tool_count: int | None,
    ) -> None:
        """Handle server_connected event."""
        # Track connected server for this task
        task_key = task or self.current_task
        if task_key and server:
            if task_key not in self.connected_servers:
                self.connected_servers[task_key] = []
            self.connected_servers[task_key].append(server)

        # Server connection logged but not displayed (too noisy)

    def _on_server_failed(self, server: str | None, error: str | None) -> None:
        """Handle server_failed event."""
        self.console.print(
            f"    [yellow]mcpFailed[/yellow]: [red]{server}[/red], error: {error}"
        )

    def _on_tool_call(
        self,
        task: str | None,
        tool_name: str | None,
        tool_args: dict[str, Any] | None,
    ) -> None:
        """Handle tool_call event - start a new tool span."""
        # Increment tool call counter
        if task and task in self.tool_call_counts:
            self.tool_call_counts[task] += 1

        server = self._get_server_for_task(task)
        call_num = self.tool_call_counts.get(task, 1) if task else 1

        # Format request as tool_name(args) - this is what the LLM sent to MCP
        request_llm = ""
        if tool_name and tool_args:
            if tool_name == "run" and "command" in tool_args:
                request_llm = str(tool_args["command"])
            else:
                request_llm = (
                    f"{tool_name}({json.dumps(tool_args, separators=(',', ':'))})"
                )

        # Create LogSpan - it captures timing automatically
        self.current_tool_span = LogSpan(
            span="bench.tool_call",
            task=task or "",
            call=call_num,
            server=server,
            tool=tool_name or "",
            requestLLM=request_llm,
        )

    def _on_tool_response(
        self,
        task: str | None,
        tool_name: str | None,  # noqa: ARG002
        tool_result: str | None,
    ) -> None:
        """Handle tool_response event - complete and emit tool span."""
        if not self.current_tool_span:
            return

        # Extract result for cleaner output
        response_mcp = _extract_result(tool_result or "")

        # Add response to span
        self.current_tool_span.add("responseMCP", response_mcp)

        # Check for error patterns and save for summary
        for pattern in TOOL_RESPONSE_ERROR_PATTERNS:
            if re.search(pattern, response_mcp):
                # Get requestLLM from the span (dict-style access)
                try:
                    request_llm = self.current_tool_span["requestLLM"]
                except KeyError:
                    request_llm = ""
                self.validation_errors.append(
                    {
                        "scenario": self.current_scenario or "",
                        "task": task or "",
                        "requestLLM": request_llm,
                        "responseMCP": response_mcp,
                    }
                )
                break

        # Get data from span for console output (includes duration)
        span_data = self.current_tool_span.to_dict()

        # Complete the LogSpan (logs to file)
        self.current_tool_span.__exit__(None, None, None)

        # Print to console
        self.span_printer.print_span(span_data)

        self.current_tool_span = None

    def _on_llm_request(
        self, task: str | None, llm_request: list[dict[str, Any]] | None
    ) -> None:
        """Handle llm_request event - start harness span on first call."""
        if not llm_request:
            return

        # Increment LLM call counter
        if task:
            if task not in self.llm_call_counts:
                self.llm_call_counts[task] = 0
            self.llm_call_counts[task] += 1

        # Only create harness span on first LLM call
        call_count = self.llm_call_counts.get(task, 0) if task else 0
        if call_count == 1:
            system_prompt = ""
            user_request = ""
            for msg in llm_request:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "system" and content:
                    system_prompt = content
                elif role == "user" and content:
                    user_request = content

            # Create LogSpan - it captures timing automatically
            self.current_harness_span = LogSpan(
                span="bench.llm_call",
                task=task or "",
                systemPrompt=system_prompt,
                taskRequest=user_request,
            )

    def _on_llm_response(self, task: str | None, llm_response: str | None) -> None:  # noqa: ARG002
        """Handle llm_response event - capture final response for harness span."""
        # Update harness span with final response
        if self.current_harness_span and llm_response:
            self.current_harness_span.add("taskResponse", llm_response)

    def _on_task_complete(self, task: str | None, result: TaskResult | None) -> None:
        """Handle task_complete event - emit harness span."""
        if not result:
            return

        # Complete and emit harness span
        if self.current_harness_span:
            # Add metrics and status to the span
            self.current_harness_span.add(
                tokensIn=result.input_tokens,
                tokensOut=result.output_tokens,
                llmCalls=result.llm_calls,
                toolCalls=result.tool_calls,
                cost=round(result.cost_usd, 6),
                taskStatus="error" if result.error else "complete",
                toolsUsed=result.tools_used or [],
            )
            if result.error:
                self.current_harness_span.add(error=result.error)

            # Get data from span for console output (includes duration)
            span_data = self.current_harness_span.to_dict()

            # Complete the LogSpan (logs to file)
            self.current_harness_span.__exit__(None, None, None)

            # Print to console
            self.span_printer.print_span(span_data)

            self.current_harness_span = None

        # Clean up task state
        if task:
            self.connected_servers.pop(task, None)

    def _on_task_evaluated(self, result: TaskResult | None) -> None:
        """Handle task_evaluated event - display evaluation result."""
        if not result or not result.evaluation:
            return

        eval_result = result.evaluation
        self.console.print()

        if eval_result.eval_type == "pass_fail":
            # Pass/fail evaluation - show PASS or FAIL
            if eval_result.passed:
                status_style = "bold green"
                status = "PASS"
            else:
                status_style = "bold red"
                status = "FAIL"

            self.console.print(
                f"    [{status_style}]evaluation[/{status_style}]: {status}"
            )

            # In verbose mode, show expected vs actual
            if self.verbose:
                if eval_result.expected:
                    self.console.print(
                        f"      [dim]expected[/dim]: {eval_result.expected}"
                    )
                if eval_result.actual:
                    self.console.print(f"      [dim]actual[/dim]: {eval_result.actual}")
                if eval_result.reason:
                    self.console.print(f"      [dim]reason[/dim]: {eval_result.reason}")
            elif not eval_result.passed:
                # For failures, always show expected vs actual for debugging
                if eval_result.expected:
                    self.console.print(
                        f"      [dim]expected[/dim]: {eval_result.expected}"
                    )
                if eval_result.actual:
                    self.console.print(f"      [dim]actual[/dim]: {eval_result.actual}")
                if eval_result.reason:
                    self.console.print(f"      [dim]reason[/dim]: {eval_result.reason}")
        else:
            # Scored evaluation - show numeric score
            score = eval_result.score
            if score >= 80:
                score_style = "bold green"
            elif score >= 50:
                score_style = "bold yellow"
            else:
                score_style = "bold red"

            self.console.print(
                f"    [{score_style}]evaluation[/{score_style}]: "
                f"score={score}/100, reason={eval_result.reason}"
            )

    def print_results_header(self) -> None:
        """Print the BENCHMARK RESULTS header with a double-line separator."""
        self.console.print()
        self.console.print(Rule("BENCHMARK RESULTS", style="bold cyan", characters="═"))
        self.console.print()

    def _format_eval_result(self, task_result: Any) -> str:
        """Format evaluation result for table display.

        Returns PASS/FAIL for pass_fail evaluations, numeric score for scored.
        """
        if not task_result.evaluation:
            return "-"

        eval_result = task_result.evaluation
        if eval_result.eval_type == "pass_fail":
            return "PASS" if eval_result.passed else "FAIL"
        else:
            return str(eval_result.score)

    def _style_eval_result(self, task_result: Any) -> str:
        """Get style for evaluation result based on pass/fail or score."""
        if not task_result.evaluation:
            return ""

        eval_result = task_result.evaluation
        if eval_result.eval_type == "pass_fail":
            return "bold green" if eval_result.passed else "bold red"
        else:
            score = eval_result.score
            if score >= 80:
                return "bold green"
            elif score >= 50:
                return "bold yellow"
            else:
                return "bold red"

    def print_results_table(
        self, scenario_result: Any, *, show_header: bool = False
    ) -> None:
        """Print a results table for a scenario.

        Args:
            scenario_result: ScenarioResult with tasks to display.
            show_header: If True, print the BENCHMARK RESULTS header first.
        """
        if show_header:
            self.print_results_header()

        self.console.print(f"[yellow]Scenario[/yellow]: {scenario_result.name}")

        # Check if any task has per-call metrics (for context columns)
        has_call_metrics = any(
            task.llm_call_metrics for task in scenario_result.tasks
        )

        # Create comparison table with ROUNDED box style
        table = Table(show_header=True, header_style="bold", box=box.ROUNDED)
        table.add_column("Task", min_width=16, no_wrap=True)
        table.add_column("tags", no_wrap=True)
        table.add_column("in", justify="right", no_wrap=True)
        table.add_column("out", justify="right", no_wrap=True)
        table.add_column("tools", justify="right", no_wrap=True)

        # Add context columns if per-call metrics exist
        if has_call_metrics:
            table.add_column("base", justify="right", no_wrap=True)
            table.add_column("growth", justify="right", no_wrap=True)

        table.add_column("time", justify="right", no_wrap=True)
        table.add_column("cost", justify="right", no_wrap=True)
        table.add_column("result", justify="right", no_wrap=True)

        for task_result in scenario_result.tasks:
            eval_display = self._format_eval_result(task_result)
            eval_style = self._style_eval_result(task_result)
            tags_str = ", ".join(task_result.tags) if task_result.tags else "-"
            cost_cents = task_result.cost_usd * 100

            # Apply style to evaluation result
            if eval_style:
                eval_display = f"[{eval_style}]{eval_display}[/{eval_style}]"

            row = [
                task_result.name,
                tags_str,
                str(task_result.input_tokens),
                str(task_result.output_tokens),
                str(task_result.tool_calls),
            ]

            # Add context metrics if available
            if has_call_metrics:
                base = task_result.base_context
                growth = task_result.context_growth_avg
                row.append(str(base) if base else "-")
                row.append(f"{growth:.0f}" if growth else "-")

            row.extend([
                f"{task_result.duration_seconds:.0f}s",
                f"{cost_cents:.2f}¢",
                eval_display,
            ])

            table.add_row(*row)

        self.console.print(table)

        # Show per-call breakdown in verbose mode
        if self.verbose and has_call_metrics:
            self.console.print("\n  [dim]Per-call breakdown:[/dim]")
            for task_result in scenario_result.tasks:
                if task_result.llm_call_metrics:
                    self.console.print(f"    [cyan]{task_result.name}[/cyan]:")
                    for m in task_result.llm_call_metrics:
                        self.console.print(
                            f"      call{m.call_number}: "
                            f"in={m.input_tokens}, out={m.output_tokens}, "
                            f"tools={m.tool_calls_made}, "
                            f"cumulative={m.cumulative_input}, "
                            f"latency={m.latency_ms}ms"
                        )

        # Calculate context efficiency comparison if multiple tasks with metrics
        tasks_with_metrics = [
            t for t in scenario_result.tasks if t.llm_call_metrics and t.input_tokens > 0
        ]
        if len(tasks_with_metrics) >= 2:
            # Sort by input tokens to find min and max
            sorted_tasks = sorted(tasks_with_metrics, key=lambda t: t.input_tokens)
            min_task = sorted_tasks[0]
            max_task = sorted_tasks[-1]

            if max_task.input_tokens > 0 and min_task.input_tokens < max_task.input_tokens:
                ratio = (min_task.input_tokens / max_task.input_tokens) * 100
                self.console.print(
                    f"\n  [dim]Context efficiency: "
                    f"{min_task.name} uses {ratio:.0f}% of {max_task.name} context[/dim]"
                )

        # Show totals with camelCase labels
        totals = scenario_result.calculate_totals()
        cost_cents = totals["total_cost_usd"] * 100

        # Build totals line
        totals_parts = [
            f"tokensIn={totals['total_input_tokens']}",
            f"tokensOut={totals['total_output_tokens']}",
            f"llmCalls={totals['total_llm_calls']}",
            f"toolCalls={totals['total_tool_calls']}",
            f"cost={cost_cents:.2f}¢",
        ]

        # Add evaluation summary
        if "pass_count" in totals or "fail_count" in totals:
            pass_count = totals.get("pass_count", 0)
            fail_count = totals.get("fail_count", 0)
            if fail_count == 0:
                totals_parts.append(f"[bold green]{pass_count} passed[/bold green]")
            else:
                totals_parts.append(
                    f"[bold green]{pass_count} passed[/bold green], "
                    f"[bold red]{fail_count} failed[/bold red]"
                )

        if "avg_score" in totals:
            avg = totals["avg_score"]
            if avg >= 80:
                style = "bold green"
            elif avg >= 50:
                style = "bold yellow"
            else:
                style = "bold red"
            totals_parts.append(f"[{style}]avgScore={avg}[/{style}]")

        self.console.print(f"\n  totals: {', '.join(totals_parts)}")

    def print_validation_errors(self) -> None:
        """Print summary of validation errors detected during the run."""
        if not self.validation_errors:
            return

        self.console.print()
        self.console.print(
            Rule("VALIDATION ERRORS", style="bold yellow", characters="─")
        )
        self.console.print()
        self.console.print(
            f"[yellow]{len(self.validation_errors)} validation error(s) detected "
            "(LLM retried after these):[/yellow]"
        )

        for error in self.validation_errors:
            self.console.print()
            self.console.print(f"  [cyan]Scenario[/cyan]: {error['scenario']}")
            self.console.print(f"  [cyan]Task[/cyan]: {error['task']}")
            self.console.print(f"  [cyan]requestLLM[/cyan]= {error['requestLLM']}")
            self.console.print(f"  [cyan]responseMCP[/cyan]= {error['responseMCP']}")
