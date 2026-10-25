"""Render only fictional fixtures; exercise controls and capture the app's own windows."""

import tempfile
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

from silent_type.recents import Recents
from silent_type.state import History
from silent_type.window import MainWindow
from tests import screen


def capture(root, path):
    root.update_idletasks()
    root.lift()
    root.attributes("-topmost", True)
    for _ in range(15):
        root.update()
        time.sleep(0.02)
    x, y = root.winfo_rootx(), root.winfo_rooty()
    screen.grab((x, y, x + root.winfo_width(), y + root.winfo_height())).save(path)


def main():
    out = Path(".impeccable/review")
    out.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    root.title("Silent Type")
    root.geometry("780x760+100+100")
    copied = []
    with tempfile.TemporaryDirectory() as folder:
        history = History(Path(folder) / "history.sqlite3")
        for phrase, outcome in (
            ("The meeting starts at nine.", "typed"),
            ("Please review the draft before Friday.", "saved: focus changed"),
            (
                "A longer example phrase wraps here so that the entire recognized sentence remains available for review before copying or sending it.",
                "saved: recorded in app",
            ),
        ):
            history.mark(history.add(phrase), outcome)
        window = MainWindow(
            root,
            history=history,
            hold_label="Right Ctrl + Right Alt",
            camera_names=["Example webcam", "Second camera"],
            camera="Example webcam",
            on_camera=lambda name: None,
            on_preview=lambda: None,
            on_record=lambda: None,
            on_copy=copied.append,
            on_hide=lambda: None,
        )
        window.status.set("Ready · CPU · Hold Right Ctrl + Right Alt")
        capture(root, out / "settings.png")
        window.copy_selected()
        assert copied and copied[0].startswith("A longer example")
        root.geometry("700x720+100+100")
        capture(root, out / "settings-minimum.png")
        with patch("silent_type.window.messagebox.askyesno", return_value=True):
            window.clear_history()
        assert not history.recent()
        assert str(window.copy_button.cget("state")) == "disabled"
        assert str(window.clear_button.cget("state")) == "disabled"
        capture(root, out / "settings-empty.png")
        root.withdraw()
        popup = Recents(
            root,
            ["Example phrase to copy.", "Another saved phrase."],
            copied.append,
            lambda: None,
            lambda action: action() if action else None,
        )
        capture(popup.top, out / "recents.png")
        popup._finish(lambda: copied.append("chosen"))
        assert copied[-1] == "chosen"
        opened = []
        popup = Recents(
            root, [], copied.append, lambda: opened.append(True), lambda action: action() if action else None
        )
        capture(popup.top, out / "recents-empty.png")
        with patch("silent_type.recents.ctypes.windll.user32.GetAsyncKeyState", return_value=0x8000):
            popup.top.event_generate("<KeyPress-l>")
            root.update()
        assert opened == [True], "L must open the log from an empty popup."
    root.destroy()
    print(
        "UI fixtures: selection, copy, confirmed clear, popup dismissal, full/minimum/empty renders passed."
    )


if __name__ == "__main__":
    main()
