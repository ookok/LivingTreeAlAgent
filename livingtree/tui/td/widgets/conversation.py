from __future__ import annotations

from asyncio import Future
import asyncio

from contextlib import suppress
from functools import partial
from itertools import filterfalse
from operator import attrgetter
from typing import TYPE_CHECKING, Literal
from pathlib import Path
from time import monotonic
import time

from typing import Callable, Any

from rich.segment import Segment

from textual import log, on, work
from textual.app import ComposeResult
from textual import containers
from textual import getters
from textual import events
from textual.actions import SkipAction
from textual.binding import Binding
from textual.content import Content
from textual.geometry import clamp
from textual.css.query import NoMatches
from textual.widget import Widget
from textual.widgets import Static
from textual.widgets.markdown import MarkdownBlock, MarkdownFence
from textual.geometry import Offset, Spacing, Region
from textual.reactive import var
from textual.layouts.grid import GridLayout
from textual.layout import WidgetPlacement
from textual.strip import Strip


from livingtree.tui.td import jsonrpc, messages
from livingtree.tui.td import paths
from livingtree.tui.td.agent_schema import Agent as AgentData
from livingtree.tui.td.acp import messages as acp_messages
from livingtree.tui.td.app import ToadApp
from livingtree.tui.td.acp import protocol as acp_protocol
from livingtree.tui.td.acp.agent import Mode
from livingtree.tui.td.answer import Answer
from livingtree.tui.td.agent import AgentBase, AgentReady, AgentFail
from livingtree.tui.td.format_path import format_path
from livingtree.tui.td.directory_watcher import DirectoryWatcher, DirectoryChanged
from livingtree.tui.td.history import History
from livingtree.tui.td.widgets.flash import Flash
from livingtree.tui.td.widgets.menu import Menu
from livingtree.tui.td.widgets.note import Note
from livingtree.tui.td.widgets.prompt import Prompt
from livingtree.tui.td.widgets.session_tabs import SessionsTabs
from livingtree.tui.td.widgets.terminal import Terminal
from livingtree.tui.td.widgets.throbber import Throbber
from livingtree.tui.td.widgets.user_input import UserInput
from livingtree.tui.td.shell import Shell, CurrentWorkingDirectoryChanged
from livingtree.tui.td.slash_command import SlashCommand
from livingtree.tui.td.protocol import BlockProtocol, MenuProtocol, ExpandProtocol
from livingtree.tui.td.menus import MenuItem
from livingtree.tui.td.widgets.shell_terminal import ShellTerminal

if TYPE_CHECKING:
    from livingtree.tui.td.session_tracker import SessionState
    from livingtree.tui.td.widgets.terminal import Terminal
    from livingtree.tui.td.widgets.agent_response import AgentResponse
    from livingtree.tui.td.widgets.agent_thought import AgentThought
    from livingtree.tui.td.widgets.terminal_tool import TerminalTool


AGENT_FAIL_HELP = {
    "fail": """\
## Agent failed to run

**The agent failed to start.**

Check that the agent is installed and up-to-date.

Note that some agents require an ACP adapter to be installed to work with Toad.

- Exit the app, and run `toad` again
- Select the agent and hit ENTER
- Click the dropdown, select "Install"
- Click the GO button
- Repeat the process to install an ACP adapter (if required)

Some agents may require you to restart your shell (open a new terminal) after installing.

If that fails, ask for help in [Discussions](https://github.com/ookok/LivingTreeAlAgent/discussions)!
""",
    "no_resume": """\
## Agent does not support resume

The agent or ACP adapter does not support resuming sessions.

Try updating to see if support has been added.

- Exit the app, and run `toad` again
- Select the agent and hit ENTER
- Click the dropdown, select "Update" or "Install" again
- Repeat the process to update the ACP adapter (if required)

If that fails, ask for help in [Discussions](https://github.com/ookok/LivingTreeAlAgent/discussions)!
""",
}

HELP_URL = "https://github.com/ookok/LivingTreeAlAgent/discussions"

INTERNAL_EROR = f"""\
## Internal error

The agent reported an internal error:

```
$ERROR
```

This is likely an issue with the agent, and not Toad.

- Try the prompt again
- Report the issue to the Agent developer

Ask on {HELP_URL} if you need assistance.

"""

STOP_REASON_MAX_TOKENS = f"""\
## Maximum tokens reached

$AGENT reported that your account is out of tokens.

- You may need to purchase additional tokens, or fund your account.
- If your account has tokens, try running any login or auth process again.

If that fails, ask on {HELP_URL}
"""

STOP_REASON_MAX_TURN_REQUESTS = f"""\
## Maximum model requests reached

$AGENT has exceeded the maximum number of model requests in a single turn.

Need help? Ask on {HELP_URL}
"""

STOP_REASON_REFUSAL = f"""\
## Agent refusal
 
$AGENT has refused to continue. 

Need help? Ask on {HELP_URL}
"""


class Loading(Static):
    """Tiny widget to show loading indicator."""

    DEFAULT_CLASSES = "block"
    DEFAULT_CSS = """
    Loading {
        height: auto;        
    }
    """


class Cursor(Static):
    """The block 'cursor' -- A vertical line to the left of a block in the conversation that
    is used to navigate the discussion history.
    """

    follow_widget: var[Widget | None] = var(None)
    blink = var(True, toggle_class="-blink")

    def on_mount(self) -> None:
        self.visible = False
        self.blink_timer = self.set_interval(0.5, self._update_blink, pause=True)

    def _update_blink(self) -> None:
        if self.query_ancestor(Window).has_focus and self.screen.is_active:
            self.blink = not self.blink
        else:
            self.blink = False

    def watch_follow_widget(self, widget: Widget | None) -> None:
        self.visible = widget is not None

    def update_follow(self) -> None:
        if self.follow_widget and self.follow_widget.is_attached:
            self.styles.height = max(1, self.follow_widget.outer_size.height)
            follow_y = (
                self.follow_widget.virtual_region.y
                + self.follow_widget.parent.virtual_region.y
            )
            self.offset = Offset(0, follow_y)
        else:
            self.styles.height = None

    def follow(self, widget: Widget | None) -> None:
        self.follow_widget = widget
        self.blink = False
        if widget is None:
            self.visible = False
            self.blink_timer.reset()
            self.blink_timer.pause()
            self.styles.height = None
        else:
            self.visible = True
            self.blink_timer.reset()
            self.blink_timer.resume()
            self.update_follow()


class Contents(containers.VerticalGroup, can_focus=False):
    BLANK = True

    def process_layout(
        self, placements: list[WidgetPlacement]
    ) -> list[WidgetPlacement]:
        if placements:
            last_placement = placements[-1]
            top, right, _bottom, left = last_placement.margin
            placements[-1] = last_placement._replace(
                margin=Spacing(top, right, 0, left)
            )
        return placements


class ContentsGrid(containers.Grid):
    BLANK = True

    def pre_layout(self, layout) -> None:
        assert isinstance(layout, GridLayout)
        layout.stretch_height = True


class CursorContainer(containers.Vertical):
    def render_lines(self, crop: Region) -> list[Strip]:
        rich_style = self.visual_style.rich_style
        strips = [Strip([Segment("▌", rich_style)], cell_length=1)] * crop.height
        if crop.y == 0 and strips:
            strips[0] = Strip([Segment(" ", rich_style)], cell_length=1)

        return strips


class Window(containers.VerticalScroll):
    HELP = """\
## Conversation

This is a view of your conversation with the agent.

- **cursor keys** Scroll
- **alt+up / alt+down** Navigate content
- **start typing** Focus the prompt
"""
    BINDING_GROUP_TITLE = "View"
    BINDINGS = [Binding("end", "screen.focus_prompt", "Prompt")]

    def update_node_styles(self, animate: bool = True) -> None:
        pass


class Conversation(containers.Vertical):
    """Holds the agent conversation (input, output, and various controls / information)."""

    BLANK = True
    BINDING_GROUP_TITLE = "Conversation"
    CURSOR_BINDING_GROUP = Binding.Group(description="Cursor")
    BINDINGS = [
        Binding(
            "alt+up",
            "cursor_up",
            "Block cursor up",
            priority=True,
            group=CURSOR_BINDING_GROUP,
        ),
        Binding(
            "alt+down",
            "cursor_down",
            "Block cursor down",
            group=CURSOR_BINDING_GROUP,
        ),
        Binding(
            "enter",
            "select_block",
            "Select",
            tooltip="Select this block",
        ),
        Binding(
            "space",
            "expand_block",
            "Expand",
            key_display="␣",
            tooltip="Expand cursor block",
        ),
        Binding(
            "space",
            "collapse_block",
            "Collapse",
            key_display="␣",
            tooltip="Collapse cursor block",
        ),
        Binding(
            "escape",
            "cancel",
            "Cancel",
            tooltip="Cancel agent's turn",
        ),
        Binding(
            "ctrl+f",
            "focus_terminal",
            "Focus",
            tooltip="Focus the active terminal",
            priority=True,
        ),
        Binding(
            "ctrl+o",
            "mode_switcher",
            "Modes",
            tooltip="Open the mode switcher",
        ),
        Binding(
            "ctrl+c",
            "interrupt",
            "Interrupt",
            tooltip="Interrupt running command",
        ),
    ]

    busy_count = var(0)
    cursor_offset = var(-1, init=False)
    project_path = var("")
    working_directory: var[str] = var("")
    _blocks: var[list[MarkdownBlock] | None] = var(None)

    throbber: getters.query_one[Throbber] = getters.query_one("#throbber")
    contents = getters.query_one(Contents)
    window = getters.query_one(Window)
    cursor = getters.query_one(Cursor)
    prompt = getters.query_one(Prompt)
    app = getters.app(ToadApp)

    _shell: var[Shell | None] = var(None)
    shell_history_index: var[int] = var(0, init=False)
    prompt_history_index: var[int] = var(0, init=False)

    agent: var[AgentBase | None] = var(None, bindings=True)
    agent_info: var[Content] = var(Content())
    agent_ready: var[bool] = var(False)
    modes: var[dict[str, Mode]] = var({}, bindings=True)
    current_mode: var[Mode | None] = var(None)
    turn: var[Literal["agent", "client"] | None] = var(None, bindings=True)
    status: var[str] = var("")
    column: var[bool] = var(False, toggle_class="-column")

    title = var("")

    def __init__(
        self,
        project_path: Path,
        agent: AgentData | None = None,
        agent_session_id: str | None = None,
        session_pk: int | None = None,
        initial_prompt: str | None = None,
        hub=None,
    ) -> None:
        super().__init__()

        project_path = project_path.resolve().absolute()

        self.set_reactive(Conversation.project_path, project_path)
        self.set_reactive(Conversation.working_directory, str(project_path))
        self.agent_slash_commands: list[SlashCommand] = []
        self.terminals: dict[str, TerminalTool] = {}
        self._loading: Loading | None = None
        self._agent_response: AgentResponse | None = None
        self._agent_thought: AgentThought | None = None
        self._last_escape_time: float = monotonic()
        self._agent_data = agent
        self._agent_session_id = agent_session_id
        self._session_pk = session_pk
        self._agent_fail = False
        self._mouse_down_offset: Offset | None = None

        self._hub = hub

        self._focusable_terminals: list[Terminal] = []

        self.project_data_path = paths.get_project_data(project_path)
        self.shell_history = History(self.project_data_path / "shell_history.jsonl")
        self.prompt_history = History(self.project_data_path / "prompt_history.jsonl")

        self.session_start_time: float | None = None
        self._terminal_count = 0
        self._require_check_prune = False

        self._turn_count = 0
        self._shell_count = 0

        self._directory_changed = False
        self._directory_watcher: DirectoryWatcher | None = None

        self._initial_prompt = initial_prompt

        self._post_lock = asyncio.Lock()

    def update_title(self) -> None:
        """Update the screen title."""

        if agent_title := self.agent_title:
            project_path = format_path(self.project_path)
            self.screen.title = f"{agent_title} {project_path}"
        else:
            self.screen.title = ""

    @property
    def agent_title(self) -> str | None:
        if self._agent_data is not None:
            return self._agent_data["name"]
        return None

    @property
    def is_watching_directory(self) -> bool:
        """Is the directory watcher enabled and watching?"""
        if self._directory_watcher is None:
            return False
        return self._directory_watcher.enabled

    def validate_shell_history_index(self, index: int) -> int:
        return clamp(index, -self.shell_history.size, 0)

    def validate_prompt_history_index(self, index: int) -> int:
        return clamp(index, -self.prompt_history.size, 0)

    def shell_complete(self, prefix: str) -> list[str]:
        completes = self.shell_history.complete(prefix)
        return completes

    def insert_path_into_prompt(self, path: Path) -> None:
        try:
            insert_path_text = str(path.relative_to(self.project_path))
        except Exception:
            self.app.bell()
            return

        insert_text = (
            f'@"{insert_path_text}"'
            if " " in insert_path_text
            else f"@{insert_path_text}"
        )
        self.prompt.prompt_text_area.insert(insert_text)
        self.prompt.prompt_text_area.insert(" ")

    def watch_project_path(self, path: Path) -> None:
        self.post_message(messages.SessionUpdate(path=str(path)))

    async def watch_shell_history_index(self, previous_index: int, index: int) -> None:
        if previous_index == 0:
            self.shell_history.current = self.prompt.text
        try:
            history_entry = await self.shell_history.get_entry(index)
        except IndexError:
            pass
        else:
            self.prompt.text = history_entry["input"]
            self.prompt.shell_mode = True

    async def watch_prompt_history_index(self, previous_index: int, index: int) -> None:
        if previous_index == 0:
            self.prompt_history.current = self.prompt.text
        try:
            history_entry = await self.prompt_history.get_entry(index)
        except IndexError:
            pass
        else:
            self.prompt.text = history_entry["input"]

    def watch_turn(self, turn: str) -> None:
        if turn == "client":
            self.post_message(messages.SessionUpdate(state="idle"))
        elif turn == "agent":
            self.post_message(messages.SessionUpdate(state="busy"))

    @on(events.Key)
    async def on_key(self, event: events.Key):
        if (
            event.character is not None
            and event.is_printable
            and (event.character.isalnum() or event.character in "$/!")
            and self.window.has_focus
        ):
            self.prompt.focus()
            self.prompt.prompt_text_area.post_message(event)

    def compose(self) -> ComposeResult:
        yield Throbber(id="throbber")
        yield SessionsTabs()
        with Window():
            with ContentsGrid():
                with CursorContainer(id="cursor-container"):
                    yield Cursor()
                yield Contents(id="contents")
        yield Flash()
        yield Prompt(complete_callback=self.shell_complete).data_bind(
            project_path=Conversation.project_path,
            working_directory=Conversation.working_directory,
            agent_info=Conversation.agent_info,
            agent_ready=Conversation.agent_ready,
            current_mode=Conversation.current_mode,
            modes=Conversation.modes,
            status=Conversation.status,
        )

    @property
    def _terminal(self) -> Terminal | None:
        """Return the last focusable terminal, if there is one.

        Returns:
            A focusable (non finalized) terminal.
        """
        # Terminals should be removed in response to the Terminal.FInalized message
        # This is a bit of a sanity check
        self._focusable_terminals[:] = list(
            filterfalse(attrgetter("is_finalized"), self._focusable_terminals)
        )

        for terminal in reversed(self._focusable_terminals):
            if terminal.display:
                return terminal
        return None

    def add_focusable_terminal(self, terminal: Terminal) -> None:
        """Add a focusable terminal.

        Args:
            terminal: Terminal instance.
        """
        if not terminal.is_finalized:
            self._focusable_terminals.append(terminal)

    @on(ShellTerminal.Interrupt)
    async def on_shell_terminal_terminate(self, event: ShellTerminal.Terminate) -> None:
        if not event.teminal.is_finalized:
            await self.shell.interrupt()
            self.cursor_offset = -1
            self.flash("Command interrupted", style="success")

    @on(DirectoryChanged)
    def on_directory_changed(self, event: DirectoryChanged) -> None:
        event.stop()
        if self.turn is None or self.turn == "client":
            self.post_message(messages.ProjectDirectoryUpdated())
        else:
            self._directory_changed = True

    @on(Terminal.Finalized)
    def on_terminal_finalized(self, event: Terminal.Finalized) -> None:
        """Terminal was finalized, so we can remove it from the list."""
        try:
            self._focusable_terminals.remove(event.terminal)
        except ValueError:
            pass

        if self._directory_changed or not self.is_watching_directory:
            self.prompt.project_directory_updated()
            self._directory_changed = False
            self.post_message(messages.ProjectDirectoryUpdated())

    @on(Terminal.LongRunning)
    def on_terminal_long_running(self, event: Terminal.LongRunning) -> None:
        if (
            not event.terminal.is_finalized
            and not event.terminal.has_focus
            and not event.terminal.state.buffer.is_blank
        ):
            self.flash("Press [b]ctrl+f[/b] to focus command", style="default")

    @on(Terminal.AlternateScreenChanged)
    def on_terminal_alternate_screen_(
        self, event: Terminal.AlternateScreenChanged
    ) -> None:
        """A terminal enabled or disabled alternate screen."""
        if event.enabled:
            event.terminal.focus()
        else:
            self.focus_prompt()

    @on(events.DescendantFocus, "Terminal")
    def on_terminal_focus(self, event: events.DescendantFocus) -> None:
        self.flash("Press [b]escape[/b] [i]twice[/] to exit terminal", style="success")

    @on(events.DescendantBlur, "Terminal")
    def on_terminal_blur(self, event: events.DescendantFocus) -> None:
        self.focus_prompt()

    @on(messages.Flash)
    def on_flash(self, event: messages.Flash) -> None:
        event.stop()
        self.flash(event.content, duration=event.duration, style=event.style)

    def flash(
        self,
        content: str | Content,
        *,
        duration: float | None = None,
        style: Literal["default", "warning", "error", "success"] = "default",
    ) -> None:
        """Flash a single-line message to the user.

        Args:
            content: Content to flash.
            style: A semantic style.
            duration: Duration in seconds of the flash, or `None` to use default in settings.
        """
        self.query_one(Flash).flash(content, duration=duration, style=style)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "focus_terminal":
            return None if self._terminal is None else True
        if action == "mode_switcher":
            return bool(self.modes)
        if action == "cancel":
            return True if (self.agent and self.turn == "agent") else None
        if action in {"expand_block", "collapse_block"}:
            if (cursor_block := self.cursor_block) is None:
                return False
            elif isinstance(cursor_block, ExpandProtocol):
                if action == "expand_block":
                    return False if cursor_block.is_block_expanded() else True
                else:
                    return True if cursor_block.is_block_expanded() else False
            return None if action == "expand_block" else False

        return True

    async def action_focus_terminal(self) -> None:
        if self._terminal is not None:
            self._terminal.focus()
        else:
            self.flash("Nothing to focus...", style="error")

    async def action_expand_block(self) -> None:
        if (cursor_block := self.cursor_block) is not None:
            if isinstance(cursor_block, ExpandProtocol):
                cursor_block.expand_block()
                self.refresh_bindings()
                self.call_after_refresh(self.cursor.follow, cursor_block)

    async def action_collapse_block(self) -> None:
        if (cursor_block := self.cursor_block) is not None:
            if isinstance(cursor_block, ExpandProtocol):
                cursor_block.collapse_block()
                self.refresh_bindings()
                self.call_after_refresh(self.cursor.follow, cursor_block)

    async def post_agent_response(self, fragment: str = "") -> AgentResponse | None:
        """Get or create an agent response widget."""
        from livingtree.tui.td.widgets.agent_response import AgentResponse

        async with self._post_lock:
            if self._agent_response is None:
                self._agent_response = agent_response = AgentResponse(fragment)
                await self.post(agent_response, new_block=False)
            else:
                await self._agent_response.append_fragment(fragment)
            return self._agent_response

    async def post_agent_thought(self, thought_fragment: str) -> AgentThought | None:
        """Get or create an agent thought widget."""
        from livingtree.tui.td.widgets.agent_thought import AgentThought

        async with self._post_lock:
            if self._agent_thought is None:
                if thought_fragment.strip():
                    self._agent_thought = AgentThought(thought_fragment)
                    await self.post(self._agent_thought, new_block=False)
            else:
                await self._agent_thought.append_fragment(thought_fragment)
            return self._agent_thought

    @property
    def cursor_block(self) -> Widget | None:
        """The block next to the cursor, or `None` if no block cursor."""
        if self.cursor_offset == -1 or not self.contents.displayed_children:
            return None
        try:
            block_widget = self.contents.displayed_children[self.cursor_offset]
        except IndexError:
            return None
        return block_widget

    @property
    def cursor_block_child(self) -> Widget | None:
        if (cursor_block := self.cursor_block) is not None:
            if isinstance(cursor_block, BlockProtocol):
                return cursor_block.get_cursor_block()
        return cursor_block

    def get_cursor_block[BlockType](
        self, block_type: type[BlockType] = Widget
    ) -> BlockType | None:
        """Get the cursor block if it matches a type.

        Args:
            block_type: The expected type.

        Returns:
            The widget next to the cursor, or `None` if the types don't match.
        """
        cursor_block = self.cursor_block_child
        if isinstance(cursor_block, block_type):
            return cursor_block
        return None

    @on(AgentReady)
    async def on_agent_ready(self) -> None:
        self.session_start_time = monotonic()
        if self.agent is not None:
            content = Content.assemble(self.agent.get_info(), " connected")
            self.flash(content, style="success")
            if self._agent_data is not None:
                self.app.capture_event(
                    "agent-session-begin",
                    agent=self._agent_data["identity"],
                )

        self.agent_ready = True

    async def on_unmount(self) -> None:
        if self._directory_watcher is not None:
            self._directory_watcher.stop()
        if self.agent is not None:
            await self.agent.stop()

        if self._agent_data is not None and self.session_start_time is not None:
            session_time = monotonic() - self.session_start_time
            await self.app.capture_event(
                "agent-session-end",
                agent=self._agent_data["identity"],
                duration=session_time,
                agent_session_fail=self._agent_fail,
                shell_count=self._shell_count,
                turn_count=self._turn_count,
            ).wait()

    @on(AgentFail)
    async def on_agent_fail(self, message: AgentFail) -> None:
        self.agent_ready = True
        self._agent_fail = True
        self.notify(message.message, title="Agent failure", severity="error", timeout=5)

        if self._agent_data is not None:
            self.app.capture_event(
                "agent-session-error",
                agent=self._agent_data["identity"],
                message=message.message,
                details=message.details,
            )

        if message.message:
            error = Content.assemble(
                Content.from_markup(message.message).stylize("$text-error"),
                " — ",
                Content.from_markup(message.details.strip()).stylize("dim"),
            )
        else:
            error = Content.from_markup(message.details.strip()).stylize("$text-error")
        await self.post(Note(error, classes="-error"))

        from livingtree.tui.td.widgets.markdown_note import MarkdownNote

        if message.help in AGENT_FAIL_HELP:
            help = AGENT_FAIL_HELP[message.help]
        else:
            help = AGENT_FAIL_HELP["fail"]

        await self.post(MarkdownNote(help))

    @on(messages.WorkStarted)
    def on_work_started(self) -> None:
        self.busy_count += 1

    @on(messages.WorkFinished)
    def on_work_finished(self) -> None:
        self.busy_count -= 1

    @work
    @on(messages.ChangeMode)
    async def on_change_mode(self, event: messages.ChangeMode) -> None:
        await self.set_mode(event.mode_id)

    @on(acp_messages.ModeUpdate)
    def on_mode_update(self, event: acp_messages.ModeUpdate) -> None:
        if (modes := self.modes) is not None:
            if (mode := modes.get(event.current_mode)) is not None:
                self.current_mode = mode

    @on(messages.UserInputSubmitted)
    async def on_user_input_submitted(self, event: messages.UserInputSubmitted) -> None:
        if not event.body.strip():
            return
        if event.shell:
            if await self.shell.is_busy():
                if self.shell.terminal is not None:
                    self.shell.terminal.focus(scroll_visible=False)
                await self.shell.send_input(event.body, paste=True)
            else:
                await self.shell_history.append(event.body)
                self.shell_history_index = 0
                await self.post_shell(event.body)
            self.window.scroll_end(animate=False)
        elif text := event.body.strip():
            await self.prompt_history.append(event.body)
            self.prompt_history_index = 0
            if text.startswith("/") and await self.slash_command(text):
                # Toad has processed the slash command.
                return
            await self.post(UserInput(text))
            self.window.scroll_end(animate=False)
            self._loading = await self.post(Loading("Please wait..."), loading=True)
            await asyncio.sleep(0)
            self.send_prompt_to_agent(text)

    @work
    async def send_prompt_to_agent(self, prompt: str) -> None:
        if self.agent is not None:
            stop_reason: str | None = None
            self.busy_count += 1
            try:
                self.turn = "agent"
                stop_reason = await self.agent.send_prompt(prompt)
            except jsonrpc.APIError as error:
                from livingtree.tui.td.widgets.markdown_note import MarkdownNote

                self.turn = "client"

                message = error.message or "no details were provided"

                await self.post(
                    MarkdownNote(
                        INTERNAL_EROR.replace("$ERROR", message),
                        classes="-stop-reason",
                    )
                )
            finally:
                self.busy_count -= 1
            self.call_later(self.agent_turn_over, stop_reason)

    async def agent_turn_over(self, stop_reason: str | None) -> None:
        """Called when the agent's turn is over.

        Args:
            stop_reason: The stop reason returned from the Agent, or `None`.
        """
        self.turn = "client"
        if self._agent_thought is not None and self._agent_thought.loading:
            await self._agent_thought.remove()
        if self._loading is not None:
            await self._loading.remove()
        self._agent_response = None
        self._agent_thought = None

        if self._directory_changed or not self.is_watching_directory:
            self._directory_changed = False
            self.post_message(messages.ProjectDirectoryUpdated())
            self.prompt.project_directory_updated()

        self._turn_count += 1

        self.post_message(messages.SessionUpdate(state="idle"))

        if stop_reason != "end_turn":
            from livingtree.tui.td.widgets.markdown_note import MarkdownNote

            agent = (self.agent_title or "agent").title()

            if stop_reason == "max_tokens":
                await self.post(
                    MarkdownNote(
                        STOP_REASON_MAX_TOKENS.replace("$AGENT", agent),
                        classes="-stop-reason",
                    )
                )
            elif stop_reason == "max_turn_requests":
                await self.post(
                    MarkdownNote(
                        STOP_REASON_MAX_TURN_REQUESTS.replace("$AGENT", agent),
                        classes="-stop-reason",
                    )
                )
            elif stop_reason == "refusal":
                await self.post(
                    MarkdownNote(
                        STOP_REASON_REFUSAL.replace("$AGENT", agent),
                        classes="-stop-reason",
                    )
                )

        if self.app.settings.get("notifications.turn_over", bool):
            self.app.system_notify(
                f"{self.agent_title} has finished working",
                title="Waiting for input",
                sound="turn-over",
            )

    @on(Menu.OptionSelected)
    async def on_menu_option_selected(self, event: Menu.OptionSelected) -> None:
        event.stop()
        event.menu.display = False
        if event.action is not None:
            await self.run_action(event.action, {"block": event.owner})
        if (cursor_block := self.get_cursor_block()) is not None:
            self.call_after_refresh(self.cursor.follow, cursor_block)
        self.call_after_refresh(event.menu.remove)

    @on(Menu.Dismissed)
    async def on_menu_dismissed(self, event: Menu.Dismissed) -> None:
        event.stop()
        if event.menu.has_focus:
            self.window.focus(scroll_visible=False)
        await event.menu.remove()

    @on(CurrentWorkingDirectoryChanged)
    def on_current_working_directory_changed(
        self, event: CurrentWorkingDirectoryChanged
    ) -> None:
        self.working_directory = str(Path(event.path).resolve().absolute())

    async def watch_busy_count(self, busy: int) -> None:
        if (throbber := self.query_one_optional("#throbber")) is not None:
            throbber.set_class(busy > 0, "-busy")

    @on(acp_messages.UpdateStatusLine)
    async def on_update_status_line(self, message: acp_messages.UpdateStatusLine):
        self.status = message.status_line

    @on(acp_messages.Update)
    async def on_acp_agent_message(self, message: acp_messages.Update):
        message.stop()
        self._agent_thought = None
        await self.post_agent_response(message.text)

    @on(acp_messages.UserMessage)
    async def on_acp_user_message(self, message: acp_messages.UserMessage):
        self._agent_thought = None
        self._agent_response = None
        message.stop()
        await self.post(UserInput(message.text))

    @on(acp_messages.Thinking)
    async def on_acp_agent_thinking(self, message: acp_messages.Thinking):
        message.stop()
        await self.post_agent_thought(message.text)

    @on(acp_messages.RequestPermission)
    async def on_acp_request_permission(self, message: acp_messages.RequestPermission):
        message.stop()
        options = [
            Answer(option["name"], option["optionId"], option["kind"])
            for option in message.options
        ]
        self.request_permissions(
            message.result_future,
            options,
            message.tool_call,
        )
        self._agent_response = None
        self._agent_thought = None

    @on(acp_messages.Plan)
    async def on_acp_plan(self, message: acp_messages.Plan):
        from livingtree.tui.td.widgets.plan import Plan

        entries = [
            Plan.Entry(
                Content(entry["content"]),
                entry.get("priority", "medium"),
                entry.get("status", "pending"),
            )
            for entry in message.entries
        ]

        if self.contents.children and isinstance(
            (current_plan := self.contents.children[-1]), Plan
        ):
            current_plan.entries = entries
        else:
            await self.post(Plan(entries))

    @on(acp_messages.ToolCallUpdate)
    @on(acp_messages.ToolCall)
    async def on_acp_tool_call_update(
        self, message: acp_messages.ToolCall | acp_messages.ToolCallUpdate
    ):
        from livingtree.tui.td.widgets.tool_call import ToolCall

        tool_call = message.tool_call

        if tool_call.get("status", None) in (None, "completed"):
            self._agent_thought = None
            self._agent_response = None

        tool_id = message.tool_id
        try:
            existing_tool_call: ToolCall | None = self.contents.get_child_by_id(
                tool_id, ToolCall
            )
        except NoMatches:
            await self.post(ToolCall(tool_call, id=message.tool_id), new_block=True)
        else:
            if existing_tool_call is not None:
                await existing_tool_call.update_tool_call(tool_call)

    @on(acp_messages.AvailableCommandsUpdate)
    async def on_acp_available_commands_update(
        self, message: acp_messages.AvailableCommandsUpdate
    ):
        slash_commands: list[SlashCommand] = []
        for available_command in message.commands:
            input = available_command.get("input", {}) or {}
            slash_command = SlashCommand(
                f"/{available_command['name']}",
                available_command["description"],
                hint=input.get("hint"),
            )
            slash_commands.append(slash_command)
        self.agent_slash_commands = slash_commands
        self.update_slash_commands()

    def get_terminal(self, terminal_id: str) -> TerminalTool | None:
        """Get a terminal from its id.

        Args:
            terminal_id: ID of the terminal.

        Returns:
            Terminal instance, or `None` if no terminal was found.
        """
        from livingtree.tui.td.widgets.terminal_tool import TerminalTool

        try:
            terminal = self.contents.query_one(f"#{terminal_id}", TerminalTool)
        except NoMatches:
            return None
        if terminal.released:
            return None
        return terminal

    async def action_interrupt(self) -> None:
        terminal = self._terminal
        if terminal is not None and not terminal.is_finalized:
            await self.shell.interrupt()
            # self._shell = None
            self.flash("Command interrupted", style="success")
        else:
            raise SkipAction()

    def action_focus_block(self, block_id: str) -> None:
        with suppress(NoMatches):
            self.query_one(f"#{block_id}").focus()

    @work
    @on(acp_messages.CreateTerminal)
    async def on_acp_create_terminal(self, message: acp_messages.CreateTerminal):
        from livingtree.tui.td.widgets.terminal_tool import TerminalTool, Command

        command = Command(
            message.command,
            message.args or [],
            message.env or {},
            message.cwd or str(self.project_path),
        )
        width = self.window.size.width - 5 - self.window.styles.scrollbar_size_vertical
        height = self.window.scrollable_content_region.height - 2

        terminal = TerminalTool(
            command,
            output_byte_limit=message.output_byte_limit,
            id=message.terminal_id,
            minimum_terminal_width=width,
        )
        self.terminals[message.terminal_id] = terminal
        terminal.display = False

        try:
            await terminal.start(width, height)
        except Exception as error:
            log(str(error))
            message.result_future.set_result(False)
            return

        try:
            await self.post(terminal)
        except Exception:
            message.result_future.set_result(False)
        else:
            message.result_future.set_result(True)

    @on(acp_messages.KillTerminal)
    async def on_acp_kill_terminal(self, message: acp_messages.KillTerminal):
        if (terminal := self.get_terminal(message.terminal_id)) is not None:
            terminal.kill()

    @on(acp_messages.GetTerminalState)
    def on_acp_get_terminal_state(self, message: acp_messages.GetTerminalState):
        if (terminal := self.get_terminal(message.terminal_id)) is None:
            message.result_future.set_exception(
                KeyError(f"No terminal with id {message.terminal_id!r}")
            )
        else:
            message.result_future.set_result(terminal.tool_state)

    @on(acp_messages.ReleaseTerminal)
    def on_acp_terminal_release(self, message: acp_messages.ReleaseTerminal):
        if (terminal := self.get_terminal(message.terminal_id)) is not None:
            terminal.kill()
            terminal.release()

    @work
    @on(acp_messages.WaitForTerminalExit)
    async def on_acp_wait_for_terminal_exit(
        self, message: acp_messages.WaitForTerminalExit
    ):
        if (terminal := self.get_terminal(message.terminal_id)) is None:
            message.result_future.set_exception(
                KeyError(f"No terminal with id {message.terminal_id!r}")
            )
        else:
            return_code, signal = await terminal.wait_for_exit()
            message.result_future.set_result((return_code or 0, signal))

    async def set_mode(self, mode_id: str | None) -> None:
        """Set the mode give its id (if it exists).

        Args:
            mode_id: Id of mode.

        Returns:
            `True` if the mode was changed, `False` if it didn't exist.
        """
        if (agent := self.agent) is None:
            return
        if mode_id is None:
            self.current_mode = None
        else:
            if (error := await agent.set_mode(mode_id)) is not None:
                self.notify(error, title="Set Mode", severity="error")
            elif (new_mode := self.modes.get(mode_id)) is not None:
                self.current_mode = new_mode
                self.flash(
                    Content.from_markup("Mode changed to [b]$mode", mode=new_mode.name),
                    style="success",
                )

    @on(acp_messages.SetModes)
    async def on_acp_set_modes(self, message: acp_messages.SetModes):
        self.modes = message.modes
        self.current_mode = self.modes[message.current_mode]

    @on(messages.HistoryMove)
    async def on_history_move(self, message: messages.HistoryMove) -> None:
        message.stop()
        if message.shell:
            await self.shell_history.open()

            if self.shell_history_index == 0:
                current_shell_command = ""
            else:
                current_shell_command = (
                    await self.shell_history.get_entry(self.shell_history_index)
                )["input"]
            while True:
                self.shell_history_index += message.direction
                new_entry = await self.shell_history.get_entry(self.shell_history_index)
                if (new_entry)["input"] != current_shell_command:
                    break
                if message.direction == +1 and self.shell_history_index == 0:
                    break
                if (
                    message.direction == -1
                    and self.shell_history_index <= -self.shell_history.size
                ):
                    break
        else:
            await self.prompt_history.open()
            self.prompt_history_index += message.direction

    @work
    async def request_permissions(
        self,
        result_future: Future[Answer],
        options: list[Answer],
        tool_call_update: acp_protocol.ToolCallUpdatePermissionRequest,
    ) -> None:
        kind = tool_call_update.get("kind", None)
        title = tool_call_update.get("title", "") or ""

        contents = tool_call_update.get("content", []) or []
        # If all the content is diffs, we will set kind to "edit" to show the permisisons screen
        for content in contents:
            if content.get("type") != "diff":
                break
        else:
            kind = "edit"

        self.post_message(messages.SessionUpdate(state="asking"))

        if kind == "edit":
            diffs: list[tuple[str, str, str | None, str]] = []

            contents = tool_call_update.get("content", []) or []
            for content in contents:
                match content:
                    case {
                        "type": "diff",
                        "oldText": old_text,
                        "newText": new_text,
                        "path": path,
                    }:
                        diffs.append((path, path, old_text, new_text))

            if diffs:
                from livingtree.tui.td.screens.permissions import PermissionsScreen

                self.app.terminal_alert()
                self.app.system_notify(
                    f"{self.agent_title} would like to write files",
                    title="Permissions request",
                    sound="question",
                )
                permissions_screen = PermissionsScreen(
                    options, diffs, agent_name=self.agent_title or "The Agent"
                )
                result = await self.app.push_screen_wait(
                    permissions_screen, mode=self.screen.id
                )
                self.post_message(messages.SessionUpdate(state="busy"))
                self.app.terminal_alert(False)
                result_future.set_result(result)
                return

        from livingtree.tui.td.widgets.acp_content import ACPToolCallContent

        def answer_callback(answer: Answer) -> None:
            try:
                result_future.set_result(answer)
            except Exception:
                # I've seen this occur in shutdown with an `InvalidStateError`
                pass

            if not self.prompt.ask_queue:
                self.post_message(messages.SessionUpdate(state="busy"))

        tool_call_content = tool_call_update.get("content", None) or []
        self.ask(
            options,
            title or "",
            (
                partial(ACPToolCallContent, tool_call_content)
                if tool_call_content
                else None
            ),
            answer_callback,
        )
        return

    async def post_tool_call(
        self, tool_call_update: acp_protocol.ToolCallUpdate
    ) -> None:
        if (contents := tool_call_update.get("content")) is None:
            return

        for content in contents:
            match content:
                case {
                    "type": "diff",
                    "oldText": old_text,
                    "newText": new_text,
                    "path": path,
                }:
                    await self.post_diff(path, old_text, new_text)

    async def post_diff(self, path: str, before: str | None, after: str) -> None:
        """Post a diff view.

        Args:
            path: Path to the file.
            before: Content of file before edit.
            after: Content of file after edit.
        """

        from livingtree.tui.td.widgets.diff_view import make_diff

        diff_view = make_diff(path, path, before, after, classes="block")
        await self.post(diff_view)

    def ask(
        self,
        options: list[Answer],
        title: str = "",
        get_content: Callable[[], Widget] | None = None,
        callback: Callable[[Answer], Any] | None = None,
    ) -> None:
        """Replace the prompt with a dialog to ask a question

        Args:
            question: Question to ask or empty string to omit.
            options: A list of (ANSWER, ANSWER_ID) tuples.
            callback: Optional callable that will be invoked with the result.
        """
        from livingtree.tui.td.widgets.question import Ask

        self.agent_info

        if self.agent_title:
            notify_title = f"[{self.agent_title}] {title}"
        else:
            notify_title = title
        notify_message = "\n".join(f" • {option.text}" for option in options)
        self.app.system_notify(notify_message, title=notify_title, sound="question")

        self.prompt.ask(Ask(title, options, get_content, callback))

    def _build_slash_commands(self) -> list[SlashCommand]:
        slash_commands = [
            SlashCommand("/toad:about", "About Toad"),
            SlashCommand(
                "/toad:clear",
                "Clear conversation window",
                "<optional number of lines to preserve>",
            ),
            SlashCommand(
                "/toad:rename",
                "Give the current session a friendly name",
                "<session name>",
            ),
            SlashCommand(
                "/toad:session-close",
                "Close the current session",
            ),
            SlashCommand(
                "/toad:session-new",
                "Open a new session in the current working directory",
                "<initial prompt or command>",
            ),
            SlashCommand(
                "/toad:testimonial",
                "Tweet a testimonial regarding Toad",
                "<what you think of toad>",
            ),
        ]

        slash_commands.extend(self.agent_slash_commands)
        deduplicated_slash_commands = {
            slash_command.command: slash_command for slash_command in slash_commands
        }
        slash_commands = sorted(
            deduplicated_slash_commands.values(), key=attrgetter("command")
        )
        return slash_commands

    def update_slash_commands(self) -> None:
        """Update slash commands, which may have changed since mounting."""
        self.prompt.slash_commands = self._build_slash_commands()

    async def on_mount(self) -> None:
        self.trap_focus()
        self.prompt.focus()
        self.prompt.slash_commands = self._build_slash_commands()
        self.call_after_refresh(self.post_welcome)
        self.app.settings_changed_signal.subscribe(self, self._settings_changed)

        self.shell_history.complete.add_words(
            self.app.settings.get("shell.allow_commands", expect_type=str).split()
        )
        self.shell
        if self._agent_data is not None:

            async def start_agent() -> None:
                """Start the agent after refreshing the UI."""
                assert self._agent_data is not None
                from livingtree.tui.td.acp.agent import Agent

                self.agent = Agent(
                    self.project_path,
                    self._agent_data,
                    self._agent_session_id,
                    self._session_pk,
                )
                await self.agent.start(self)
                self.post_message(
                    messages.SessionUpdate("New Session", self.agent_title)
                )

            self.call_after_refresh(start_agent)

        elif self._hub is not None:
            async def start_neon() -> None:
                from livingtree.tui.neon_agent import NeonAgent, NEON_AGENT_DATA
                self._agent_data = NEON_AGENT_DATA
                self.agent = NeonAgent(self.project_path, hub=self._hub)
                await self.agent.start(self)
                self.post_message(
                    messages.SessionUpdate("Neon", "Neon Genesis")
                )

            self.call_after_refresh(start_neon)

        else:
            self.agent_ready = True

        self.update_title()
        self.window.anchor()

    def _settings_changed(self, setting_item: tuple[str, str]) -> None:
        key, value = setting_item
        if key == "shell.allow_commands":
            self.shell_history.complete.add_words(value.split())

    @work
    async def post_welcome(self) -> None:
        """Post any welcome content."""

    def watch_agent(self, agent: AgentBase | None) -> None:
        if agent is None:
            self.agent_info = Content.styled("shell")
        else:
            self.agent_info = agent.get_info()
            self.agent_ready = False
        self.update_title()

    @work
    async def watch_agent_ready(self, ready: bool) -> None:
        with suppress(asyncio.TimeoutError):
            async with asyncio.timeout(2.0):
                await self.shell.wait_for_ready()
        if ready:
            self._directory_watcher = DirectoryWatcher(self.project_path, self)
            self._directory_watcher.start()
        if ready and (agent_data := self._agent_data) is not None:
            welcome = agent_data.get("welcome", None)
            if welcome is not None:
                from livingtree.tui.td.widgets.markdown_note import MarkdownNote

                await self.post(MarkdownNote(welcome))
        if ready and self._initial_prompt is not None:
            prompt = self._initial_prompt
            if prompt.startswith("!"):
                self.post_message(
                    messages.UserInputSubmitted(self._initial_prompt[1:], shell=True)
                )
            else:
                self.post_message(
                    messages.UserInputSubmitted(self._initial_prompt, shell=False)
                )
            self._initial_prompt = None

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self._mouse_down_offset = event.screen_offset

    def on_click(self, event: events.Click) -> None:
        if (
            self._mouse_down_offset is not None
            and event.screen_offset != self._mouse_down_offset
        ):
            return
        widget = event.widget

        contents = self.contents
        if self.screen.get_selected_text():
            return
        if widget is None or widget.is_maximized:
            return
        try:
            widget.query_ancestor(Prompt)
        except NoMatches:
            pass
        else:
            return

        if widget in contents.displayed_children:
            self.cursor_offset = contents.displayed_children.index(widget)
            self.refresh_block_cursor()
            return
        for parent in widget.ancestors:
            if not isinstance(parent, Widget):
                break
            if (
                parent is self or parent is contents
            ) and widget in contents.displayed_children:
                self.cursor_offset = contents.displayed_children.index(widget)
                self.refresh_block_cursor()
                break
            if (
                isinstance(parent, BlockProtocol)
                and parent in contents.displayed_children
            ):
                self.cursor_offset = contents.displayed_children.index(parent)
                parent.block_select(widget)
                self.refresh_block_cursor()
                break
            widget = parent

    def new_block(self) -> None:
        """Start a new block for agent response."""
        self._agent_thought = None
        self._agent_response = None

    async def post[WidgetType: Widget](
        self,
        widget: WidgetType,
        *,
        loading: bool = False,
        new_block: bool = True,
    ) -> WidgetType:
        """Post a widget to the converstaion.

        Args:
            widget: Widget to post.
            loading: Set the widget to an initial loading state?
            new_block: Start a new block?

        Returns:
            The widget that was mounted.
        """
        if self._loading is not None:
            await self._loading.remove()
        if new_block and not loading:
            self.new_block()
        if not self.contents.is_attached:
            return widget
        await self.contents.mount(widget)

        widget.loading = loading
        self._require_check_prune = True
        self.call_after_refresh(self.check_prune)
        return widget

    async def check_prune(self) -> None:
        """Check if a prune is required."""
        if self._require_check_prune:
            self._require_check_prune = False
            low_mark = self.app.settings.get("ui.prune_low_mark", int)
            high_mark = low_mark + self.app.settings.get("ui.prune_excess", int)
            await self.prune_window(low_mark, high_mark)

    async def prune_window(self, low_mark: int, high_mark: int) -> None:
        """Remove older children to keep within a certain range.

        Args:
            low_mark: Height to aim for.
            high_mark: Height to start pruning.
        """

        assert high_mark >= low_mark

        contents = self.contents

        height = contents.virtual_size.height
        if height <= high_mark:
            return
        prune_children: list[Widget] = []
        bottom_margin = 0
        prune_height = 0

        if low_mark == 0:
            prune_children = list(contents.children)
        else:
            for child in contents.children:
                if not child.display:
                    prune_children.append(child)
                    continue
                top, _, bottom, _ = child.styles.margin
                child_height = child.outer_size.height
                prune_height = (
                    (prune_height - bottom_margin + max(bottom_margin, top))
                    + bottom
                    + child_height
                )
                bottom_margin = bottom
                if height - prune_height <= low_mark:
                    break
                prune_children.append(child)

        self.cursor_offset = -1
        self.cursor.visible = False
        self.cursor.follow(None)
        contents.refresh(layout=True)

        if prune_children:
            await contents.remove_children(prune_children)

        self.call_later(self.window.anchor)

    async def new_terminal(self) -> Terminal:
        """Create a new interactive Terminal.

        Args:
            width: Initial width of the terminal.
            display: Initial display.

        Returns:
            A new (mounted) Terminal widget.
        """

        if (terminal := self._terminal) is not None:
            if terminal.state.buffer.is_blank:
                terminal.finalize()
                await terminal.remove()

        self._terminal_count += 1

        terminal_width, terminal_height = self.get_terminal_dimensions()
        terminal = ShellTerminal(
            f"terminal #{self._terminal_count}",
            id=f"shell-terminal-{self._terminal_count}",
            size=(terminal_width, terminal_height),
            get_terminal_dimensions=self.get_terminal_dimensions,
        )

        terminal.display = False
        terminal = await self.post(terminal)
        self.add_focusable_terminal(terminal)
        self.refresh_bindings()
        return terminal

    def get_terminal_dimensions(self) -> tuple[int, int]:
        """Get the default dimensions of new terminals.

        Returns:
            Tuple of (WIDTH, HEIGHT)
        """
        terminal_width = max(
            16,
            (self.window.size.width - 2 - self.window.styles.scrollbar_size_vertical),
        )
        terminal_height = max(8, self.window.scrollable_content_region.height)
        return terminal_width, terminal_height

    @property
    def shell(self) -> Shell:
        """A Shell instance."""

        if self._shell is None or self._shell.is_finished:
            shell_command = self.app.settings.get(
                "shell.command",
                str,
                expand=False,
            )
            shell_start = self.app.settings.get(
                "shell.command_start",
                str,
                expand=False,
            )
            shell_directory = self.working_directory
            self._shell = Shell(
                self, shell_directory, shell=shell_command, start=shell_start
            )
            self._shell.start()
        return self._shell

    async def post_shell(self, command: str) -> None:
        """Post a command to the shell.

        Args:
            command: Command to execute.
        """
        from livingtree.tui.td.widgets.shell_result import ShellResult

        if command.strip():
            self._shell_count += 1
            await self.post(ShellResult(command))
            width, height = self.get_terminal_dimensions()
            await self.shell.send(command, width, height)

    def action_cursor_up(self) -> None:
        if not self.contents.displayed_children or self.cursor_offset == 0:
            # No children
            return
        if self.cursor_offset == -1:
            # Start cursor at end
            self.cursor_offset = len(self.contents.displayed_children) - 1
            cursor_block = self.cursor_block
            if isinstance(cursor_block, BlockProtocol):
                cursor_block.block_cursor_clear()
                cursor_block.block_cursor_up()
        else:
            cursor_block = self.cursor_block
            if isinstance(cursor_block, BlockProtocol):
                if cursor_block.block_cursor_up() is None:
                    self.cursor_offset -= 1
                    cursor_block = self.cursor_block
                    if isinstance(cursor_block, BlockProtocol):
                        cursor_block.block_cursor_clear()
                        cursor_block.block_cursor_up()
            else:
                # Move cursor up
                self.cursor_offset -= 1
                cursor_block = self.cursor_block
                if isinstance(cursor_block, BlockProtocol):
                    cursor_block.block_cursor_clear()
                    cursor_block.block_cursor_up()
        self.refresh_block_cursor()

    def action_cursor_down(self) -> None:
        if not self.contents.displayed_children or self.cursor_offset == -1:
            # No children, or no cursor
            return

        cursor_block = self.cursor_block
        if isinstance(cursor_block, BlockProtocol):
            if cursor_block.block_cursor_down() is None:
                self.cursor_offset += 1
                if self.cursor_offset >= len(self.contents.displayed_children):
                    self.cursor_offset = -1
                    self.refresh_block_cursor()
                    return
                cursor_block = self.cursor_block
                if isinstance(cursor_block, BlockProtocol):
                    cursor_block.block_cursor_clear()
                    cursor_block.block_cursor_down()
        else:
            self.cursor_offset += 1
            if self.cursor_offset >= len(self.contents.displayed_children):
                self.cursor_offset = -1
                self.refresh_block_cursor()
                return
            cursor_block = self.cursor_block
            if isinstance(cursor_block, BlockProtocol):
                cursor_block.block_cursor_clear()
                cursor_block.block_cursor_down()
        self.refresh_block_cursor()

    @work
    async def action_cancel(self) -> None:
        if monotonic() - self._last_escape_time < 3:
            if (agent := self.agent) is not None:
                if await agent.cancel():
                    self.flash("Turn cancelled", style="success")
                else:
                    self.flash("Agent declined to cancel. Please wait.", style="error")
        else:
            self.flash("Press [b]esc[/] again to cancel agent's turn")
            self._last_escape_time = monotonic()

    def focus_prompt(self, reset_cursor: bool = True, scroll_end: bool = True) -> None:
        """Focus the prompt input.

        Args:
            reset_cursor: Reset the block cursor.
            scroll_end: Scroll t the end of the content.
        """
        if reset_cursor:
            self.cursor_offset = -1
            self.cursor.visible = False
        if scroll_end:
            self.window.scroll_end()
        self.prompt.focus()

    async def action_select_block(self) -> None:
        if (block := self.get_cursor_block(Widget)) is None:
            return

        menu_options = [
            MenuItem("[u]C[/]opy to clipboard", "copy_to_clipboard", "c"),
            MenuItem("Co[u]p[/u]y to prompt", "copy_to_prompt", "p"),
            MenuItem("Open as S[u]V[/]G", "export_to_svg", "v"),
        ]

        print(repr(block))
        if block.allow_maximize:
            menu_options.append(MenuItem("[u]M[/u]aximize", "maximize_block", "m"))

        if isinstance(block, MenuProtocol):
            menu_options.extend(block.get_block_menu())
            menu = Menu(block, menu_options)
        else:
            menu = Menu(block, menu_options)

        menu.offset = Offset(1, block.region.offset.y)
        await self.mount(menu)
        menu.focus()

    def action_copy_to_clipboard(self) -> None:
        block = self.get_cursor_block()
        if isinstance(block, MenuProtocol):
            text = block.get_block_content("clipboard")
        elif isinstance(block, MarkdownFence):
            text = block._content.plain
        elif isinstance(block, MarkdownBlock):
            text = block.source
        else:
            return
        if text:
            self.app.copy_to_clipboard(text)
            self.flash("Copied to clipboard")

    def action_copy_to_prompt(self) -> None:
        block = self.get_cursor_block()
        if isinstance(block, MenuProtocol):
            text = block.get_block_content("prompt")
        elif isinstance(block, MarkdownFence):
            # Copy to prompt leaves MD formatting
            text = block.source
        elif isinstance(block, MarkdownBlock):
            text = block.source
        else:
            return

        if text:
            self.prompt.append(text)
            self.flash("Copied to prompt")
            self.focus_prompt()

    def action_maximize_block(self) -> None:
        if (block := self.get_cursor_block()) is not None:
            self.screen.maximize(block, container=False)
            block.focus()

    def action_export_to_svg(self) -> None:
        block = self.get_cursor_block()
        if block is None:
            return
        import platformdirs
        from textual._compositor import Compositor
        from textual._files import generate_datetime_filename

        width, height = block.outer_size
        compositor = Compositor()
        compositor.reflow(block, block.outer_size)
        render = compositor.render_full_update()

        from rich.console import Console
        import io
        import os.path

        console = Console(
            width=width,
            height=height,
            file=io.StringIO(),
            force_terminal=True,
            color_system="truecolor",
            record=True,
            legacy_windows=False,
            safe_box=False,
        )
        console.print(render)
        path = platformdirs.user_pictures_dir()
        svg_filename = generate_datetime_filename("LivingTree", ".svg", None)
        svg_path = os.path.expanduser(os.path.join(path, svg_filename))
        console.save_svg(svg_path)
        import webbrowser

        webbrowser.open(f"file:///{svg_path}")

    async def action_mode_switcher(self) -> None:
        self.prompt.mode_switcher.focus()

    def refresh_block_cursor(self) -> None:
        if (cursor_block := self.cursor_block_child) is not None:
            self.window.focus()
            self.cursor.visible = True
            self.cursor.follow(cursor_block)
            self.call_after_refresh(
                self.window.scroll_to_center, cursor_block, immediate=True
            )
        else:
            self.cursor.visible = False
            self.window.anchor(False)
            self.window.scroll_end(duration=2 / 10)
            self.cursor.follow(None)
            self.prompt.focus()
        self.refresh_bindings()

    async def slash_command(self, text: str) -> bool:
        """Give Toad the opertunity to process slash commands.

        Args:
            text: The prompt, including the slash in the first position.

        Returns:
            `True` if Toad has processed the slash command, `False` if it should
                be forwarded to the agent.
        """
        command, _, parameters = text[1:].partition(" ")
        # ═══ LivingTree slash commands ═══
        if command in ("search", "fetch", "clear", "status", "help", "evolve", "tools", "route", "optimize", "role", "graph", "cron", "recall", "gateway", "compute", "sysinfo", "factcheck", "gaps", "plan", "batch", "template", "compliance", "cost", "mine", "connect", "peers", "login", "find", "save", "replace", "locate", "dedup", "patch", "render", "backup", "watch", "history", "web", "sql", "git", "shell", "debate", "snapshot", "evolvetool", "modify", "consolidate", "market", "synthesize", "continue", "activity", "eval", "trust", "branch", "semdiff", "selfdocs", "deepsearch", "ghmirror", "dns", "lineage", "practice", "profile"):
            return await self._handle_livingtree_command(command, parameters.strip())
        if command == "toad:about":
            from livingtree.tui.td import about
            from livingtree.tui.td.widgets.markdown_note import MarkdownNote

            app = self.app
            about_md = about.render(app)
            await self.post(MarkdownNote(about_md, classes="about"))
            self.app.copy_to_clipboard(about_md)
            self.notify(
                "A copy of /about:toad has been placed in your clipboard",
                title="/toad:about",
            )
            return True
        elif command == "toad:clear":
            try:
                line_count = max(0, int(parameters) if parameters.strip() else 0)
            except ValueError:
                self.notify(
                    "Unable to clear—a number was expected",
                    title="/toad:clear",
                    severity="error",
                )
                return True
            await self.prune_window(line_count, line_count)
            return True
        elif command == "toad:rename":
            name = parameters.strip()
            if not name:
                self.notify(
                    "Expected a name for the session.\n"
                    'For example: "add comments to blog"',
                    title="/toad:rename",
                    severity="error",
                )
                return True
            if self.agent is not None:
                await self.agent.set_session_name(name)
                self.post_message(messages.SessionUpdate(name=name))
                self.flash(f"Renamed session to [b]'{name}'", style="success")
            return True
        elif command == "toad:session-close":
            if self.turn == "agent" and self.agent is not None:
                await self.agent.cancel()
            if self.screen.id is not None:
                self.post_message(messages.SessionClose(self.screen.id))
                return True
        elif command == "toad:session-new":
            if self._agent_data is not None:
                self.post_message(
                    messages.SessionNew(
                        self.working_directory,
                        self._agent_data["identity"],
                        parameters.strip(),
                    )
                )
                return True
        elif command == "toad:testimonial":
            if self.agent_title is not None:
                default_testimonial = (
                    f"I'm running {self.agent_title} in the terminal with Toad."
                )
            else:
                default_testimonial = (
                    "Try Toad, the universal interface for AI in your terminal"
                )

            testimonial = parameters or default_testimonial
            from livingtree.tui.td.twitter import open_tweet_intent

            open_tweet_intent(
                testimonial,
                url="https://github.com/ookok/LivingTreeAlAgent",
                via="willmcgugan",
                hashtags=["ai"],
            )
            return True

        return False

    # ═══ LivingTree slash command handlers ═══

    async def _handle_livingtree_command(self, command: str, params: str) -> bool:
        from livingtree.tui.i18n import t

        if command == "clear":
            try:
                line_count = max(0, int(params) if params.strip() else 0)
            except ValueError:
                line_count = 0
            await self.prune_window(line_count, line_count)
            return True

        elif command == "status":
            try:
                hub = getattr(self.app, 'hub', None)
                if hub:
                    status = hub.status()
                    from livingtree.tui.td.widgets.markdown_note import MarkdownNote
                    lines = [t("cmd.status_title")]
                    for k, v in status.items():
                        if not isinstance(v, dict):
                            lines.append(f"- **{k}**: {v}")
                    await self.post(MarkdownNote("\n".join(lines)))
                else:
                    from livingtree.tui.td.widgets.note import Note
                    await self.post(Note(t("cmd.not_ready")))
            except Exception:
                pass
            return True

        elif command == "help":
            from livingtree.tui.td.widgets.note import Note
            await self.post(Note(t("cmd.help_text")))
            return True

        elif command in ("search", "fetch"):
            if not params:
                from livingtree.tui.td.widgets.note import Note
                usage = t("cmd.search_usage") if command == "search" else t("cmd.fetch_usage")
                await self.post(Note(usage))
                return True

            async def do_work():
                hub = getattr(self.app, 'hub', None)
                if not hub or not hub.world:
                    from livingtree.tui.td.widgets.note import Note
                    await self.post(Note(t("cmd.not_ready")))
                    return

                if command == "search":
                    from livingtree.capability.unified_search import get_unified_search
                    search_engine = get_unified_search()
                    from livingtree.tui.td.widgets.note import Note
                    await self.post(Note(t("cmd.searching", q=params)))
                    try:
                        results = await search_engine.query(params)
                        if results:
                            await self.post(Note(search_engine.format_results(results)))
                        else:
                            await self.post(Note(t("cmd.no_results")))
                    except Exception as e:
                        await self.post(Note(t("cmd.search_error", e=str(e))))

                elif command == "fetch":
                    from livingtree.capability.web_reach import WebReach
                    from livingtree.tui.td.widgets.note import Note
                    await self.post(Note(t("cmd.fetching", url=params)))
                    try:
                        reach = WebReach()
                        page = await reach.fetch(params)
                        if page.status_code == 200:
                            lines = [
                                f"## {page.title or params}",
                                f"*{page.url}*",
                                "",
                                page.snippet(500),
                            ]
                            await self.post(Note("\n".join(lines)))
                        else:
                            await self.post(Note(t("cmd.http_error", code=page.status_code)))
                    except Exception as e:
                        await self.post(Note(t("cmd.fetch_error", e=str(e))))

            asyncio.create_task(do_work())
            return True

        elif command == "evolve":
            from livingtree.tui.td.widgets.note import Note
            try:
                from livingtree.dna.tui_orchestrator import get_orchestrator
                orch = get_orchestrator()
                status = orch.get_status()
                lines = [
                    t("cmd.evolve_title"),
                    t("cmd.evolve_requests", n=status['total_requests']),
                    t("cmd.evolve_hits", n=status['structured_hits'], pct=f"{status['hit_rate']:.1%}"),
                    t("cmd.evolve_failures", n=status['parse_failures']),
                    t("cmd.evolve_latency", ms=status['avg_latency_ms']),
                    "",
                    t("cmd.evolve_widgets"),
                ]
                for widget, count in status.get("widget_renders", {}).items():
                    lines.append(f"- {widget}: {count}")
                lines.append("")
                lines.append(t("cmd.evolve_parser"))
                for stype, stats in status.get("parser_stats", {}).items():
                    lines.append(f"- {stype}: {stats['success']}/{stats['total']} ({stats['rate']:.1%})")
                await self.post(Note("\n".join(lines)))
            except Exception as e:
                await self.post(Note(t("cmd.evolve_error", e=str(e))))
            return True

        elif command == "tools":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.tui.widgets.enhanced_tool_call import format_tool_list
            await self.post(Note(format_tool_list()))
            return True

        elif command == "route":
            if not params:
                from livingtree.tui.td.widgets.note import Note
                await self.post(Note(t("cmd.route_usage")))
                return True
            from livingtree.tui.td.widgets.note import Note
            from livingtree.treellm.skill_router import get_router
            try:
                router = get_router()
                decision = router.route(params)
                lines = [t("cmd.route_title", q=params), ""]
                if decision.providers:
                    lines.append(t("cmd.route_providers"))
                    for r in decision.providers[:3]:
                        lines.append(f"- {r.name} ({t('cmd.score')}={r.score:.3f})")
                if decision.tools:
                    lines.append(f"\n{t('cmd.route_tools')}")
                    for r in decision.tools[:5]:
                        lines.append(f"- {r.name} ({t('cmd.score')}={r.score:.3f})")
                if decision.roles:
                    lines.append(f"\n{t('cmd.route_roles')}")
                    for r in decision.roles[:3]:
                        lines.append(f"- {r.name} ({t('cmd.score')}={r.score:.3f})")
                await self.post(Note("\n".join(lines)))
            except Exception as e:
                await self.post(Note(t("cmd.route_error", e=str(e))))
            return True

        elif command == "optimize":
            if not params:
                from livingtree.tui.td.widgets.note import Note
                await self.post(Note(t("cmd.optimize_usage")))
                return True
            from livingtree.tui.td.widgets.note import Note
            from livingtree.dna.prompt_optimizer import optimize_prompt
            hub = getattr(self.app, 'hub', None)
            if not hub:
                await self.post(Note(t("cmd.not_ready")))
                return True
            await self.post(Note(t("cmd.optimizing", p=params[:100])))
            result = await optimize_prompt(params, rounds=2, hub=hub)
            lines = [
                t("cmd.optimize_title", rounds=result.rounds, score=f"{result.quality_score:.2f}"),
                "",
                t("cmd.optimize_original"),
                f"> {result.original[:300]}",
                "",
                t("cmd.optimize_result"),
                result.optimized[:2000],
            ]
            if result.improvements:
                lines.append(f"\n{t('cmd.optimize_improvements')}")
                for imp in result.improvements:
                    lines.append(f"- {imp}")
            await self.post(Note("\n".join(lines)))
            return True

        elif command == "role":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.dna.prompt_optimizer import get_roles, get_role
            if not params:
                lines = [t("cmd.role_title"), ""]
                for name in get_roles():
                    role = get_role(name)
                    if role:
                        lines.append(f"- **{name}**: {role.role_prompt[:80]}...")
                await self.post(Note("\n".join(lines)))
            return True

        elif command == "connect":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.network.p2p_node import get_p2p_node
            if not params:
                await self.post(Note("用法: /connect <节点ID>"))
                return True
            node = get_p2p_node()
            result = await node.connect_to(params.strip())
                await self.post(Note(result))
            return True

        elif command == "locate":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.document_editor import get_editor
            if not params:
                await self.post(Note("用法: /locate <代码描述>"))
                await self.post(Note("示例: /locate 用户认证逻辑"))
                return True
            hub = getattr(self.app, 'hub', None)
            editor = get_editor()
            await self.post(Note(f"**🔎 定位:** {params}"))
            locations = await editor.find_location(params, hub=hub)
            if not locations:
                await self.post(Note("[dim]未找到匹配位置[/dim]"))
            else:
                lines = [f"## 🔎 找到 {len(locations)} 处", ""]
                for loc in locations:
                    lines.append(f"- **{Path(loc['file']).name}**:{loc['line']}")
                    lines.append(f"  [dim]{loc['file']}[/dim]")
                    if loc.get('context'):
                        lines.append(f"  `{loc['context'][:120]}`")
                    if loc.get('reason'):
                        lines.append(f"  {loc['reason']}")
                await self.post(Note("\n".join(lines)))
            return True

        elif command == "find":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.unified_file_tool import UnifiedFileTool
            if not params:
                await self.post(Note("用法: /find <关键词> — 搜索文件/代码/文档/历史/知识库"))
                return True
            await self.post(Note(f"**🔍 全域搜索:** {params}"))
            tool = UnifiedFileTool()
            hits = await tool.search(params, max_results=15)
            if not hits:
                await self.post(Note("[dim]未找到任何结果[/dim]"))
            else:
                lines = [f"## 🔍 搜索结果 ({len(hits)} 条)", ""]
                for h in hits:
                    icon = {"filesystem": "📁", "code": "💻", "document": "📄", "history": "💬", "kb": "📚", "graph": "🕸"}.get(h.source, "🔗")
                    lines.append(f"{icon} **{h.name[:80]}** [{h.source}]")
                    if h.path:
                        lines.append(f"  [dim]{h.path[:100]}[/dim]")
                    if h.content_preview:
                        lines.append(f"  {h.content_preview[:120]}")
                    if h.relevance:
                        lines.append(f"  [dim]{h.relevance}[/dim]")
                await self.post(Note("\n".join(lines)))
            return True

        elif command == "replace":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.document_editor import get_editor
            parts = params.split(maxsplit=2) if params else []
            if len(parts) < 2:
                await self.post(Note("用法: /replace <文件> <旧文本> [新文本]"))
                await self.post(Note("模式: heading|block|key|pattern (默认:模糊匹配)")
                await self.post(Note("示例: /replace config.yaml port:8100 port:8888"))
                return True
            editor = get_editor()
            path = parts[0]; arg = parts[1]; new = parts[2] if len(parts) > 2 else ""
            # Smart mode detection
            mode = "pattern"  # default: regex
            if arg.startswith("section|"):
                heading = arg.split("|", 1)[1]
                result = editor.smart_replace(path, heading, new, mode="heading")
            elif arg.startswith("block|"):
                anchor = arg.split("|", 1)[1]
                result = editor.smart_replace(path, anchor, new, mode="block")
            elif arg.startswith("key|"):
                key = arg.split("|", 1)[1]
                result = editor.smart_replace(path, key, new, mode="key")
            elif len(arg) > 20 and arg == new[:len(arg)]:
                # Looks like a block replacement (long text), use block mode
                result = editor.smart_replace(path, arg, new, mode="block")
            else:
                # Short pattern → try regex first, fall back to smart
                result = editor.replace_pattern(path, arg, new)
                if result.replacements == 0:
                    result = editor.smart_replace(path, arg, new, mode="key")
            await self.post(Note(f"替换: {result.replacements} 处 {result.preview or ''} {'[已应用]' if result.applied else '[未找到匹配]'}"))
            return True

        elif command == "save":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.core.file_resolver import get_resolver
            parts = params.split(maxsplit=1) if params else []
            filename = parts[0].strip() if parts else ""
            content = parts[1] if len(parts) > 1 else ""
            if not filename:
                await self.post(Note("用法: /save <文件名> [内容]"))
                await self.post(Note("目录自动选择: .py→src/  .docx→output/  .md→docs/"))
                return True
            resolver = get_resolver()
            resolved = resolver.resolve(filename, content=content)
            rel = resolver.write(resolved, content or "")
            await self.post(Note(f"已保存: {rel}"))
            return True

        elif command == "peers":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.network.p2p_node import get_p2p_node
            node = get_p2p_node()
            await self.post(Note(f"**🔍 发现网络中...** 节点ID: {node.node_id[:16]}..."))
            peers = await node.discover_peers()
            if not peers:
                await self.post(Note("[dim]未发现其他节点。请确保中继服务器正在运行。[/dim]"))
            else:
                lines = [f"## 🌐 P2P 网络 ({len(peers)} 节点)", ""]
                for p in peers:
                    caps = p.capabilities
                    caps_str = ""
                    if caps:
                        parts = []
                        if caps.providers: parts.append(f"LLM:{len(caps.providers)}")
                        if caps.tools: parts.append(f"工具:{len(caps.tools)}")
                        if caps.skills: parts.append(f"技能:{len(caps.skills)}")
                        caps_str = " | ".join(parts)
                    lines.append(f"- **{p.peer_id[:16]}...**  [{caps_str}]")
                lines.append("")
                lines.append("使用 /connect <节点ID> 连接特定节点")
                await self.post(Note("\n".join(lines)))
            return True

        elif command == "login":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.network.p2p_node import get_p2p_node
            parts = params.split() if params else []
            if len(parts) < 2:
                await self.post(Note("用法: /login <用户名> <密码>"))
                return True
            node = get_p2p_node()
            result = await node.login(parts[0], parts[1])
            if result:
                await self.post(Note(f"[red]{result}[/red]"))
            else:
                await self.post(Note(f"[green]✓ 已登录为 {parts[0]}[/green]"))
            return True

        elif command == "mine":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.knowledge.auto_knowledge_miner import get_miner
            miner = get_miner()
            target = params.strip() if params else "."
            await self.post(Note(f"**⛏ 正在自动挖掘: {target}** ..."))
            stats = await miner.mine_directory(target)
            lines = [
                "## ⛏ 知识挖掘完成",
                f"- 📄 文档解析: {stats.get('docs_parsed', 0)} 篇",
                f"- 📦 项目扫描: {stats.get('projects_scanned', 0)} 个",
                f"- 📝 术语提取: {stats.get('terms_mined', 0)} 条",
                f"- 📋 模板合成: {stats.get('templates_extracted', 0)} 套",
                f"- ⏱ 耗时: {stats.get('_last_mining_duration', 0):.1f}s",
                "",
                "### 🔍 发现的术语 (前10)",
            ]
            for t in miner.get_terms()[:10]:
                lines.append(f"- **{t.term}** [{t.category}] (×{t.frequency})")

            templates = miner.get_templates()
            if templates:
                lines.append("\n### 📋 合成的模板")
                for t in templates[:5]:
                    lines.append(f"- **{t.name}** (置信度 {t.confidence:.0%}): {' → '.join(t.sections[:5])}")

            patterns = miner.get_patterns()
            if patterns:
                lines.append("\n### 💻 代码模式")
                for p in patterns[:5]:
                    lines.append(f"- **{p.name}**: {p.description[:80]}")

            await self.post(Note("\n".join(lines)))
            return True

        elif command == "batch":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.industrial_doc_engine import get_batch_gen, get_template_mgr
            parts = params.split(maxsplit=1) if params else []
            if not params:
                await self.post(Note("用法: /batch <CSV文件> <模板名>"))
                return True
            hub = getattr(self.app, 'hub', None)
            gen = get_batch_gen(hub)
            try:
                csv_path, template = parts[0], parts[1] if len(parts) > 1 else "通用报告"
                gen.enqueue_csv(csv_path, template)
                await self.post(Note(f"📦 批量生成: {len(gen._jobs)} 个任务, 模板: {template}"))
                progress = await gen.generate_all()
                lines = [f"## 📦 批量生成完成 ({progress.pct:.0%})", f"✅ {progress.done}  | ❌ {progress.failed}"]
                for j in progress.jobs[:10]:
                    status = "✅" if j.status == "done" else "❌"
                    lines.append(f"  {status} {j.id}: {str(j.params)[:60]}")
                await self.post(Note("\n".join(lines)))
            except Exception as e:
                await self.post(Note(f"[red]Batch error: {e}[/red]"))
            return True

        elif command == "template":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.industrial_doc_engine import get_template_mgr
            mgr = get_template_mgr()
            parts = params.split(maxsplit=1)
            sub = parts[0].lower() if parts else "list"
            if sub == "list":
                lines = ["## 📋 模板版本"]
                for name, versions in mgr._templates.items():
                    v = versions[-1]
                    lines.append(f"- **{name}** v{v.version} (quality={v.quality_score:.2f})")
                if not mgr._templates:
                    lines.append("[dim]暂无模板[/dim]")
                await self.post(Note("\n".join(lines)))
            elif sub == "save" and len(parts) > 1:
                name, content = parts[1].split(maxsplit=1) if " " in parts[1] else (parts[1], "")
                v = mgr.save(name, content)
                await self.post(Note(f"✓ 模板 {name} v{v.version} 已保存"))
            elif sub == "history" and len(parts) > 1:
                history = mgr.get_history(parts[1])
                lines = [f"## 📜 {parts[1]} 版本历史"]
                for v in history:
                    lines.append(f"- v{v.version}: {v.diff_from_previous or '初版'} (quality={v.quality_score:.2f})")
                await self.post(Note("\n".join(lines)))
            else:
                await self.post(Note("用法: /template list|save <名> <内容>|history <名>"))
            return True

        elif command == "compliance":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.industrial_doc_engine import get_compliance
            if not params:
                await self.post(Note("用法: /compliance <标准代码> <文档内容>"))
                await self.post(Note("可用标准: GB3095-2012, GB3096-2008, GB3838-2002, GB/T3840-1991"))
                return True
            cc = get_compliance()
            parts = params.split(maxsplit=1)
            if len(parts) < 2:
                await self.post(Note("需要标准代码和文档内容"))
                return True
            result = cc.check(parts[1], parts[0])
            lines = [f"## 📋 合规检查: {result['standard']} ({result['name']})"]
            if result["violations"]:
                lines.append("\n### ❌ 不合规项:")
                for v in result["violations"]:
                    lines.append(f"- {v}")
            else:
                lines.append("\n### ✅ 未发现不合规项")
            if result["suggestions"]:
                lines.append("\n### 💡 建议:")
                for s in result["suggestions"]:
                    lines.append(f"- {s}")
            await self.post(Note("\n".join(lines)))
            return True

        elif command == "cost":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.industrial_doc_engine import get_cost_dash
            dash = get_cost_dash()
            stats = dash.get_stats()
            lines = [f"## 💰 Token 成本仪表盘", f"**总费用**: ${stats['total_cost']:.4f}"]
            if stats['budget'] > 0:
                pct = stats['total_cost'] / stats['budget'] * 100
                lines.append(f"**预算**: ${stats['budget']:.2f} ({pct:.0f}%)")
            lines.append("")
            for p, s in stats.get("per_provider", {}).items():
                if s["cost"] > 0:
                    lines.append(f"- **{p}**: ${s['cost']:.4f} ({s['calls']} calls, {s['tokens_in']}+{s['tokens_out']} tokens)")
            await self.post(Note("\n".join(lines)))
            return True

        elif command == "plan":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.execution.real_pipeline import get_real_orchestrator
            if not params:
                await self.post(Note("用法: /plan <复杂任务描述>"))
                return True
            hub = getattr(self.app, 'hub', None)
            orch = get_real_orchestrator(hub)
            await self.post(Note(f"**📋 任务规划:** {params[:100]}"))
            ctx = await orch.plan(params)
            lines = [f"## 📋 任务分解 (意图: {ctx.intent}, 域: {ctx.domain}, 置信度: {ctx.confidence:.0%})", ""]
            for s in ctx.steps:
                deps = f" ← {', '.join(s.dependencies)}" if s.dependencies else ""
                lines.append(f"### {s.id}. {s.name}")
                lines.append(f"  [{s.action}] {s.agent_role}{deps}")
                lines.append(f"  {s.description[:120]}")
            await self.post(Note("\n".join(lines)))
            return True

        elif command == "factcheck":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.knowledge.intelligent_kb import fact_check
            if not params:
                await self.post(Note("用法: /factcheck <需要验证的陈述>"))
                return True
            hub = getattr(self.app, 'hub', None)
            await self.post(Note(f"**🔍 事实核查:** {params[:100]}"))
            result = await fact_check(params, hub)
            icon = {"SUPPORTED": "✅", "REFUTED": "❌", "UNCERTAIN": "❓", "UNKNOWN": "❓"}
            lines = [
                f"{icon.get(result.verdict, '❓')} **{result.verdict}** (置信度: {result.confidence:.0%})",
                "",
                f"**证据来源**: {result.source}",
                f"> {result.evidence[:500]}",
            ]
            await self.post(Note("\n".join(lines)))
            return True

        elif command == "gaps":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.knowledge.intelligent_kb import detect_semantic_gaps
            gaps = detect_semantic_gaps()
            lines = ["## 🔬 知识缺口分析", ""]
            for g in gaps[:10]:
                prio_bar = "█" * int(g.priority * 10) + "░" * (10 - int(g.priority * 10))
                lines.append(f"- **{g.domain}** [{prio_bar}] {g.priority:.0%}")
                lines.append(f"  {g.description}")
                lines.append(f"  建议搜索: {g.suggested_queries[0] if g.suggested_queries else 'N/A'}")
            lines.append("")
            lines.append("使用 /learn <领域> 自动填补缺口")
            await self.post(Note("\n".join(lines)))
            return True
            role = get_role(params)
            if not role:
                await self.post(Note(t("cmd.role_unknown", name=params)))
                return True
            lines = [
                t("cmd.role_detail", name=role.name),
                "",
                f"**{t('cmd.role_prompt')}**: {role.role_prompt}",
                "",
                f"**{t('cmd.role_gates')}**: " + ", ".join(role.quality_gates),
                "",
                f"**{t('cmd.role_format')}**:\n{role.output_format[:500]}",
            ]
            if role.few_shot_examples:
                lines.append(f"\n**{t('cmd.role_examples')}**:")
                for ex in role.few_shot_examples:
                    lines.append(f"- {t('cmd.input')}: {ex['input']}")
                    lines.append(f"  {t('cmd.output')}: {ex['output'][:100]}...")
            await self.post(Note("\n".join(lines)))
            return True

        elif command == "graph":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.dna.skill_graph import get_skill_graph
            graph = get_skill_graph()
            highlight = params.strip() if params else ""
            ascii_graph = graph.format_ascii(highlight=highlight, depth=2)
            await self.post(Note(ascii_graph))
            return True

        elif command == "cron":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.execution.cron_scheduler import get_scheduler
            sched = get_scheduler()
            parts = params.split(maxsplit=1) if params else []
            sub = parts[0].lower() if parts else "list"
            arg = parts[1] if len(parts) > 1 else ""

            if sub == "list":
                jobs = sched.list()
                if not jobs:
                    await self.post(Note(t("cmd.cron_empty")))
                else:
                    lines = [t("cmd.cron_title")]
                    for j in jobs:
                        next_ts = datetime.fromtimestamp(j.next_run).strftime("%m-%d %H:%M")
                        lines.append(f"- [{j.id}] {next_ts} | {j.description} ({j.run_count}x)")
                    await self.post(Note("\n".join(lines)))
            elif sub == "add" and arg:
                sched.add(description=arg[:100], schedule="daily 08:00", prompt=arg)
                await self.post(Note(t("cmd.cron_added", desc=arg[:80])))
            elif sub == "remove" and arg:
                ok = sched.remove(arg)
                await self.post(Note(t("cmd.cron_removed", id=arg) if ok else t("cmd.cron_notfound", id=arg)))
            elif sub == "test" and arg:
                job = sched.get(arg)
                if job and sched._callback:
                    await sched._callback(job)
                    await self.post(Note(t("cmd.cron_tested", id=arg)))
                else:
                    await self.post(Note(t("cmd.cron_notfound", id=arg)))
            else:
                await self.post(Note(t("cmd.cron_usage")))
            return True

        elif command == "recall":
            from livingtree.tui.td.widgets.note import Note
            try:
                from livingtree.knowledge.session_search import get_search
            except ImportError:
                await self.post(Note("[dim]SQLite FTS5 unavailable[/dim]"))
                return True
            if not params:
                await self.post(Note(t("cmd.recall_usage")))
                return True
            search = get_search()
            hits = search.search(params, limit=10)
            stats = search.get_stats()
            lines = [t("cmd.recall_title", q=params, n=stats["indexed_turns"])]
            if hits:
                for h in hits[:8]:
                    role_icon = "👤" if h.role == "user" else "🤖"
                    lines.append(f"\n{role_icon} [{h.session_id}·{h.turn_id}] {h.snippet[:150]}")
            else:
                lines.append(t("cmd.recall_empty"))
            await self.post(Note("\n".join(lines)))
            return True

        elif command == "gateway":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.integration.message_gateway import get_gateway
            gw = get_gateway()
            sub = params.split()[0].lower() if params else "status"
            if sub == "status":
                status = gw.get_status()
                lines = [t("cmd.gateway_title")]
                for p in status["enabled_platforms"]:
                    lines.append(f"- {p} ✓")
                if not status["telegram_configured"]:
                    lines.append("- telegram (未配置)")
                await self.post(Note("\n".join(lines)))
            elif sub == "config" and "telegram" in params:
                parts = params.split()
                if len(parts) >= 3:
                    gw.configure("telegram", token=parts[2])
                    if len(parts) >= 4:
                        gw.configure("telegram", token=parts[2], chat_id=parts[3])
                    asyncio.create_task(gw.start_polling(5.0))
                    await self.post(Note(t("cmd.gateway_configured", platform="telegram")))
            else:
                await self.post(Note(t("cmd.gateway_usage")))
            return True

        elif command == "compute":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.tui.widgets.enhanced_tool_call import SYSTEM_TOOLS
            import math
            if not params:
                await self.post(Note("用法: /compute <模型> <参数>\n可用模型: gaussian_plume, noise_attenuation, dispersion_coeff\n示例: /compute gaussian_plume Q=100 u=3.5 x=500 y=0 z=0 stability=D He=80"))
                return True

            parts = params.split(maxsplit=1)
            model_name = parts[0].lower()
            args_str = parts[1] if len(parts) > 1 else ""

            tool = SYSTEM_TOOLS.get(model_name)
            if not tool:
                await self.post(Note(f"未知模型: {model_name}。可用: gaussian_plume, noise_attenuation, dispersion_coeff"))
                return True

            try:
                args = {}
                for m in re.finditer(r'(\w+)=([\d.]+|(?:\w+))', args_str):
                    key = m.group(1)
                    val = m.group(2)
                    try:
                        args[key] = float(val)
                    except ValueError:
                        args[key] = val

                result_lines = [f"## 📐 {tool['name']} 计算", "", f"**公式**: {tool.get('formula', '无')}", "", "**输入参数**:"]
                for k, v in args.items():
                    result_lines.append(f"- {k} = {v}")

                if model_name == "gaussian_plume" and all(k in args for k in ("Q", "u", "x")):
                    Q, u, x = args["Q"], args["u"], args["x"]
                    y = args.get("y", 0)
                    z = args.get("z", 0)
                    He = args.get("He", 0)
                    stability = args.get("stability", "D")

                    # Pasquill-Gifford coefficients for stability class
                    pg_coeff = {
                        "A": (0.527, 0.865, 0.28, 0.90),
                        "B": (0.371, 0.866, 0.23, 0.85),
                        "C": (0.209, 0.897, 0.22, 0.80),
                        "D": (0.128, 0.905, 0.20, 0.76),
                        "E": (0.098, 0.902, 0.15, 0.73),
                        "F": (0.065, 0.902, 0.12, 0.67),
                    }
                    a1, b1, a2, b2 = pg_coeff.get(stability.upper(), pg_coeff["D"])
                    sigma_y = a1 * (x ** b1)
                    sigma_z = a2 * (x ** b2)

                    C = (Q / (2 * math.pi * u * sigma_y * sigma_z)) * \
                        math.exp(-y**2 / (2 * sigma_y**2)) * \
                        (math.exp(-(z - He)**2 / (2 * sigma_z**2)) + math.exp(-(z + He)**2 / (2 * sigma_z**2)))

                    result_lines.append("")
                    result_lines.append("**计算结果**:")
                    result_lines.append(f"- σy = {sigma_y:.2f} m")
                    result_lines.append(f"- σz = {sigma_z:.2f} m")
                    result_lines.append(f"- C = {C:.6f} g/m³ = {C*1e6:.2f} μg/m³")
                    result_lines.append("")
                    result_lines.append(f"**标准对比** ({tool.get('standard', 'N/A')}):")
                    C_ug = C * 1e6
                    if C_ug < 150:
                        result_lines.append(f"  ✅ 一级标准 ({'小时均值 150μg/m³' if 'SO2' in str(args) else '日均 150μg/m³'}) — 达标")
                    elif C_ug < 500:
                        result_lines.append(f"  ⚠️ 二级标准 (500μg/m³) — 达标，一级超标")
                    else:
                        result_lines.append(f"  ❌ 二级标准 (500μg/m³) — 超标 {C_ug/150:.1f} 倍")

                elif model_name == "noise_attenuation" and all(k in args for k in ("Lw", "r")):
                    Lw, r = args["Lw"], args["r"]
                    Lp = Lw - 20 * math.log10(r) - 11
                    result_lines.append("")
                    result_lines.append("**计算结果**:")
                    result_lines.append(f"- Lp = {Lp:.1f} dB")
                    result_lines.append("")
                    result_lines.append(f"**标准对比** (GB3096-2008):")
                    if Lp < 50:
                        result_lines.append("  ✅ 0类 (疗养区 50dB) — 达标")
                    elif Lp < 55:
                        result_lines.append("  ✅ 1类 (居住区 55dB) — 达标")
                    elif Lp < 60:
                        result_lines.append("  ⚠️ 2类 (商业区 60dB) — 达标")
                    elif Lp < 65:
                        result_lines.append("  ⚠️ 3类 (工业区 65dB) — 达标")
                    else:
                        result_lines.append("  ❌ 超标 — 需要降噪措施")

                elif model_name == "dispersion_coeff" and "x" in args and "stability" in args:
                    x = args["x"]
                    stability = str(args["stability"]).upper()
                    pg_coeff = {
                        "A": (0.527, 0.865, 0.28, 0.90),
                        "B": (0.371, 0.866, 0.23, 0.85),
                        "C": (0.209, 0.897, 0.22, 0.80),
                        "D": (0.128, 0.905, 0.20, 0.76),
                        "E": (0.098, 0.902, 0.15, 0.73),
                        "F": (0.065, 0.902, 0.12, 0.67),
                    }
                    a1, b1, a2, b2 = pg_coeff.get(stability, pg_coeff["D"])
                    sigma_y = a1 * (x ** b1)
                    sigma_z = a2 * (x ** b2)
                    result_lines.append("")
                    result_lines.append("**计算结果**:")
                    result_lines.append(f"- σy = {sigma_y:.2f} m")
                    result_lines.append(f"- σz = {sigma_z:.2f} m")

                else:
                    result_lines.append("")
                    result_lines.append(f"[yellow]需要参数: {' '.join(tool['params'].keys())}[/yellow]")

                await self.post(Note("\n".join(result_lines)))
            except Exception as e:
                await self.post(Note(f"[red]计算错误: {e}[/red]"))
            return True

        elif command == "sysinfo":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.observability.system_monitor import get_monitor
            m = get_monitor()
            stats = m.get_stats()
            snap = stats["snapshot"]
            lines = [
                "## 📊 系统资源",
                f"- {snap}",
                f"- 已延迟任务: {stats['deferred']}",
                f"- 连续跳过: {stats['consecutive_skips']}",
                "",
                "**阈值 (环境变量可配):**",
                f"- CPU 上限: {stats['thresholds']['cpu_high']}% (重任务: {stats['thresholds']['cpu_idle']}%)",
                f"- 内存上限: {stats['thresholds']['mem_high']}%",
                f"- 内存最低: {stats['thresholds']['mem_low_mb']}MB",
            ]
            await self.post(Note("\n".join(lines)))
            return True

        elif command == "render":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.template_engine import get_template_engine
            parts = params.split(maxsplit=2) if params else []
            if len(parts) < 2:
                await self.post(Note("用法: /render <模板> <键=值...>"))
                await self.post(Note("示例: /render 报告.md 项目名=XX大桥 日期=2026-05"))
                return True
            hub = getattr(self.app, 'hub', None)
            engine = get_template_engine()
            tpl_path, raw_args = parts[0], parts[1]
            context = {}
            if "=" in raw_args:
                for kv in raw_args.replace("  ", " ").split():
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        context[k.strip()] = v.strip()
            result = await engine.instantiate(tpl_path, context, hub=hub)
            lines = [
                f"## ✨ 模板渲染: {Path(result.path).name}",
                f"变量: {result.variables_found} 个 / 填充 {result.variables_filled} 个",
                result.preview,
            ]
            if result.applied:
                lines.append(f"[green]✓ 已输出: {result.path}[/green]")
            if result.variables_missing:
                lines.append(f"[yellow]⚠ 未填充: {result.variables_missing} 个[/yellow]")
            await self.post(Note("\n".join(lines)))
            return True

        elif command == "dedup":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.content_dedup import get_dedup
            parts = params.split() if params else []
            sub = parts[0].lower() if parts else "scan"
            hub = getattr(self.app, 'hub', None)
            dedup = get_dedup()
            if sub == "scan":
                pattern = parts[1] if len(parts) > 1 else "*.py"
                await self.post(Note(f"**🔍 扫描重复代码:** {pattern} ..."))
                report = await dedup.scan(pattern=pattern, hub=hub)
                lines = [f"## 🔍 重复代码扫描 ({report.scanned_files} 文件)", ""]
                if report.duplicate_groups:
                    lines.append(f"### 完全重复 ({len(report.duplicate_groups)} 组)")
                    for d in report.duplicate_groups[:10]:
                        files = ", ".join(Path(f).name for f in d.files)
                        lines.append(f"- [{len(d.files)} 处] {files} (行 {d.lines[0][0]}-{d.lines[0][1]})")
                if report.near_duplicate_groups:
                    lines.append(f"\n### 近似重复 ({len(report.near_duplicate_groups)} 组)")
                    for d in report.near_duplicate_groups[:5]:
                        files = ", ".join(Path(f).name for f in d.files[:4])
                        lines.append(f"- [{len(d.files)} 处] {files}")
                if report.estimated_lines_saved:
                    lines.append(f"\n[bold]💰 合并可节省 ~{report.estimated_lines_saved} 行代码[/bold]")
                if report.suggestion:
                    lines.append(f"\n[dim]{report.suggestion}[/dim]")
                await self.post(Note("\n".join(lines)))
            else:
                await self.post(Note("用法: /dedup scan [文件模式]"))
            return True

        elif command == "patch":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.patch_manager import get_patch_manager
            parts = params.split(maxsplit=3) if params else []
            sub = parts[0].lower() if parts else "list"
            pm = get_patch_manager()
            if sub == "list":
                patches = pm.list_patches()
                if not patches:
                    await self.post(Note("[dim]暂无补丁[/dim]"))
                else:
                    lines = [f"## 📦 补丁列表 ({len(patches)})", ""]
                    for p in patches[:15]:
                        lines.append(f"- **{p.name}** +{p.lines_added}/-{p.lines_removed}")
                    await self.post(Note("\n".join(lines)))
            elif sub == "apply" and len(parts) > 1:
                result = pm.apply(parts[1])
                if result.applied:
                    await self.post(Note(f"[green]✓ 补丁已应用: {result.name} ({len(result.files_changed)} 文件, +{result.lines_added}/-{result.lines_removed})[/green]"))
                else:
                    await self.post(Note(f"[red]补丁应用失败: {result.error or '未知错误'}[/red]"))
            elif sub == "revert" and len(parts) > 1:
                result = pm.revert(parts[1])
                if result.reverted:
                    await self.post(Note(f"[green]✓ 已回滚: {result.name}[/green]"))
                else:
                    await self.post(Note(f"[red]回滚失败: {result.error}[/red]"))
            elif sub == "gen" and len(parts) > 1:
                hub = getattr(self.app, 'hub', None)
                if hub and hub.world:
                    result = await pm.llm_patch(parts[1], parts[2] if len(parts) > 2 else "", hub)
                    await self.post(Note(f"补丁生成: {result.name} +{result.lines_added}/-{result.lines_removed}"))
            else:
                await self.post(Note("用法: /patch list|apply <补丁名>|revert <补丁名>"))
            return True

        elif command == "backup":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.semantic_backup import get_semantic_backup
            parts = params.split(maxsplit=1) if params else []
            sub = parts[0].lower() if parts else "list"
            sb = get_semantic_backup()
            if sub == "list":
                all_backups = sb.list_all()
                if not all_backups:
                    await self.post(Note("[dim]暂无备份[/dim]"))
                else:
                    lines = [f"## 💾 备份文件 ({sum(len(v) for v in all_backups.values())} 个)", ""]
                    for path, entries in sorted(all_backups.items()):
                        fname = Path(path).name
                        latest = entries[0]
                        ts = time.strftime("%m-%d %H:%M", time.localtime(latest.timestamp))
                        lines.append(f"- **{fname}** ({len(entries)} 版) | {ts}: {latest.message[:60]}")
                    await self.post(Note("\n".join(lines)))
            elif sub == "save" and len(parts) > 1:
                hub = getattr(self.app, 'hub', None)
                result = await sb.backup(parts[1], hub=hub)
                if result.backed_up:
                    await self.post(Note(f"💾 已备份: {result.path.name} → {result.message[:80]}"))
                else:
                    await self.post(Note(f"[red]备份失败: 文件不存在[/red]"))
            elif sub == "restore" and len(parts) > 1:
                args = parts[1].split(maxsplit=1)
                filepath = args[0]
                identifier = args[1] if len(args) > 1 else ""
                result = await sb.restore(filepath, identifier)
                if result.backup_path:
                    await self.post(Note(f"♻ 已恢复: {result.path.name} ← {result.message[:80]}"))
                else:
                    await self.post(Note(f"[red]未找到备份[/red]"))
            elif sub == "prune" and len(parts) > 1:
                args = parts[1].split()
                filepath = args[0]
                keep = int(args[1]) if len(args) > 1 else 10
                sb.prune(filepath, keep)
                await self.post(Note(f"🧹 保留最近 {keep} 个备份"))
            else:
                await self.post(Note("用法: /backup list|save <文件>|restore <文件> [时间/关键词]|prune <文件> [数量]"))
            return True

        elif command == "watch":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.file_watcher import get_file_watcher
            parts = params.split() if params else []
            sub = parts[0].lower() if parts else "start"
            watcher = get_file_watcher()
            if sub == "start":
                hub = getattr(self.app, 'hub', None)
                interval = int(parts[1]) if len(parts) > 1 else 30
                await self.post(Note(f"👁 FileWatcher 已启动 (间隔 {interval}s)"))
                asyncio.create_task(watcher.start(hub=hub, interval=interval))
            elif sub == "stop":
                watcher.stop()
                await self.post(Note("FileWatcher 已停止"))
            else:
                await self.post(Note("用法: /watch start [间隔秒] | stop"))
            return True

        elif command == "history":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.semantic_backup import get_semantic_backup
            if not params:
                await self.post(Note("用法: /history <文件名> — 查看文件的所有备份版本"))
                return True
            sb = get_semantic_backup()
            entries = sb.list(params.strip())
            if not entries:
                await self.post(Note(f"[dim]文件 {params} 暂无备份[/dim]"))
            else:
                lines = [f"## 📜 {Path(params).name} 版本历史 ({len(entries)})", ""]
                for e in entries[:20]:
                    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(e.timestamp))
                    size_kb = e.size / 1024
                    lines.append(f"- **{ts}** {size_kb:.1f}KB")
                    if e.message:
                        lines.append(f"  {e.message[:100]}")
                await self.post(Note("\n".join(lines)))
            return True

        elif command == "web":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.tool_executor import get_executor
            if not params:
                await self.post(Note("用法: /web <URL> — 获取网页内容（自动提取表格/列表/标题）"))
                return True
            exe = get_executor()
            r = await exe.url_fetch(params.strip())
            await self.post(Note(f"🌐 {r.output[:5000]}" if r.success else f"[red]Web error: {r.error}[/red]"))
            return True

        elif command == "sql":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.tool_executor import get_executor
            parts = params.split(maxsplit=2) if params else []
            if len(parts) < 2:
                await self.post(Note("用法: /sql query <SQL> [db_path] | schema <db_path> [table]"))
                return True
            exe = get_executor()
            sub = parts[0].lower()
            if sub == "query":
                db = parts[2] if len(parts) > 2 else ":memory:"
                r = exe.db_query(parts[1], db)
                await self.post(Note(f"🗄 SQL:\n{r.output[:3000]}" if r.success else f"[red]DB error: {r.error}[/red]"))
            elif sub == "schema":
                db = parts[1]
                table = parts[2] if len(parts) > 2 else ""
                r = exe.db_schema(db, table)
                await self.post(Note(f"📋 SCHEMA:\n{r.output[:3000]}" if r.success else f"[red]Schema error: {r.error}[/red]"))
            return True

        elif command == "git":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.tool_executor import get_executor
            parts = params.split(maxsplit=1) if params else []
            sub = parts[0].lower() if parts else "log"
            exe = get_executor()
            arg = parts[1] if len(parts) > 1 else ""
            if sub == "log":
                n = int(arg) if arg.isdigit() else 10
                r = exe.git_log(n=n)
                await self.post(Note(f"📜 GIT LOG:\n```\n{r.output[:5000]}\n```" if r.success else f"[red]Git error: {r.error}[/red]"))
            elif sub == "diff":
                r = exe.git_diff(path=arg)
                await self.post(Note(f"📊 GIT DIFF:\n```diff\n{r.output[:5000]}\n```" if r.success else f"[red]Git error: {r.error}[/red]"))
            elif sub == "blame" and arg:
                r = exe.git_blame(arg)
                await self.post(Note(f"🔎 GIT BLAME:\n```\n{r.output[:3000]}\n```" if r.success else f"[red]Git error: {r.error}[/red]"))
            else:
                await self.post(Note("用法: /git log [N] | diff [path] | blame <file>"))
            return True

        elif command == "shell":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.tool_executor import get_executor
            exe = get_executor()
            if not params:
                await self.post(Note("用法: /shell <命令>"))
                return True
            r = await exe.run_command(params.strip())
            await self.post(Note(f"⚡ CMD:\n```\n{r.output[:5000]}\n```" if r.success else f"[red]Shell error ({r.elapsed_ms:.0f}ms): {r.error}[/red]"))
            return True

        elif command == "debate":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.tool_meta import get_tool_meta
            parts = params.split(maxsplit=2) if params else []
            if not params:
                await self.post(Note("用法: /debate <主题> [角色列表] [轮数]"))
                await self.post(Note("默认: 全栈工程师, 产品经理, 数据分析师 × 3轮"))
                return True
            hub = getattr(self.app, 'hub', None)
            meta = get_tool_meta()
            topic = parts[0]
            roles = parts[1].split(",") if len(parts) > 1 else None
            rounds = int(parts[2]) if len(parts) > 2 else 3
            await self.post(Note(f"**🗣 辩论开始:** {topic}"))
            result = await meta.debate(topic, roles=roles, rounds=rounds, hub=hub)
            lines = [f"## 🗣 辩论结果: {topic}", ""]
            for role, pos in result.positions.items():
                lines.append(f"### {role}")
                lines.append(f"{pos[:300]}")
            if result.consensus:
                lines.append(f"\n### 🎯 共识\n{result.consensus[:1000]}")
            if result.voting:
                lines.append(f"\n### 📊 评分\n" + " | ".join(f"{r}:{s}/5" for r, s in result.voting.items()))
            await self.post(Note("\n".join(lines)))
            return True

        elif command == "snapshot":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.tool_orchestrator import get_orchestrator
            parts = params.split(maxsplit=1) if params else []
            sub = parts[0].lower() if parts else "list"
            orch = get_orchestrator()
            if sub == "list":
                snaps = orch.snapshot_list()
                if not snaps:
                    await self.post(Note("[dim]暂无快照[/dim]"))
                else:
                    lines = [f"## 📸 快照 ({len(snaps)})", ""]
                    for s in snaps[:15]:
                        ts = time.strftime("%m-%d %H:%M", time.localtime(s.timestamp))
                        lines.append(f"- **{s.name}** [{ts}] | 工具:{s.tool_state.get('tools_count', '?')} 技能:{s.tool_state.get('skills_count', '?')}")
                    await self.post(Note("\n".join(lines)))
            elif sub == "save":
                name = parts[1] if len(parts) > 1 else ""
                snap = orch.snapshot_save(name)
                await self.post(Note(f"📸 快照已保存: {snap.name}"))
            elif sub == "restore" and len(parts) > 1:
                ok = orch.snapshot_restore(parts[1])
                await self.post(Note(f"♻ 快照已恢复: {parts[1]}" if ok else f"[red]快照 {parts[1]} 未找到[/red]"))
            else:
                await self.post(Note("用法: /snapshot list|save [name]|restore <name>"))
            return True

        elif command == "evolvetool":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.tool_meta import get_tool_meta
            parts = params.split(maxsplit=1) if params else []
            if len(parts) < 2:
                await self.post(Note("用法: /evolvetool <工具名> <错误日志>"))
                return True
            hub = getattr(self.app, 'hub', None)
            meta = get_tool_meta()
            result = await meta.self_evolve(parts[0], parts[1], hub=hub)
            lines = [f"## 🧬 工具进化: {result.tool_name}"]
            if result.improvement:
                lines.append(f"改进: {result.improvement[:300]}")
            if result.applied:
                lines.append(f"[green]✓ 热修复已保存到 .livingtree/hotfixes/[/green]")
            else:
                lines.append("[dim]未生成修复方案[/dim]")
            await self.post(Note("\n".join(lines)))
            return True

        elif command == "modify":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.self_modifier import get_self_modifier
            if not params:
                await self.post(Note("用法: /modify <功能描述> — LLM 自动修改自己的代码"))
                await self.post(Note("示例: /modify 添加 WebSocket 实时推送"))
                return True
            hub = getattr(self.app, 'hub', None)
            sm = get_self_modifier()
            await self.post(Note(f"**🔧 自我修改:** {params}"))
            result = await sm.modify(params, hub)
            lines = [f"## 🔧 修改结果", f"任务: {result.task}"]
            if result.files_changed:
                lines.append(f"\n文件: {', '.join(Path(f).name for f in result.files_changed[:5])}")
            if result.diff_summary:
                lines.append(f"{result.diff_summary}")
            if result.test_result:
                lines.append(f"\n测试: {result.test_result}")
            if result.success and not result.rolled_back:
                lines.append(f"\n[green]✓ 已应用 - 使用 /git diff 查看变化[/green]")
            elif result.rolled_back:
                lines.append(f"\n[red]已回滚 - {result.error or '导入验证失败'}[/red]")
            else:
                lines.append(f"\n[red]失败: {result.error}[/red]")
            await self.post(Note("\n".join(lines)))
            return True

        elif command == "consolidate":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.idle_consolidator import get_idle_consolidator
            ic = get_idle_consolidator()
            entries = ic.recent_consolidations(10)
            if not entries:
                await self.post(Note("[dim]暂无巩固记录。系统会在空闲时自动整理对话知识。[/dim]"))
            else:
                lines = [f"## 🧠 知识巩固 ({len(entries)} 条)", ""]
                for e in entries:
                    tags = " ".join(f"`{t}`" for t in e.tags[:4]) if hasattr(e, 'tags') else ""
                    ts = time.strftime("%H:%M", time.localtime(e.timestamp))
                    lines.append(f"**[{ts}]** {e.topic[:80]}")
                    lines.append(f"  {e.summary[:120]}")
                    if tags:
                        lines.append(f"  {tags}")
                await self.post(Note("\n".join(lines)))
            return True

        elif command == "market":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.agent_marketplace import get_marketplace
            parts = params.split(maxsplit=1) if params else []
            sub = parts[0].lower() if parts else "list"
            am = get_marketplace()
            if sub == "list":
                items = am.search()
                if not items:
                    await self.post(Note("[dim]市场暂无技能/工具[/dim]"))
                else:
                    lines = [f"## 🏪 技能市场 ({len(items)} 项)", ""]
                    for item in items[:15]:
                        icon = "🔧" if item.type == "tool" else "🧩"
                        lines.append(f"{icon} **{item.name}** [{item.type}]")
                        lines.append(f"  {item.description[:100]}")
                        if item.author and item.author != "self":
                            lines.append(f"  [dim]by {item.author[:20]}[/dim]")
                    lines.append("\n/discover — 从P2P网络发现新技能")
                    await self.post(Note("\n".join(lines)))
            elif sub == "discover":
                hub = getattr(self.app, 'hub', None)
                new_items = await am.discover_skills(hub)
                await self.post(Note(f"🔍 发现 {len(new_items)} 个新技能/工具"))
            elif sub == "publish" and len(parts) > 1:
                args = parts[1].split(maxsplit=2)
                name = args[0]; desc = args[1] if len(args) > 1 else ""
                code = args[2] if len(args) > 2 else ""
                if code:
                    am.publish_tool(name, code, desc)
                else:
                    am.publish_skill(name, desc or name)
                await self.post(Note(f"✓ 已发布: {name}"))
            else:
                await self.post(Note("用法: /market list|discover|publish <名> <描述> [代码]"))
            return True

        elif command == "synthesize":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.tool_synthesis import get_tool_synthesizer
            if not params:
                await self.post(Note("用法: /synthesize <任务描述> — LLM 现场生成工具代码"))
                await self.post(Note("示例: /synthesize 对比两个CSV的第三列差异"))
                return True
            hub = getattr(self.app, 'hub', None)
            ts = get_tool_synthesizer()
            await self.post(Note(f"**🔧 工具合成中:** {params}"))
            result = await ts.synthesize(params, hub)
            if result.registered and result.tool:
                lines = [
                    f"## 🔧 工具合成完成",
                    f"**{result.tool.name}** v{result.tool.version} [{result.tool.category}]",
                    f"描述: {result.tool.description}",
                    f"成功: {result.tool.success_count} | 失败: {result.tool.fail_count}",
                ]
                if result.output:
                    lines.append(f"\n测试输出:\n```\n{result.output[:2000]}\n```")
                lines.append(f"\n[green]✓ 已注册为永久工具 — 现在可用于 /synthesize 或其他调用[/green]")
                await self.post(Note("\n".join(lines)))
            else:
                await self.post(Note(f"[red]合成失败: {result.error}[/red]"))
            return True

        elif command == "continue":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.session_continuity import get_session_continuity
            sc = get_session_continuity()
            state = sc.load()
            if not state:
                await self.post(Note("[dim]没有上一轮的会话记录[/dim]"))
            else:
                text = sc.resume_text()
                files = "\n".join(f"- {f}" for f in state.open_files[:5]) if state.open_files else ""
                lines = [
                    text,
                    "",
                    "[dim]--- 上次会话详情 ---[/dim]",
                    f"[dim]文件:[/dim]" if files else "",
                    files,
                    f"\n[dim]时长: {state.session_duration_minutes:.0f}分钟 | 决策: {len(state.decisions_made)}[/dim]",
                ]
                await self.post(Note("\n".join(lines)))
            return True

        elif command == "activity":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.observability.activity_feed import get_activity_feed
            feed = get_activity_feed()
            parts = params.split() if params else []
            filter_type = parts[0] if parts else ""
            events = feed.query(limit=30, event_type=filter_type)
            if not events:
                await self.post(Note("[dim]暂无活动记录[/dim]"))
            else:
                lines = [f"## 📡 活动流 ({len(events)} 条)"]
                if not filter_type:
                    lines.append("[dim]/activity election|tool_call|cache|eval|synthesize|modify|consolidate|error[/dim]")
                lines.append("")
                for e in events:
                    icon = {"election": "⚡", "tool_call": "🔧", "cache": "💾", "eval": "📊",
                            "synthesize": "🔧", "modify": "✏️", "consolidate": "🧠",
                            "error": "❌", "system": "🖥"}.get(e.type, "•")
                    ts = time.strftime("%H:%M:%S", time.localtime(e.timestamp))
                    lines.append(f"{icon} `{ts}` **{e.agent[:20]}** {e.message[:120]}")
                lines.append(f"\n{feed.summary_24h()}")
                await self.post(Note("\n".join(lines)))
            return True

        elif command == "eval":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.observability.agent_eval import get_eval
            ev = get_eval()
            parts = params.split() if params else []
            sub = parts[0].lower() if parts else "components"
            if sub == "components" or sub == "comp":
                reports = ev.all_component_reports()
                if not reports:
                    await self.post(Note("[dim]暂无组件评估数据[/dim]"))
                else:
                    lines = [f"## 📊 组件评测 ({len(reports)} 个)", ""]
                    sorted_r = sorted(reports.values(), key=lambda r: -r.total_calls)
                    for cm in sorted_r[:15]:
                        health = "🟢" if cm.success_rate > 0.95 else "🟡" if cm.success_rate > 0.8 else "🔴"
                        lines.append(
                            f"{health} **{cm.tool}** | "
                            f"成功率:{cm.success_rate:.0%} | "
                            f"调用:{cm.total_calls} | "
                            f"P50:{cm.p50_ms:.0f}ms P95:{cm.p95_ms:.0f}ms"
                        )
                    await self.post(Note("\n".join(lines)))
            elif sub == "drift":
                drifts = ev.drift_status()
                if not drifts:
                    await self.post(Note("[dim]暂无漂移数据（需至少10次评估）[/dim]"))
                else:
                    lines = [f"## 📉 漂移检测", ""]
                    for agent, d in drifts.items():
                        alert = "🔴" if d.alert else "🟢"
                        lines.append(
                            f"{alert} **{agent}** | "
                            f"基线:{d.baseline_score:.2f} → 当前:{d.current_score:.2f} | "
                            f"漂移:{d.drift_pct:.1f}% (阈值:{d.threshold:.0f}%)"
                        )
                    await self.post(Note("\n".join(lines)))
            elif sub == "output":
                evals = ev.recent_output_evals(10)
                if not evals:
                    await self.post(Note("[dim]暂无输出评测[/dim]"))
                else:
                    lines = [f"## 🎯 输出评测 ({len(evals)} 次)", ""]
                    for e in evals[-10:]:
                        icon = "🟢" if e.level == "pass" else "🟡" if e.level == "warn" else "🔴"
                        lines.append(f"{icon} **{e.agent}** score={e.score:.2f} | {e.task[:60]}")
                        if e.feedback:
                            lines.append(f"  {e.feedback[:120]}")
                    await self.post(Note("\n".join(lines)))
            else:
                await self.post(Note("用法: /eval components|drift|output"))
            return True

        elif command == "trust":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.observability.trust_scoring import get_trust_scorer
            ts = get_trust_scorer()
            parts = params.split() if params else []
            sub = parts[0].lower() if parts else "all"
            if sub == "profile" and len(parts) > 1:
                ts.set_profile(parts[1])
                await self.post(Note(f"✓ 安全配置切换为: {parts[1]} (阈值:{ts.PROFILE_THRESHOLDS.get(parts[1],60)})"))
            elif sub == "all" or sub == "list":
                summary = ts.summary()
                lines = [
                    f"## 🛡 信任评分 ({summary['agents']} 个智能体)",
                    f"平均: {summary['avg_score']}/100 | 配置: {summary['profile']} (阈值:{summary['threshold']})",
                    f"最低: {summary.get('lowest_agent','?')} ({summary.get('lowest_score','?')})",
                    "",
                ]
                for name, p in summary.get("all", {}).items():
                    lines.append(f"{p['level']} **{name}** | {p['score']}/{p['calls']}次 | 成功率:{p['success_rate']}%")
                await self.post(Note("\n".join(lines)))
            else:
                score = ts.score(sub)
                level = ts.trust_level(sub)
                can = ts.can_auto_approve(sub)
                lines = [
                    f"## 🛡 {sub}",
                    f"分数: {score:.1f}/100 {level}",
                    f"自动审批: {'✅ 通过' if can else '❌ 需要审查'}",
                ]
                await self.post(Note("\n".join(lines)))
            return True

        elif command == "branch":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.conversation_branch import get_conversation_brancher
            cb = get_conversation_brancher()
            parts = params.split(maxsplit=1) if params else []
            sub = parts[0].lower() if parts else "list"
            if sub == "list" or sub == "tree":
                tree = cb.render_tree()
                await self.post(Note(tree))
            elif sub == "fork" and len(parts) > 1:
                args = parts[1].split(maxsplit=1)
                name = args[0]
                snapshot = args[1] if len(args) > 1 else ""
                cb.fork(name, snapshot)
                await self.post(Note(f"🌿 已分叉: {name}"))
            elif sub == "switch" and len(parts) > 1:
                branch = cb.switch(parts[1])
                if branch:
                    await self.post(Note(f"🔄 已切换: {branch.name} ({len(branch.turns)}轮)"))
                else:
                    await self.post(Note(f"[red]分支 {parts[1]} 不存在[/red]"))
            elif sub == "merge" and len(parts) > 1:
                args = parts[1].split(maxsplit=1)
                branch = cb.merge(args[0], args[1] if len(args) > 1 else "")
                if branch:
                    await self.post(Note(f"✅ 已合并: {branch.name} → {branch.merged_into}"))
                else:
                    await self.post(Note(f"[red]合并失败[/red]"))
            elif sub == "abandon" and len(parts) > 1:
                branch = cb.abandon(parts[1])
                if branch:
                    await self.post(Note(f"❌ 已放弃: {branch.name}"))
            else:
                await self.post(Note("用法: /branch list|fork <名> [上下文]|switch <名>|merge <名> [摘要]|abandon <名>"))
            return True

        elif command == "semdiff":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.semantic_diff import get_semantic_diff
            hub = getattr(self.app, 'hub', None)
            sd = get_semantic_diff()
            target = params.strip() if params else ""
            await self.post(Note(f"**📊 语义差异分析...**"))
            explanation = await sd.explain_diff(hub, target=target)
            result = sd.format(explanation)
            await self.post(Note(result))
            return True

        elif command == "selfdocs":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.self_documentation import get_self_documenter
            hub = getattr(self.app, 'hub', None)
            sdoc = get_self_documenter()
            await self.post(Note("**📝 自动生成系统文档...**"))
            doc = await sdoc.generate(hub)
            lines = [
                f"## 📝 {doc.title}",
                f"已保存到 .livingtree/self_docs/",
                f"",
                f"包含章节:",
            ]
            if doc.feature_timeline: lines.append("  ✅ 功能时间线")
            if doc.provider_stats: lines.append("  ✅ Provider 使用统计")
            if doc.tool_inventory: lines.append("  ✅ 工具清单")
            if doc.architecture: lines.append("  ✅ 架构图")
            if doc.known_issues: lines.append("  ✅ 已知问题")
            if doc.security: lines.append("  ✅ 安全建议")
            await self.post(Note("\n".join(lines)))
            return True

        elif command == "deepsearch":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.network.external_access import get_external_access
            if not params:
                await self.post(Note("用法: /deepsearch <关键词> — 多引擎聚合搜索+LLM重排"))
                return True
            hub = getattr(self.app, 'hub', None)
            ext = get_external_access()
            await self.post(Note(f"**🔍 深度搜索:** {params}"))
            results = await ext.deep_search(params, hub=hub)
            if not results:
                await self.post(Note("[dim]所有搜索引擎均无结果[/dim]"))
            else:
                lines = [f"## 🔍 深度搜索: {params} ({len(results)} 条)", ""]
                for r in results:
                    score_str = f" [{r.relevance:.0%}]" if r.relevance else ""
                    lines.append(f"**{r.title[:100]}** {score_str}")
                    lines.append(f"  [dim]{r.url[:120]}[/dim]")
                    if r.snippet:
                        lines.append(f"  {r.snippet[:150]}")
                    lines.append(f"  [dim]引擎: {r.engine}[/dim]")
                await self.post(Note("\n".join(lines)))
            return True

        elif command == "ghmirror":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.network.external_access import get_external_access
            parts = params.split(maxsplit=1) if params else []
            sub = parts[0].lower() if parts else "watch"
            ext = get_external_access()
            if sub == "watch" and len(parts) > 1:
                info = await ext.gh_watch(parts[1])
                if info:
                    lines = [f"## 📦 {info.repo}", f"版本: {info.tag} ({info.name})", f"发布时间: {info.published_at}"]
                    if info.assets:
                        lines.append("\n下载:")
                        for a in info.assets:
                            lines.append(f"  - {a['name']} ({a['size']/1024/1024:.1f}MB)")
                    await self.post(Note("\n".join(lines)))
                else:
                    await self.post(Note(f"[red]无法获取 {parts[1]} 的发布信息[/red]"))
            elif sub == "list":
                watched = ext.github.watched_status()
                if not watched:
                    await self.post(Note("[dim]未监控任何仓库[/dim]"))
                else:
                    lines = [f"## 📦 监控的仓库 ({len(watched)})", ""]
                    for repo, info in watched.items():
                        lines.append(f"- **{repo}** → {info.tag} ({info.name})")
                    await self.post(Note("\n".join(lines)))
            else:
                await self.post(Note("用法: /ghmirror watch <user/repo> | list"))
            return True

        elif command == "dns":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.network.external_access import get_external_access
            if not params:
                await self.post(Note("用法: /dns <域名> — DNS-over-HTTPS解析（绕过DNS污染）"))
                return True
            ext = get_external_access()
            result = await ext.dns_lookup(params.strip())
            lines = [
                f"## 🌐 DNS: {result.domain}",
                f"Provider: {result.provider} | TTL: {result.ttl}s",
                f"{'[dim]缓存命中[/dim]' if result.cached else '实时查询'}",
                "",
            ]
            for ip in result.ips:
                lines.append(f"  → {ip}")
            if not result.ips:
                lines.append("  [red]解析失败[/red]")
            await self.post(Note("\n".join(lines)))
            return True

        elif command == "lineage":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.data_lineage import get_data_lineage
            dl = get_data_lineage()
            parts = params.split() if params else []
            node_id = parts[0] if parts else ""
            if node_id:
                ancestors = dl.trace_backward(node_id)
                descendants = dl.trace_forward(node_id)
                lines = [f"## 🔗 数据血缘: {node_id}", ""]
                lines.append("### ↑ 上游 (来源)")
                if ancestors:
                    for n in ancestors[:10]:
                        icon = {"user_provided": "👤", "computed": "🔢", "learned": "📚", "assumed": "⚠️"}.get(n.derivation, "•")
                        lines.append(f"{icon} **{n.id}** = {n.value} {n.unit} [{n.derivation}]")
                else:
                    lines.append("  (无上游 — 根数据)")
                lines.append("\n### ↓ 下游 (影响)")
                if descendants:
                    for n in descendants[:10]:
                        lines.append(f"  → **{n.id}** = {n.value} {n.unit} [{n.derivation}]")
                else:
                    lines.append("  (无下游)")
                await self.post(Note("\n".join(lines)))
            else:
                summary = dl.summary()
                lines = [
                    f"## 🔗 数据血缘",
                    f"节点: {summary['total_nodes']} | "
                    f"根节点: {summary['root_nodes']} | "
                    f"用户提供: {summary['user_provided_pct']:.0f}%",
                    f"高置信: {summary['by_confidence']['high']} | "
                    f"中: {summary['by_confidence']['medium']} | "
                    f"低: {summary['by_confidence']['low']}",
                ]
                await self.post(Note("\n".join(lines)))
            return True

        elif command == "practice":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.adaptive_practice import get_adaptive_practice
            ap = get_adaptive_practice()
            parts = params.split() if params else []
            sub = parts[0].lower() if parts else "report"
            if sub == "report" or sub == "weak":
                report = ap.report()
                lines = [f"## 🎯 自适应学习 — 最弱项 (需练习)", ""]
                for w in report.get("weakest", []):
                    trend_icon = {"improving": "📈", "declining": "📉", "stable": "➡️"}.get(w["trend"], "")
                    lines.append(
                        f"{trend_icon} **{w['template']}/{w['section']}** | "
                        f"分数:{w['score']} | 修改率:{w['mod_rate']}%"
                    )
                if not report["weakest"]:
                    lines.append("暂无足够数据 — 多生成几份报告后自动开始追踪")
                lines.append(f"\n### 🏆 最强项")
                for s in report.get("strongest", [])[:3]:
                    lines.append(f"✅ **{s['template']}/{s['section']}** — {s['score']}")
                await self.post(Note("\n".join(lines)))
            else:
                await self.post(Note("用法: /practice [report]"))
            return True

        elif command == "profile":
            from livingtree.tui.td.widgets.note import Note
            from livingtree.capability.progressive_trust import get_progressive_trust
            pt = get_progressive_trust()
            parts = params.split() if params else []
            username = parts[0] if parts else ""
            if username:
                profile = pt.get_user_profile(username)
                if not profile:
                    await self.post(Note(f"[dim]用户 {username} 暂无数据[/dim]"))
                else:
                    lines = [
                        f"## 👤 {username}",
                        f"交互: {profile['interactions']}次 | 回话: {profile['sessions']}次",
                        f"",
                        f"### 专业领域",
                    ]
                    for domain, exp in profile.get("expertise", {}).items():
                        icon = {"expert": "🟢", "proficient": "🟡", "learning": "🟠", "novice": "🔴"}.get(exp["level"], "")
                        lines.append(f"{icon} **{domain}** — {exp['level']} (skill:{exp['skill']}, 修正率:{exp['correction_rate']}%)")
                    if profile.get("auto_approval_domains"):
                        lines.append(f"\n⏭ 自动通过: {', '.join(profile['auto_approval_domains'])}")
                    await self.post(Note("\n".join(lines)))
            else:
                await self.post(Note("用法: /profile <用户名>"))
            return True

        return False
