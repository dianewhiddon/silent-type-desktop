"""Failure-path regressions for the public desktop release."""

import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from silent_type import punctuate, state, windows
from silent_type.session import PartReader, Session, Signals


class SettingsTests(unittest.TestCase):
    def test_defaults_are_local_and_bad_settings_fail_before_devices_open(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(state, "DATA", Path(folder)):
            self.assertFalse(state.settings()["punctuate"])
            for invalid in (
                [],
                {"beam": True},
                {"beam": 0},
                {"device": "gpu"},
                {"max_seconds": -1},
                {"names": "name"},
                {"hold_pair": [162, 165]},
                {"punctuate": "false"},
                {"unknown": 1},
            ):
                (Path(folder) / "settings.json").write_text(json.dumps(invalid))
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    state.settings()

    def test_atomic_settings_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(state, "DATA", Path(folder)):
            config = state.settings()
            config["names"] = ["Example Company"]
            state.save_settings(config)
            self.assertEqual(state.settings(), config)
            self.assertFalse((Path(folder) / "settings.tmp").exists())


class PartLifecycleTests(unittest.TestCase):
    def test_close_cancels_active_decode_and_discards_queue(self):
        entered = threading.Event()

        def decode(frames, times, cancelled):
            entered.set()
            while not cancelled():
                threading.Event().wait(0.01)
            raise RuntimeError("cancelled")

        reader = PartReader(SimpleNamespace(decode=decode), lambda: False)
        reader.add([(b"frame", 0)])
        self.assertTrue(entered.wait(1))
        reader.add([(b"more", 1)])
        reader.close()
        self.assertFalse(reader.thread.is_alive())
        self.assertEqual(reader.queue.qsize(), 0)

    def test_backlog_is_bounded(self):
        gate = threading.Event()
        entered = threading.Event()

        def decode(*_, **__):
            entered.set()
            gate.wait(2)
            return "one", 0

        reader = PartReader(SimpleNamespace(decode=decode), lambda: False)
        try:
            reader.add([(b"frame", 0)])
            self.assertTrue(entered.wait(1))
            for _ in range(3):
                reader.add([(b"frame", 0)])
            with self.assertRaisesRegex(RuntimeError, "cannot keep up"):
                reader.add([(b"frame", 0)])
        finally:
            gate.set()
            reader.close()
        self.assertFalse(reader.thread.is_alive())

    def session(self):
        return Session(
            feed=Mock(),
            recognizer=Mock(),
            config={"names": [], "punctuate": False},
            history=Mock(),
            signals=Signals(),
            post=Mock(),
            destination=42,
        )

    def test_recording_failure_always_closes_reader(self):
        session = self.session()
        session._wait_for_camera = Mock(return_value=True)
        session._record = Mock(side_effect=RuntimeError("camera failed"))
        with patch("silent_type.session.PartReader") as reader:
            with self.assertRaisesRegex(RuntimeError, "camera failed"):
                session._run()
            reader.return_value.close.assert_called_once()

    def test_incomplete_text_is_saved_but_never_inserted(self):
        session = self.session()
        session._record = Mock(return_value=(12, []))
        session.deliver = Mock()
        parts = Mock(count=2)
        parts.finish.return_value = ("remaining words", 1)
        with patch("silent_type.session.append_log"):
            session._read_parts(parts)
        session.history.add.assert_called_once_with("Remaining words")
        session.deliver.assert_not_called()
        self.assertIn("incomplete", session.history.mark.call_args.args[1])

    def test_history_failure_blocks_insertion(self):
        session = self.session()
        session._record = Mock(return_value=(12, []))
        session.history.add.side_effect = OSError("disk full")
        session.deliver = Mock()
        parts = Mock(count=1)
        parts.finish.return_value = ("hello", 0)
        with patch("silent_type.session.append_log"), self.assertRaises(OSError):
            session._read_parts(parts)
        session.deliver.assert_not_called()


class PunctuationReleaseTests(unittest.TestCase):
    def test_real_sdk_client_roundtrip_uses_completed_response_and_reuses_one_client(self):
        import httpx2

        original = httpx2.Client
        clients = []

        def respond(request):
            self.assertEqual(request.headers["x-api-key"], "test")
            return httpx2.Response(
                200,
                json={
                    "id": "msg_fixture",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-haiku-5-5",
                    "content": [{"type": "text", "text": "Hello there."}],
                    "stop_reason": "end_turn",
                    "stop_sequence": None,
                    "usage": {"input_tokens": 2, "output_tokens": 3},
                },
            )

        class Client(original):
            def __init__(self, **kwargs):
                super().__init__(transport=httpx2.MockTransport(respond), **kwargs)
                clients.append(self)

        punctuate._client = None
        self.addCleanup(setattr, punctuate, "_client", None)
        with patch.object(httpx2, "Client", Client), patch.object(punctuate, "api_key", return_value="test"):
            client = punctuate._shared_client("test")
            self.addCleanup(client.close)
            self.assertEqual(
                punctuate.punctuate("hello there", {"punctuate": True, "punctuation_timeout": 10}),
                "Hello there.",
            )
            self.assertEqual(
                punctuate.punctuate("hello there", {"punctuate": True, "punctuation_timeout": 10}),
                "Hello there.",
            )
        self.assertEqual(len(clients), 1)
        self.assertFalse(clients[0].is_closed)

    def test_no_network_without_explicit_opt_in_even_with_key(self):
        create = Mock()
        with patch.object(punctuate, "api_key", return_value="test"):
            self.assertEqual(punctuate.punctuate("hello", {}, create=create), "hello")
        create.assert_not_called()

    def test_truncated_response_and_hidden_characters_are_rejected(self):
        for stop, text in (
            ("max_tokens", "Hello."),
            ("end_turn", "Hello.\x1b"),
            ("end_turn", "Hello.😀"),
            ("refusal", "Hello."),
        ):
            response = SimpleNamespace(stop_reason=stop, content=[SimpleNamespace(type="text", text=text)])
            with patch.object(punctuate, "api_key", return_value="test"):
                self.assertEqual(
                    punctuate.punctuate("hello", {"punctuate": True}, create=Mock(return_value=response)),
                    "hello",
                )

    def test_menu_opened_mid_input_stops_remaining_characters(self):
        with (
            patch.object(windows, "target", return_value=42),
            patch.object(windows, "modifiers_down", return_value=False),
            patch.object(windows, "in_menu_mode", side_effect=[False, False, True]),
            patch.object(windows.time, "sleep"),
            patch.object(windows.user32, "SendInput", return_value=2) as send,
        ):
            self.assertEqual(windows.insert("ab", 42), "saved: partial input; check destination")
            send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
