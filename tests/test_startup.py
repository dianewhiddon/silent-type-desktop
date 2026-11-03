import tempfile
import unittest
from pathlib import Path

from silent_type import startup


class StartupTests(unittest.TestCase):
    def test_toggle_creates_and_removes_the_shortcut(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(startup.enabled(folder))
            self.assertTrue(startup.toggle(folder))
            self.assertTrue(startup.enabled(folder))
            self.assertTrue(Path(folder, startup.LINK_NAME).stat().st_size > 0)
            self.assertFalse(startup.toggle(folder))
            self.assertFalse(startup.enabled(folder))

    def test_shortcut_points_at_this_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            startup.enable(folder)
            import subprocess

            out = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-Command",
                    "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:L);$s.TargetPath;$s.Arguments;$s.WorkingDirectory",
                ],
                env={**__import__("os").environ, "L": str(Path(folder, startup.LINK_NAME))},
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout.splitlines()
            self.assertEqual(Path(out[0]), startup.interpreter())
            self.assertEqual(out[1], "-m silent_type")
            self.assertEqual(Path(out[2]), startup.ROOT)


if __name__ == "__main__":
    unittest.main()
