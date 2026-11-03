"""Bound DirectShow enumeration so an unresponsive driver cannot freeze startup."""

import multiprocessing as mp
import time


def _enumerate(connection):
    try:
        from comtypes import CoInitialize, CoUninitialize
        from pygrabber.dshow_graph import FilterGraph

        CoInitialize()
        try:
            connection.send((True, FilterGraph().get_input_devices()))
        finally:
            CoUninitialize()
    except Exception as exc:
        connection.send((False, str(exc)))
    finally:
        connection.close()


def cameras(timeout=8, cancelled=lambda: False):
    context = mp.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_enumerate, args=(child,), daemon=True)
    try:
        process.start()
    except Exception:
        parent.close()
        child.close()
        raise
    child.close()
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not cancelled():
            if parent.poll(0.05):
                ok, value = parent.recv()
                if not ok:
                    raise RuntimeError(value)
                return value
            if not process.is_alive():
                raise RuntimeError("Camera discovery stopped. Retry Camera and settings.")
        raise RuntimeError("Camera discovery timed out. Reconnect the camera and retry.")
    finally:
        parent.close()
        if process.is_alive():
            process.terminate()
        process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join(timeout=1)
