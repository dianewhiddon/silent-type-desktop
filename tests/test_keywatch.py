import threading
import time
import unittest
import uuid

from silent_type import keywatch, windows


class KeyWatchTests(unittest.TestCase):
    def watch(self, **kwargs):
        wake = threading.Event()
        found = keywatch.KeyWatch(wake, name="SilentTypeTest" + uuid.uuid4().hex, **kwargs)
        self.assertTrue(found.start(), "Raw Input should register for a message-only window")
        self.addCleanup(found.stop)
        return wake, found

    def test_idle_watcher_stays_quiet_then_wakes_on_a_key_message(self):
        wake, found = self.watch()
        time.sleep(0.3)
        if not found.heard:  # a real keystroke during the test legitimately wakes it
            self.assertFalse(wake.is_set())
        wake.clear()
        keywatch.user32.PostMessageW(found.hwnd, keywatch.WM_INPUT, 0, 0)
        self.assertTrue(wake.wait(2))

    def test_open_request_calls_back_and_wakes(self):
        instance = windows.Instance(r"Local\SilentTypeTest" + uuid.uuid4().hex)
        self.addCleanup(instance.close)
        opened = threading.Event()
        wake, _ = self.watch(open_event=instance.open_event, on_open=opened.set)
        instance.request_open()
        self.assertTrue(opened.wait(2))
        self.assertTrue(wake.wait(2))

    def test_stop_ends_the_thread(self):
        _, found = self.watch()
        found.stop()
        found.thread.join(2)
        self.assertFalse(found.thread.is_alive())
        self.assertFalse(found.active)


if __name__ == "__main__":
    unittest.main()
