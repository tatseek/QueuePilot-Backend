import logging
import signal
import threading


def run_until_stopped(log: logging.Logger, message: str) -> None:
    log.info(message)
    stop = threading.Event()

    def handle(signum: int, _frame: object) -> None:
        log.info("Received signal %s, shutting down.", signum)
        stop.set()

    signal.signal(signal.SIGTERM, handle)
    signal.signal(signal.SIGINT, handle)
    stop.wait()
