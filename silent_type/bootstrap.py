"""Early diagnostics: imports, UI construction and model readiness are covered."""

import faulthandler
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler


def run():
    try:
        _run()
    except Exception as exc:
        logging.getLogger(__name__).exception("Application could not start")
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            f"Silent Type could not start.\n\n{exc}\n\nCheck the data folder and silent-type.log.",
            "Silent Type",
            0x10,
        )
        raise


def _run():
    # state imports only standard-library helpers; start tracing before heavy imports.
    from .state import data_dir

    folder = data_dir()
    handler = RotatingFileHandler(
        folder / "silent-type.log", maxBytes=500_000, backupCount=2, encoding="utf-8"
    )
    logging.basicConfig(
        handlers=[handler], level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger("silent_type").setLevel(logging.INFO)
    log = logging.getLogger(__name__)
    # Append so a second launch cannot erase the evidence of the first failure.
    with (folder / "silent-type-startup-hang.txt").open("a", encoding="utf-8") as trace:
        trace.write(f"\nLaunch {datetime.now().isoformat()} pid={os.getpid()}\n")
        trace.flush()
        faulthandler.dump_traceback_later(20, repeat=True, file=trace)
        log.info("Launching pid=%s data=%s", os.getpid(), folder)
        try:
            from .app import main

            main()
        finally:
            faulthandler.cancel_dump_traceback_later()
