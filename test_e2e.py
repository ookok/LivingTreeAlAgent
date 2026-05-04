"""E2E TUI test — focus, activation, navigation."""
import asyncio, sys, os
from pathlib import Path

PROJECT = Path(__file__).parent
LOCAL_T = PROJECT / "livingtree" / "tui" / "textual" / "src"
sys.path.insert(0, str(LOCAL_T.resolve()))
sys.path.insert(0, str(PROJECT.resolve()))
os.chdir(str(PROJECT.resolve()))

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from livingtree.tui.widgets.card import Card

R = {"ok": 0, "ng": 0}

def check(n, c):
    s = "PASS" if c else "FAIL"
    R["ok" if c else "ng"] += 1
    print(f"  [{s}] {n}")
    return c

class MockScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "back")]
    def compose(self): yield Static("Mock")

class TestApp(App):
    SCREENS = {"chat": MockScreen, "code": MockScreen}
    BINDINGS = [("enter", "activate_card", "enter")]

    CSS = """
    Card { width: 1fr; height: 10; border: solid blue; padding: 1 2; margin: 1 1; }
    Card:focus { border: solid yellow; }
    """

    def compose(self):
        yield Static("Test", id="title-bar")
        with VerticalScroll():
            with Horizontal():
                yield Card("Chat Card", "chat")
                yield Card("Code Card", "code")

    def action_activate_card(self):
        f = self.focused
        if isinstance(f, Card):
            self.push_screen(f.screen_name)

async def main():
    print("=" * 50)
    print("TUI E2E Test")
    print("=" * 50)

    app = TestApp()

    async def plan():
        await asyncio.sleep(0.5)
        cards = list(app.query(Card))

        print(f"\n[cards] {len(cards)} mounted")
        check("2 cards", len(cards) == 2)

        # Focus test
        app.set_focus(cards[0])
        await asyncio.sleep(0.2)
        print(f"\n[focus] focused={type(app.focused).__name__}")
        check("card focused", isinstance(app.focused, Card))
        check("is card[0]", app.focused is cards[0])

        # Switch focus
        app.set_focus(cards[1])
        await asyncio.sleep(0.1)
        check("focus card[1]", app.focused is cards[1])

        # CSS check
        print(f"\n[css] card[0] border={cards[0].styles.border}")
        print(f"      card[1] border={cards[1].styles.border}")

        # Screen mapping
        print(f"\n[mapping]")
        check("card[0].screen_name='chat'", cards[0].screen_name == "chat")
        check("card[1].screen_name='code'", cards[1].screen_name == "code")
        check("'chat' in SCREENS", "chat" in app.SCREENS)

        # Action test
        app.set_focus(cards[0])
        await asyncio.sleep(0.1)
        f = app.focused
        check("can activate via focused Card", isinstance(f, Card) and f.screen_name in app.SCREENS)

        app.exit()

    asyncio.create_task(plan())
    await app.run_async()

    print(f"\n{'='*50}")
    print(f"Results: {R['ok']} ok, {R['ng']} fail")
    print(f"{'='*50}")
    return R['ng'] == 0

if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
