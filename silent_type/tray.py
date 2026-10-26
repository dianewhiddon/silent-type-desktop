"""Tray icon: the lips badge with state dots; left-click opens Recents.

The menu's checked "Silent Type on" item is the on/off switch.
"""

from .icon import mark


class Tray:
    def __init__(self, post, enabled=lambda: True):
        import pystray

        self.images = {state: mark(64, state) for state in ("ready", "recording", "working", "off")}
        self.icon = pystray.Icon(
            "silent-type",
            self.images["working"],
            "Silent Type · loading",
            menu=pystray.Menu(
                pystray.MenuItem("Recent phrases", lambda *_: post("recents"), default=True),
                pystray.MenuItem("Silent Type on", lambda *_: post("toggle"), checked=lambda _: enabled()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Open the full log", lambda *_: post("open_log")),
                pystray.MenuItem("Camera and settings", lambda *_: post("open")),
                pystray.MenuItem("Quit", lambda *_: post("quit")),
            ),
        )

    def run(self):
        self.icon.run()

    def show(self, state):
        self.icon.icon = self.images[state]

    def set_title(self, text):
        self.icon.title = "Silent Type · " + text[:100]

    def stop(self):
        self.icon.stop()
