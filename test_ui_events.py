"""UI interaction test — programmatic verification of event dispatch.

Checks: focus, :focus CSS, :hover CSS, Click→push_screen, Enter→push_screen
"""
import asyncio
import sys
from pathlib import Path

PROJECT = Path(__file__).parent
LOCAL_TEXTUAL = PROJECT / "livingtree" / "tui" / "textual" / "src"
sys.path.insert(0, str(LOCAL_TEXTUAL.resolve()))
sys.path.insert(0, str(PROJECT.resolve()))

from textual import events
from textual.app import App
from textual.geometry import Offset
from textual.screen import Screen
from textual.widgets._static import Static

from livingtree.tui.widgets.card import Card


# ── Test 1: Card CSS pseudo-classes ──
def test_card_css():
    """Verify Card's CSS has :focus and :hover rules."""
    card = Card("test", "chat")
    rules = Card.DEFAULT_CSS
    has_focus_css = ":focus" in rules
    has_hover_css = ":hover" in rules

    print(f"\n  CSS :focus rule found: {has_focus_css}")
    print(f"  CSS :hover rule found: {has_hover_css}")
    print(f"  can_focus: {card.can_focus}")
    print(f"  focusable: {card.focusable}")
    print(f"  FOCUS_ON_CLICK: {Card.FOCUS_ON_CLICK}")
    return has_focus_css and has_hover_css


# ── Test 2: Event handler existence ──
def test_handler_methods():
    """Check what handler methods are available on Card vs Widget."""
    card = Card("test", "chat")

    handlers = ["_on_click", "on_click", "_on_key", "on_key",
                "_on_enter", "on_enter", "_on_leave", "on_leave",
                "_on_focus", "on_focus", "_on_blur", "on_blur"]

    print("\n  Handler methods on Card:")
    for h in handlers:
        m = getattr(card, h, None)
        where = "Card" if h in Card.__dict__ else "Widget" if hasattr(type(card).__bases__[0], h) else "?"
        print(f"    {h}: {'✓' if m else '✗'} ({where})")

    # Check if Card actually OVERRIDES any
    card_own = [h for h in handlers if h in Card.__dict__]
    print(f"  Card own handlers: {card_own}")
    return len(card_own) > 0


# ── Test 3: App binding for enter ──
def test_app_binding():
    """Check App has binding for enter → activate_card."""
    from livingtree.tui.app import LivingTreeTuiApp

    enter_bindings = [b for b in LivingTreeTuiApp.BINDINGS if b.key == "enter"]
    has_activate = hasattr(LivingTreeTuiApp, "action_activate_card")

    print(f"\n  App BINDINGS with 'enter': {[b.action for b in enter_bindings]}")
    print(f"  action_activate_card exists: {has_activate}")
    return bool(enter_bindings) and has_activate


# ── Test 4: Screen._forward_event trace ──
async def test_forward_event():
    """Trace how events flow through Screen._forward_event for a Card."""

    from textual.app import App, ComposeResult
    from textual.containers import VerticalScroll, Horizontal

    events_captured = []

    class TestCard(Card):
        def __init__(self):
            super().__init__("test", "chat")

        async def _on_click(self, event: events.Click) -> None:
            events_captured.append(("_on_click", event))
            # Don't push screen, just record

        def on_click(self, event: events.Click) -> None:
            events_captured.append(("on_click", event))

        async def _on_focus(self, event: events.Focus) -> None:
            events_captured.append(("_on_focus", event))

        def on_focus(self, event: events.Focus) -> None:
            events_captured.append(("on_focus", event))

        async def _on_key(self, event: events.Key) -> None:
            if event.key == "enter":
                events_captured.append(("_on_key", event))

        def on_key(self, event: events.Key) -> None:
            if event.key == "enter":
                events_captured.append(("on_key", event))

    class TestApp(App):
        def compose(self):
            with VerticalScroll():
                with Horizontal():
                    yield TestCard()

        async def on_mount(self):
            self.set_focus(self.query_one(TestCard))
            self.call_later(self._test)

        def _test(self):
            card = self.query_one(TestCard)
            # Test 1: Check focus already set
            print(f"\n  Focused widget: {type(self.focused).__name__}")
            print(f"  Is TestCard: {isinstance(self.focused, TestCard)}")

            # Test 2: Try posting Click event
            click = events.Click(
                widget=card,
                x=10, y=10,
                screen_x=10, screen_y=10,
                button=1,
                nclicks=1,
            )
            card.post_message(click)

            # Test 3: Try Key event
            key = events.Key(key="enter", character="\n")
            key._sender = card
            card.post_message(key)

            # Test 4: Try Focus event  
            focus = events.Focus(from_app_focus=True)
            focus._sender = card
            card.post_message(focus)

            asyncio.create_task(self._check())

        async def _check(self):
            await asyncio.sleep(1.0)
            print(f"\n  Events captured: {len(events_captured)}")
            for name, event in events_captured:
                print(f"    {name} from {type(event).__name__}")
            self.exit()

    app = TestApp()
    await app.run_async()

    # Print results
    found_click = any(e[0] in ("_on_click", "on_click") for e in events_captured)
    found_key = any(e[0] in ("_on_key", "on_key") for e in events_captured)
    found_focus = any(e[0] in ("_on_focus", "on_focus") for e in events_captured)

    print(f"\n  Click received: {found_click}")
    print(f"  Key(Enter) received: {found_key}")
    print(f"  Focus received: {found_focus}")

    return events_captured


# ── Test 5: Full App.run_async with Binding check ──
async def test_app_binding_dispatch():
    """Test if App-level Enter binding dispatches action_activate_card."""

    from livingtree.tui.app import LivingTreeTuiApp

    activated = []

    class ProbeApp(LivingTreeTuiApp):
        def action_activate_card(self):
            focused = self.focused
            activated.append(type(focused).__name__ if focused else "None")
            super().action_activate_card()

    app = ProbeApp(workspace=str(PROJECT))

    async def send_enter():
        await asyncio.sleep(0.5)
        focused = app.focused
        print(f"\n  Focused before Enter: {type(focused).__name__ if focused else 'None'}")

        key = events.Key(key="enter", character="\n")
        key._sender = app
        app.post_message(key)

        await asyncio.sleep(0.5)
        print(f"  action_activate_card called: {len(activated)} times")
        for a in activated:
            print(f"    focused was: {a}")
        app.exit()

    asyncio.create_task(send_enter())
    await app.run_async()
    return activated


# ═══ Main ═══
async def main():
    print("═" * 50)
    print("TUI Event Dispatch Test Suite")
    print("═" * 50)

    print("\n[1] Card CSS & focus properties")
    r1 = test_card_css()

    print("\n[2] Handler method inventory")
    r2 = test_handler_methods()

    print("\n[3] App binding check")
    r3 = test_app_binding()

    print("\n[4] Event forwarding trace (standalone app)")
    r4 = await test_forward_event()

    print("\n[5] App-level binding dispatch")
    r5 = await test_app_binding_dispatch()

    print("\n" + "═" * 50)
    print("SUMMARY")
    print(f"  CSS rules: {'PASS' if r1 else 'FAIL'}")
    print(f"  Handlers:  {'PASS' if r2 else 'FAIL'}")
    print(f"  Bindings:  {'PASS' if r3 else 'FAIL'}")
    print(f"  Events:    {'PASS' if r4 else 'FAIL'} ({len(r4)} captured)")
    print(f"  App Enter: {'PASS' if r5 else 'FAIL'} ({len(r5)} activations)")
    print("═" * 50)


if __name__ == "__main__":
    asyncio.run(main())
