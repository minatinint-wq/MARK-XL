"""Safe CPU acceleration defaults shared by the JARVIS runtime.

This module deliberately configures native libraries before NumPy, OpenCV or
an inference runtime are imported.  It leaves two logical processors for the
desktop, audio callback and Qt WebEngine, preventing camera work from starving
the rest of the assistant.
"""
from __future__ import annotations

import importlib.util
import os
from typing import Mapping, MutableMapping


_THREAD_ENVIRONMENT = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "OPENCV_FOR_THREADS_NUM",
)


def _worker_count(environ: Mapping[str, str], logical_cpus: int | None = None) -> int:
    logical_cpus = logical_cpus or os.cpu_count() or 4
    requested = environ.get("JARVIS_CPU_WORKERS", "").strip()
    try:
        return max(1, min(int(requested), logical_cpus)) if requested else max(1, min(8, logical_cpus - 2))
    except ValueError:
        return max(1, min(8, logical_cpus - 2))


def configure_cpu_acceleration(
    environ: MutableMapping[str, str] | None = None,
    logical_cpus: int | None = None,
) -> dict[str, int | str]:
    """Set bounded CPU-native runtime defaults before native imports occur."""
    env = os.environ if environ is None else environ
    workers = _worker_count(env, logical_cpus)
    for name in _THREAD_ENVIRONMENT:
        env.setdefault(name, str(workers))
    # Avoid busy-waiting OpenMP threads while the microphone callback is idle.
    env.setdefault("OMP_WAIT_POLICY", "PASSIVE")
    env.setdefault("KMP_BLOCKTIME", "0")
    return {"workers": workers, "mode": "cpu"}


def configure_opencv(cv2_module) -> None:
    """Apply the same bounded worker budget to an already imported OpenCV."""
    workers = _worker_count(os.environ)
    try:
        cv2_module.setUseOptimized(True)
        cv2_module.setNumThreads(workers)
    except Exception:
        pass
    # The Jarvis camera path is CPU-only.  Do not let OpenCV pick a fragile
    # OpenCL device after the WebEngine renderer has already started.
    try:
        cv2_module.ocl.setUseOpenCL(False)
    except Exception:
        pass


def acceleration_status() -> dict[str, object]:
    """Return install state without importing heavy inference runtimes."""
    return {
        "mode": "cpu",
        "workers": _worker_count(os.environ),
        "openvino_available": importlib.util.find_spec("openvino") is not None,
        "onnxruntime_available": importlib.util.find_spec("onnxruntime") is not None,
    }


CPU_ACCELERATION = configure_cpu_acceleration()
