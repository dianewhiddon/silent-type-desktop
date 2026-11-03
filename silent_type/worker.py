"""Bounded inference process; a stalled model cannot block the UI/hotkey loop."""

import multiprocessing as mp
import threading
import time


class Cancelled(RuntimeError):
    pass


def run(connection, config):
    try:
        from .recognition import Recognizer

        recognizer = Recognizer(config)
        try:
            # The first search after loading runs slowly while the math libraries
            # set up; do it now so the first phrase is as fast as the rest.
            import numpy as np

            recognizer.decode_mouths(np.zeros((25, 96, 96), dtype=np.uint8))
        except Exception:
            pass
        connection.send(("ready", recognizer.device))
        while True:
            try:
                request = connection.recv()
            except EOFError:
                break
            if request[0] == "quit":
                break
            try:
                if request[0] == "discard":
                    recognizer.preparation = None
                    connection.send(("discarded",))
                elif request[0] == "prefetch":
                    recognizer.prefetch(request[1], request[2])
                    connection.send(("prepared",))
                else:
                    text, elapsed = recognizer.decode(request[1], request[2])
                    connection.send(("text", text, elapsed))
            except Exception as exc:
                connection.send(("error", str(exc)))
            finally:
                request = None  # Release this phrase's frames before waiting again.
    except Exception as exc:
        try:
            connection.send(("error", str(exc)))
        except (EOFError, BrokenPipeError, OSError):
            pass
    finally:
        connection.close()


class ManagedRecognizer:
    def __init__(self, config, cancelled=lambda: False):
        self.closed = False
        context = mp.get_context("spawn")
        self.connection, child = context.Pipe()
        self.process = context.Process(target=run, args=(child, config), daemon=True)
        self.process.start()
        child.close()
        try:
            answer = self.wait(60, cancelled)
            if answer[0] != "ready":
                raise RuntimeError(answer[1])
            self.device = answer[1]
        except Exception:
            self.close()
            raise

    def wait(self, seconds, cancelled=lambda: False):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if cancelled():
                self.close()
                raise Cancelled("Cancelled. Nothing typed.")
            try:
                if self.connection.poll(0.05):
                    return self.connection.recv()
            except (EOFError, OSError) as exc:
                self.close()
                raise RuntimeError("Recognition worker stopped.") from exc
            if self.closed or not self.process.is_alive():
                self.close()
                raise RuntimeError("Recognition worker stopped.")
        self.close()
        raise RuntimeError("Recognition timed out. Nothing typed.")

    def discard(self):
        """Release speculative video when a phrase ends without a final decode."""
        if not self.closed:
            self._exchange("discard", [], [], lambda: False, timeout=2)

    def prefetch(self, frames, timestamps, cancelled=lambda: False):
        self._exchange("prefetch", frames, timestamps, cancelled)

    def decode(self, frames, timestamps, cancelled=lambda: False):
        answer = self._exchange("decode", frames, timestamps, cancelled)
        return answer[1], answer[2]

    def _exchange(self, command, frames, timestamps, cancelled, timeout=30):
        # A blocked pipe transfer must also be cancellable and time-limited.
        def send():
            try:
                self.connection.send((command, frames, timestamps))
            except (EOFError, BrokenPipeError, OSError):
                self.close()

        sender = threading.Thread(target=send, daemon=True)
        sender.start()
        try:
            answer = self.wait(timeout, cancelled)
        finally:
            sender.join(timeout=2)
        if answer[0] == "error":
            raise RuntimeError(answer[1])
        return answer

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.process.is_alive():
            self.process.terminate()
        self.process.join(timeout=2)
        if self.process.is_alive():
            self.process.kill()
            self.process.join(timeout=2)
        self.connection.close()
