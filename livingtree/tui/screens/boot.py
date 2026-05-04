"""Boot splash — life story of a tree 🌱→🌳."""
from __future__ import annotations

import time
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Label

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

# 9-stage tree life story with ASCII art
STAGES = [
    # 0: 幼苗
    {
        "name": "播种育苗",
        "tree": [
            "             🌱",
            "             ╿",
            "         ▂▃▅▆█▆",
            "         ▔▔▔▔▔▔",
        ],
        "deco": "",
        "msg":  "一颗种子落入土壤...",
    },
    # 1: 浇水
    {
        "name": "浇水灌溉",
        "tree": [
            "       💧   💧 ",
            "         🌿    ",
            "       ▗▄▛▘    ",
            "       ▞██▚    ",
            "      ▂████▅   ",
            "      ▔▔▔▔▔▔   ",
        ],
        "deco": "",
        "msg":  "甘露滋润着幼小的生命",
    },
    # 2: 施肥
    {
        "name": "施肥滋养",
        "tree": [
            "         🌳    ",
            "      ▗▄▛▘▝▀▚  ",
            "     ▞████████▚ ",
            "    ▟██████████▙",
            "       ╿  ╿    ",
            "   ▂▅████████▅▂ ",
            "   ▔▔▔▔▔▔▔▔▔▔  ",
        ],
        "deco": "",
        "msg":  "养分渗透根系，茁壮成长",
    },
    # 3: 小树
    {
        "name": "小树初成",
        "tree": [
            "        🌳       ",
            "     ▗▄▛▘▝▀▚▄▖   ",
            "    ▞██████████▚  ",
            "   ▟████████████▙ ",
            "  ▗█████▌ ▐████▖ ",
            "     ╿   ╿      ",
            "  ▂▅█████████▅▂  ",
            "  ▔▔▔▔▔▔▔▔▔▔▔   ",
        ],
        "deco": "",
        "msg":  "一棵小树昂首挺立",
    },
    # 4: 风雨
    {
        "name": "风雨洗礼",
        "tree": [
            "🌬       🌳 🍃  🌧",
            "   ▗▄▛▘▝▀▚▄▖▗▄▛▘",
            "  ▞██████████████▚",
            " ▟████████████████▙",
            "▗██████▌   ▐██████▖",
            "    ╿       ╿     ",
            " ▂▅████████████▅▂  ",
            " ▔▔▔▔▔▔▔▔▔▔▔▔▔   ",
        ],
        "deco": "",
        "msg":  "历经风雨，根系愈加深厚",
    },
    # 5: 开花
    {
        "name": "开花绽放",
        "tree": [
            "🌸     🌳 ✿  🌺   ",
            "  ▗▄▛▘▝▀▚▄▖▗▄▛▘▝▀",
            " ▞████████████████▚",
            "▟██████████████████▙",
            "▗██▛▘▝▀▚▄▖▗▄▛▘▝▀██▖",
            "    ╿   ╿   ╿    ",
            " ▂▅██████████████▅▂",
            " ▔▔▔▔▔▔▔▔▔▔▔▔▔▔  ",
        ],
        "deco": "🌸✿🌺🌷",
        "msg":  "花朵绽放，芬芳四溢",
    },
    # 6: 结果
    {
        "name": "硕果累累",
        "tree": [
            "🍎    🌳 ✿  🍊   ",
            " ▗▄▛▘▝▀▚▄▖▗▄▛▘▝▀ ",
            "▞████████████████▚",
            "▟██████████████████▙",
            "▗██▛▘▝▀▚▄▖▗▄▛▘▝▀██▖",
            "   ╿    ╿    ╿   ",
            "▂▅████████████████▅▂",
            "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔  ",
        ],
        "deco": "🍎🍊🍋🍇",
        "msg":  "硕果累累，丰收在望",
    },
    # 7: 参天
    {
        "name": "参天大树",
        "tree": [
            "🦋   🌳 ✿  🐦   ",
            "╱┃╲╱┃╲╱┃╲╱┃╲╱┃╲",
            "▗▄▛▘▝▀▚▄▖▗▄▛▘▝▀▚▄▖",
            "▞████████████████████▚",
            "▟██████████████████████▙",
            "▗██▛▘▝▀▚▄▖▗▄▛▘▝▀▚▄██▖",
            "  ╿  ╿  ╿  ╿ ╿  ╿ ",
            "▅████████████████████▅ ",
        ],
        "deco": "🦋🐦🐛🌿",
        "msg":  "参天大树，生机盎然",
    },
    # 8: 栖息
    {
        "name": "生命栖息",
        "tree": [
            "🦋 ✿ 🦉 🌳 🐦 ✿ 🦋",
            "╱┃╲╱┃╲╱┃╲╱┃╲╱┃╲╱┃╲",
            "▗▄▛▘▝▀▚▄▖▗▄▛▘▝▀▚▄▖▗▄",
            "▞██████████████████████▚",
            "▟████████████████████████▙",
            "▗██▛▘▝▀▚▄▖▗▄▛▘▝▀▚▄▖▗██▖",
            " ╿  ╿  ╿  ╿ ╿  ╿  ╿ ",
            "🚶▅████████████████████▅🚶",
        ],
        "deco": "🦋🐦🦉🚶🌿🍃",
        "msg":  "万物共生，生命之树永存",
    },
]

POEMS = [
    "一粒种子沉入黑暗，\n等待第一缕光的召唤。",
    "水滴石穿，甘露滋养，\n生命在寂静中悄然萌动。",
    "根系向深处探寻，\n汲取大地的智慧与力量。",
    "嫩芽破土而出，\n向着天空伸展稚嫩的枝桠。",
    "狂风骤雨无法摧折，\n每一次摇晃都让根系更深一寸。",
    "花朵在晨露中绽放，\n芬芳是生命最温柔的语言。",
    "果实压弯了枝头，\n那是时间赠予坚守者的礼物。",
    "绿荫如盖，遮天蔽日，\n一棵树就是一座庙宇。",
    "蝴蝶驻足，飞鸟筑巢，\n所有的生命都找到了归宿。",
]


class BootScreen(Screen):
    """LivingTree — the life story of a tree."""

    CSS = """
    BootScreen {
        align: center middle;
        background: $surface;
    }
    #boot-box {
        width: 54;
        height: auto;
        border: thick $success;
        background: $panel;
        padding: 2 3;
    }
    #boot-tree {
        content-align: center middle;
        height: 10;
        color: $success;
    }
    #boot-deco {
        content-align: center middle;
        height: 1;
        color: $text-muted;
    }
    #boot-title {
        content-align: center middle;
        height: 1;
        text-style: bold;
        color: $text;
    }
    #boot-sub {
        content-align: center middle;
        height: 1;
        color: $text-muted;
    }
    #boot-gap { height: 1; }
    #boot-steps {
        content-align: center middle;
        height: auto;
        min-height: 2;
    }
    #boot-status {
        content-align: center middle;
        height: 1;
        color: $primary;
    }
    #boot-msg {
        content-align: center middle;
        height: 3;
        color: $text-muted;
        text-style: italic;
    }
    """

    current: int = -1
    done: set[int] = set()
    _tick: int = 0
    _stage: int = 0
    _stage_start: float = 0
    _type_chars: int = 0
    _type_text: str = ""
    _type_full: str = ""
    _timer = None

    def __init__(self, steps: list[str]):
        super().__init__()
        self._step_names = steps + ["完成"]
        self._stage_start = time.time()

    def compose(self) -> ComposeResult:
        with Container(id="boot-box"):
            yield Label("", id="boot-tree")
            yield Label("", id="boot-deco")
            yield Label("LivingTree AI Agent", id="boot-title")
            yield Label("数字生命体 v2.0", id="boot-sub")
            yield Label("", id="boot-gap")
            yield Label("", id="boot-steps")
            yield Label("初始化中...", id="boot-status")
            yield Label("", id="boot-msg")

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.2, self._tick_render)
        self._stage_start = time.time()
        self._type_chars = 0

    def on_unmount(self) -> None:
        if self._timer:
            self._timer.stop()

    def advance(self) -> None:
        if self.current >= 0:
            self.done.add(self.current)

    def _tick_render(self) -> None:
        try:
            self._tick += 1
            elapsed = time.time() - self._stage_start

            # Stage changes every ~1s, or with boot steps
            n = len(self.done)
            target_stage = min(n, len(STAGES) - 1)
            if target_stage > self._stage and elapsed > 0.5:
                self._stage = target_stage
                self._stage_start = time.time()
            elif elapsed > 2.0 and self._stage < len(STAGES) - 1:
                self._stage += 1
                self._stage_start = time.time()

            stage = min(self._stage, len(STAGES) - 1)
            data = STAGES[stage]

            # Render tree with animation
            tree_lines = list(data["tree"])
            s = SPINNER[self._tick % len(SPINNER)]
            if stage < 8:  # not final stage
                # Flicker the canopy
                flicker_row = 2 if stage >= 3 else (1 if stage >= 1 else 0)
                if self._tick % 3 == 0 and len(tree_lines) > flicker_row:
                    tree_lines[flicker_row] = tree_lines[flicker_row].replace("🌳", s)

            trunk_color = "#fea62b" if stage >= 5 else "$success"
            colored = []
            for line in tree_lines:
                if "┃" in line or "╿" in line:
                    colored.append(f"[bold {trunk_color}]{line}[/bold {trunk_color}]")
                else:
                    colored.append(line)
            if stage >= 7:
                colored[-1] = f"[bold $success]{colored[-1]}[/bold $success]"

            self.query_one("#boot-tree", Label).update("\n".join(colored))
            self.query_one("#boot-deco", Label).update(data["deco"])

            # Steps
            parts = []
            for i, name in enumerate(self._step_names):
                if i in self.done:
                    p = "[green]●[/green]"
                elif i == self.current:
                    p = f"[bold #fea62b]{s}[/bold #fea62b]"
                else:
                    p = "[dim]○[/dim]"
                if i > 0:
                    a = "[green]▸[/green]" if i - 1 in self.done else "[dim]▸[/dim]"
                    parts.append(f"{a}")
                parts.append(f"{p}[bold]{name}[/bold]")
            self.query_one("#boot-steps", Label).update(" ".join(parts))

            # Status
            done_total = len(self.done)
            boot_total = len(self._step_names) - 1  # exclude "完成"
            if done_total >= boot_total:
                self.query_one("#boot-status", Label).update("[bold green]✓ 系统就绪[/bold green]")
            else:
                pct = int(done_total / max(boot_total, 1) * 100)
                self.query_one("#boot-status", Label).update(
                    f"[bold #fea62b]{data['name']}  ·  {pct}%[/bold #fea62b]"
                )
            # Typewriter poem
            stage_data = STAGES[self._stage]
            poem = POEMS[self._stage]
            msgs = stage_data["msg"]
            
            # Advance typewriter
            self._type_chars += 1
            shown = poem[:self._type_chars]
            cursor = "▌" if self._tick % 4 < 2 else " "
            type_text = shown + cursor
            
            self.query_one("#boot-msg", Label).update(
                f"[dim italic]{msgs}[/dim italic]\n[bold #fea62b]{type_text}[/bold #fea62b]"
            )
        except Exception:
            pass
