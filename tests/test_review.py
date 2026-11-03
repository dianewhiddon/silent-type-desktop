import queue
import unittest
from unittest.mock import Mock, call

from silent_type.app import POLL_MS, App
from silent_type.session import Session, Signals, picture_brightness


class ReviewTests(unittest.TestCase):
    def test_review_blocks_insertion_even_with_valid_destination(self):
        insert = Mock()
        session = Session(
            feed=None,
            recognizer=None,
            config={},
            history=None,
            signals=Signals(),
            post=Mock(),
            destination=(1, 2),
            review_only=True,
            insert=insert,
        )
        self.assertEqual(session.deliver("Hello"), "saved: review test only")
        insert.assert_not_called()

    def test_changed_destination_saves_instead_of_typing(self):
        insert = Mock()
        signals = Signals()
        signals.changed.set()
        session = Session(
            feed=None,
            recognizer=None,
            config={},
            history=None,
            signals=signals,
            post=Mock(),
            destination=(1, 2),
            insert=insert,
        )
        self.assertEqual(session.deliver("Hello"), "saved: focus changed")
        insert.assert_not_called()

    def fixture(self):
        app = App.__new__(App)
        app.events = queue.Queue()
        app.root = Mock()
        app.status = Mock()
        app.tray = Mock()
        app.window = Mock()
        app.show_indicator = Mock()
        app.hide_indicator = Mock()
        app.terminal_indicator = False
        app.review_only = True
        app.strip_token = 0
        app.busy = True
        return app

    def test_error_remains_visible_after_idle(self):
        app = self.fixture()
        app.post("error", "Face was not visible throughout the phrase.")
        app.post("idle")
        app.drain()
        app.show_indicator.assert_called_once_with(
            "Face was not visible throughout the phrase.", "#252525", None
        )
        app.hide_indicator.assert_not_called()
        self.assertFalse(app.busy)

    def test_recognized_words_remain_visible_after_idle_without_old_timer(self):
        app = self.fixture()
        app.post("result", ("saved: review test only", "Hello there", 0))
        app.post("idle")
        app.drain()
        self.assertIn("Hello there", app.show_indicator.call_args.args[0])
        app.hide_indicator.assert_not_called()
        timers = [c for c in app.root.after.call_args_list if c.args[1] != app.wake]
        self.assertEqual(timers, [call(POLL_MS, app.drain)])

    def test_normal_use_clears_the_result_after_a_few_seconds(self):
        app = self.fixture()
        app.review_only = False
        app.strip = Mock()
        del app.show_indicator
        app.post("result", ("typed", "Hello there", 0))
        app.post("idle")
        app.drain()
        delays = [call.args[0] for call in app.root.after.call_args_list]
        self.assertIn(8000, delays)
        hide = next(call.args[1] for call in app.root.after.call_args_list if call.args[0] == 8000)
        hide()
        app.hide_indicator.assert_called_once()


if __name__ == "__main__":
    unittest.main()


class LightWarningTests(unittest.TestCase):
    def failing_session(self, dark):
        post = Mock()
        session = Session(
            feed=Mock(),
            recognizer=None,
            config={},
            history=None,
            signals=Signals(),
            post=post,
            destination=(1, 2),
        )
        session.dark = dark
        session._run = Mock(side_effect=RuntimeError("Face was not visible throughout the phrase."))
        session.run()
        return post

    def test_a_dark_picture_is_named_when_the_face_is_not_found(self):
        post = self.failing_session(dark=True)
        status = next(call.args[1] for call in post.call_args_list if call.args[0] == "status")
        self.assertIn("Face was not visible", status)
        self.assertIn("very dark", status)

    def test_a_lit_picture_gets_the_plain_message(self):
        post = self.failing_session(dark=False)
        status = next(call.args[1] for call in post.call_args_list if call.args[0] == "status")
        self.assertNotIn("dark", status)

    def test_brightness_is_read_from_a_frame_and_defaults_to_bright(self):
        import numpy as np

        self.assertEqual(picture_brightness(np.full((4, 4, 3), 40, dtype=np.uint8)), 40.0)
        self.assertEqual(picture_brightness(None), 255.0)
        self.assertEqual(picture_brightness(Mock()), 255.0)
