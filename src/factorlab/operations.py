"""Fila limitada e observabilidade sem dados financeiros nos logs."""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

LOGGER = logging.getLogger("factorlab.jobs")


class BoundedExecutor:
    def __init__(self, workers=2, capacity=4):
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="factorlab")
        self.slots = threading.BoundedSemaphore(capacity)

    def submit(self, function, *args, **kwargs):
        if not self.slots.acquire(blocking=False):
            raise ValueError("Fila global ocupada; aguarde e tente novamente.")

        def measured():
            started = time.monotonic()
            try:
                return function(*args, **kwargs)
            except Exception:
                LOGGER.exception("background_job_failed")
                raise
            finally:
                LOGGER.info(
                    "background_job_completed duration_seconds=%.3f", time.monotonic() - started
                )

        try:
            future = self.pool.submit(measured)
            future.add_done_callback(lambda _: self.slots.release())
            return future
        except Exception:
            self.slots.release()
            raise


EXECUTOR = BoundedExecutor()


def classify_error(exc):
    import requests

    if isinstance(exc, (ConnectionError, TimeoutError, requests.RequestException)):
        return "REDE", "Verifique conexão, DNS e disponibilidade do provedor."
    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return "DADOS / PARÂMETROS", "Revise a central de qualidade e os parâmetros."
    return "CÁLCULO / SISTEMA", "Consulte os logs; não utilize resultados parciais."
