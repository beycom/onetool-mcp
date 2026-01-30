"""Agentic loop runner for executing prompts with MCP servers."""

from __future__ import annotations

import asyncio
import fnmatch
import json
import time
from typing import TYPE_CHECKING, Any, Protocol

from loguru import logger
from openai import OpenAI

from bench.harness.client import (
    ServerConnectionCallback,
    call_tool,
    connect_to_servers,
    multi_server_tools_to_openai,
)
from bench.harness.evaluate import evaluate_task, resolve_evaluator
from bench.harness.metrics import (
    EvaluationResult,
    LLMCallMetrics,
    ScenarioResult,
    TaskResult,
    calculate_cost,
)
from bench.secrets import get_bench_secret
from ot.logging import LogSpan
from ot.utils import flatten_exception_group

# Delay between tasks to avoid rate limits on external APIs (OpenRouter, etc.)
TASK_DELAY_SECONDS = 3.0

# Delimiter for multi-prompt tasks
PROMPT_DELIMITER = "---PROMPT---"


def split_prompts(prompt: str) -> list[str]:
    """Split a prompt into multiple sequential prompts.

    Uses the `---PROMPT---` delimiter to split a single prompt field
    into multiple prompts for controlled benchmarking.

    Args:
        prompt: The prompt string (may contain delimiters).

    Returns:
        List of prompt strings. Single element if no delimiter found.
    """
    if not prompt:
        return [""]
    parts = prompt.split(PROMPT_DELIMITER)
    return [p.strip() for p in parts if p.strip()]

if TYPE_CHECKING:
    from bench.harness.config import HarnessConfig, TaskConfig


class ProgressCallback(Protocol):
    """Protocol for progress callbacks."""

    def __call__(
        self,
        event: str,
        *,
        scenario: str | None = None,
        task: str | None = None,
        result: TaskResult | None = None,
        server: str | None = None,
        server_status: str | None = None,
        tool_count: int | None = None,
        error: str | None = None,
        tool_name: str | None = None,
        tool_args: dict[str, Any] | None = None,
        tool_result: str | None = None,
        llm_request: list[dict[str, Any]] | None = None,
        llm_response: str | None = None,
    ) -> None:
        """Called when progress is made.

        Args:
            event: Event type (scenario_start, task_start, task_complete,
                   server_connecting, server_connected, server_failed,
                   tool_call, tool_response, llm_request, llm_response).
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
        ...


class AgenticRunner:
    """Runner that executes prompts with optional MCP server integration."""

    def __init__(
        self,
        config: HarnessConfig,
        dry_run: bool = False,
        verbose: bool = False,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        """Initialize the runner.

        Args:
            config: Harness configuration.
            dry_run: If True, validate config without making API calls.
            verbose: If True, log detailed MCP tool call info.
            on_progress: Optional callback for progress updates.
        """
        self.config = config
        self.dry_run = dry_run
        self.verbose = verbose
        self.on_progress = on_progress
        # Partial results accumulated during run (for interrupt handling)
        self.partial_results: list[ScenarioResult] = []
        self.client = OpenAI(
            api_key=get_bench_secret("OPENAI_API_KEY"),
            base_url=get_bench_secret("OPENAI_BASE_URL"),
        )

    def _emit(
        self,
        event: str,
        *,
        scenario: str | None = None,
        task: str | None = None,
        result: TaskResult | None = None,
        server: str | None = None,
        server_status: str | None = None,
        tool_count: int | None = None,
        error: str | None = None,
        tool_name: str | None = None,
        tool_args: dict[str, Any] | None = None,
        tool_result: str | None = None,
        llm_request: list[dict[str, Any]] | None = None,
        llm_response: str | None = None,
    ) -> None:
        """Emit a progress event if callback is set."""
        if self.on_progress:
            self.on_progress(
                event,
                scenario=scenario,
                task=task,
                result=result,
                server=server,
                server_status=server_status,
                tool_count=tool_count,
                error=error,
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=tool_result,
                llm_request=llm_request,
                llm_response=llm_response,
            )

    def _update_partial_results(
        self,
        completed_scenarios: list[ScenarioResult],
        current_scenario_name: str,
        current_model: str,
        current_tasks: list[TaskResult],
    ) -> None:
        """Update partial_results with completed scenarios plus current progress.

        Called after each task to enable interrupt handling with full visibility.
        """
        # Start with completed scenarios
        self.partial_results = completed_scenarios.copy()
        # Add current scenario's progress if any tasks completed
        if current_tasks:
            self.partial_results.append(
                ScenarioResult(
                    name=current_scenario_name,
                    model=current_model,
                    tasks=current_tasks.copy(),
                )
            )

    def _get_server_names(self, server: str | list[str] | None) -> list[str]:
        """Get list of server names from task config.

        Args:
            server: Server name, list of names, or None.

        Returns:
            List of server names (empty if None).
        """
        if server is None:
            return []
        if isinstance(server, list):
            return server
        return [server]

    async def run_task(
        self,
        task: TaskConfig,
        default_model: str,
        default_timeout: int,
    ) -> TaskResult:
        """Run a single task (direct or harness).

        Args:
            task: Task configuration.
            default_model: Default model from scenario/config.
            default_timeout: Default timeout from scenario/config.

        Returns:
            TaskResult with metrics and response.
        """
        if task.type == "direct":
            return await self._run_direct_task(task, default_timeout)
        return await self._run_harness_task(task, default_model, default_timeout)

    async def _run_direct_task(
        self,
        task: TaskConfig,
        default_timeout: int,
    ) -> TaskResult:
        """Run a direct MCP tool invocation task.

        Args:
            task: Task configuration (type: direct).
            default_timeout: Default timeout from scenario/config.

        Returns:
            TaskResult with tool result.
        """
        timeout = task.timeout or default_timeout
        start_time = time.time()
        response_text = ""
        error_msg: str | None = None

        if self.dry_run:
            logger.info(f"[dry-run] Would call tool: {task.tool}")
            return TaskResult(
                name=task.name,
                server=task.server,
                model="direct",
                prompt=f"Tool: {task.tool}",
                response="[dry-run] No API call made",
                input_tokens=0,
                output_tokens=0,
                llm_calls=0,
                tool_calls=0,
                tools_used=[],
                duration_seconds=0.0,
                cost_usd=0.0,
                tags=task.tags,
            )

        server_names = self._get_server_names(task.server)

        try:
            async with asyncio.timeout(timeout):
                async with connect_to_servers(
                    self.config.servers,
                    server_names,
                    timeout=timeout,
                ) as multi:
                    # Find the session for this tool
                    session = multi.get_session_for_tool(task.tool)  # type: ignore[arg-type]
                    if not session:
                        error_msg = f"Tool '{task.tool}' not found in any server"
                        logger.error(f"[{task.name}] {error_msg}")
                    else:
                        self._emit(
                            "tool_call",
                            task=task.name,
                            tool_name=task.tool,
                            tool_args=task.arguments,
                        )
                        response_text = await call_tool(
                            session,
                            task.tool,
                            task.arguments,
                            timeout=timeout,  # type: ignore[arg-type]
                        )
                        self._emit(
                            "tool_response",
                            task=task.name,
                            tool_name=task.tool,
                            tool_result=response_text,
                        )
        except TimeoutError:
            error_msg = f"Task timed out after {timeout}s"
            logger.error(f"[{task.name}] {error_msg}")
        except BaseExceptionGroup as eg:
            leaf_exceptions = flatten_exception_group(eg)
            error_msg = "; ".join(str(e) for e in leaf_exceptions)
            logger.error(f"Error running task {task.name}: {error_msg}")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error running task {task.name}: {e}")

        duration = time.time() - start_time

        return TaskResult(
            name=task.name,
            server=task.server,
            model="direct",
            prompt=f"Tool: {task.tool}",
            response=response_text,
            input_tokens=0,
            output_tokens=0,
            llm_calls=0,
            tool_calls=1 if not error_msg else 0,
            tools_used=[task.tool] if task.tool and not error_msg else [],
            tool_results=[response_text] if response_text else [],
            duration_seconds=duration,
            cost_usd=0.0,
            error=error_msg,
            tags=task.tags,
        )

    async def _run_harness_task(
        self,
        task: TaskConfig,
        default_model: str,
        default_timeout: int,
    ) -> TaskResult:
        """Run an agent benchmark task.

        Args:
            task: Task configuration (type: harness).
            default_model: Default model from scenario/config.
            default_timeout: Default timeout from scenario/config.

        Returns:
            TaskResult with metrics and response.
        """
        model = task.model or default_model
        timeout = task.timeout or default_timeout

        if self.dry_run:
            logger.info(f"[dry-run] Would run task: {task.name}")
            return TaskResult(
                name=task.name,
                server=task.server,
                model=model,
                prompt=task.prompt or "",
                response="[dry-run] No API call made",
                input_tokens=0,
                output_tokens=0,
                llm_calls=0,
                tool_calls=0,
                tools_used=[],
                duration_seconds=0.0,
                cost_usd=0.0,
                tags=task.tags,
            )

        start_time = time.time()
        input_tokens = 0
        output_tokens = 0
        llm_call_count = 0
        tool_call_count = 0
        tools_used: list[str] = []
        tool_results: list[str] = []
        response_text = ""
        error_msg: str | None = None
        # Per-call metrics tracking
        llm_call_metrics: list[LLMCallMetrics] = []
        cumulative_input = 0

        # Get list of servers to connect to
        server_names = self._get_server_names(task.server)

        # Create a callback to emit progress events for server connections
        class ConnectionProgress(ServerConnectionCallback):
            def __init__(inner_self) -> None:
                inner_self.runner = self
                inner_self.task_name = task.name

            def on_connecting(inner_self, name: str) -> None:
                inner_self.runner._emit(
                    "server_connecting",
                    task=inner_self.task_name,
                    server=name,
                )

            def on_connected(inner_self, name: str, tool_count: int) -> None:
                inner_self.runner._emit(
                    "server_connected",
                    task=inner_self.task_name,
                    server=name,
                    tool_count=tool_count,
                )

            def on_failed(inner_self, name: str, error: str) -> None:
                inner_self.runner._emit(
                    "server_failed",
                    task=inner_self.task_name,
                    server=name,
                    error=error,
                )

        try:
            # Timeout covers entire task: server connections + LLM calls + tool calls
            async with asyncio.timeout(timeout):
                async with connect_to_servers(
                    self.config.servers,
                    server_names,
                    timeout=timeout,
                    on_progress=ConnectionProgress() if self.on_progress else None,
                ) as multi:
                    # Log MCP connection summary
                    logger.info(
                        f"    mcpConnected={multi.healthy_count}, "
                        f"toolCount={len(multi.all_tools)}"
                    )
                    if multi.all_tools:
                        tool_names = [t.name for t in multi.all_tools]
                        logger.info(f"    tools={tool_names}")

                    # Build system message with server instructions
                    system_parts: list[str] = []
                    if self.config.defaults.system_prompt:
                        system_parts.append(self.config.defaults.system_prompt.strip())

                    # Include instructions from all connected MCP servers
                    for server_name, instructions in multi.all_instructions:
                        if len(multi.connections) > 1:
                            system_parts.append(
                                f"## {server_name} Instructions\n{instructions.strip()}"
                            )
                        else:
                            system_parts.append(instructions.strip())

                    # Include prompts from all connected MCP servers
                    if multi.all_prompts:
                        prompts_text = "## Available Prompts\n"
                        for server_name, prompt in multi.all_prompts:
                            prefix = (
                                f"[{server_name}] "
                                if len(multi.connections) > 1
                                else ""
                            )
                            desc = (
                                f" - {prompt.description}" if prompt.description else ""
                            )
                            prompts_text += f"- {prefix}{prompt.name}{desc}\n"
                        system_parts.append(prompts_text.strip())

                    # Include resources from all connected MCP servers
                    if multi.all_resources:
                        resources_text = "## Available Resources\n"
                        for server_name, resource in multi.all_resources:
                            prefix = (
                                f"[{server_name}] "
                                if len(multi.connections) > 1
                                else ""
                            )
                            desc = (
                                f" - {resource.description}"
                                if resource.description
                                else ""
                            )
                            resources_text += f"- {prefix}{resource.uri}{desc}\n"
                        system_parts.append(resources_text.strip())

                    if multi.healthy_count > 0:
                        system_parts.append(
                            f"You have access to {len(multi.all_tools)} tools from "
                            f"{multi.healthy_count} MCP server(s)."
                        )
                    if multi.failed_count > 0:
                        failed_names = [h.name for h in multi.health if not h.healthy]
                        system_parts.append(
                            f"Note: {multi.failed_count} server(s) failed to start: "
                            f"{', '.join(failed_names)}"
                        )

                    messages: list[dict[str, Any]] = []
                    if system_parts:
                        messages.append(
                            {"role": "system", "content": "\n".join(system_parts)}
                        )

                    # Get combined tools from all servers (with prefixed names if multiple)
                    tools = None
                    tool_mapping: dict[str, tuple[str, str]] = {}
                    if multi.all_tools:
                        tools, tool_mapping = multi_server_tools_to_openai(multi)

                    # Split prompts for multi-prompt tasks
                    prompts = split_prompts(task.prompt or "")

                    # Process each prompt sequentially (conversation accumulates)
                    for prompt_text in prompts:
                        messages.append({"role": "user", "content": prompt_text})

                        while True:
                            # Emit LLM request event before calling
                            self._emit(
                                "llm_request",
                                task=task.name,
                                llm_request=messages,
                            )

                            # Track per-call timing
                            call_start = time.time()

                            # Run sync LLM call in thread so asyncio.timeout can cancel it
                            with LogSpan(
                                span="bench.llm.request",
                                model=model,
                                call=llm_call_count + 1,
                            ) as llm_span:
                                response = await asyncio.to_thread(
                                    self.client.chat.completions.create,  # type: ignore[arg-type]
                                    model=model,
                                    messages=messages,
                                    tools=tools,
                                    timeout=timeout,
                                )
                                if response.usage:
                                    llm_span.add(
                                        inputTokens=response.usage.prompt_tokens,
                                        outputTokens=response.usage.completion_tokens,
                                    )

                            call_latency_ms = int((time.time() - call_start) * 1000)
                            llm_call_count += 1

                            # Track token usage
                            call_input_tokens = 0
                            call_output_tokens = 0
                            if response.usage:
                                call_input_tokens = response.usage.prompt_tokens
                                call_output_tokens = response.usage.completion_tokens
                                input_tokens += call_input_tokens
                                output_tokens += call_output_tokens
                                cumulative_input += call_input_tokens

                            assistant_msg = response.choices[0].message

                            # Count tool calls in this response
                            call_tool_count = (
                                len(assistant_msg.tool_calls)
                                if assistant_msg.tool_calls
                                else 0
                            )

                            # Create per-call metrics
                            llm_call_metrics.append(
                                LLMCallMetrics(
                                    call_number=llm_call_count,
                                    input_tokens=call_input_tokens,
                                    output_tokens=call_output_tokens,
                                    tool_calls_made=call_tool_count,
                                    cumulative_input=cumulative_input,
                                    latency_ms=call_latency_ms,
                                )
                            )

                            if assistant_msg.tool_calls and multi.all_tools:
                                # Add assistant message with tool calls
                                messages.append(
                                    {
                                        "role": "assistant",
                                        "content": assistant_msg.content,
                                        "tool_calls": [
                                            {
                                                "id": tc.id,
                                                "type": "function",
                                                "function": {
                                                    "name": tc.function.name,  # type: ignore[union-attr]
                                                    "arguments": tc.function.arguments,  # type: ignore[union-attr]
                                                },
                                            }
                                            for tc in assistant_msg.tool_calls
                                        ],
                                    }
                                )

                                # Execute each tool call
                                for tc in assistant_msg.tool_calls:
                                    tool_call_count += 1
                                    prefixed_name = tc.function.name  # type: ignore[union-attr]
                                    tool_args = json.loads(tc.function.arguments)  # type: ignore[union-attr]

                                    # Look up server and original tool name from mapping
                                    if prefixed_name in tool_mapping:
                                        server_name, original_tool_name = tool_mapping[
                                            prefixed_name
                                        ]
                                    else:
                                        # Fallback: tool name not prefixed (single server)
                                        server_name = ""
                                        original_tool_name = prefixed_name

                                    # Track unique tools used (use prefixed name for display)
                                    if prefixed_name not in tools_used:
                                        tools_used.append(prefixed_name)

                                    # Emit tool_call event for progress callback
                                    self._emit(
                                        "tool_call",
                                        task=task.name,
                                        tool_name=prefixed_name,
                                        tool_args=tool_args,
                                    )

                                    # Find the session for this tool
                                    if server_name and server_name in multi.connections:
                                        session = multi.connections[server_name].session
                                    else:
                                        # Fallback: search by original name
                                        session = multi.get_session_for_tool(
                                            original_tool_name
                                        )

                                    if not session:
                                        result = f"Error: Tool '{prefixed_name}' not found in any server"
                                        logger.error(f"[{task.name}] {result}")
                                    else:
                                        try:
                                            # Call with original (unprefixed) tool name
                                            result = await call_tool(
                                                session,
                                                original_tool_name,
                                                tool_args,
                                                timeout=timeout,
                                            )
                                        except TimeoutError:
                                            result = f"Error: Tool '{prefixed_name}' timed out after {timeout}s"
                                            logger.error(
                                                f"[{task.name}] Tool timeout | "
                                                f"tool={prefixed_name} | timeout={timeout}s"
                                            )
                                        except RuntimeError as e:
                                            # Tool returned an error - pass to LLM
                                            result = str(e)
                                            logger.warning(
                                                f"[{task.name}] Tool error | "
                                                f"tool={prefixed_name} | error={str(e)[:200]}"
                                            )
                                        except Exception as e:
                                            # Unexpected error - log and pass to LLM
                                            result = (
                                                f"Error: Tool '{prefixed_name}' failed: {e}"
                                            )
                                            logger.error(
                                                f"[{task.name}] Tool exception | "
                                                f"tool={prefixed_name} | type={type(e).__name__} | error={e}"
                                            )

                                    # Emit tool_response event for progress callback
                                    self._emit(
                                        "tool_response",
                                        task=task.name,
                                        tool_name=prefixed_name,
                                        tool_result=result,
                                    )

                                    # Capture tool result for evaluation
                                    tool_results.append(result)

                                    messages.append(
                                        {
                                            "role": "tool",
                                            "tool_call_id": tc.id,
                                            "content": result,
                                        }
                                    )

                            else:
                                # No tool calls, done with this prompt
                                response_text = assistant_msg.content or ""
                                self._emit(
                                    "llm_response",
                                    task=task.name,
                                    llm_response=response_text,
                                )
                                # Add assistant response to messages for next prompt
                                messages.append(
                                    {"role": "assistant", "content": response_text}
                                )
                                break

        except TimeoutError:
            error_msg = f"Task timed out after {timeout}s"
            logger.error(f"[{task.name}] {error_msg}")
        except BaseExceptionGroup as eg:
            # Extract underlying exceptions from nested TaskGroups
            leaf_exceptions = flatten_exception_group(eg)
            error_msg = "; ".join(str(e) for e in leaf_exceptions)
            logger.error(f"Error running task {task.name}: {error_msg}")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error running task {task.name}: {e}")

        duration = time.time() - start_time
        cost = calculate_cost(model, input_tokens, output_tokens)

        return TaskResult(
            name=task.name,
            server=task.server,
            model=model,
            prompt=task.prompt or "",
            response=response_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            llm_calls=llm_call_count,
            tool_calls=tool_call_count,
            tools_used=tools_used,
            tool_results=tool_results,
            duration_seconds=duration,
            cost_usd=cost,
            error=error_msg,
            tags=task.tags,
            llm_call_metrics=llm_call_metrics,
        )

    async def run_scenario(
        self,
        scenario_name: str | None = None,
        task_name: str | None = None,
        tags: list[str] | None = None,
    ) -> list[ScenarioResult]:
        """Run benchmark scenarios.

        Args:
            scenario_name: Filter scenarios by pattern with wildcard support (optional).
            task_name: Filter tasks by pattern with wildcard support (optional).
            tags: Filter tasks with any of these tags (optional).

        Returns:
            List of ScenarioResult objects.
        """
        results: list[ScenarioResult] = []
        default_model = self.config.defaults.model
        default_timeout = self.config.defaults.timeout

        for scenario in self.config.scenarios:
            if scenario_name and not fnmatch.fnmatch(scenario.name, scenario_name):
                continue

            self._emit("scenario_start", scenario=scenario.name)
            task_results: list[TaskResult] = []

            for task in scenario.tasks:
                if task_name and not fnmatch.fnmatch(task.name, task_name):
                    continue

                # Filter by tags on tasks (supports wildcards like "focus*")
                if tags:
                    task_matches_tags = any(
                        fnmatch.fnmatch(task_tag, pattern)
                        for pattern in tags
                        for task_tag in task.tags
                    )
                    if not task_matches_tags:
                        continue

                self._emit("task_start", scenario=scenario.name, task=task.name)
                # Pre-compute display values for error handling
                prompt_display = task.prompt or f"Tool: {task.tool}"
                model_display = (
                    "direct" if task.type == "direct" else (task.model or default_model)
                )
                try:
                    result = await self.run_task(task, default_model, default_timeout)
                except asyncio.CancelledError:
                    # Task was cancelled (e.g., timeout) - create error result
                    # Note: CancelledError is BaseException, must come before Exception
                    logger.error(f"Task {task.name} was cancelled (timeout)")
                    result = TaskResult(
                        name=task.name,
                        server=task.server,
                        model=model_display,
                        prompt=prompt_display,
                        response="",
                        input_tokens=0,
                        output_tokens=0,
                        llm_calls=0,
                        tool_calls=0,
                        tools_used=[],
                        duration_seconds=0.0,
                        cost_usd=0.0,
                        error="Task timed out",
                        tags=task.tags,
                    )
                except BaseExceptionGroup as eg:
                    # Task crashed with exception group - create error result
                    leaf_exceptions = flatten_exception_group(eg)
                    error_msg = "; ".join(str(e) for e in leaf_exceptions)
                    logger.error(f"Task {task.name} crashed: {error_msg}")
                    result = TaskResult(
                        name=task.name,
                        server=task.server,
                        model=model_display,
                        prompt=prompt_display,
                        response="",
                        input_tokens=0,
                        output_tokens=0,
                        llm_calls=0,
                        tool_calls=0,
                        tools_used=[],
                        duration_seconds=0.0,
                        cost_usd=0.0,
                        error=f"Task crashed: {error_msg}",
                        tags=task.tags,
                    )
                except Exception as e:
                    # Task crashed with regular exception - create error result
                    error_msg = str(e)
                    logger.error(f"Task {task.name} crashed: {error_msg}")
                    result = TaskResult(
                        name=task.name,
                        server=task.server,
                        model=model_display,
                        prompt=prompt_display,
                        response="",
                        input_tokens=0,
                        output_tokens=0,
                        llm_calls=0,
                        tool_calls=0,
                        tools_used=[],
                        duration_seconds=0.0,
                        cost_usd=0.0,
                        error=f"Task crashed: {error_msg}",
                        tags=task.tags,
                    )
                task_results.append(result)
                # Update partial results with current scenario's progress
                self._update_partial_results(
                    results, scenario.name, default_model, task_results
                )
                # Emit task_complete BEFORE evaluation so LogSpan duration is accurate
                self._emit(
                    "task_complete",
                    scenario=scenario.name,
                    task=task.name,
                    result=result,
                )

                # Evaluate task after task_complete (so span duration excludes evaluation)
                if not self.dry_run:
                    with LogSpan(span="bench.evaluate", task=task.name) as eval_span:
                        if result.error:
                            # Check if this test expects an error (e.g., timeout tests)
                            # Must resolve evaluator first since task.evaluate can be a string
                            eval_config = resolve_evaluator(task, self.config)
                            if eval_config and eval_config.expect_error:
                                # Use error message as response for evaluation
                                result.response = result.error
                                evaluation = evaluate_task(result, task, self.config)
                                if evaluation:
                                    result.evaluation = evaluation
                                    eval_span.add(
                                        passed=evaluation.passed,
                                        evalType=evaluation.eval_type,
                                    )
                            else:
                                result.evaluation = EvaluationResult(
                                    score=0,
                                    reason=f"Skipped due to error: {result.error}",
                                    eval_type="pass_fail",
                                    passed=False,
                                )
                                eval_span.add(skipped=True, error=result.error)
                        else:
                            evaluation = evaluate_task(result, task, self.config)
                            if evaluation:
                                result.evaluation = evaluation
                                eval_span.add(
                                    passed=evaluation.passed,
                                    evalType=evaluation.eval_type,
                                )
                    # Emit separate event for evaluation display
                    self._emit(
                        "task_evaluated",
                        scenario=scenario.name,
                        task=task.name,
                        result=result,
                    )

                await asyncio.sleep(TASK_DELAY_SECONDS)

            if task_results:
                scenario_result = ScenarioResult(
                    name=scenario.name,
                    model=default_model,
                    tasks=task_results,
                )
                results.append(scenario_result)

        return results
