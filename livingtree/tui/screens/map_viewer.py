"""Map Viewer Screen — Geographic visualization with search.

Features:
- Location search
- Map display (placeholder for 天地图/Sixel integration)
- Coordinate display
- Layer switching concepts
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button, Input, Label, RichLog, Static,
)


class MapScreen(Screen):
    """Map/GIS viewer screen."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hub = None

    def set_hub(self, hub) -> None:
        self._hub = hub

    def compose(self) -> ComposeResult:
        yield Vertical(
            Horizontal(
                Input(placeholder="Search location... (city, address, coordinates)", id="map-search-input"),
                Button("Search", variant="primary", id="map-search-btn"),
                Button("Beijing", variant="default", id="map-beijing"),
                Button("Shanghai", variant="default", id="map-shanghai"),
                Button("Current", variant="default", id="map-current"),
                id="map-search-bar",
            ),
            Static(
                "\n\n"
                "                     🗺️  Map Viewer\n\n"
                "         Enter a location to search or select a preset\n\n"
                "     Integration: 天地图 API  |  Sixel render (if supported)\n"
                "                 Unicode block art (fallback)\n\n"
                "  ┌─────────────────────────────────────────────────┐\n"
                "  │  ╔═══════════════════════════════════════════╗  │\n"
                "  │  ║     ██     ███     ██    ████    ███     ║  │\n"
                "  │  ║    ████    ███    ████   ████   ████    ║  │\n"
                "  │  ║   ██████   ███   ██████  ████  ██████   ║  │\n"
                "  │  ║  ████████  ███  ████████ ████ ████████  ║  │\n"
                "  │  ║ ██████████ ███ ██████████ █████████████  ║  │\n"
                "  │  ╚═══════════════════════════════════════════╝  │\n"
                "  └─────────────────────────────────────────────────┘\n\n"
                "     [dim]Keyboard: +/- zoom  |  Arrows pan  |  / search[/dim]\n",
                id="map-view",
            ),
            RichLog(id="map-info", highlight=True, markup=True),
        )

    def on_mount(self) -> None:
        info = self.query_one("#map-info", RichLog)
        info.write("[bold green]Map Viewer[/bold green]")
        info.write("[dim]Search for a location to view coordinates. 天地图 integration pending.[/dim]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        info = self.query_one("#map-info", RichLog)
        search_input = self.query_one("#map-search-input", Input)

        if event.button.id == "map-search-btn":
            query = search_input.value.strip()
            if query:
                info.write(f"\n[bold]Search:[/bold] {query}")
                info.write(f"  [dim]Coordinates would be fetched via 天地图 API[/dim]")
                info.write(f"  [dim]Map tile would render here if Sixel supported[/dim]")

        elif event.button.id == "map-beijing":
            info.write("\n[bold]Beijing (北京)[/bold]")
            info.write("  Lat: 39.9042  Lon: 116.4074")
            info.write("  [dim]天地图 tile: beijing_center_z12[/dim]")

        elif event.button.id == "map-shanghai":
            info.write("\n[bold]Shanghai (上海)[/bold]")
            info.write("  Lat: 31.2304  Lon: 121.4737")
            info.write("  [dim]天地图 tile: shanghai_center_z12[/dim]")

        elif event.button.id == "map-current":
            info.write("\n[bold]Current Location[/bold]")
            info.write("  [dim]Would use geolocation/IP[/dim]")
            info.write("  [dim]Or Windows Location API[/dim]")

    async def refresh(self) -> None:
        pass
