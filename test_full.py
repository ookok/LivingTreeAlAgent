"""Full TUI integration test — runs complete LivingTreeTuiApp."""
import asyncio, sys, os
from pathlib import Path

PROJECT = Path(__file__).parent
sys.path.insert(0, str((PROJECT / "livingtree" / "tui" / "textual" / "src").resolve()))
sys.path.insert(0, str(PROJECT.resolve()))
os.chdir(str(PROJECT.resolve()))

from textual.screen import Screen
from livingtree.tui.widgets.card import Card
from livingtree.tui.app import LivingTreeTuiApp

R = {"ok": 0, "ng": 0}

def check(n, c):
    s = "PASS" if c else "FAIL"
    R["ok" if c else "ng"] += 1
    print(f"  [{s}] {n}")
    return c


async def main():
    print("=" * 50)
    print("Full TUI Integration Test")
    print("=" * 50)

    # Use pre-built hub=False (will skip boot for speed)
    # But we need boot to happen to show the UI properly
    app = LivingTreeTuiApp(workspace=str(PROJECT))

    class ProbeScreen(Screen):
        count = 0
        def on_mount(self):
            ProbeScreen.count += 1
        BINDINGS = [("escape", "app.pop_screen", "back")]

    app.SCREENS["chat"] = ProbeScreen
    app.SCREENS["code"] = ProbeScreen
    app.SCREENS["docs"] = ProbeScreen
    app.SCREENS["tools"] = ProbeScreen
    app.SCREENS["settings"] = ProbeScreen

    async def test_plan():
        await asyncio.sleep(0.3)

        # ── Test 1: Cards exist ──
        cards = list(app.query(Card))
        print(f"\n[1] Cards: {len(cards)}")
        check("5 cards exist", len(cards) == 5)
        for c in cards:
            print(f"    {c.screen_name}: can_focus={c.can_focus} focusable={c.focusable}")

        # ── Test 2: Focus works ──
        print(f"\n[2] Focus")
        app.set_focus(cards[0])
        await asyncio.sleep(0.1)
        check("focus set to card[0]", isinstance(app.focused, Card) and app.focused is cards[0])

        app.set_focus(cards[2])
        await asyncio.sleep(0.1)
        check("focus set to card[2]", isinstance(app.focused, Card) and app.focused is cards[2])

        # Focus all cards sequentially
        all_focused = True
        for i, c in enumerate(cards):
            app.set_focus(c)
            await asyncio.sleep(0.05)
            if app.focused is not c:
                all_focused = False
                print(f"    card[{i}] focus FAILED")
        check("all 5 cards focusable", all_focused)

        # ── Test 3: action_activate_card ──
        print(f"\n[3] action_activate_card")
        app.set_focus(cards[0])
        await asyncio.sleep(0.1)
        ProbeScreen.count = 0
        app.action_activate_card()
        await asyncio.sleep(0.3)
        # Check if screen was pushed (stack should have more than 1)
        screen_count = len(app._screen_stack)
        check(f"push_screen called (stack={screen_count})", screen_count >= 2)

        # ── Test 4: Pop back ──
        print(f"\n[4] Pop screen")
        app.pop_screen()
        await asyncio.sleep(0.2)
        back_stack = len(app._screen_stack)
        check(f"pop_screen (stack={back_stack})", back_stack == 1)

        # ── Test 5: Card data ──
        print(f"\n[5] Card data integrity")
        names = ["chat", "code", "docs", "tools", "settings"]
        for i, name in enumerate(names):
            check(f"card[{i}].screen_name='{name}'", cards[i].screen_name == name)

        # ── Test 6: CSS rendering hints ──
        print(f"\n[6] Card rendering")
        for i, c in enumerate(cards):
            r = c.render()
            has_text = len(r) > 0
            print(f"    card[{i}] render: {len(r)} chars - {r[:30]}...")
            check(f"card[{i}] has render content", has_text)

        # ── Test 7: Status bar ──
        print(f"\n[7] Status bar")
        from livingtree.tui.widgets.footer_bar import StatusBar
        bar = app.query_one(StatusBar)
        check("StatusBar exists", bar is not None)

        app.exit()

    asyncio.create_task(test_plan())
    await app.run_async()

    print(f"\n{'='*50}")
    print(f"Results: {R['ok']} ok, {R['ng']} fail")
    print(f"{'='*50}")
    return R['ng'] == 0


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
