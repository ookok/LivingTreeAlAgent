# LivingTree AI Agent - PyDracula UI Framework

A modern, beautiful Qt-based UI framework for LivingTree AI Agent, built on top of PyDracula.

## Features

- **Modern Dark/Light Themes**: Based on Dracula color palette
- **Smooth Animations**: Menu transitions and resize effects
- **Custom Title Bar**: Frameless window with drag support
- **Responsive Layout**: Adaptive UI that works on different screen sizes
- **Easy Theme Switching**: Switch between light and dark themes with one click

## Installation

### Requirements

- Python 3.8+
- PySide6 or PyQt6

```bash
pip install PySide6
# or
pip install PyQt6
```

### Quick Start

```bash
# Run with default light theme
python ui/ui_run.py

# Run with dark theme
python ui/ui_run.py --dark
```

## Project Structure

```
ui/
├── __init__.py              # Package init
├── main_window.py           # Main window class
├── theme_manager.py         # Theme management
├── modules/
│   ├── __init__.py
│   ├── ui_settings.py      # UI settings/constants
│   └── ui_functions.py      # UI utility functions
├── themes/
│   ├── py_dracula_dark.qss  # Dark theme stylesheet
│   └── py_dracula_light.qss # Light theme stylesheet
├── widgets/
│   ├── __init__.py
│   └── custom_grips/         # Custom window resize grips
└── ui_run.py                # Entry point script
```

## Theme Switching

### Programmatic

```python
from ui.theme_manager import get_theme_manager

theme_manager = get_theme_manager()

# Set theme
theme_manager.set_theme(is_light=True)   # Light theme
theme_manager.set_theme(is_light=False)  # Dark theme

# Toggle theme
theme_manager.toggle_theme()

# Get current theme
is_light = theme_manager.is_light
```

### In Application

Click the **Theme** button in the bottom menu or use the right panel to switch themes.

## Customization

### Colors

Edit the QSS files in `themes/` directory:

- `py_dracula_light.qss` - Light theme colors
- `py_dracula_dark.qss` - Dark theme colors

### Menu Items

Modify `Ui_MainWindow._setup_left_menu()` in `main_window.py` to add/remove menu items.

## Credits

- **PyDracula**: [Wanderson M. Pimenta](https://github.com/Wanderson-Magalhaes/Modern_GUI_PyDracula_PySide6_or_PyQt6)
- **Dracula Theme**: [Zeno Rocha](https://draculatheme.com/)

## License

MIT License - See LICENSE file for details.
