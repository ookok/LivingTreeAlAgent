from __future__ import annotations

from textual.app import ComposeResult
from textual import containers

from textual.widgets import Label, Markdown


ASCII_TREE = r"""
          🌳
         /🌿\
        / 🌿 \
       /  🌿  \
      /   🌿   \
     /_________\
       |||||||
       |||||||
  🌱🌱🌱🌱🌱🌱🌱🌱🌱
"""

WELCOME_MD = """\
## 🌳 LivingTree v2.1

Welcome to LivingTree — Digital Life Form AI Agent.

Type a message and press **Ctrl+Enter** to send.
Use **/search** to search the web, **/tools** to see available tools.
"""


class Welcome(containers.Vertical):
    def compose(self) -> ComposeResult:
        with containers.Center():
            yield Label(ASCII_TREE, id="logo")
        yield Markdown(WELCOME_MD, id="message", classes="note")
