"""Hardened FFmpeg worker.

Threat model (C7): the project document is untrusted input. It can describe
*media* and *text*, but it can never choose a program, a flag, a protocol or an
output path. Everything the worker executes is compiled here from a fixed
template:

  * only ``ffmpeg.exe`` / ``ffprobe.exe`` from the configured tools directory
    may run, always by absolute path, verified on every call;
  * every flag is checked against an allowlist before the process starts;
  * media paths must be relative, inside the project media root, with a video
    or image extension — an ``.exe`` reference is rejected, not executed;
  * the child gets a filtered environment (no ``*_API_KEY``, no tokens, no
    profile paths) and no shell;
  * on Windows the child is assigned to a Job Object with a memory ceiling and
    kill-on-close, so cancelling a job kills the whole tree and a crashed
    service cannot leave ffmpeg behind;
  * text is passed through ``textfile=`` (never inlined in the filter graph),
    so a caption cannot inject filter syntax;
  * output is staged inside the job folder, probed, and only then promoted with
    ``os.replace`` — a partial MP4 is never published as a success.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

if __package__ in (None, ""):  # allow `python service/worker.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import paths as path_rules  # noqa: E402
import project  # noqa: E402

ALLOWED_TOOLS = ("ffmpeg", "ffprobe")
ALLOWED_MEDIA_EXTENSIONS = {
    ".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".mts", ".m2ts",
    ".png", ".jpg", ".jpeg", ".webp", ".bmp",
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".oga", ".flac", ".opus",
}
FORBIDDEN_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".ps1", ".psm1", ".dll", ".msi", ".com", ".scr",
    ".vbs", ".js", ".jse", ".wsf", ".hta", ".cpl", ".pif", ".jar", ".py",
}
ALLOWED_FLAGS = {
    "-nostdin", "-hide_banner", "-nostats", "-loglevel", "-progress",
    "-ss", "-t", "-i", "-loop", "-framerate", "-stream_loop",
    "-filter_complex_script", "-map",
    "-c:v", "-preset", "-crf", "-pix_fmt", "-r",
    "-c:a", "-b:a", "-ar", "-ac",
    "-movflags", "-f", "-y",
    "-v", "-print_format", "-show_streams", "-show_format", "-select_streams",
}
#: Flags that must never appear, even if a future template adds them.
FORBIDDEN_FLAGS = {
    "-vf", "-filter_complex", "-lavfi", "-filter_script",
    "-safe", "-fpre", "-filter", "-init_hw_device", "-hwaccel",
}
ENV_ALLOWLIST = (
    "SystemRoot", "SYSTEMROOT", "windir", "WINDIR", "SystemDrive", "SYSTEMDRIVE",
    "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "PROCESSOR_IDENTIFIER",
    "PATHEXT", "TEMP", "TMP", "TZ",
)
SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL", "AUTH", "COOKIE", "SESSION")

DEFAULT_MEMORY_LIMIT_MB = 2048
DEFAULT_ACTIVE_PROCESS_LIMIT = 8
DEFAULT_TIMEOUT_S = 20 * 60
PROBE_TIMEOUT_S = 60
MAX_INPUT_BYTES = project.MAX_JOB_INPUT_BYTES
MAX_OUTPUT_BYTES = project.MAX_JOB_INPUT_BYTES
MAX_STDERR_BYTES = 256 * 1024
#: The inline graph rides on the Windows command line (32767 chars for the whole
#: line), so it gets a hard ceiling well below that and fails loudly instead of
#: letting CreateProcess truncate a render silently.
MAX_FILTER_GRAPH_CHARS = 20000
JOB_ID_RE = re.compile(r"^[a-z0-9]{4,32}$")
DURATION_TOLERANCE_S = 0.35

CREATE_NO_WINDOW = 0x08000000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
_JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
_JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_PROCESS_SET_QUOTA = 0x0100
_PROCESS_TERMINATE = 0x0001
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class WorkerError(RuntimeError):
    """Any failure that must surface to the user as a failed job."""


class ToolRejected(WorkerError):
    """A program outside the allowlist was requested."""


class MediaRejected(WorkerError):
    """A media reference is missing, too large or not an allowed file type."""


# --------------------------------------------------------------------------- #
# tools
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Tools:
    ffmpeg: Path
    ffprobe: Path
    root: Path


def resolve_tools(tools_root: str | os.PathLike[str]) -> Tools:
    """Resolve the two allowed executables by absolute path inside *tools_root*."""
    root = Path(tools_root).resolve()
    if not root.is_dir():
        raise ToolRejected(f"tools directory not found: {root}")
    resolved: dict[str, Path] = {}
    expected_names = {f"{name}.exe" for name in ALLOWED_TOOLS} if os.name == "nt" else set(ALLOWED_TOOLS)
    for name in ALLOWED_TOOLS:
        candidate = (root / f"{name}.exe").resolve() if os.name == "nt" else (root / name).resolve()
        if candidate.name.lower() not in expected_names:
            raise ToolRejected(f"unexpected executable name: {candidate.name}")
        if not path_rules.is_within(candidate, root):
            raise ToolRejected(f"{name} resolves outside the tools directory")
        if not candidate.is_file():
            raise ToolRejected(f"{name} not found at {candidate}")
        resolved[name] = candidate
    return Tools(ffmpeg=resolved["ffmpeg"], ffprobe=resolved["ffprobe"], root=root)


def tool_version(tools: Tools) -> str:
    """First line of ``ffmpeg -version`` (used by /health), never fails hard."""
    try:
        result = subprocess.run(
            [str(tools.ffmpeg), "-hide_banner", "-version"],
            capture_output=True, text=True, timeout=15, check=False,
            env=filtered_env(Path(os.environ.get("TEMP", "."))), creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        first = (result.stdout or "").splitlines()[0]
        match = re.search(r"ffmpeg version (\S+)", first)
        return match.group(1) if match else first.strip()
    except (OSError, subprocess.SubprocessError, IndexError):
        return "unknown"


# --------------------------------------------------------------------------- #
# media
# --------------------------------------------------------------------------- #


def verify_media_file(media_root: str | os.PathLike[str], relative: str, *, max_bytes: int = MAX_INPUT_BYTES) -> Path:
    """Resolve a document media reference to a real file inside the media root."""
    suffix = Path(relative).suffix.lower()
    if suffix in FORBIDDEN_EXTENSIONS:
        raise MediaRejected(f"{relative}: executable or script files are not accepted")
    if suffix not in ALLOWED_MEDIA_EXTENSIONS:
        raise MediaRejected(f"{relative}: unsupported extension {suffix or '(none)'}")
    try:
        resolved = path_rules.resolve_within(media_root, relative, must_exist=True, field=relative)
    except path_rules.PathError as exc:
        raise MediaRejected(str(exc)) from exc
    size = resolved.stat().st_size
    if size <= 0:
        raise MediaRejected(f"{relative}: file is empty")
    if size > max_bytes:
        raise MediaRejected(f"{relative}: {size} bytes exceeds the {max_bytes} byte limit")
    return resolved


def sha256_file(path: Path, *, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def probe_media(path: Path, tools: Tools) -> dict:
    """ffprobe a media file and return the parts the renderer needs."""
    args = [
        str(tools.ffprobe), "-hide_banner", "-v", "error",
        "-print_format", "json", "-show_streams", "-show_format", str(path),
    ]
    result = subprocess.run(
        args, capture_output=True, text=True, timeout=PROBE_TIMEOUT_S, check=False,
        env=filtered_env(path.parent), creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode != 0:
        raise MediaRejected(f"ffprobe failed for {path.name}: {(result.stderr or '').strip()[:300]}")
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise MediaRejected(f"ffprobe returned invalid JSON for {path.name}") from exc

    streams = payload.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = 0.0
    for source in (payload.get("format") or {}, video or {}, audio or {}):
        try:
            duration = float(source.get("duration") or 0.0)
        except (TypeError, ValueError):
            duration = 0.0
        if duration > 0:
            break
    return {
        "path": str(path),
        "duration": round(duration, 3),
        "has_video": video is not None,
        "has_audio": audio is not None,
        "video_codec": (video or {}).get("codec_name"),
        "audio_codec": (audio or {}).get("codec_name"),
        "width": (video or {}).get("width"),
        "height": (video or {}).get("height"),
        "avg_frame_rate": (video or {}).get("avg_frame_rate"),
    }


# --------------------------------------------------------------------------- #
# environment
# --------------------------------------------------------------------------- #


def filtered_env(job_dir: str | os.PathLike[str], *, extra: dict[str, str] | None = None) -> dict[str, str]:
    """Default-deny environment for the child process.

    Only the handful of Windows variables ffmpeg needs to start survive, and
    TEMP/TMP are redirected into the job folder. Everything else — API keys,
    tokens, profile paths, SSH agent sockets — is dropped.
    """
    env: dict[str, str] = {}
    for name in ENV_ALLOWLIST:
        value = os.environ.get(name)
        if value:
            if any(marker in name.upper() for marker in SECRET_MARKERS):
                continue
            env[name] = value
    temp_dir = Path(job_dir) / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    env["TEMP"] = str(temp_dir)
    env["TMP"] = str(temp_dir)
    env.setdefault("SystemRoot", os.environ.get("SystemRoot", r"C:\Windows"))
    env.setdefault("windir", env["SystemRoot"])
    env.setdefault("SystemDrive", os.environ.get("SystemDrive", "C:"))
    if extra:
        for name, value in extra.items():
            if any(marker in name.upper() for marker in SECRET_MARKERS):
                raise WorkerError(f"refusing to pass suspicious variable {name}")
            env[name] = value
    return env


# --------------------------------------------------------------------------- #
# argument allowlist
# --------------------------------------------------------------------------- #


def inline_graph(graph: str) -> str:
    """Collapse a compiled graph into one argv-safe line (ffmpeg joins on ';')."""
    return graph.replace(";\n", ";").strip()


def assert_args_allowed(
    args: Iterable[str],
    *,
    roots: Iterable[str | os.PathLike[str]],
    allow_program: str | os.PathLike[str] | None = None,
    allow_graph: str | None = None,
) -> None:
    """Verify a compiled command line before execution.

    Every ``-flag`` must be allowlisted; every positional value must be a
    numeric token, an allowlisted literal (``pipe:1``, ``mp4``, ...), or a path
    inside one of *roots* with an accepted extension. When *allow_program* is
    given, argv[0] must resolve to exactly that executable.

    *allow_graph* is the one exception allowed to look like free text: the
    inline filtergraph. It is accepted only when the argument is byte-identical
    to the graph this process compiled, never because "-filter_complex" happens
    to be a known flag.
    """
    args = [arg for arg in args]
    if allow_program is not None:
        if not args or Path(args[0]).resolve() != Path(allow_program).resolve():
            raise WorkerError(f"first argument must be the allowlisted tool {allow_program}")
        args = args[1:]
    if allow_graph is not None:
        position = args.index("-filter_complex") if "-filter_complex" in args else -1
        if position > 0:
            if position + 1 >= len(args) or args[position + 1] != allow_graph:
                raise WorkerError("inline filter graph does not match the compiled graph")
            del args[position:position + 2]
    allowed_roots = [Path(root).resolve() for root in roots]
    literals = {
        "pipe:1", "error", "mp4", "json", "veryfast", "ultrafast", "medium", "yuv420p",
        "faststart", "aac", "libx264", "warning", "info",
    }
    total = 0
    for arg in args:
        total += 1
        if not isinstance(arg, str) or not arg:
            raise WorkerError("empty or non-string argument rejected")
        if "\x00" in arg or "\n" in arg or "\r" in arg:
            raise WorkerError(f"control characters in argument: {arg!r}")
        if arg.startswith("-"):
            if re.fullmatch(r"-\d+(\.\d+)?", arg):
                continue  # valor numérico negativo (p. ej. -stream_loop -1)
            flag = arg.split("=", 1)[0]
            if flag in FORBIDDEN_FLAGS:
                raise WorkerError(f"forbidden flag: {flag}")
            if flag not in ALLOWED_FLAGS:
                raise WorkerError(f"flag not in allowlist: {flag}")
            continue
        if arg in literals or arg.lstrip("+") in literals:
            continue
        if re.fullmatch(r"-?\d+(\.\d+)?[kKmM]?", arg) or re.fullmatch(r"\d+/\d+", arg):
            continue
        if re.fullmatch(r"\[[A-Za-z0-9_]+\]", arg):  # filtergraph label for -map
            continue
        if re.fullmatch(r"[a-z0-9]+:[a-z0-9]+", arg):  # -loglevel / -progress style values
            continue
        candidate = Path(arg)
        suffix = candidate.suffix.lower()
        if suffix in FORBIDDEN_EXTENSIONS:
            raise WorkerError(f"executable or script argument rejected: {arg}")
        if suffix and suffix not in ALLOWED_MEDIA_EXTENSIONS | {".txt", ".json", ".log"}:
            raise WorkerError(f"argument with unsupported extension: {arg}")
        if suffix in {".txt", ".json", ".log"}:
            if not candidate.is_absolute():
                raise WorkerError(f"script/log path must be absolute: {arg}")
            if not any(path_rules.is_within(candidate, root) for root in allowed_roots):
                raise WorkerError(f"script/log path escapes the job directory: {arg}")
            continue
        if not candidate.is_absolute():
            raise WorkerError(f"media argument must be absolute: {arg}")
        if not any(path_rules.is_within(candidate, root) for root in allowed_roots):
            raise WorkerError(f"media path escapes the allowed roots: {arg}")
    if total == 0:
        raise WorkerError("empty command line")


# --------------------------------------------------------------------------- #
# Job Object (Windows)
# --------------------------------------------------------------------------- #


class _JobObjectBasicLimits(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JobObjectExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobObjectBasicLimits),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class ProcessLimit:
    """Windows Job Object: memory ceiling, active-process cap, kill-on-close.

    Not a security boundary (PLAN explicitly says so). It bounds resources and
    guarantees the whole tree dies when the job is cancelled or the service
    exits. When the API is unavailable the worker falls back to
    ``taskkill /T /F`` and reports ``enforced=False``.
    """

    def __init__(self, *, memory_limit_mb: int = DEFAULT_MEMORY_LIMIT_MB,
                 active_processes: int = DEFAULT_ACTIVE_PROCESS_LIMIT):
        self.memory_limit_mb = int(memory_limit_mb)
        self.active_processes = int(active_processes)
        self.handle: int | None = None
        self.enforced = False
        self.fallback = ""
        self.assigned = False
        self._k32: Any = None

    # -- lifecycle ------------------------------------------------------- #
    def __enter__(self) -> "ProcessLimit":
        self.create()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def create(self) -> bool:
        if os.name != "nt":
            self.fallback = "Job Objects are Windows-only; using process-group kill"
            return False
        try:
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.CreateJobObjectW.restype = ctypes.c_void_p
            k32.CreateJobObjectW.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p)
            k32.SetInformationJobObject.restype = ctypes.c_int
            k32.SetInformationJobObject.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32)
            k32.AssignProcessToJobObject.restype = ctypes.c_int
            k32.AssignProcessToJobObject.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
            k32.TerminateJobObject.restype = ctypes.c_int
            k32.TerminateJobObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
            k32.CloseHandle.restype = ctypes.c_int
            k32.CloseHandle.argtypes = (ctypes.c_void_p,)
            k32.OpenProcess.restype = ctypes.c_void_p
            k32.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
            k32.QueryInformationJobObject.restype = ctypes.c_int
            k32.QueryInformationJobObject.argtypes = (
                ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p,
            )

            handle = k32.CreateJobObjectW(None, None)
            if not handle:
                raise ctypes.WinError(ctypes.get_last_error())
            info = _JobObjectExtendedLimits()
            info.BasicLimitInformation.LimitFlags = (
                _JOB_OBJECT_LIMIT_PROCESS_MEMORY
                | _JOB_OBJECT_LIMIT_JOB_MEMORY
                | _JOB_OBJECT_LIMIT_ACTIVE_PROCESS
                | _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )
            limit_bytes = self.memory_limit_mb * 1024 * 1024
            info.ProcessMemoryLimit = limit_bytes
            info.JobMemoryLimit = limit_bytes
            info.BasicLimitInformation.ActiveProcessLimit = self.active_processes
            if not k32.SetInformationJobObject(handle, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                                               ctypes.byref(info), ctypes.sizeof(info)):
                error = ctypes.get_last_error()
                k32.CloseHandle(handle)
                raise ctypes.WinError(error)
            self._k32 = k32
            self.handle = handle
            self.enforced = True
            return True
        except (OSError, AttributeError, ValueError) as exc:
            self.fallback = f"{type(exc).__name__}: {exc}"
            self.handle = None
            self.enforced = False
            return False

    def assign(self, pid: int) -> bool:
        if not self.enforced or not self.handle or not self._k32:
            return False
        handle = self._k32.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, 0, int(pid))
        if not handle:
            return False
        try:
            self.assigned = bool(self._k32.AssignProcessToJobObject(self.handle, handle))
            return self.assigned
        finally:
            self._k32.CloseHandle(handle)

    def terminate(self) -> bool:
        if self.enforced and self.handle and self._k32:
            return bool(self._k32.TerminateJobObject(self.handle, 1))
        return False

    def peak_memory_bytes(self) -> int | None:
        if not self.enforced or not self.handle or not self._k32:
            return None
        info = _JobObjectExtendedLimits()
        ok = self._k32.QueryInformationJobObject(
            self.handle, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(info), ctypes.sizeof(info), None,
        )
        return int(info.PeakProcessMemoryUsed) if ok else None

    def close(self) -> None:
        if self.handle and self._k32:
            # KILL_ON_JOB_CLOSE: closing the handle terminates any survivor.
            self._k32.CloseHandle(self.handle)
        self.handle = None
        self.enforced = False


def process_image_path(pid: int) -> str | None:
    """Full image path of a PID, or None when it is gone or inaccessible."""
    if os.name != "nt":
        return None
    try:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = ctypes.c_void_p
        k32.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
        k32.QueryFullProcessImageNameW.restype = ctypes.c_int
        k32.QueryFullProcessImageNameW.argtypes = (
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_uint32),
        )
        k32.CloseHandle.argtypes = (ctypes.c_void_p,)
        handle = k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, 0, int(pid))
        if not handle:
            return None
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = ctypes.c_uint32(len(buffer))
            if not k32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return None
            return buffer.value
        finally:
            k32.CloseHandle(handle)
    except (OSError, AttributeError):
        return None


def terminate_pid_tree(pid: int, *, tools_root: str | os.PathLike[str], timeout_s: float = 5.0) -> bool:
    """Kill a leftover renderer PID, but only if it really is our ffmpeg.

    A recycled PID belonging to another program must never be killed (C7), so
    the image path is verified against the tools directory first.
    """
    if not isinstance(pid, int) or pid <= 1:
        return False
    image = process_image_path(pid)
    if image is None:
        return False
    if not path_rules.is_within(image, tools_root):
        return False
    return _taskkill(pid, timeout_s=timeout_s)


def _taskkill(pid: int, *, timeout_s: float = 5.0) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, 9)
            return True
        except OSError:
            return False
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    taskkill = Path(system_root) / "System32" / "taskkill.exe"
    if not taskkill.is_file():
        return False
    try:
        subprocess.run(
            [str(taskkill), "/T", "/F", "/PID", str(int(pid))],
            capture_output=True, timeout=timeout_s, check=False,
            env=filtered_env(Path(os.environ.get("TEMP", "."))),
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def pid_is_alive(pid: int) -> bool:
    if not isinstance(pid, int) or pid <= 1:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    return process_image_path(pid) is not None


# --------------------------------------------------------------------------- #
# command compilation
# --------------------------------------------------------------------------- #


#: Export presets (phase 2C). A preset fixes the *output frame size*; the frame
#: rate still comes from the document. ``experimental`` marks sizes that work and
#: are tested but are not offered as the default.
@dataclass(frozen=True)
class Preset:
    name: str
    width: int
    height: int
    experimental: bool = False


PRESETS: dict[str, Preset] = {
    "mp4-720p30": Preset("mp4-720p30", 1280, 720),
    "mp4-1080p30": Preset("mp4-1080p30", 1920, 1080, experimental=True),
    "mp4-720p30-vertical": Preset("mp4-720p30-vertical", 720, 1280),
    "mp4-720p30-square": Preset("mp4-720p30-square", 720, 720),
}
DEFAULT_PRESET = "mp4-720p30"


def preset_spec(preset: str) -> Preset:
    """Catalogue lookup; an unknown name is a worker error, not a crash."""
    spec = PRESETS.get(str(preset))
    if spec is None:
        raise WorkerError(f"unsupported preset: {preset!r}")
    return spec


def _fit_filters(width: int, height: int, *, native: bool) -> list[str]:
    """Scale a source into the output frame.

    ``native`` keeps the historical letterbox path byte-identical (2B behaviour);
    a preset that changes the frame size scales to cover and crops the centre,
    so a landscape project exported vertical fills the frame without bars.
    """
    if native:
        return [
            f"scale={width}:{height}:force_original_aspect_ratio=decrease",
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black",
        ]
    return [
        f"scale={width}:{height}:force_original_aspect_ratio=increase",
        f"crop={width}:{height}",
    ]


def _ken_burns_filter(motion: dict, *, duration: float, fps_num: int, fps_den: int,
                      width: int, height: int) -> str:
    """``zoompan`` for a still image: one output frame per looped input frame.

    ``d=1`` keeps the looped still's frame count (no frame explosion) and ``in``
    is that looped frame index, so the motion is linear across the scene.
    """
    frames = max(1, int(round(duration * fps_num / fps_den)))
    span = max(1, frames - 1)
    progress = f"min(1,in/{span})"
    zoom = motion["zoom"]
    z = f"1+{zoom - 1:.4f}*{progress}"
    pan = motion["pan"]
    x = "(iw-iw/zoom)/2"
    y = "(ih-ih/zoom)/2"
    if pan == "right":
        x = f"{progress}*(iw-iw/zoom)"
    elif pan == "left":
        x = f"(1-{progress})*(iw-iw/zoom)"
    elif pan == "down":
        y = f"{progress}*(ih-ih/zoom)"
    elif pan == "up":
        y = f"(1-{progress})*(ih-ih/zoom)"
    rate = str(fps_num) if fps_den == 1 else f"{fps_num}/{fps_den}"
    return f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={width}x{height}:fps={rate}"


def _f(value: Any) -> str:
    return f"{float(value):.3f}"


def _filter_path(path: Path) -> str:
    """Quote a path for a filtergraph option, the way this build actually parses it.

    Measured on ffmpeg n9.0.1: the graph is tokenised *before* quotes are honoured,
    so ``:`` in ``C:/…`` splits the option list even inside ``'…'``. The form that
    renders is quotes **plus** a backslash before the colon (``'C\\:/…'``); plain
    quotes, plain backslashes and no-fontfile all fail with "No option name near".
    An embedded quote uses ffmpeg's documented ``'\\''`` recipe.
    """
    text = str(path).replace("\\", "/").replace("'", "'\\''")
    for char in (":", ",", "[", "]", ";"):
        text = text.replace(char, "\\" + char)
    return f"'{text}'"


def _transition_fades(doc: dict) -> tuple[list[float], list[float]]:
    """Legacy cut path: (fade_in, fade_out) per scene, fades through black.

    ``scenes[i].transition`` is the transition *entering* scene i, so the fade
    out belongs to the previous scene and uses the same duration. This is only
    used when **no** scene overlaps its neighbour; as soon as one does, the
    video chain is compiled with real ``xfade`` transitions (phase 2B) and this
    function contributes nothing, so the graph of a document without
    transitions stays byte-identical to the pre-2B renderer.
    """
    scenes = doc["scenes"]
    fade_in = [project.transition_seconds(scene.get("transition", "none")) for scene in scenes]
    fade_out = [0.0] * len(scenes)
    for index in range(1, len(scenes)):
        fade_out[index - 1] = fade_in[index]
    return fade_in, fade_out


def _r(value: float) -> float:
    """Round a timeline value to the document's precision (same as project.py)."""
    return round(float(value), project.FLOAT_DECIMALS)


def xfade_lines(doc: dict, overlaps: list[float]) -> list[str]:
    """Compile the crossfade chain that replaces the video concat.

    Scene segments keep their ``[vN]`` labels; each step consumes the running
    result plus one scene and emits either an ``xfade`` (real overlap, offset =
    accumulated duration - overlap) or a ``concat`` for a pending cut. The last
    step always emits ``[vcat]`` so every downstream stage (drawtext, logo,
    final trim) keeps working on one continuous line with absolute timestamps.
    """
    scenes = doc["scenes"]
    durations = [project.scene_duration(scene) for scene in scenes]
    total = project.timeline_duration(doc)
    lines: list[str] = []
    current = "v0"
    accumulated = durations[0]
    for index in range(1, len(scenes)):
        last = index == len(scenes) - 1
        label = "vcat" if last else f"vx{index}"
        overlap = overlaps[index]
        if overlap <= 0:
            lines.append(f"[{current}][v{index}]concat=n=2:v=1:a=0[{label}]")
            accumulated = _r(accumulated + durations[index])
            current = label
            continue
        style = project.transition_style(scenes[index].get("transition"))
        offset = _r(accumulated - overlap)
        if offset < 0 or overlap > accumulated:
            raise WorkerError(
                f"transition {scenes[index].get('transition')!r} does not fit "
                f"({overlap}s needs {accumulated}s of material before it)"
            )
        lines.append(
            f"[{current}][v{index}]xfade=transition={style}:"
            f"duration={_f(overlap)}:offset={_f(offset)}[{label}]"
        )
        accumulated = _r(offset + durations[index])
        current = label
    if abs(accumulated - total) > 0.002:  # pragma: no cover - invariant guard
        raise WorkerError(
            f"crossfade timeline mismatch: chain ends at {accumulated:.3f}s, "
            f"document says {total:.3f}s"
        )
    return lines


#: Text animation timing (phase 2A). Both directions last the same 300 ms and a
#: slide travels 40 px, so the look stays consistent across projects.
TEXT_FADE_S = 0.3
TEXT_SLIDE_PX = 40

#: Watermark geometry: margin as a fraction of the frame height, floor 8 px.
LOGO_MARGIN_RATIO = 0.03
LOGO_MIN_MARGIN = 8

#: overlay x/y expressions keyed by the document's ``logo.position`` enum.
LOGO_POSITION_EXPRESSIONS = {
    "top-left": ("{m}", "{m}"),
    "top-center": ("(W-w)/2", "{m}"),
    "top-right": ("W-w-{m}", "{m}"),
    "center-left": ("{m}", "(H-h)/2"),
    "center": ("(W-w)/2", "(H-h)/2"),
    "center-right": ("W-w-{m}", "(H-h)/2"),
    "bottom-left": ("{m}", "H-h-{m}"),
    "bottom-center": ("(W-w)/2", "H-h-{m}"),
    "bottom-right": ("W-w-{m}", "H-h-{m}"),
}


def _asset_for(doc: dict, asset_id: Any) -> dict | None:
    if not isinstance(asset_id, str):
        return None
    return next((a for a in doc.get("assets") or [] if isinstance(a, dict) and a.get("id") == asset_id), None)


def _music_asset(doc: dict) -> dict | None:
    music = doc.get("music")
    if not isinstance(music, dict):
        return None
    return _asset_for(doc, music.get("assetId"))


def _logo_asset(doc: dict) -> dict | None:
    logo = doc.get("logo")
    if not isinstance(logo, dict):
        return None
    return _asset_for(doc, logo.get("assetId"))


def extra_input_indexes(doc: dict) -> tuple[int | None, int | None]:
    """The only place that knows how extra inputs are numbered.

    Scenes occupy ``0..len(scenes)-1``; music (when present) comes next and the
    logo image after it. Callers must never assume the music is the last input:
    with a watermark the logo is.
    """
    count = len(doc.get("scenes") or [])
    music_index = count if _music_asset(doc) is not None else None
    logo_index = None
    if _logo_asset(doc) is not None:
        logo_index = count + (1 if music_index is not None else 0)
    return music_index, logo_index


def _audio_event_pairs(doc: dict) -> list[tuple[dict, dict]]:
    """``(event, asset)`` pairs for the document's sound effects, in order.

    Only events whose asset resolves to an audio asset are returned: the
    validator already rejects anything else, and the mixer must never index an
    input that :func:`build_input_plan` did not create.
    """
    events = doc.get("audioEvents")
    if not isinstance(events, list):
        return []
    pairs: list[tuple[dict, dict]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        asset = _asset_for(doc, event.get("assetId"))
        if asset is None or asset.get("kind") != "audio":
            continue
        pairs.append((event, asset))
    return pairs


def audio_event_indexes(doc: dict) -> list[int]:
    """Input indexes of the sound-effect files, one per event.

    Same asset used twice gets two inputs: each event needs its own ``adelay``,
    so sharing a stream would need an ``asplit`` and a second label anyway.
    """
    base = len(doc.get("scenes") or [])
    if _music_asset(doc) is not None:
        base += 1
    if _logo_asset(doc) is not None:
        base += 1
    return [base + offset for offset in range(len(_audio_event_pairs(doc)))]


@dataclass(frozen=True)
class InputPlan:
    """Explicit input layout handed to ffmpeg and to the filtergraph."""

    args: list[str] = field(default_factory=list)
    scene_labels: list[str] = field(default_factory=list)
    music_index: int | None = None
    logo_index: int | None = None
    event_indexes: list[int] = field(default_factory=list)


def build_input_plan(doc: dict, media_files: dict[str, Path]) -> InputPlan:
    """Compile the input arguments and the index map for scenes, music and logo."""
    args: list[str] = []
    labels: list[str] = []
    fps_num = int(doc["fps"]["num"])
    for index, scene in enumerate(doc["scenes"]):
        source = scene["source"]
        path = media_files[source["path"]]
        # A still plays for its on-screen length; a video reads its whole source
        # span and speed is applied later with setpts/atempo.
        duration = project.scene_duration(scene)
        if source["kind"] == "image":
            args += ["-loop", "1", "-framerate", str(fps_num), "-t", _f(duration)]
        else:
            args += ["-ss", _f(scene["in"]), "-t", _f(project.scene_source_duration(scene))]
        args += ["-i", str(path)]
        labels.append(str(index))

    music_index, logo_index = extra_input_indexes(doc)
    music = doc.get("music")
    if music_index is not None and isinstance(music, dict):
        asset = _music_asset(doc)
        if asset is not None:
            if music.get("loop"):
                args += ["-stream_loop", "-1"]
            args += ["-i", str(media_files[asset["path"]])]

    logo = doc.get("logo")
    logo_asset = _logo_asset(doc)
    if logo_index is not None and logo_asset is not None and isinstance(logo, dict):
        fps = f'{int(doc["fps"]["num"])}/{int(doc["fps"]["den"])}'
        # A still image needs a timed, constant-rate stream to overlay over.
        args += ["-loop", "1", "-framerate", fps, "-t", _f(project.timeline_duration(doc))]
        args += ["-i", str(media_files[logo_asset["path"]])]

    for _event, asset in _audio_event_pairs(doc):
        args += ["-i", str(media_files[asset["path"]])]

    return InputPlan(
        args=args,
        scene_labels=labels,
        music_index=music_index,
        logo_index=logo_index,
        event_indexes=audio_event_indexes(doc),
    )


def build_inputs(doc: dict, media_files: dict[str, Path]) -> tuple[list[str], list[str]]:
    """Compatibility view of :func:`build_input_plan`: (args, scene_input_labels)."""
    plan = build_input_plan(doc, media_files)
    return plan.args, plan.scene_labels


def _drawtext_color(value: str) -> str:
    """``#RRGGBB`` -> ``0xRRGGBB``, the form ffmpeg parses without shell trouble."""
    return "0x" + str(value).lstrip("#").upper()


def _text_style(item: dict) -> dict:
    """Resolve one caption's style, applying the documented defaults."""
    animation = item.get("animation")
    if not isinstance(animation, dict):
        animation = {}
    return {
        "size": int(item.get("size") or project.TEXT_SIZE_DEFAULT),
        "color": item.get("color") or project.TEXT_COLOR_DEFAULT,
        "border": int(item.get("border") or 0),
        "borderColor": item.get("borderColor") or project.TEXT_BORDER_COLOR_DEFAULT,
        "shadow": int(item.get("shadow") or 0),
        "in": animation.get("in") or "none",
        "out": animation.get("out") or "none",
    }


def _text_motion(item: dict, start: float, end: float) -> tuple[str, str | None]:
    """Return ``(y_suffix, alpha_expression)`` for a caption's animation.

    ``y_suffix`` is appended to the static y expression; ``alpha`` is ``None``
    when the caption does not fade, so a static caption keeps the previous graph.
    """
    style = _text_style(item)
    begin, finish = _f(start), _f(end)
    span = _f(TEXT_FADE_S)
    y_parts: list[str] = []
    ramp_in = f"min(1,max(0,(t-{begin})/{span}))"
    ramp_out = f"min(1,max(0,(t-{_f(max(0.0, end - TEXT_FADE_S))})/{span}))"
    if style["in"] == "slide-up":
        y_parts.append(f"+(1-{ramp_in})*{TEXT_SLIDE_PX}")
    elif style["in"] == "slide-down":
        y_parts.append(f"-(1-{ramp_in})*{TEXT_SLIDE_PX}")
    if style["out"] == "slide-up":
        y_parts.append(f"-{ramp_out}*{TEXT_SLIDE_PX}")
    elif style["out"] == "slide-down":
        y_parts.append(f"+{ramp_out}*{TEXT_SLIDE_PX}")

    fading = {style["in"], style["out"]} & {"fade"}
    alpha = None
    if fading:
        fin = ramp_in if style["in"] == "fade" else "1"
        fout = f"min(1,max(0,({finish}-t)/{span}))" if style["out"] == "fade" else "1"
        alpha = f"{fin}*{fout}"
    return "".join(y_parts), alpha


def _scene_filter_chain(filters: Any, *, width: int, height: int) -> list[str]:
    """Compile ``scene.filters`` into eq/hue/vignette/boxblur, fixed order.

    An empty result means the scene graph is byte-identical to a document
    without filters. The chain runs before scale/pad so a vignette is centred
    on the framed picture and a blur radius refers to source pixels.
    """
    if not isinstance(filters, dict):
        return []
    chain: list[str] = []

    eq_parts: list[str] = []
    brightness = filters.get("brightness")
    if brightness is not None:
        eq_parts.append(f"brightness={float(brightness):.3f}")
    contrast = filters.get("contrast")
    if contrast is not None:
        eq_parts.append(f"contrast={float(contrast):.3f}")
    saturation = filters.get("saturation")
    if saturation is not None:
        eq_parts.append(f"saturation={float(saturation):.3f}")
    if eq_parts:
        chain.append("eq=" + ":".join(eq_parts))

    if filters.get("grayscale") is True:
        chain.append("hue=s=0")
    if filters.get("vignette") is True:
        chain.append("vignette")

    blur = float(filters.get("blur") or 0)
    if blur > 0:
        # boxblur takes an integer radius and refuses anything above half the frame.
        radius = max(1, min(int(round(blur)), max(1, min(width, height) // 2)))
        chain.append(f"boxblur={radius}")
    return chain


def build_filter_graph(
    doc: dict,
    *,
    job_dir: Path,
    probe_cache: dict[str, dict],
    captions: bool = True,
    font_file: Path | None = None,
    target: tuple[int, int] | None = None,
) -> str:
    """Compile the filtergraph. User text reaches ffmpeg only through files.

    ``target`` is the preset's output frame size. Without it the project's own
    ``width``/``height`` are used and the graph is byte-identical to phase 2B.
    """
    native_width, native_height = int(doc["width"]), int(doc["height"])
    width, height = (int(target[0]), int(target[1])) if target else (native_width, native_height)
    native_frame = (width, height) == (native_width, native_height)
    fps = f'{int(doc["fps"]["num"])}/{int(doc["fps"]["den"])}'
    master = int((doc.get("audio") or {}).get("masterVolume", 100)) / 100.0
    overlaps = project.transition_overlaps(doc)
    crossfade = project.has_crossfade(doc)
    if crossfade:
        # A real overlap replaces both the video concat and the legacy fades;
        # the first scene has nothing to blend with, so it is never faded.
        fade_in, fade_out = [0.0] * len(doc["scenes"]), [0.0] * len(doc["scenes"])
    else:
        fade_in, fade_out = _transition_fades(doc)
    lines: list[str] = []
    concat_inputs: list[str] = []

    for index, scene in enumerate(doc["scenes"]):
        source = scene["source"]
        probe = probe_cache.get(source["path"], {})
        is_image = source["kind"] == "image"
        duration = project.scene_duration(scene)  # on-screen seconds (span / speed)
        speed = project.scene_speed(scene)
        # A still slows down by being shown for less time; a video is retimed by
        # setpts, so it must read its whole source span first.
        trim_seconds = duration if is_image else project.scene_source_duration(scene)

        video_filters = [f"trim=duration={_f(trim_seconds)}"]
        if speed != 1.0 and not is_image:
            video_filters.append(f"setpts=(PTS-STARTPTS)/{speed:.3f}")
        else:
            video_filters.append("setpts=PTS-STARTPTS")
        video_filters += _scene_filter_chain(scene.get("filters"), width=width, height=height)
        video_filters += _fit_filters(width, height, native=native_frame)
        video_filters += ["setsar=1", f"fps={fps}"]
        motion = project.ken_burns(scene) if is_image else None
        if motion is not None:
            video_filters.append(_ken_burns_filter(
                motion, duration=duration,
                fps_num=int(doc["fps"]["num"]), fps_den=int(doc["fps"]["den"]),
                width=width, height=height,
            ))
        video_filters.append("format=yuv420p")
        if fade_in[index] > 0:
            video_filters.append(f"fade=t=in:st=0:d={_f(fade_in[index])}")
        if fade_out[index] > 0:
            start = max(0.0, duration - fade_out[index])
            video_filters.append(f"fade=t=out:st={_f(start)}:d={_f(fade_out[index])}")
        lines.append(f"[{index}:v]{','.join(video_filters)}[v{index}]")

        scene_audio = scene.get("audio") or {}
        volume = max(0.0, min(2.0, (float(scene_audio.get("volume", 100)) / 100.0) * master))
        audio_filters = [f"atrim=duration={_f(trim_seconds)}", "asetpts=PTS-STARTPTS"]
        if speed != 1.0 and not is_image:
            audio_filters.append(f"atempo={speed:.3f}")
        audio_filters.append(f"volume={volume:.4f}")
        if probe.get("has_audio") and source["kind"] == "video":
            if float(scene_audio.get("fadeIn") or 0) > 0:
                audio_filters.append(f"afade=t=in:st=0:d={_f(scene_audio['fadeIn'])}")
            if float(scene_audio.get("fadeOut") or 0) > 0:
                start = max(0.0, duration - float(scene_audio["fadeOut"]))
                audio_filters.append(f"afade=t=out:st={_f(start)}:d={_f(scene_audio['fadeOut'])}")
            audio_filters += ["aresample=48000", "aformat=channel_layouts=stereo", "apad", f"atrim=duration={_f(duration)}"]
            lines.append(f"[{index}:a]{','.join(audio_filters)}[a{index}]")
        else:
            lines.append(
                f"anullsrc=channel_layout=stereo:sample_rate=48000,atrim=duration={_f(duration)},"
                f"asetpts=PTS-STARTPTS,volume=0[a{index}]"
            )
        concat_inputs += [f"[v{index}]", f"[a{index}]"]

    scene_count = len(doc["scenes"])
    if crossfade:
        lines.extend(xfade_lines(doc, overlaps))
        audio_inputs = "".join(f"[a{index}]" for index in range(scene_count))
        lines.append(f"{audio_inputs}concat=n={scene_count}:v=0:a=1[acat]")
    else:
        lines.append(f"{''.join(concat_inputs)}concat=n={scene_count}:v=1:a=1[vcat][acat]")

    video_label = "vcat"
    if captions:
        starts = project.scene_starts(doc)
        overlay_index = 0
        for scene_index, scene in enumerate(doc["scenes"]):
            cursor = starts[scene_index]
            for item_index, item in enumerate(scene.get("text") or []):
                text_file = job_dir / f"text_{overlay_index}.txt"
                text_file.write_text(item["content"], encoding="utf-8", newline="")
                start = cursor + float(item["at"])
                end = cursor + float(item["until"])
                style = _text_style(item)
                position = item.get("position") or "bottom"
                base_y = {
                    "top": "h*0.08",
                    "center": "(h-text_h)/2",
                    "bottom": "h-text_h-h*0.08",
                }[position]
                y_suffix, alpha_expr = _text_motion(item, start, end)
                y_expr = base_y + y_suffix
                options = [
                    f"textfile={_filter_path(text_file)}",
                    "expansion=none",
                    f"fontsize={style['size']}",
                    f"fontcolor={_drawtext_color(style['color'])}",
                    "box=1",
                    "boxcolor=black@0.45",
                    "boxborderw=10",
                    "x=(w-text_w)/2",
                    f"y='{y_expr}'" if y_suffix else f"y={y_expr}",
                    f"enable='between(t,{_f(start)},{_f(end)})'",
                ]
                if style["border"] > 0:
                    options += [
                        f"borderw={style['border']}",
                        f"bordercolor={_drawtext_color(style['borderColor'])}",
                    ]
                if style["shadow"] > 0:
                    options += [f"shadowx={style['shadow']}", f"shadowy={style['shadow']}"]
                if alpha_expr is not None:
                    options += [f"alpha='{alpha_expr}'"]
                if font_file is not None:
                    options.insert(0, f"fontfile={_filter_path(font_file)}")
                next_label = f"vt{overlay_index}"
                lines.append(f"[{video_label}]drawtext={':'.join(options)}[{next_label}]")
                video_label = next_label
                overlay_index += 1

    total = project.timeline_duration(doc)
    logo = doc.get("logo")
    logo_asset = _logo_asset(doc)
    _music_index, logo_index = extra_input_indexes(doc)
    if isinstance(logo, dict) and logo_index is not None and logo_asset is not None:
        logo_scale = float(logo.get("scale") or project.LOGO_SCALE_DEFAULT)
        logo_opacity = float(logo.get("opacity", project.LOGO_OPACITY_DEFAULT))
        logo_width = max(2, int(round(width * logo_scale)))
        logo_width -= logo_width % 2  # even width keeps the alpha blend clean
        margin = max(LOGO_MIN_MARGIN, int(round(height * LOGO_MARGIN_RATIO)))
        x_expr, y_expr = LOGO_POSITION_EXPRESSIONS.get(
            str(logo.get("position") or project.LOGO_POSITION_DEFAULT),
            LOGO_POSITION_EXPRESSIONS[project.LOGO_POSITION_DEFAULT],
        )
        x_expr, y_expr = x_expr.format(m=margin), y_expr.format(m=margin)
        lines.append(
            f"[{logo_index}:v]format=rgba,scale={logo_width}:-2,"
            f"colorchannelmixer=aa={logo_opacity:.3f}[logo]"
        )
        lines.append(f"[{video_label}][logo]overlay=x={x_expr}:y={y_expr}:format=auto[vlogo]")
        video_label = "vlogo"

    lines.append(f"[{video_label}]trim=duration={_f(total)},setpts=PTS-STARTPTS,format=yuv420p[vout]")
    audio_label = "acat"
    events = _audio_event_pairs(doc)
    if events:
        # Sound effects join the scene bed *before* the music so a ducking music
        # bed reacts to effects too, and so the bed keeps its own loudness
        # treatment (an effect never re-runs loudnorm on the master mix).
        sfx_labels: list[str] = []
        for slot, ((event, asset), input_index) in enumerate(zip(events, audio_event_indexes(doc))):
            asset_seconds = float((probe_cache.get(asset["path"]) or {}).get("duration") or 0.0)
            volume = max(0.0, min(2.0, (float(event.get("volume", 100)) / 100.0) * master))
            chain = [
                f"[{input_index}:a]aresample=48000",
                "aformat=channel_layouts=stereo",
                f"volume={volume:.4f}",
            ]
            fade_in = float(event.get("fadeIn") or 0)
            fade_out = float(event.get("fadeOut") or 0)
            # Fades run before adelay: afade times are relative to the sound, and
            # adelay rewrites the timestamps afterwards.
            if fade_in > 0:
                chain.append(f"afade=t=in:st=0:d={_f(fade_in)}")
            if fade_out > 0 and asset_seconds > 0:
                chain.append(f"afade=t=out:st={_f(max(0.0, asset_seconds - fade_out))}:d={_f(fade_out)}")
            chain.append(f"adelay=delays={int(round(float(event['at']) * 1000))}:all=1")
            lines.append(",".join(chain) + f"[sfx{slot}]")
            sfx_labels.append(f"[sfx{slot}]")
        mix_inputs = f"[{audio_label}]" + "".join(sfx_labels)
        lines.append(
            f"{mix_inputs}amix=inputs={len(sfx_labels) + 1}:duration=longest:normalize=0[asfx]"
        )
        audio_label = "asfx"
    music = doc.get("music")
    music_index, _logo_index = extra_input_indexes(doc)
    if isinstance(music, dict) and music_index is not None:
        music_volume = max(0.0, min(2.0, (float(music.get("volume", 100)) / 100.0) * master))
        music_chain = [
            f"[{music_index}:a]aresample=48000",
            "aformat=channel_layouts=stereo",
            f"volume={music_volume:.4f}",
            f"atrim=duration={_f(total)}",
            "asetpts=PTS-STARTPTS",
        ]
        if float(music.get("fadeIn") or 0) > 0:
            music_chain.append(f"afade=t=in:st=0:d={_f(music['fadeIn'])}")
        if float(music.get("fadeOut") or 0) > 0:
            start = max(0.0, total - float(music["fadeOut"]))
            music_chain.append(f"afade=t=out:st={_f(start)}:d={_f(music['fadeOut'])}")
        lines.append(",".join(music_chain) + "[amus]")
        if music.get("ducking"):
            lines.append(f"[{audio_label}]asplit=2[adry][asc]")
            lines.append("[amus][asc]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=400[aduck]")
            lines.append("[adry][aduck]amix=inputs=2:duration=first:normalize=0[amixed]")
        else:
            lines.append(f"[{audio_label}][amus]amix=inputs=2:duration=first:normalize=0[amixed]")
        audio_label = "amixed"
    if (doc.get("audio") or {}).get("normalize"):
        lines.append(f"[{audio_label}]loudnorm=I=-16:TP=-1.5:LRA=11[anorm]")
        audio_label = "anorm"
    lines.append(f"[{audio_label}]atrim=duration={_f(total)},asetpts=PTS-STARTPTS[aout]")
    return ";\n".join(lines) + "\n"


def build_render_command(
    doc: dict,
    *,
    tools: Tools,
    media_files: dict[str, Path],
    filter_graph: str,
    output: Path,
    preset: str = "mp4-720p30",
) -> list[str]:
    """Compile the ffmpeg command line from the document (no user strings).

    The graph travels inline because this ffmpeg build has no
    ``-filter_complex_script`` (verified: ``ffmpeg -h full`` lists only
    ``-filter_complex``). That is safe only while two invariants hold, and both
    are tested: the graph is compiled here from numbers and fixed filter names
    (user text always goes to a ``textfile=``), and ``assert_args_allowed``
    compares the argument byte-for-byte against the graph we just compiled.
    """
    preset_spec(preset)  # catalogue check; the frame size is already in the graph
    if not filter_graph:
        raise WorkerError("empty filter graph")
    if "\n" in filter_graph or "\r" in filter_graph:
        raise WorkerError("filter graph must be a single line; use inline_graph()")
    if len(filter_graph) > MAX_FILTER_GRAPH_CHARS:
        raise WorkerError(
            f"filter graph is {len(filter_graph)} chars (limit {MAX_FILTER_GRAPH_CHARS}); "
            "render fewer scenes per job"
        )
    plan = build_input_plan(doc, media_files)
    total = project.timeline_duration(doc)
    args = [
        str(tools.ffmpeg), "-nostdin", "-hide_banner", "-nostats",
        "-loglevel", "error", "-progress", "pipe:1",
        *plan.args,
        "-filter_complex", filter_graph,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-r", f'{int(doc["fps"]["num"])}/{int(doc["fps"]["den"])}',
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        "-t", _f(total),
        "-f", "mp4", "-y", str(output),
    ]
    return args


def build_probe_command(path: Path, tools: Tools) -> list[str]:
    return [
        str(tools.ffprobe), "-hide_banner", "-v", "error",
        "-print_format", "json", "-show_streams", "-show_format", str(path),
    ]


# --------------------------------------------------------------------------- #
# process execution
# --------------------------------------------------------------------------- #


@dataclass
class ToolRun:
    exit_code: int | None
    cancelled: bool
    timed_out: bool
    wall_s: float
    stderr_tail: str
    stdout_tail: str
    peak_memory_bytes: int | None
    limits_enforced: bool


def run_tool(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    limit: ProcessLimit,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    cancel_event: threading.Event | None = None,
    should_cancel: Callable[[], bool] | None = None,
    on_line: Callable[[str], None] | None = None,
) -> ToolRun:
    """Run one allowlisted tool with cancellation, timeout and a memory ceiling."""
    started = time.monotonic()
    proc = subprocess.Popen(
        args,
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        close_fds=True,
        creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    limit.assigned = limit.assign(proc.pid)

    lock = threading.Lock()
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    stderr_size = 0

    def read_stdout() -> None:
        assert proc.stdout is not None
        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode("utf-8", "replace")
            with lock:
                stdout_chunks.append(line)
                del stdout_chunks[:-4000]
            if on_line is not None:
                try:
                    on_line(line)
                except Exception:  # progress callbacks must never kill the render
                    pass

    def read_stderr() -> None:
        nonlocal stderr_size
        assert proc.stderr is not None
        for raw in iter(proc.stderr.readline, b""):
            line = raw.decode("utf-8", "replace")
            with lock:
                if stderr_size < MAX_STDERR_BYTES:
                    stderr_chunks.append(line)
                    stderr_size += len(line)

    threads = [
        threading.Thread(target=read_stdout, name="ffmpeg-stdout", daemon=True),
        threading.Thread(target=read_stderr, name="ffmpeg-stderr", daemon=True),
    ]
    for thread in threads:
        thread.start()

    cancelled = False
    timed_out = False
    deadline = started + max(1.0, float(timeout_s))
    while proc.poll() is None:
        if cancel_event is not None and cancel_event.is_set():
            cancelled = True
        elif should_cancel is not None and should_cancel():
            cancelled = True
        if cancelled:
            _stop(proc, limit)
            break
        if time.monotonic() > deadline:
            timed_out = True
            _stop(proc, limit)
            break
        time.sleep(0.05)

    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:  # pragma: no cover - last-resort hard kill
        proc.kill()
        proc.wait(timeout=10)
    for thread in threads:
        thread.join(timeout=2)
    for stream in (proc.stdout, proc.stderr):
        if stream is not None:
            try:
                stream.close()  # the read threads own them while running; leak otherwise
            except OSError:
                pass

    with lock:
        stderr_tail = "".join(stderr_chunks)
        stdout_tail = "".join(stdout_chunks[-50:])

    return ToolRun(
        exit_code=proc.returncode,
        cancelled=cancelled,
        timed_out=timed_out,
        wall_s=round(time.monotonic() - started, 3),
        stderr_tail=stderr_tail,
        stdout_tail=stdout_tail,
        peak_memory_bytes=limit.peak_memory_bytes(),
        limits_enforced=limit.enforced and limit.assigned,
    )


def _stop(proc: subprocess.Popen, limit: ProcessLimit) -> None:
    """Terminate ffmpeg and everything it spawned, quickly and only here."""
    if limit.terminate():
        try:
            proc.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            pass
    try:
        proc.terminate()
    except OSError:
        pass
    try:
        proc.wait(timeout=5)
        return
    except subprocess.TimeoutExpired:
        pass
    _taskkill(proc.pid)
    try:
        proc.kill()
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# job layout
# --------------------------------------------------------------------------- #


@dataclass
class Layout:
    """Filesystem layout. jobs/ and out/ share one volume so rename is atomic."""

    data_root: Path
    media_root: Path

    def __post_init__(self) -> None:
        self.data_root = Path(self.data_root).resolve()
        self.media_root = Path(self.media_root).resolve()

    def ensure(self) -> "Layout":
        (self.data_root / "jobs").mkdir(parents=True, exist_ok=True)
        (self.data_root / "out").mkdir(parents=True, exist_ok=True)
        return self

    def check_job_id(self, job_id: str) -> str:
        if not isinstance(job_id, str) or not JOB_ID_RE.match(job_id):
            raise WorkerError(f"invalid job id: {job_id!r}")
        return job_id

    def job_dir(self, job_id: str) -> Path:
        return self.data_root / "jobs" / self.check_job_id(job_id)

    def out_dir(self, job_id: str) -> Path:
        return self.data_root / "out" / self.check_job_id(job_id)

    def staging_dir(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "staging"

    def snapshot_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "snapshot.json"

    def output_path(self, job_id: str, name: str = "output.mp4") -> Path:
        return self.out_dir(job_id) / name


@dataclass
class JobResult:
    state: str
    exit_code: int | None = None
    output_path: str | None = None
    output_name: str | None = None
    artifacts: list[str] = field(default_factory=list)
    duration_s: float = 0.0
    wall_s: float = 0.0
    error: str | None = None
    stage: str = "done"
    progress: float = 0.0
    limits_enforced: bool = False
    peak_memory_bytes: int | None = None
    verify_hash: bool = True

    @property
    def ok(self) -> bool:
        return self.state == "succeeded"


def _redact(text: str) -> str:
    """Strip the home directory and account name from anything kept as evidence.

    QA found the spike's ffmpeg log repeated the Windows user path four times
    (plan-pruebas.md §452). Logs are deliverable artefacts, so they are redacted
    at the source instead of at packaging time.
    """
    home = str(Path.home())
    out = text.replace(home, "<home>").replace(home.replace("\\", "/"), "<home>")
    user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    if len(user) >= 3:
        out = out.replace(user, "<user>")
    return out


def write_job_log(job_dir: str | os.PathLike[str], args: Sequence[str], run: "ToolRun") -> Path | None:
    """Write the redacted command + stderr of one render (diagnosis on failure)."""
    try:
        log = Path(job_dir) / "ffmpeg.log"
        body = (
            "[command]\n" + _redact(" ".join(str(arg) for arg in args)) + "\n\n"
            "[exit] " + str(run.exit_code) + "\n"
            "[stderr]\n" + _redact(run.stderr_tail or "") + "\n"
        )
        log.write_text(body, encoding="utf-8", newline="")
        return log
    except OSError:
        return None


def purge_derivatives(layout: Layout, job_id: str, *, keep_output: bool = True) -> list[str]:
    """Delete per-job derivatives (staging, text files, tmp) but keep the log."""
    job_dir = layout.job_dir(job_id)
    removed: list[str] = []
    staging = job_dir / "staging"
    if staging.exists():
        for entry in sorted(staging.rglob("*"), reverse=True):
            try:
                entry.unlink() if entry.is_file() else entry.rmdir()
            except OSError:
                pass
        removed.append("staging")
    for pattern in ("text_*.txt", "filters.txt", "ffprobe_*.json"):
        for entry in job_dir.glob(pattern):
            try:
                entry.unlink()
                removed.append(entry.name)
            except OSError:
                pass
    tmp = job_dir / "tmp"
    if tmp.exists():
        for entry in sorted(tmp.rglob("*"), reverse=True):
            try:
                entry.unlink() if entry.is_file() else entry.rmdir()
            except OSError:
                pass
        removed.append("tmp")
    if not keep_output:
        out_dir = layout.out_dir(job_id)
        if out_dir.exists():
            for entry in sorted(out_dir.rglob("*"), reverse=True):
                try:
                    entry.unlink() if entry.is_file() else entry.rmdir()
                except OSError:
                    pass
            removed.append("out")
    return removed


# --------------------------------------------------------------------------- #
# job execution
# --------------------------------------------------------------------------- #


def _find_font() -> Path | None:
    candidates = [
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts" / "segoeui.ttf",
        Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts" / "arial.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _progress_from_line(line: str) -> tuple[int | None, int | None]:
    """Parse one ``-progress`` line into (frame, out_time_us)."""
    text = line.strip()
    if text.startswith("frame="):
        try:
            return int(text.split("=", 1)[1]), None
        except ValueError:
            return None, None
    if text.startswith("out_time_us="):
        try:
            return None, int(text.split("=", 1)[1])
        except ValueError:
            return None, None
    return None, None


def validate_staged_output(
    path: Path,
    doc: dict,
    tools: Tools,
    *,
    expected_duration: float | None = None,
    expected_size: tuple[int, int] | None = None,
) -> dict:
    """Probe the staged MP4 and refuse anything that is not a complete render.

    ``expected_size`` is the preset's frame size; without it the document's own
    ``width``/``height`` are the contract.
    """
    if not path.is_file():
        raise WorkerError("staged output missing")
    size = path.stat().st_size
    if size <= 0:
        raise WorkerError("staged output is empty")
    if size > MAX_OUTPUT_BYTES:
        raise WorkerError(f"staged output exceeds {MAX_OUTPUT_BYTES} bytes")

    probe = probe_media(path, tools)
    if "mp4" not in str(probe.get("video_codec") or "") and not probe.get("has_video"):
        raise WorkerError("staged output has no video stream")
    if probe.get("video_codec") != "h264":
        raise WorkerError(f"unexpected video codec: {probe.get('video_codec')}")
    want_width, want_height = (
        (int(expected_size[0]), int(expected_size[1])) if expected_size
        else (int(doc["width"]), int(doc["height"]))
    )
    if (probe.get("width"), probe.get("height")) != (want_width, want_height):
        raise WorkerError(
            f"unexpected resolution {probe.get('width')}x{probe.get('height')}, "
            f"expected {want_width}x{want_height}"
        )
    if not probe.get("has_audio") or probe.get("audio_codec") != "aac":
        raise WorkerError(f"unexpected audio stream: {probe.get('audio_codec')}")
    expected = expected_duration if expected_duration is not None else project.timeline_duration(doc)
    if abs(float(probe.get("duration") or 0) - expected) > max(DURATION_TOLERANCE_S, expected * 0.05):
        raise WorkerError(
            f"unexpected duration {probe.get('duration')}s, expected {expected:.3f}s"
        )
    return {
        "bytes": size,
        "duration": probe["duration"],
        "width": probe["width"],
        "height": probe["height"],
        "video_codec": probe["video_codec"],
        "audio_codec": probe["audio_codec"],
    }


def run_job(
    snapshot: dict,
    *,
    job_id: str,
    layout: Layout,
    tools: Tools,
    preset: str = "mp4-720p30",
    captions: bool = True,
    cancel_event: threading.Event | None = None,
    should_cancel: Callable[[], bool] | None = None,
    progress_cb: Callable[[str, float, float | None], None] | None = None,
    memory_limit_mb: int = DEFAULT_MEMORY_LIMIT_MB,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    verify_hash: bool = True,
    output_name: str = "output.mp4",
) -> JobResult:
    """Probe → render → validate → promote. Never publishes a partial MP4."""
    started = time.monotonic()
    layout.check_job_id(job_id)
    job_dir = layout.job_dir(job_id)
    staging_dir = layout.staging_dir(job_id)
    staging_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "tmp").mkdir(parents=True, exist_ok=True)
    staged = staging_dir / output_name

    def report(stage: str, progress: float, eta: float | None = None) -> None:
        if progress_cb is not None:
            try:
                progress_cb(stage, progress, eta)
            except Exception:
                pass

    def cancelled() -> bool:
        if cancel_event is not None and cancel_event.is_set():
            return True
        return bool(should_cancel and should_cancel())

    total = project.timeline_duration(snapshot)
    preset_info = preset_spec(preset)
    target_size = (preset_info.width, preset_info.height)
    result = JobResult(state="failed", duration_s=total, stage="probing", progress=0.0,
                       limits_enforced=False, verify_hash=verify_hash)

    try:
        errors = project.validate_for_export(snapshot)
        if errors:
            raise WorkerError("; ".join(errors))

        report("probing", 1.0)
        media_files: dict[str, Path] = {}
        probe_cache: dict[str, dict] = {}
        assets = {asset["id"]: asset for asset in snapshot.get("assets") or []}
        for scene in snapshot["scenes"]:
            relative = scene["source"]["path"]
            if relative in media_files:
                continue
            path = verify_media_file(layout.media_root, relative)
            declared = None
            asset_id = scene["source"].get("assetId")
            if asset_id and asset_id in assets:
                declared = assets[asset_id].get("sha256")
            if verify_hash and declared:
                actual = sha256_file(path)
                if actual != declared:
                    raise MediaRejected(
                        f"{relative}: sha256 mismatch (document {declared[:12]}…, file {actual[:12]}…)"
                    )
            media_files[relative] = path
            probe_cache[relative] = probe_media(path, tools)
            if not probe_cache[relative].get("has_video"):
                raise MediaRejected(f"{relative}: no video stream")
            source_duration = float(probe_cache[relative].get("duration") or 0)
            if source_duration and float(scene["out"]) > source_duration + 0.1:
                raise MediaRejected(
                    f"{relative}: scene ends at {scene['out']}s but the file has {source_duration}s"
                )
            if cancelled():
                raise _Cancelled()

        music = snapshot.get("music")
        if music:
            music_asset = assets.get(music.get("assetId"))
            if music_asset is not None:
                relative = music_asset["path"]
                if relative not in media_files:
                    path = verify_media_file(layout.media_root, relative)
                    if verify_hash and music_asset.get("sha256"):
                        actual = sha256_file(path)
                        if actual != music_asset["sha256"]:
                            raise MediaRejected(
                                f"{relative}: sha256 mismatch (document {music_asset['sha256'][:12]}…, file {actual[:12]}…)"
                            )
                    music_probe = probe_media(path, tools)
                    if not music_probe.get("has_audio"):
                        raise MediaRejected(f"{relative}: no audio stream")
                    media_files[relative] = path

        logo = snapshot.get("logo")
        if isinstance(logo, dict):
            logo_asset = assets.get(logo.get("assetId"))
            if logo_asset is not None:
                relative = logo_asset["path"]
                if relative not in media_files:
                    path = verify_media_file(layout.media_root, relative)
                    if verify_hash and logo_asset.get("sha256"):
                        actual = sha256_file(path)
                        if actual != logo_asset["sha256"]:
                            raise MediaRejected(
                                f"{relative}: sha256 mismatch (document {logo_asset['sha256'][:12]}…, file {actual[:12]}…)"
                            )
                    logo_probe = probe_media(path, tools)
                    if not logo_probe.get("has_video"):
                        raise MediaRejected(f"{relative}: logo has no image stream")
                    media_files[relative] = path
                    probe_cache[relative] = logo_probe

        for event, event_asset in _audio_event_pairs(snapshot):
            relative = event_asset["path"]
            if relative not in media_files:
                path = verify_media_file(layout.media_root, relative)
                if verify_hash and event_asset.get("sha256"):
                    actual = sha256_file(path)
                    if actual != event_asset["sha256"]:
                        raise MediaRejected(
                            f"{relative}: sha256 mismatch (document {event_asset['sha256'][:12]}…, file {actual[:12]}…)"
                        )
                event_probe = probe_media(path, tools)
                if not event_probe.get("has_audio"):
                    raise MediaRejected(f"{relative}: audio event {event.get('id')!r} has no audio stream")
                media_files[relative] = path
                probe_cache[relative] = event_probe
            if cancelled():
                raise _Cancelled()

        report("rendering", 5.0)
        graph = inline_graph(build_filter_graph(
            snapshot, job_dir=job_dir, probe_cache=probe_cache,
            captions=captions, font_file=_find_font(), target=target_size,
        ))
        args = build_render_command(snapshot, tools=tools, media_files=media_files,
                                    filter_graph=graph, output=staged, preset=preset)
        assert_args_allowed(args, roots=[layout.media_root, job_dir, layout.out_dir(job_id)],
                            allow_program=tools.ffmpeg, allow_graph=graph)
        assert_args_allowed(build_probe_command(staged, tools), roots=[job_dir], allow_program=tools.ffprobe)

        limit = ProcessLimit(memory_limit_mb=memory_limit_mb)
        limit.create()
        result.limits_enforced = limit.enforced and limit.assigned
        progress_state = {"last": 0.0}

        def on_line(line: str) -> None:
            frame, out_time_us = _progress_from_line(line)
            if out_time_us is None or total <= 0:
                return
            pct = max(0.0, min(99.0, (out_time_us / 1_000_000.0) / total * 90.0 + 5.0))
            if pct - progress_state["last"] >= 1.0:
                progress_state["last"] = pct
                elapsed = max(0.001, time.monotonic() - started)
                done = max(0.001, pct - 5.0)
                eta = (elapsed / done) * (95.0 - pct)
                report("rendering", pct, round(eta, 1))

        try:
            run = run_tool(
                args, cwd=job_dir, env=filtered_env(job_dir), limit=limit,
                timeout_s=timeout_s, cancel_event=cancel_event, should_cancel=should_cancel,
                on_line=on_line,
            )
            result.peak_memory_bytes = run.peak_memory_bytes
            write_job_log(job_dir, args, run)
        finally:
            limit.close()

        result.wall_s = round(time.monotonic() - started, 3)
        if run.cancelled or cancelled():
            raise _Cancelled()
        if run.timed_out:
            raise WorkerError(f"render exceeded the {int(timeout_s)}s time limit")
        if run.exit_code != 0:
            tail = (run.stderr_tail or "").strip().splitlines()[-6:]
            raise WorkerError("ffmpeg failed: " + (" | ".join(tail) if tail else f"exit {run.exit_code}"))

        report("validating", 96.0)
        info = validate_staged_output(
            staged, snapshot, tools, expected_duration=total, expected_size=target_size,
        )

        report("promoting", 99.0)
        out_dir = layout.out_dir(job_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        final = out_dir / output_name
        os.replace(staged, final)  # same volume: atomic, no partial MP4 ever visible
        purge_derivatives(layout, job_id)
        report("done", 100.0, 0.0)

        result.state = "succeeded"
        result.stage = "done"
        result.progress = 100.0
        result.output_path = str(final)
        result.output_name = output_name
        result.artifacts = [output_name]
        result.duration_s = float(info.get("duration") or total)
        result.wall_s = round(time.monotonic() - started, 3)
        result.exit_code = 0
        return result

    except _Cancelled:
        purge_derivatives(layout, job_id)
        result.state = "cancelled"
        result.stage = "failed"
        result.error = "trabajo cancelado"
        result.wall_s = round(time.monotonic() - started, 3)
        return result
    except (WorkerError, project.ProjectError) as exc:
        purge_derivatives(layout, job_id)
        result.state = "failed"
        result.stage = "failed"
        result.error = str(exc)
        result.wall_s = round(time.monotonic() - started, 3)
        return result
    except Exception as exc:  # unexpected: still never publish a partial file
        purge_derivatives(layout, job_id)
        result.state = "failed"
        result.stage = "failed"
        result.error = f"{type(exc).__name__}: {exc}"
        result.wall_s = round(time.monotonic() - started, 3)
        return result


class _Cancelled(Exception):
    """Internal control-flow marker for a cancelled job."""
