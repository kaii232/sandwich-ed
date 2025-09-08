# app/services/inflight.py
import hashlib, json, threading
from typing import Dict, Any

class Inflight:
    def __init__(self):
        self._lock = threading.Lock()
        self._f: Dict[str, threading.Event] = {}
        self._r: Dict[str, Any] = {}
        self._e: Dict[str, Exception] = {}

    def _key(self, name: str, payload: dict) -> str:
        h = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return f"{name}:{h}"

    def get_or_run(self, name: str, payload: dict, fn):
        k = self._key(name, payload)
        with self._lock:
            if k in self._f:
                ev = self._f[k]
            else:
                ev = threading.Event()
                self._f[k] = ev
                # we run outside lock
                runner = (k, ev)
                break_out = True
            # if already in-flight, wait outside lock
        if "break_out" not in locals():
            ev.wait()
            if k in self._e: raise self._e.pop(k)
            return self._r.pop(k)

        # leader runs the function
        try:
            res = fn()
            with self._lock:
                self._r[k] = res
        except Exception as ex:
            with self._lock:
                self._e[k] = ex
        finally:
            with self._lock:
                ev.set()
                self._f.pop(k, None)
        if k in self._e: raise self._e.pop(k)
        return self._r.pop(k)

inflight = Inflight()
