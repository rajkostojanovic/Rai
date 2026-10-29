import math
import os
import random
import json
import sys
import time
import traceback
import importlib
import importlib.util
import threading
import warnings
from array import array
from pathlib import Path

existing_qt_logging_rules = os.environ.get("QT_LOGGING_RULES", "").strip()
_rai_qt_logging_rules = [
    "qt.multimedia.*=false",
]
if existing_qt_logging_rules:
    os.environ["QT_LOGGING_RULES"] = existing_qt_logging_rules + ";" + ";".join(_rai_qt_logging_rules)
else:
    os.environ["QT_LOGGING_RULES"] = ";".join(_rai_qt_logging_rules)

from PySide6.QtCore import Qt, QPoint, QPointF, Signal, QRectF, QSize, QSizeF, QObject, QTimer, QThread, QProcess, QEvent, qInstallMessageHandler
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QSplitter, QVBoxLayout, QLabel, QSlider, QComboBox, QPushButton, QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout, QTabWidget, QFileDialog, QMessageBox, QGroupBox, QScrollArea, QFrame, QLineEdit, QMenu
from PySide6.QtGui import QGuiApplication, QIcon, QImage, QPainter, QPen, QColor, QTabletEvent, QTransform, QFont, QFontMetricsF, QPixmap

from backend.further_development import (
    DEVELOPMENT_BRUSH_STYLE_LABELS,
    DEVELOPMENT_SHAPE_TOOL_LABELS,
    development_draw_brush_path,
    development_draw_brush_stamp,
    development_draw_color,
    development_draw_image_variant_object,
    development_draw_shape_geometry,
    development_draw_shape_spray,
    development_draw_spray_line,
    development_draw_spray_stamp,
    development_lerp_color,
    development_regular_polygon,
    development_shape_pen,
    development_smoothed_stroke_samples,
    development_spray_color,
    development_spray_factor,
    development_spray_spread,
    development_spray_step,
    development_stroke_size_from_pressure,
    default_image_variant_params,
    default_image_variant_stage_presets,
    development_tool_is_brush,
    development_tool_is_polygon,
    development_tool_is_shape,
    is_development_brush_style,
    is_development_polygon_side,
    normalize_image_variant_params,
)
from backend.further_development_ui import (
    build_further_development_change_tab,
    build_further_development_module_tab,
    build_further_development_object_tab,
    rebuild_photo_timeline,
    rebuild_stage_preview_grid,
)

_qt_suppressed_messages = (
    "No QtMultimedia backends found. Only QMediaDevices, QAudioDevice, QSoundEffect, QAudioSink, and QAudioSource are available.",
    "qt.multimedia.audiodevice.probes: toWaveFormatExtensible failed",
)


def _install_qt_message_filter():
    def handler(msg_type, context, message):
        text = str(message).strip()
        for prefix in _qt_suppressed_messages:
            if text.startswith(prefix):
                return
        if previous_handler is not None:
            previous_handler(msg_type, context, message)
        else:
            sys.stderr.write(text + "\n")

    previous_handler = qInstallMessageHandler(handler)
    return previous_handler


_previous_qt_message_handler = _install_qt_message_filter()

from PySide6.QtMultimedia import QAudioSource, QAudioFormat, QMediaDevices

warnings.filterwarnings(
    "ignore",
    message="data discontinuity in recording",
    module=r"soundcard\.mediafoundation",
)

APP_NAME = "Rai"
APP_VERSION = "0.1.0"
STARTUP_LOG_PATH = Path(__file__).with_name("rai_startup.log")
DEFAULT_BEAT_TRANSITION_DURATION_SCALE = 0.55
BEAT_TRANSITION_EFFECT_OPTIONS = (
    ("Immediate", "cut"),
    ("Interpolate", "interpolate"),
    ("Fade", "fade"),
    ("Wipe Left to Right", "wipe_horizontal"),
    ("Wipe Top to Bottom", "wipe_vertical"),
    ("Scanline Reconstruct", "scanline_reconstruct"),
)
BEAT_TRANSITION_EFFECTS = tuple(value for _, value in BEAT_TRANSITION_EFFECT_OPTIONS)
BEAT_TRANSITION_EASING_OPTIONS = (
    ("Linear", "linear"),
    ("Ease In", "ease_in"),
    ("Ease Out", "ease_out"),
    ("Ease In/Out", "ease_in_out"),
)
BEAT_TRANSITION_EASINGS = tuple(value for _, value in BEAT_TRANSITION_EASING_OPTIONS)
CHANGE_VISIBILITY_OPTIONS = (
    ("Visible", "visible"),
)
CHANGE_VISIBILITY_VALUES = tuple(value for _, value in CHANGE_VISIBILITY_OPTIONS)
IMAGE_SET_TIMING_MODE_OPTIONS = (
    ("Manual Window", "manual"),
    ("Average BPM", "average_bpm"),
)
IMAGE_SET_TIMING_MODE_VALUES = tuple(value for _, value in IMAGE_SET_TIMING_MODE_OPTIONS)
IMAGE_SET_FILE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif")
IMAGE_SET_CORE_PREFIXES = ("1v", "v", "core")
IMAGE_SET_TEXTURE_ORDER = ("u", "d", "h", "v")
IMAGE_SET_ATMOSPHERE_ORDER = ("w", "c", "n", "m")
IMAGE_SET_RHYTHM_ORDER = ("f", "s")
IMAGE_SET_RULE_SPECS = (
    ("texture", "High-Hats", IMAGE_SET_TEXTURE_ORDER),
    ("atmosphere", "Bass / Melody", IMAGE_SET_ATMOSPHERE_ORDER),
    ("rhythm", "Kick / Snare", IMAGE_SET_RHYTHM_ORDER),
)
LEGACY_BEAT_TRANSITION_MODES = (
    "cut",
    "fade",
    "linear",
    "ease_in",
    "ease_out",
    "ease_in_out",
    "wipe_horizontal",
    "wipe_vertical",
)
AUDIO_LOOPBACK_KEYWORDS = (
    "loopback",
    "stereo mix",
    "what u hear",
    "wave out",
    "monitor",
    "blackhole",
    "vb-audio",
    "virtual cable",
    "cable output",
)
AUDIO_SOURCE_BACKEND_QT = "qt"
AUDIO_SOURCE_BACKEND_SOUNDCARD = "soundcard"
SOUNDCARD_SAMPLE_RATE = 48000
SOUNDCARD_BLOCKSIZE = 1024


def log_startup_event(message: str):
    text = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    try:
        with STARTUP_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(text + "\n")
    except Exception:
        pass
    try:
        print(text, file=sys.stderr, flush=True)
    except Exception:
        pass


def _startup_excepthook(exc_type, exc_value, exc_traceback):
    details = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    log_startup_event("UNCAUGHT EXCEPTION\n" + details.rstrip())
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


sys.excepthook = _startup_excepthook


def clean_beat_transition_effect(value):
    effect = str(value).strip().lower()
    if effect == "immediate":
        effect = "cut"
    return effect if effect in BEAT_TRANSITION_EFFECTS else "cut"


def clean_beat_transition_easing(value):
    easing = str(value).strip().lower()
    return easing if easing in BEAT_TRANSITION_EASINGS else "linear"


def transition_effect_uses_easing(effect: str):
    return clean_beat_transition_effect(effect) != "cut"


def default_transition_duration_scale(effect: str = "cut"):
    effect = clean_beat_transition_effect(effect)
    if effect == "cut":
        return 0.0
    return DEFAULT_BEAT_TRANSITION_DURATION_SCALE


def clean_change_visibility_mode(value):
    _ = value
    return "visible"


def clean_image_set_timing_mode(value):
    mode = str(value).strip().lower()
    return mode if mode in IMAGE_SET_TIMING_MODE_VALUES else "manual"


def list_image_set_files(folder_path: str):
    folder = Path(str(folder_path or "").strip())
    if not folder.is_dir():
        return []
    files = [path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SET_FILE_SUFFIXES]
    return sorted(files, key=lambda path: path.name.lower())


def choose_image_set_core_path(paths):
    if not paths:
        return None
    lowered = [(path, path.stem.strip().lower()) for path in paths]
    for prefix in IMAGE_SET_CORE_PREFIXES:
        for path, stem in lowered:
            if stem.startswith(prefix):
                return path
    return paths[0]


def default_stage_labels_from_paths(paths):
    return [path.stem for path in list(paths)]


def default_loop_slot_count():
    return 4


def default_loop_stage_map(count: int = None):
    try:
        slot_count = default_loop_slot_count() if count is None else max(1, int(count))
    except Exception:
        slot_count = default_loop_slot_count()
    return [0 for _ in range(slot_count)]


def default_sequential_stage_map(stage_count: int, slot_count: int = None):
    try:
        clean_stage_count = max(0, int(stage_count))
    except Exception:
        clean_stage_count = 0
    if clean_stage_count <= 0:
        return default_loop_stage_map(slot_count)

    try:
        normalized_slot_count = default_loop_slot_count() if slot_count is None else max(1, int(slot_count))
    except Exception:
        normalized_slot_count = default_loop_slot_count()

    return [((slot_index % clean_stage_count) + 1) for slot_index in range(normalized_slot_count)]


def default_image_set_beat_map(stage_labels, slot_count: int = None):
    try:
        normalized_slot_count = default_loop_slot_count() if slot_count is None else max(1, int(slot_count))
    except Exception:
        normalized_slot_count = default_loop_slot_count()

    clean_labels = [str(label).strip().lower() for label in list(stage_labels)]
    if not clean_labels:
        return default_loop_stage_map(normalized_slot_count)

    stage_lookup = {label: index + 1 for index, label in enumerate(clean_labels)}
    pattern = []
    if "dnf" in stage_lookup and "dwf" in stage_lookup and "hwf" in stage_lookup:
        pattern = [
            stage_lookup["dnf"],
            stage_lookup["dwf"],
            stage_lookup["hwf"],
            stage_lookup["dwf"],
        ]
    else:
        pattern = [index + 1 for index in range(len(clean_labels))]

    if not pattern:
        return default_loop_stage_map(normalized_slot_count)

    return [int(pattern[slot_index % len(pattern)]) for slot_index in range(normalized_slot_count)]


def default_image_set_switch_time():
    return 0.22


def default_image_set_timing_mode():
    return "manual"


def default_image_set_timing_translation():
    return 1.0


def default_image_set_timing_pause():
    return 0.0


def parse_image_set_stage_axes(label: str):
    letters = "".join(ch for ch in str(label or "").strip().lower() if ch.isalpha())
    if len(letters) < 3:
        return None
    texture = letters[0]
    atmosphere = letters[1]
    rhythm = letters[2]
    if texture not in IMAGE_SET_TEXTURE_ORDER:
        return None
    if atmosphere not in IMAGE_SET_ATMOSPHERE_ORDER:
        return None
    if rhythm not in IMAGE_SET_RHYTHM_ORDER:
        return None
    return {
        "texture": texture,
        "atmosphere": atmosphere,
        "rhythm": rhythm,
    }


def audio_filter_alpha(cutoff_hz: float, sample_rate: int):
    cutoff_hz = max(1.0, float(cutoff_hz))
    sample_rate = max(1, int(sample_rate))
    dt = 1.0 / float(sample_rate)
    rc = 1.0 / (math.tau * cutoff_hz)
    return max(0.0, min(1.0, dt / (rc + dt)))


def audio_device_key(device) -> str:
    if device is None:
        return ""
    try:
        raw = bytes(device.id())
        if raw:
            return raw.hex()
    except Exception:
        pass
    try:
        return str(device.description()).strip().lower()
    except Exception:
        return ""


def looks_like_loopback_input(description: str) -> bool:
    text = str(description).strip().lower()
    if not text:
        return False
    return any(keyword in text for keyword in AUDIO_LOOPBACK_KEYWORDS)


def audio_format_is_reasonable(fmt: QAudioFormat) -> bool:
    if fmt is None:
        return False
    try:
        sample_rate = int(fmt.sampleRate())
        channels = int(fmt.channelCount())
        sample_format = fmt.sampleFormat()
    except Exception:
        return False
    if sample_rate < 8000 or sample_rate > 192000:
        return False
    if channels < 1 or channels > 8:
        return False
    if sample_format == QAudioFormat.Unknown:
        return False
    return True


def _unique_preserve_order(values):
    result = []
    seen = set()
    for value in values:
        key = value
        try:
            if key in seen:
                continue
            seen.add(key)
        except TypeError:
            key = repr(value)
            if key in seen:
                continue
            seen.add(key)
        result.append(value)
    return result


def make_audio_format(sample_rate: int, channel_count: int, sample_format):
    fmt = QAudioFormat()
    fmt.setSampleRate(int(sample_rate))
    fmt.setChannelCount(int(channel_count))
    fmt.setSampleFormat(sample_format)
    return fmt


def resolve_supported_qt_audio_format(device, preferred: QAudioFormat | None = None):
    fmt = QAudioFormat()
    if device is None or device.isNull():
        return fmt

    base_candidates = []
    if audio_format_is_reasonable(preferred):
        base_candidates.append(QAudioFormat(preferred))

    try:
        device_preferred = device.preferredFormat()
    except Exception:
        device_preferred = QAudioFormat()
    if audio_format_is_reasonable(device_preferred):
        base_candidates.append(QAudioFormat(device_preferred))

    for candidate in base_candidates:
        try:
            if device.isFormatSupported(candidate):
                return candidate
        except Exception:
            pass

    try:
        minimum_rate = int(device.minimumSampleRate())
    except Exception:
        minimum_rate = 0
    try:
        maximum_rate = int(device.maximumSampleRate())
    except Exception:
        maximum_rate = 0
    try:
        minimum_channels = int(device.minimumChannelCount())
    except Exception:
        minimum_channels = 0
    try:
        maximum_channels = int(device.maximumChannelCount())
    except Exception:
        maximum_channels = 0
    try:
        supported_formats = list(device.supportedSampleFormats())
    except Exception:
        supported_formats = []

    rates = []
    channels = []
    formats = []

    for candidate in base_candidates:
        rates.append(int(candidate.sampleRate()))
        channels.append(int(candidate.channelCount()))
        formats.append(candidate.sampleFormat())

    rates.extend([48000, 44100, 32000, 24000, 22050, 16000, 11025, 8000])
    channels.extend([1, 2, minimum_channels, maximum_channels])
    formats.extend(supported_formats)
    formats.extend([QAudioFormat.Int16, QAudioFormat.Float, QAudioFormat.Int32, QAudioFormat.UInt8])

    rates = _unique_preserve_order(
        rate
        for rate in rates
        if int(rate) > 0 and (minimum_rate <= 0 or rate >= minimum_rate) and (maximum_rate <= 0 or rate <= maximum_rate)
    )
    channels = _unique_preserve_order(
        channel
        for channel in channels
        if int(channel) > 0
        and int(channel) <= 8
        and (minimum_channels <= 0 or channel >= minimum_channels)
        and (maximum_channels <= 0 or channel <= maximum_channels)
    )
    formats = _unique_preserve_order(
        sample_format for sample_format in formats if sample_format != QAudioFormat.Unknown
    )

    for rate in rates:
        for channel_count in channels:
            for sample_format in formats:
                candidate = make_audio_format(rate, channel_count, sample_format)
                if not audio_format_is_reasonable(candidate):
                    continue
                try:
                    if device.isFormatSupported(candidate):
                        return candidate
                except Exception:
                    continue
    return QAudioFormat()


def qt_audio_device_supports_capture(device, preferred: QAudioFormat | None = None) -> bool:
    return audio_format_is_reasonable(resolve_supported_qt_audio_format(device, preferred))


def soundcard_available() -> bool:
    return importlib.util.find_spec("soundcard") is not None


def apply_soundcard_numpy_compatibility_patch():
    if getattr(apply_soundcard_numpy_compatibility_patch, "_done", False):
        return
    apply_soundcard_numpy_compatibility_patch._done = True

    try:
        import numpy as _np
    except Exception:
        return

    original_fromstring = getattr(_np, "fromstring", None)
    if original_fromstring is None or getattr(original_fromstring, "_rai_binary_patch", False):
        return

    def _compat_fromstring(obj, dtype=float, count=-1, sep="", like=None):
        if sep == "" and not isinstance(obj, str):
            try:
                buffer_obj = obj if isinstance(obj, (bytes, bytearray, memoryview)) else memoryview(obj)
            except TypeError:
                buffer_obj = None
            if buffer_obj is not None:
                if like is not None:
                    return _np.frombuffer(buffer_obj, dtype=dtype, count=count, like=like)
                return _np.frombuffer(buffer_obj, dtype=dtype, count=count)

        if like is not None:
            return original_fromstring(obj, dtype=dtype, count=count, sep=sep, like=like)
        return original_fromstring(obj, dtype=dtype, count=count, sep=sep)

    _compat_fromstring._rai_binary_patch = True
    _np.fromstring = _compat_fromstring


def soundcard_microphone_key(microphone) -> str:
    if microphone is None:
        return ""
    try:
        value = str(microphone.id).strip()
        if value:
            return value.lower()
    except Exception:
        pass
    try:
        return str(microphone.name).strip().lower()
    except Exception:
        return ""


def safe_soundcard_microphone_name(microphone) -> str:
    try:
        name = str(microphone.name).strip()
        if name:
            return name
    except Exception:
        pass
    return "Unnamed sound card source"


def _run_soundcard_call(callable_obj, timeout: float = 3.0):
    if not soundcard_available():
        return None

    holder = {"value": None}

    def runner():
        try:
            holder["value"] = callable_obj()
        except Exception:
            holder["value"] = None

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        return None
    return holder.get("value")


def _enumerate_soundcard_sources_impl():
    sc = importlib.import_module("soundcard")
    default_key = ""
    try:
        speaker = sc.default_speaker()
        if speaker is not None:
            default_key = str(speaker.id).strip().lower()
    except Exception:
        default_key = ""

    entries = []
    seen = set()
    for microphone in sc.all_microphones(include_loopback=True):
        try:
            is_loopback = bool(getattr(microphone, "isloopback", False))
        except Exception:
            is_loopback = False
        if not is_loopback:
            continue
        try:
            _ = microphone.channels
        except Exception:
            continue
        native_id = soundcard_microphone_key(microphone)
        if not native_id or native_id in seen:
            continue
        seen.add(native_id)
        description = safe_soundcard_microphone_name(microphone)
        is_default = bool(default_key and native_id == default_key)
        label = f"System / Sound Card: {description}"
        if is_default:
            label = f"{label} [Default]"
        entries.append(
            {
                "id": f"{AUDIO_SOURCE_BACKEND_SOUNDCARD}:{native_id}",
                "backend": AUDIO_SOURCE_BACKEND_SOUNDCARD,
                "native_id": native_id,
                "label": label,
                "description": description,
                "role": "system",
                "is_default": is_default,
            }
        )
    return entries


def available_soundcard_sources():
    result = _run_soundcard_call(_enumerate_soundcard_sources_impl)
    return list(result) if isinstance(result, list) else []


def available_audio_sources():
    entries = []
    for device in QMediaDevices.audioInputs():
        description = str(device.description()).strip() or "Unnamed input"
        role = "system" if looks_like_loopback_input(description) else "microphone"
        prefix = "System / Loopback" if role == "system" else "Microphone / Input"
        label = f"{prefix}: {description}"
        supported = qt_audio_device_supports_capture(device)
        if device.isDefault():
            label = f"{label} [Default]"
        if not supported:
            label = f"{label} [Unsupported]"
        entries.append(
            {
                "id": f"{AUDIO_SOURCE_BACKEND_QT}:{audio_device_key(device)}",
                "backend": AUDIO_SOURCE_BACKEND_QT,
                "native_id": audio_device_key(device),
                "label": label,
                "description": description,
                "role": role,
                "is_default": bool(device.isDefault()),
                "supported": supported,
            }
        )

    entries.extend(available_soundcard_sources())
    entries.sort(
        key=lambda item: (
            0 if item.get("supported", True) else 1,
            0 if item["is_default"] else 1,
            item["label"].lower(),
        )
    )
    return entries


def preferred_audio_source_id(sources, current_id: str = ""):
    current_id = str(current_id or "").strip()
    if current_id and any(str(source.get("id", "")) == current_id for source in sources):
        return current_id

    if not sources:
        return ""

    ranked_sources = sorted(
        list(sources),
        key=lambda source: (
            0 if str(source.get("backend", "")) == AUDIO_SOURCE_BACKEND_SOUNDCARD else 1,
            0 if bool(source.get("supported", True)) else 1,
            0 if bool(source.get("is_default")) else 1,
            str(source.get("label", "")).lower(),
        ),
    )
    return str(ranked_sources[0].get("id", "")) if ranked_sources else ""


def compute_audio_band_metrics(samples, sample_rate: int, low_state: float = 0.0, mid_state: float = 0.0):
    sample_count = len(samples)
    if sample_count <= 0:
        return None

    sum_sq = 0.0
    sum_low = 0.0
    sum_mid = 0.0
    sum_high = 0.0
    sample_rate = max(1, int(sample_rate))
    low_alpha = audio_filter_alpha(180.0, sample_rate)
    mid_alpha = audio_filter_alpha(2200.0, sample_rate)
    current_low_state = float(low_state)
    current_mid_state = float(mid_state)

    for sample in samples:
        x = max(-1.0, min(1.0, float(sample)))
        current_low_state += low_alpha * (x - current_low_state)
        current_mid_state += mid_alpha * (x - current_mid_state)
        low = current_low_state
        mid = current_mid_state - current_low_state
        high = x - current_mid_state
        sum_sq += x * x
        sum_low += low * low
        sum_mid += mid * mid
        sum_high += high * high

    return {
        "rms": max(0.0, min(1.0, math.sqrt(sum_sq / sample_count))),
        "low": max(0.0, min(1.0, math.sqrt(sum_low / sample_count) * 1.85)),
        "mid": max(0.0, min(1.0, math.sqrt(sum_mid / sample_count) * 2.35)),
        "high": max(0.0, min(1.0, math.sqrt(sum_high / sample_count) * 3.10)),
        "low_state": current_low_state,
        "mid_state": current_mid_state,
    }


def emit_soundcard_worker_message(payload) -> bool:
    try:
        sys.stdout.write(json.dumps(payload) + "\n")
        sys.stdout.flush()
        return True
    except OSError:
        return False


def run_soundcard_worker(source_native_id: str) -> int:
    warnings.filterwarnings("ignore", message=".*data discontinuity.*")
    apply_soundcard_numpy_compatibility_patch()
    try:
        sc = importlib.import_module("soundcard")
        warnings.filterwarnings("ignore", category=getattr(sc, "SoundcardRuntimeWarning", Warning))
    except Exception:
        emit_soundcard_worker_message({"type": "error", "message": "Sound card loopback backend is not installed"})
        return 1

    source_native_id = str(source_native_id or "").strip().lower()
    target = None
    try:
        microphones = sc.all_microphones(include_loopback=True)
    except Exception:
        microphones = []

    for microphone in microphones:
        try:
            is_loopback = bool(getattr(microphone, "isloopback", False))
        except Exception:
            is_loopback = False
        if not is_loopback:
            continue
        try:
            _ = microphone.channels
        except Exception:
            continue
        if soundcard_microphone_key(microphone) == source_native_id:
            target = microphone
            break

    if target is None:
        emit_soundcard_worker_message({"type": "error", "message": "Selected sound card source is unavailable"})
        return 1

    low_state = 0.0
    mid_state = 0.0
    try:
        with target.recorder(
            samplerate=SOUNDCARD_SAMPLE_RATE,
            channels=None,
            blocksize=SOUNDCARD_BLOCKSIZE,
        ) as recorder:
            if not emit_soundcard_worker_message(
                {
                    "type": "opened",
                    "message": f"Listening to sound card output: {safe_soundcard_microphone_name(target)}...",
                }
            ):
                return 0
            while True:
                data = recorder.record(numframes=SOUNDCARD_BLOCKSIZE)
                if data is None:
                    continue
                try:
                    if len(getattr(data, "shape", ())) == 1:
                        samples = [max(-1.0, min(1.0, float(value))) for value in data.tolist()]
                    else:
                        samples = [max(-1.0, min(1.0, float(value))) for value in data.mean(axis=1).tolist()]
                except Exception:
                    samples = []
                metrics = compute_audio_band_metrics(samples, SOUNDCARD_SAMPLE_RATE, low_state, mid_state)
                if not metrics:
                    continue
                low_state = metrics["low_state"]
                mid_state = metrics["mid_state"]
                if not emit_soundcard_worker_message(
                    {
                        "type": "metrics",
                        "rms": metrics["rms"],
                        "low": metrics["low"],
                        "mid": metrics["mid"],
                        "high": metrics["high"],
                    }
                ):
                    return 0
    except KeyboardInterrupt:
        return 0
    except BrokenPipeError:
        return 0
    except Exception as exc:
        emit_soundcard_worker_message({"type": "error", "message": f"Sound card loopback capture failed: {exc}"})
        return 1


class SoundcardLoopbackThread(QThread):
    samplesReady = Signal(object, int)
    sourceOpened = Signal(str)
    errorRaised = Signal(str)

    def __init__(self, source_native_id: str, parent=None):
        super().__init__(parent)
        self._source_native_id = str(source_native_id or "").strip().lower()
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        try:
            apply_soundcard_numpy_compatibility_patch()
            sc = importlib.import_module("soundcard")
            warnings.filterwarnings("ignore", category=getattr(sc, "SoundcardRuntimeWarning", Warning))
            target = None
            microphones = sc.all_microphones(include_loopback=True)
            for microphone in microphones:
                try:
                    is_loopback = bool(getattr(microphone, "isloopback", False))
                except Exception:
                    is_loopback = False
                if not is_loopback:
                    continue
                try:
                    _ = microphone.channels
                except Exception:
                    continue
                if soundcard_microphone_key(microphone) == self._source_native_id:
                    target = microphone
                    break

            if target is None:
                self.errorRaised.emit("Selected sound card source is unavailable")
                return

            with target.recorder(
                samplerate=SOUNDCARD_SAMPLE_RATE,
                channels=None,
                blocksize=SOUNDCARD_BLOCKSIZE,
            ) as recorder:
                self.sourceOpened.emit(f"Listening to sound card output: {safe_soundcard_microphone_name(target)}...")
                while self._running:
                    data = recorder.record(numframes=SOUNDCARD_BLOCKSIZE)
                    if data is None:
                        continue
                    try:
                        if len(getattr(data, "shape", ())) == 1:
                            samples = [max(-1.0, min(1.0, float(value))) for value in data.tolist()]
                        else:
                            samples = [max(-1.0, min(1.0, float(value))) for value in data.mean(axis=1).tolist()]
                    except Exception:
                        samples = []
                    if samples:
                        self.samplesReady.emit(samples, SOUNDCARD_SAMPLE_RATE)
        except Exception as exc:
            self.errorRaised.emit(f"Sound card loopback capture failed: {exc}")


def _clean_scanline_params(params):
    if not isinstance(params, dict):
        params = {}

    direction = str(params.get("direction", "horizontal")).strip().lower()
    if direction not in ("horizontal", "vertical"):
        direction = "horizontal"

    try:
        band_px = max(4, int(round(float(params.get("band_px", 24)))))
    except Exception:
        band_px = 24

    try:
        glow = max(0.0, min(1.0, float(params.get("glow", 0.25))))
    except Exception:
        glow = 0.25

    return {
        "direction": direction,
        "band_px": band_px,
        "glow": glow,
    }


def default_transition_spec(effect: str = "cut", easing: str = "linear", duration_scale=None, params=None):
    effect = clean_beat_transition_effect(effect)
    easing = clean_beat_transition_easing(easing)

    if duration_scale is None:
        scale = default_transition_duration_scale(effect)
    else:
        try:
            scale = max(0.0, float(duration_scale))
        except Exception:
            scale = default_transition_duration_scale(effect)
    if effect == "cut":
        scale = 0.0

    if effect == "scanline_reconstruct":
        clean_params = _clean_scanline_params(params)
    else:
        clean_params = dict(params) if isinstance(params, dict) else {}

    return {
        "effect": effect,
        "easing": easing,
        "duration_scale": scale,
        "params": clean_params,
    }


def default_transition_specs(count: int = None):
    try:
        normalized_count = default_loop_slot_count() if count is None else max(0, int(count))
    except Exception:
        normalized_count = default_loop_slot_count()
    return [default_transition_spec() for _ in range(normalized_count)]


def normalize_transition_spec(value):
    if isinstance(value, dict):
        return default_transition_spec(
            value.get("effect", "cut"),
            value.get("easing", "linear"),
            value.get("duration_scale"),
            value.get("params"),
        )

    mode = str(value).strip().lower()
    if mode == "immediate":
        mode = "cut"

    if mode in BEAT_TRANSITION_EFFECTS:
        return default_transition_spec(effect=mode, easing="linear")
    if mode in BEAT_TRANSITION_EASINGS:
        return default_transition_spec(effect="interpolate", easing=mode)
    if mode in LEGACY_BEAT_TRANSITION_MODES:
        return default_transition_spec(effect=mode, easing="linear")
    return default_transition_spec()


TIMELINE_POSITION_EPSILON = 1e-3


def default_timeline_transition_spec():
    return default_transition_spec(effect="cut", easing="linear")


def normalize_loop_timeline_points(points, slot_count: int, stage_count: int, beat_map=None, beat_transitions=None):
    try:
        clean_slot_count = max(1, int(slot_count))
    except Exception:
        clean_slot_count = default_loop_slot_count()

    try:
        clean_stage_count = max(0, int(stage_count))
    except Exception:
        clean_stage_count = 0

    normalized = []
    if isinstance(points, (list, tuple)):
        for entry in points:
            if not isinstance(entry, dict):
                continue
            try:
                position = float(entry.get("position", entry.get("beat", entry.get("slot", 0.0))))
            except Exception:
                position = 0.0
            position = position % float(clean_slot_count)

            try:
                state = max(0, int(entry.get("state", entry.get("stage", 0))))
            except Exception:
                state = 0
            if clean_stage_count > 0:
                state = min(state, clean_stage_count)
            else:
                state = 0
            if state <= 0:
                continue

            transition = normalize_transition_spec(entry.get("transition", default_timeline_transition_spec()))
            if transition["effect"] == "cut":
                transition = default_transition_spec(effect="cut", easing="linear")

            normalized.append(
                {
                    "position": position,
                    "state": state,
                    "transition": transition,
                }
            )

    if not normalized:
        beat_map_values = list(beat_map) if isinstance(beat_map, (list, tuple)) else []
        beat_transition_values = list(beat_transitions) if isinstance(beat_transitions, (list, tuple)) else []
        previous_state = None
        for slot_index, value in enumerate(beat_map_values[:clean_slot_count]):
            try:
                state = max(0, int(value))
            except Exception:
                state = 0
            if clean_stage_count > 0:
                state = min(state, clean_stage_count)
            else:
                state = 0
            if state <= 0:
                previous_state = 0
                continue
            if previous_state == state:
                previous_state = state
                continue
            transition = (
                normalize_transition_spec(beat_transition_values[slot_index])
                if 0 <= slot_index < len(beat_transition_values)
                else default_timeline_transition_spec()
            )
            if transition["effect"] == "cut":
                transition = default_transition_spec(effect="cut", easing="linear")
            normalized.append(
                {
                    "position": float(slot_index),
                    "state": state,
                    "transition": transition,
                }
            )
            previous_state = state

    normalized.sort(key=lambda item: float(item["position"]))
    deduped = []
    for item in normalized:
        if deduped and abs(float(item["position"]) - float(deduped[-1]["position"])) < TIMELINE_POSITION_EPSILON:
            deduped[-1] = item
        else:
            deduped.append(item)
    return deduped


def app_data_dir() -> Path:
    root = os.getenv("APPDATA")
    base = Path(root) if root else (Path.home() / "AppData" / "Roaming")
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def app_asset_path(name: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    else:
        base = Path(__file__).resolve().parent
    return base / name


def load_app_icon() -> QIcon:
    for name in ("logo.png", "logo.ico"):
        path = app_asset_path(name)
        if not path.exists():
            continue
        icon = QIcon(str(path))
        if not icon.isNull():
            return icon
    return QIcon()

class ColorWheelWidget(QWidget):
    colorChanged = Signal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hue = 0.0
        self._sat = 0.0
        self._value = 255
        self._wheel_img = QImage()
        self._wheel_size = 0
        self.setMinimumSize(240, 240)

    def sizeHint(self):
        return QSize(320, 320)

    def color(self):
        return QColor.fromHsv(int(self._hue) % 360, int(round(self._sat * 255.0)), self._value)

    def set_color(self, color: QColor):
        if not color.isValid():
            return
        h, s, v, _ = color.getHsv()
        self._hue = float(0 if h < 0 else h)
        self._sat = s / 255.0
        self._value = int(v)
        self._rebuild_wheel(force=True)
        self.update()

    def set_value(self, v: int):
        v = max(0, min(255, int(v)))
        if v == self._value:
            return
        self._value = v
        self._rebuild_wheel(force=True)
        self.update()
        self.colorChanged.emit(self.color())

    def _wheel_rect(self):
        margin = 6
        side = max(1, min(self.width(), self.height()) - (margin * 2))
        x = (self.width() - side) // 2
        y = (self.height() - side) // 2
        return QRectF(x, y, side, side)

    def _rebuild_wheel(self, force: bool = False):
        rect = self._wheel_rect()
        side = max(1, int(round(rect.width())))
        if not force and side == self._wheel_size and not self._wheel_img.isNull():
            return

        self._wheel_size = side
        img = QImage(side, side, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)

        cx = (side - 1) / 2.0
        cy = (side - 1) / 2.0
        radius = (side / 2.0) - 1.0
        if radius <= 0:
            self._wheel_img = img
            return

        for y in range(side):
            dy = y - cy
            for x in range(side):
                dx = x - cx
                dist = math.hypot(dx, dy)
                if dist <= radius:
                    sat = dist / radius
                    hue = (math.degrees(math.atan2(-dy, dx)) + 360.0) % 360.0
                    c = QColor.fromHsv(int(hue), int(round(sat * 255.0)), self._value)
                    img.setPixelColor(x, y, c)

        self._wheel_img = img

    def _pick_from_pos(self, pos: QPointF):
        rect = self._wheel_rect()
        cx = rect.center().x()
        cy = rect.center().y()
        radius = (rect.width() / 2.0) - 1.0
        if radius <= 0:
            return

        dx = pos.x() - cx
        dy = pos.y() - cy
        dist = math.hypot(dx, dy)
        if dist > radius and dist > 1e-6:
            s = radius / dist
            dx *= s
            dy *= s
            dist = radius

        self._sat = max(0.0, min(1.0, dist / radius))
        self._hue = (math.degrees(math.atan2(-dy, dx)) + 360.0) % 360.0
        self.update()
        self.colorChanged.emit(self.color())

    def resizeEvent(self, e):
        self._rebuild_wheel(force=True)
        super().resizeEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._pick_from_pos(e.position())
            e.accept()
            return
        e.ignore()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self._pick_from_pos(e.position())
            e.accept()
            return
        e.ignore()

    def paintEvent(self, _):
        self._rebuild_wheel()
        rect = self._wheel_rect()

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.drawImage(rect, self._wheel_img)

        p.setPen(QPen(QColor(20, 20, 20), 1))
        p.drawEllipse(rect)

        cx = rect.center().x()
        cy = rect.center().y()
        radius = (rect.width() / 2.0) - 1.0
        r = self._sat * radius
        a = math.radians(self._hue)
        x = cx + (math.cos(a) * r)
        y = cy - (math.sin(a) * r)

        p.setPen(QPen(Qt.black, 2))
        p.drawLine(QPointF(x - 8, y), QPointF(x + 8, y))
        p.drawLine(QPointF(x, y - 8), QPointF(x, y + 8))
        p.setPen(QPen(Qt.white, 1))
        p.drawEllipse(QPointF(x, y), 4, 4)

class ColorWheelDialog(QDialog):
    def __init__(self, initial_color: QColor, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Colors")
        self.setModal(True)

        layout = QVBoxLayout(self)

        self.wheel = ColorWheelWidget(self)
        layout.addWidget(self.wheel)

        self.value_slider = QSlider(Qt.Horizontal, self)
        self.value_slider.setRange(0, 255)
        layout.addWidget(self.value_slider)

        self.preview = QLabel(self)
        self.preview.setFixedHeight(26)
        layout.addWidget(self.preview)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.wheel.colorChanged.connect(self._on_wheel_color_changed)
        self.value_slider.valueChanged.connect(self.wheel.set_value)

        self._selected = QColor(initial_color) if initial_color.isValid() else QColor(255, 255, 255)
        self.wheel.set_color(self._selected)
        self.value_slider.setValue(self._selected.value())
        self._on_wheel_color_changed(self._selected)

    def _on_wheel_color_changed(self, color: QColor):
        self._selected = QColor(color)
        fg = "#000000" if self._selected.lightness() > 140 else "#FFFFFF"
        self.preview.setText(f"  {self._selected.name(QColor.HexRgb).upper()}")
        self.preview.setStyleSheet(
            f"background-color: {self._selected.name()}; color: {fg}; border: 1px solid #222;"
        )

    def selected_color(self):
        return QColor(self._selected)

class PresetPickerDialog(QDialog):
    def __init__(self, main_presets, saved_presets, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Load Preset")
        self.setModal(True)
        self._selected = QColor()

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Main Presets"))
        layout.addLayout(self._make_preset_grid(main_presets))

        layout.addWidget(QLabel("Saved Presets"))
        if saved_presets:
            layout.addLayout(self._make_preset_grid(saved_presets))
        else:
            empty = QLabel("No saved presets yet.")
            empty.setStyleSheet("color: #666;")
            layout.addWidget(empty)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel, parent=self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _make_preset_grid(self, colors):
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        columns = 8
        for i, color in enumerate(colors):
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setToolTip(color.name(QColor.HexRgb).upper())
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {color.name()}; border: 1px solid #444; border-radius: 12px; }}"
            )
            btn.clicked.connect(lambda _=False, c=QColor(color): self._pick(c))
            grid.addWidget(btn, i // columns, i % columns)
        return grid

    def _pick(self, color: QColor):
        self._selected = QColor(color)
        self.accept()

    def selected_color(self):
        return QColor(self._selected)


class BeatDetector(QObject):
    beatDetected = Signal(float)
    levelChanged = Signal(float)
    bandLevelsChanged = Signal(float, float, float)
    stateChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = False
        self.sensitivity = 60
        self._selected_audio_source_id = ""
        self._audio_backend = AUDIO_SOURCE_BACKEND_QT

        self._audio_source = None
        self._audio_device = None
        self._active_format = QAudioFormat()
        self._soundcard_process = None
        self._soundcard_stdout_buffer = ""
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(20)
        self._poll_timer.timeout.connect(self._poll_audio)

        self._short_env = 0.0
        self._long_env = 0.0
        self._last_beat_ms = 0.0
        self._cooldown_ms = 180.0
        self._low_state = 0.0
        self._mid_state = 0.0

        self._format = QAudioFormat()
        self._format.setSampleRate(44100)
        self._format.setChannelCount(1)
        self._format.setSampleFormat(QAudioFormat.Int16)

    def set_enabled(self, enabled: bool):
        enabled = bool(enabled)
        if enabled == self.enabled:
            return
        self.enabled = enabled
        if self.enabled:
            self._start()
        else:
            self._stop()
            self.stateChanged.emit("Audio reactivity off")

    def set_sensitivity(self, value: int):
        self.sensitivity = max(1, min(100, int(value)))

    def set_audio_source(self, device_id: str):
        device_id = str(device_id or "").strip().lower()
        if device_id == self._selected_audio_source_id:
            return
        self._selected_audio_source_id = device_id
        if self.enabled:
            self._start()

    def audio_source_id(self) -> str:
        return self._selected_audio_source_id

    def stop(self):
        self.enabled = False
        self._stop()

    def _reset_analysis_state(self):
        self._short_env = 0.0
        self._long_env = 0.0
        self._last_beat_ms = 0.0
        self._low_state = 0.0
        self._mid_state = 0.0

    def _emit_silence(self):
        self.levelChanged.emit(0.0)
        self.bandLevelsChanged.emit(0.0, 0.0, 0.0)

    def _resolve_audio_source_entry(self):
        sources = available_audio_sources()
        if not sources:
            return None

        if self._selected_audio_source_id:
            for source in sources:
                if str(source.get("id", "")).strip().lower() == self._selected_audio_source_id:
                    return source
        return sources[0]

    def _resolve_qt_audio_device(self, native_id: str):
        native_id = str(native_id or "").strip().lower()
        devices = list(QMediaDevices.audioInputs())
        if not devices:
            return None

        if native_id:
            for device in devices:
                if audio_device_key(device) == native_id:
                    return device

        for device in devices:
            if device.isDefault() and qt_audio_device_supports_capture(device, self._format):
                return device
        for device in devices:
            if qt_audio_device_supports_capture(device, self._format):
                return device
        for device in devices:
            if device.isDefault():
                return device
        return devices[0]

    def _resolved_format_for_device(self, device):
        return resolve_supported_qt_audio_format(device, self._format)

    def _start(self):
        self._stop()
        source = self._resolve_audio_source_entry()
        if source is None:
            self.stateChanged.emit("No audio capture source found")
            self.enabled = False
            return

        backend = str(source.get("backend", AUDIO_SOURCE_BACKEND_QT))
        self._audio_backend = backend
        if backend == AUDIO_SOURCE_BACKEND_SOUNDCARD:
            self._start_soundcard_source(source)
            return
        self._start_qt_source(source)

    def _start_qt_source(self, source):
        device = self._resolve_qt_audio_device(source.get("native_id", ""))
        if device is None or device.isNull():
            self.stateChanged.emit("Selected audio input is unavailable")
            self.enabled = False
            return

        try:
            self._active_format = self._resolved_format_for_device(device)
            if not audio_format_is_reasonable(self._active_format):
                raise ValueError("unsupported format")
            self._audio_source = QAudioSource(device, self._active_format, self)
            self._audio_source.setBufferSize(4096)
            self._audio_device = self._audio_source.start()
        except Exception:
            self._audio_source = None
            self._audio_device = None
            self._active_format = QAudioFormat()
            self.stateChanged.emit("Selected audio input does not expose a supported capture format")
            self.enabled = False
            self._emit_silence()
            return

        if self._audio_device is None:
            self.stateChanged.emit("Audio source unavailable")
            self.enabled = False
            self._stop()
            return

        self._reset_analysis_state()
        self._poll_timer.start()
        self.stateChanged.emit(f"Listening to {device.description()}...")

    def _start_soundcard_source(self, source):
        if not soundcard_available():
            self.stateChanged.emit("Sound card loopback backend is not installed")
            self.enabled = False
            self._emit_silence()
            return

        self._reset_analysis_state()
        process = QProcess(self)
        process.readyReadStandardOutput.connect(self._on_soundcard_process_stdout)
        process.readyReadStandardError.connect(self._on_soundcard_process_stderr)
        process.finished.connect(self._on_soundcard_process_finished)
        process.errorOccurred.connect(self._on_soundcard_process_error)

        if getattr(sys, "frozen", False):
            program = sys.executable
            arguments = ["--soundcard-worker", str(source.get("native_id", ""))]
        else:
            program = sys.executable
            arguments = [str(Path(__file__).resolve()), "--soundcard-worker", str(source.get("native_id", ""))]

        process.setProgram(program)
        process.setArguments(arguments)
        self._soundcard_stdout_buffer = ""
        process.start()
        if not process.waitForStarted(3000):
            self.stateChanged.emit("Sound card loopback start failed")
            self.enabled = False
            process.deleteLater()
            self._emit_silence()
            return
        self._soundcard_process = process

    def _stop(self):
        self._poll_timer.stop()
        if self._audio_source is not None:
            self._audio_source.stop()
            self._audio_source.deleteLater()
        if self._soundcard_process is not None:
            try:
                self._soundcard_process.blockSignals(True)
                self._soundcard_process.terminate()
                if not self._soundcard_process.waitForFinished(1000):
                    self._soundcard_process.kill()
                    self._soundcard_process.waitForFinished(1000)
            except Exception:
                pass
            self._soundcard_process.deleteLater()
        self._audio_source = None
        self._audio_device = None
        self._active_format = QAudioFormat()
        self._soundcard_process = None
        self._soundcard_stdout_buffer = ""
        self._reset_analysis_state()
        self._emit_silence()

    def _decode_samples(self, chunk):
        raw = bytes(chunk)
        if not raw:
            return []

        channels = max(1, int(self._active_format.channelCount() or 1))
        sample_format = self._active_format.sampleFormat()

        if sample_format == QAudioFormat.UInt8:
            values = raw
            frame_count = len(values) // channels
            samples = []
            index = 0
            for _ in range(frame_count):
                total = 0.0
                for _ in range(channels):
                    total += (float(values[index]) - 128.0) / 128.0
                    index += 1
                samples.append(total / channels)
            return samples

        item_size = 0
        values = None
        scale = 1.0
        if sample_format == QAudioFormat.Int16:
            item_size = 2
            values = array("h")
            scale = 32768.0
        elif sample_format == QAudioFormat.Int32:
            item_size = 4
            values = array("i")
            scale = 2147483648.0
        elif sample_format == QAudioFormat.Float:
            item_size = 4
            values = array("f")
            scale = None
        else:
            return []

        usable = len(raw) - (len(raw) % item_size)
        if usable <= 0:
            return []

        values.frombytes(raw[:usable])
        if sys.byteorder != "little":
            values.byteswap()

        frame_count = len(values) // channels
        samples = []
        index = 0
        for _ in range(frame_count):
            total = 0.0
            for _ in range(channels):
                value = float(values[index])
                index += 1
                if scale is None:
                    total += max(-1.0, min(1.0, value))
                else:
                    total += max(-1.0, min(1.0, value / scale))
            samples.append(total / channels)
        return samples

    def _process_audio_samples(self, samples, sample_rate: int):
        metrics = compute_audio_band_metrics(samples, sample_rate, self._low_state, self._mid_state)
        if not metrics:
            return
        self._process_audio_metrics(metrics["rms"], metrics["low"], metrics["mid"], metrics["high"], metrics["low_state"], metrics["mid_state"])

    def _process_audio_metrics(self, rms: float, low_rms: float, mid_rms: float, high_rms: float, low_state=None, mid_state=None):
        if low_state is not None:
            self._low_state = float(low_state)
        if mid_state is not None:
            self._mid_state = float(mid_state)

        rms = max(0.0, min(1.0, float(rms)))
        low_rms = max(0.0, min(1.0, float(low_rms)))
        mid_rms = max(0.0, min(1.0, float(mid_rms)))
        high_rms = max(0.0, min(1.0, float(high_rms)))
        self.levelChanged.emit(rms)
        self.bandLevelsChanged.emit(low_rms, mid_rms, high_rms)

        short_alpha = 0.35
        long_alpha = 0.03
        beat_driver = max(rms, min(1.0, (low_rms * 1.25) + (mid_rms * 0.70) + (high_rms * 0.25)))
        self._short_env = ((1.0 - short_alpha) * self._short_env) + (short_alpha * beat_driver)
        self._long_env = ((1.0 - long_alpha) * self._long_env) + (long_alpha * beat_driver)

        if self._long_env < 1e-4:
            return

        sensitivity = self.sensitivity / 100.0
        threshold_ratio = 1.75 - (0.6 * sensitivity)
        threshold = self._long_env * threshold_ratio
        over_energy = self._short_env - threshold
        if over_energy <= 0.0:
            return

        now_ms = time.monotonic() * 1000.0
        if (now_ms - self._last_beat_ms) < self._cooldown_ms:
            return
        self._last_beat_ms = now_ms

        strength = min(1.0, max(0.05, over_energy / max(1e-6, self._long_env)))
        self.beatDetected.emit(strength)
        self.stateChanged.emit(f"Beat {strength:.2f} | Low {low_rms:.2f} | Mid {mid_rms:.2f} | High {high_rms:.2f}")

    def _on_soundcard_process_stdout(self):
        if self._soundcard_process is None:
            return
        data = bytes(self._soundcard_process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if not data:
            return
        self._soundcard_stdout_buffer += data
        while "\n" in self._soundcard_stdout_buffer:
            line, self._soundcard_stdout_buffer = self._soundcard_stdout_buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            msg_type = str(payload.get("type", ""))
            if msg_type == "opened":
                self.stateChanged.emit(str(payload.get("message", "Listening to sound card output...")))
            elif msg_type == "metrics":
                self._process_audio_metrics(
                    payload.get("rms", 0.0),
                    payload.get("low", 0.0),
                    payload.get("mid", 0.0),
                    payload.get("high", 0.0),
                )
            elif msg_type == "error":
                self._on_soundcard_runtime_error(str(payload.get("message", "Sound card loopback capture failed")))

    def _on_soundcard_process_stderr(self):
        if self._soundcard_process is None:
            return
        data = bytes(self._soundcard_process.readAllStandardError()).decode("utf-8", errors="replace").strip()
        if data:
            log_startup_event("soundcard stderr: " + data)

    def _on_soundcard_runtime_error(self, text: str):
        if self._audio_backend != AUDIO_SOURCE_BACKEND_SOUNDCARD:
            return
        self.stateChanged.emit(str(text))
        self.enabled = False
        self._stop()

    def _on_soundcard_process_error(self, _error):
        self._on_soundcard_runtime_error("Sound card loopback process failed")

    def _on_soundcard_process_finished(self, _exit_code, _exit_status):
        if self._audio_backend == AUDIO_SOURCE_BACKEND_SOUNDCARD and self.enabled:
            self._on_soundcard_runtime_error("Sound card loopback process stopped")

    def _poll_audio(self):
        if self._audio_backend == AUDIO_SOURCE_BACKEND_SOUNDCARD:
            return

        if self._audio_device is None:
            return

        chunk = self._audio_device.read(4096)
        if not chunk:
            return

        samples = self._decode_samples(chunk)
        sample_rate = max(1, int(self._active_format.sampleRate() or self._format.sampleRate()))
        self._process_audio_samples(samples, sample_rate)

class ControlPanel(QWidget):
    MAIN_PRESET_HEX = [
        "#FFFFFF",
        "#000000",
        "#FF0000",
        "#00FF00",
        "#0000FF",
        "#FFFF00",
        "#00FFFF",
        "#FF00FF",
        "#FFA500",
        "#800080",
        "#808080",
        "#8B4513",
    ]
    PRESET_FILE = app_data_dir() / "color_presets.json"
    BEAT_TRANSITION_EFFECT_OPTIONS = BEAT_TRANSITION_EFFECT_OPTIONS
    BEAT_TRANSITION_EASING_OPTIONS = BEAT_TRANSITION_EASING_OPTIONS
    CHANGE_VISIBILITY_OPTIONS = CHANGE_VISIBILITY_OPTIONS

    toolChanged = Signal(str)
    polygonSidesChanged = Signal(int)
    shapeFilledChanged = Signal(bool)
    brushStyleChanged = Signal(str)
    brushColorChanged = Signal(QColor)
    brushSizeChanged = Signal(int)
    brushBrightnessChanged = Signal(int)
    brushOpacityChanged = Signal(int)
    brushSprayChanged = Signal(int)
    textValueChanged = Signal(str)
    textSizeChanged = Signal(int)
    importImageRequested = Signal()
    importBackgroundRequested = Signal()
    backgroundImportRequested = Signal()
    imageVariantParamsChanged = Signal(dict)
    beatEnabledChanged = Signal(bool)
    beatSensitivityChanged = Signal(int)
    audioSourceChanged = Signal(str)
    refreshAudioSourcesRequested = Signal()
    externalOutputToggled = Signal(bool)
    externalDisplayChanged = Signal(int)
    refreshExternalDisplaysRequested = Signal()
    performanceModeChanged = Signal(bool)
    objectSelectionChanged = Signal(int)
    backgroundSelectionChanged = Signal(int)
    changeTargetChanged = Signal(str)
    transformModeChanged = Signal(str)
    changeOpacityChanged = Signal(int)
    changeColorChanged = Signal(QColor)
    backgroundChangeColorChanged = Signal(QColor)
    changeVisibilityModeChanged = Signal(str)
    backgroundChangeVisibilityModeChanged = Signal(str)
    changePreviewEnabledChanged = Signal(bool)
    backgroundChangePreviewEnabledChanged = Signal(bool)
    imageSetSwitchTimeChanged = Signal(float)
    imageSetTimingModeChanged = Signal(str)
    imageSetTimingTranslationChanged = Signal(float)
    imageSetTimingPauseChanged = Signal(float)
    selectedLoopTimelineChanged = Signal(int, dict)
    backgroundSelectedLoopTimelineChanged = Signal(int, dict)
    applyStageRequested = Signal()
    backgroundApplyStageRequested = Signal()
    resetStagePreviewRequested = Signal()
    backgroundResetStagePreviewRequested = Signal()
    resetStagesRequested = Signal()
    backgroundResetStagesRequested = Signal()

    def __init__(self):
        super().__init__()
        self._apply_panel_theme()
        self._color = QColor(255, 255, 255)
        self._change_color = QColor(0, 0, 0)
        self._saved_preset_hex = self._load_saved_presets()
        self._main_presets = [QColor(v) for v in self.MAIN_PRESET_HEX]
        self._object_metadata = []
        self._background_metadata = []
        self._selected_loop_timeline = {"beat_map": [], "beat_transitions": []}
        self._selected_background_loop_timeline = {"beat_map": [], "beat_transitions": []}
        self._active_change_editor_key = "object"
        self._change_editor_colors = {
            "object": QColor(0, 0, 0),
            "background": QColor(0, 0, 0),
        }
        self._change_editor_visibility = {
            "object": "visible",
            "background": "visible",
        }
        self._change_editor_preview_enabled = {
            "object": True,
            "background": True,
        }
        self._change_editor_transform_modes = {
            "object": "translate",
            "background": "translate",
        }
        self._change_editor_config_dirty = {
            "object": False,
            "background": False,
        }
        self._performance_mode = False
        self._image_stage_preview_items = []
        self._selected_photo_stage_index = 0
        self._stage_preview_buttons = []
        self.object_tab = None
        self.change_tab = None
        self.beat_tab = None
        self.further_development_tab = None
        self.image_subtab = None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        self.tabs = QTabWidget(self)
        self.tabs.setTabPosition(QTabWidget.North)
        root.addWidget(self.tabs)

        self._build_object_tab()
        self._build_change_tab()
        self._build_beat_tab()
        self._build_further_development_tab()

        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.object_subtabs.setCurrentWidget(self.image_subtab)
        self._set_active_change_editor("object", emit=False)
        self._update_draw_control_states()

        self.installEventFilter(self)

    def _apply_panel_theme(self):
        self.setObjectName("controlPanel")
        self.setMinimumWidth(390)
        self.setStyleSheet(
            """
            QWidget#controlPanel {
                background: #f3efe6;
                color: #24313a;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QTabWidget::pane {
                border: 1px solid #d8d0c3;
                border-radius: 16px;
                background: #fbfaf6;
            }
            QTabBar::tab {
                background: #e7e0d3;
                color: #51606a;
                border: 1px solid #d8d0c3;
                border-radius: 12px;
                padding: 10px 14px;
                margin: 4px 4px 4px 0;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #1f6f78;
                color: white;
                border-color: #1f6f78;
            }
            QTabBar::tab:!selected:hover {
                background: #efe8dc;
            }
            QGroupBox#panelSection {
                border: 1px solid #ddd5c9;
                border-radius: 14px;
                margin-top: 14px;
                background: #fffdf8;
                font-weight: 700;
                color: #2c4751;
            }
            QGroupBox#panelSection::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QLabel[role="note"] {
                color: #6a7077;
                background: #f6f1e8;
                border: 1px solid #e4dccf;
                border-radius: 10px;
                padding: 8px 10px;
            }
            QLabel[role="status"] {
                color: #31424d;
                background: #edf4f3;
                border: 1px solid #d7e3e1;
                border-radius: 10px;
                padding: 8px 10px;
            }
            QPushButton {
                background: #f2ebdf;
                border: 1px solid #d2c8b8;
                border-radius: 10px;
                padding: 7px 10px;
                min-height: 20px;
            }
            QPushButton:hover {
                background: #ebe2d4;
            }
            QPushButton:checked {
                background: #1f6f78;
                color: white;
                border-color: #1f6f78;
            }
            QPushButton:disabled {
                background: #ece7de;
                color: #9aa1a7;
                border-color: #ddd7cc;
            }
            QComboBox, QLineEdit {
                background: #fffdf9;
                border: 1px solid #d8d0c3;
                border-radius: 10px;
                padding: 6px 10px;
                min-height: 22px;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                border-radius: 3px;
                background: #d9d1c3;
            }
            QSlider::sub-page:horizontal {
                background: #1f6f78;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #fffdf8;
                border: 2px solid #1f6f78;
                width: 18px;
                margin: -7px 0;
                border-radius: 9px;
            }
            QTableWidget {
                background: #fffdf8;
                alternate-background-color: #faf6ee;
                border: 1px solid #d8d0c3;
                border-radius: 12px;
                gridline-color: #ebe3d6;
            }
            QHeaderView::section {
                background: #efe7da;
                color: #43535d;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #ddd5c9;
                font-weight: 700;
            }
            """
        )

    def _make_note_label(self, text: str):
        label = QLabel(str(text))
        label.setWordWrap(True)
        label.setProperty("role", "note")
        return label

    def _make_status_label(self, text: str):
        label = QLabel(str(text))
        label.setWordWrap(True)
        label.setProperty("role", "status")
        return label

    def _build_scroll_tab(self):
        tab = QWidget(self)
        shell_layout = QVBoxLayout(tab)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        scroll = QScrollArea(tab)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        shell_layout.addWidget(scroll)

        content = QWidget(scroll)
        content.setMinimumWidth(0)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        scroll.setWidget(content)
        return tab, content, layout

    def _make_section_box(self, title: str):
        box = QGroupBox(str(title), self)
        box.setObjectName("panelSection")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(8)
        return box, layout

    def _build_object_tab(self):
        build_further_development_object_tab(self, ColorWheelWidget)

    def _build_change_tab(self):
        build_further_development_change_tab(
            self,
            image_set_timing_mode_options=IMAGE_SET_TIMING_MODE_OPTIONS,
            default_switch_time_seconds=default_image_set_switch_time(),
            default_timing_translation=default_image_set_timing_translation(),
            default_timing_pause=default_image_set_timing_pause(),
        )

    def _build_beat_tab(self):
        self.beat_tab, _content, layout = self._build_scroll_tab()

        input_box, input_layout = self._make_section_box("Audio Input")

        input_layout.addWidget(QLabel("Audio Source"))
        self.audio_source_combo = QComboBox(self.beat_tab)
        self.audio_source_combo.currentIndexChanged.connect(self._emit_audio_source_changed)
        input_layout.addWidget(self.audio_source_combo)

        audio_actions = QVBoxLayout()
        self.refresh_audio_sources_button = QPushButton("Refresh Sources")
        self.refresh_audio_sources_button.clicked.connect(self.refreshAudioSourcesRequested.emit)
        audio_actions.addWidget(self.refresh_audio_sources_button)
        input_layout.addLayout(audio_actions)

        self.audio_source_note = self._make_note_label(
            "Use any microphone/input device here. Internal/system audio can come either from a real sound-card loopback source or from loopback-capable inputs such as Stereo Mix and virtual cables."
        )
        input_layout.addWidget(self.audio_source_note)

        self.beat_enable = QPushButton("Enable Audio")
        self.beat_enable.setCheckable(True)
        self.beat_enable.toggled.connect(self._emit_beat_enabled)
        input_layout.addWidget(self.beat_enable)

        input_layout.addWidget(QLabel("Beat Sensitivity"))
        self.beat_sensitivity = QSlider(Qt.Horizontal)
        self.beat_sensitivity.setRange(1, 100)
        self.beat_sensitivity.setValue(60)
        self.beat_sensitivity.valueChanged.connect(self._emit_beat_sensitivity)
        input_layout.addWidget(self.beat_sensitivity)

        self.beat_status = self._make_status_label("Audio reactivity off")
        input_layout.addWidget(self.beat_status)
        layout.addWidget(input_box)

        output_box, output_layout = self._make_section_box("External Output")
        output_layout.addWidget(QLabel("Display"))
        self.external_display_combo = QComboBox(self.beat_tab)
        self.external_display_combo.currentIndexChanged.connect(self._emit_external_display_changed)
        output_layout.addWidget(self.external_display_combo)

        external_actions = QVBoxLayout()
        self.refresh_external_displays_button = QPushButton("Refresh Displays")
        self.refresh_external_displays_button.clicked.connect(self.refreshExternalDisplaysRequested.emit)
        external_actions.addWidget(self.refresh_external_displays_button)
        self.external_output_button = QPushButton("Open Projector")
        self.external_output_button.setCheckable(True)
        self.external_output_button.toggled.connect(self._emit_external_output_toggled)
        external_actions.addWidget(self.external_output_button)
        output_layout.addLayout(external_actions)

        self.external_output_status = self._make_status_label("External output off")
        output_layout.addWidget(self.external_output_status)
        layout.addWidget(output_box)

        routing_note = self._make_note_label(
            "Loop routing is handled in Change. Build the visual loop there by assigning pictures to beat places and choosing transitions between them."
        )
        layout.addWidget(routing_note)

        layout.addStretch(1)
        self.tabs.addTab(self.beat_tab, "Audio")

    def _build_further_development_tab(self):
        build_further_development_module_tab(self)

    def _on_tab_changed(self, _):
        self._emit_tool_for_current_tab()

    def _emit_tool_for_current_tab(self):
        current = self.tabs.currentWidget()
        if current is None:
            return
        if current is self.object_tab:
            self._emit_object_tool_changed()
        elif current is self.change_tab:
            self.toolChanged.emit("select")
        elif current is self.beat_tab:
            self.toolChanged.emit("beat")
        elif current is self.further_development_tab:
            self.toolChanged.emit("text")

    def _emit_object_tool_changed(self):
        self._update_draw_control_states()
        if self.tabs.currentWidget() is not self.object_tab:
            return
        if self.object_subtabs.currentWidget() is self.image_subtab:
            self.toolChanged.emit("select")
            return
        if hasattr(self, "object_tool") and self.object_tool is not None:
            self.toolChanged.emit(str(self.object_tool.currentData()))
            return
        self.toolChanged.emit("select")

    def _emit_polygon_sides_changed(self):
        if self.polygon_sides is None:
            return
        self.polygonSidesChanged.emit(int(self.polygon_sides.currentData()))

    def _emit_shape_fill_changed(self):
        if self.shape_fill_mode is None:
            return
        self.shapeFilledChanged.emit(bool(self.shape_fill_mode.currentData()))

    def _emit_brush_style_changed(self):
        if self.brush_style is None:
            return
        self.brushStyleChanged.emit(str(self.brush_style.currentData()))

    def _emit_text_value_changed(self, text: str):
        self.textValueChanged.emit(str(text))

    def _emit_text_size_changed(self, value: int):
        self.textSizeChanged.emit(int(value))

    def _emit_beat_enabled(self, enabled: bool):
        self.beat_enable.setText("Disable Audio" if enabled else "Enable Audio")
        self.beatEnabledChanged.emit(bool(enabled))

    def _update_workspace_buttons(self):
        return

    def _set_workspace_mode(self, mode: str):
        return

    def _set_performance_mode_state(self, enabled: bool):
        self._performance_mode = bool(enabled)

    def _emit_performance_mode_changed(self, enabled: bool):
        self._set_performance_mode_state(enabled)

    def _emit_beat_sensitivity(self, value: int):
        self.beatSensitivityChanged.emit(int(value))

    def _emit_audio_source_changed(self):
        data = self.audio_source_combo.currentData()
        self.audioSourceChanged.emit(str(data or ""))

    def _emit_external_output_toggled(self, enabled: bool):
        self.external_output_button.setText("Close Projector" if enabled else "Open Projector")
        self.externalOutputToggled.emit(bool(enabled))

    def _emit_external_display_changed(self):
        data = self.external_display_combo.currentData()
        self.externalDisplayChanged.emit(int(data) if isinstance(data, int) else -1)

    def _emit_object_selection_changed(self):
        idx = self.object_combo.currentData()
        self._update_change_stage_info()
        self._sync_selected_loop_timeline()
        self._sync_image_set_matrix_controls()
        self.objectSelectionChanged.emit(int(idx) if isinstance(idx, int) else -1)

    def _emit_transform_mode_changed(self):
        if self.transform_mode is None:
            return
        self._update_transform_mode_hint()
        self.transformModeChanged.emit(str(self.transform_mode.currentData()))

    def _emit_change_visibility_mode_changed(self):
        if self.change_visibility_mode is None:
            return
        self.changeVisibilityModeChanged.emit(str(self.change_visibility_mode.currentData()))

    def _emit_image_set_switch_time_changed(self, value: int):
        millis = max(0, int(value))
        if getattr(self, "image_set_switch_time_value", None) is not None:
            self.image_set_switch_time_value.setText(f"{millis} ms")
        self.imageSetSwitchTimeChanged.emit(millis / 1000.0)

    def _emit_image_set_timing_mode_changed(self):
        if getattr(self, "image_set_timing_mode", None) is None:
            return
        self._update_image_set_timing_control_state()
        self.imageSetTimingModeChanged.emit(str(self.image_set_timing_mode.currentData()))

    def _emit_image_set_timing_translation_changed(self, value: int):
        ratio = max(25, min(300, int(value)))
        if getattr(self, "image_set_timing_translation_value", None) is not None:
            self.image_set_timing_translation_value.setText(f"{ratio}% of beat")
        self.imageSetTimingTranslationChanged.emit(ratio / 100.0)

    def _emit_image_set_timing_pause_changed(self, value: int):
        pause_percent = max(0, min(95, int(value)))
        if getattr(self, "image_set_timing_pause_value", None) is not None:
            self.image_set_timing_pause_value.setText(f"{pause_percent}% hold")
        self.imageSetTimingPauseChanged.emit(pause_percent / 100.0)

    def _emit_image_variant_params_changed(self, *_args):
        if not hasattr(self, "image_variant_palette"):
            return
        params = {
            "palette_mode": str(self.image_variant_palette.currentData()),
            "stroke_scale": self.image_variant_stroke_scale.value() / 100.0,
            "stroke_angle": float(self.image_variant_angle.value()),
            "density": self.image_variant_density.value() / 100.0,
            "shell_opacity": self.image_variant_shell_opacity.value() / 100.0,
            "palette_mix": self.image_variant_palette_mix.value() / 100.0,
        }
        self.imageVariantParamsChanged.emit(params)

    def _update_transform_mode_hint(self):
        if self.transform_mode is None or self.transform_mode_hint is None:
            return
        mode = str(self.transform_mode.currentData())
        if mode == "reflect":
            text = "Reflection: choose the first point of the symmetry line on the canvas, then choose the second point. Use the object list or right-click on canvas to choose which object to mirror."
        elif mode == "rotate":
            text = "Rotation: choose the rotation point on the canvas with one click, then drag from another point to rotate through angles. Use the object list or right-click on canvas to choose the object."
        elif mode == "scale":
            text = "Scale: choose the scale center on the canvas with one click, then drag away from or toward it to resize the selected object. Use the object list or right-click on canvas to choose the object."
        else:
            text = "Translation: drag the selected object directly on the canvas to move it."
        self.transform_mode_hint.setText(text)

    def _update_draw_control_states(self):
        if not hasattr(self, "object_tool") or self.object_tool is None:
            return
        mode = str(self.object_tool.currentData())
        is_brush = development_tool_is_brush(mode)
        is_polygon = development_tool_is_polygon(mode)
        is_shape = development_tool_is_shape(mode)
        self.object_tool.setEnabled(False)
        if self.brush_style is not None:
            self.brush_style.setEnabled(is_brush)
        if self.size is not None:
            self.size.setEnabled(is_brush or is_shape)
        if self.spray is not None:
            self.spray.setEnabled(is_brush or is_shape)
        if self.polygon_sides is not None:
            self.polygon_sides.setEnabled(is_polygon)
        if self.shape_fill_mode is not None:
            self.shape_fill_mode.setEnabled(is_shape and mode != "line")

    def _set_tab_enabled(self, tabs: QTabWidget, widget: QWidget, enabled: bool):
        if tabs is None or widget is None:
            return
        index = tabs.indexOf(widget)
        if index >= 0:
            tabs.setTabEnabled(index, bool(enabled))

    def _apply_performance_mode_ui(self):
        self._update_draw_control_states()

    def _sync_object_color_ui(self, color: QColor):
        if not color.isValid():
            return
        self._color = QColor(color)
        if self.object_wheel is not None:
            self.object_wheel.blockSignals(True)
            self.object_wheel.set_color(self._color)
            self.object_wheel.blockSignals(False)
        if self.object_value_slider is not None:
            self.object_value_slider.blockSignals(True)
            self.object_value_slider.setValue(self._color.value())
            self.object_value_slider.blockSignals(False)
        fg = "#000000" if self._color.lightness() > 140 else "#FFFFFF"
        if self.object_color_preview is not None:
            self.object_color_preview.setText(f"  {self._color.name(QColor.HexRgb).upper()}")
            self.object_color_preview.setStyleSheet(
                f"background-color: {self._color.name()}; color: {fg}; border: 1px solid #d2c8b8; border-radius: 10px; padding: 6px 8px;"
            )

    def _on_object_wheel_color_changed(self, color: QColor):
        if not color.isValid():
            return
        self._sync_object_color_ui(color)
        self.brushColorChanged.emit(QColor(self._color))

    def _choose_change_color(self):
        if self.change_color_button is None:
            return
        dialog = ColorWheelDialog(self._change_color, self)
        anchor = self.change_color_button.mapToGlobal(self.change_color_button.rect().bottomLeft())
        dialog.move(anchor)
        if dialog.exec() == QDialog.Accepted:
            self._apply_change_color(dialog.selected_color())

    def _apply_change_color(self, color: QColor):
        if not color.isValid():
            return
        self._change_color = QColor(color)
        self._update_change_color_button()
        self.changeColorChanged.emit(QColor(self._change_color))

    def _update_change_color_button(self):
        if self.change_color_button is None:
            return
        fg = "#000000" if self._change_color.lightness() > 140 else "#FFFFFF"
        self.change_color_button.setText(self._change_color.name(QColor.HexRgb).upper())
        self.change_color_button.setStyleSheet(
            f"QPushButton {{ background-color: {self._change_color.name()}; color: {fg}; border: 1px solid #d2c8b8; border-radius: 10px; padding: 7px 10px; }}"
        )

    def sync_defaults(self):
        self._set_change_editor_color("object", self._change_editor_colors["object"], emit=False)
        self._set_change_editor_color("background", self._change_editor_colors["background"], emit=False)
        self.brushColorChanged.emit(QColor(self._color))
        if self.brightness is not None:
            self.brushBrightnessChanged.emit(self.brightness.value())
        self._emit_brush_style_changed()
        if self.size is not None:
            self.brushSizeChanged.emit(self.size.value())
        if self.opacity is not None:
            self.brushOpacityChanged.emit(self.opacity.value())
        if self.spray is not None:
            self.brushSprayChanged.emit(self.spray.value())
        self._emit_text_value_changed(self.text_input.text())
        self._emit_text_size_changed(self.text_size.value())
        self._emit_audio_source_changed()
        self._emit_beat_sensitivity(self.beat_sensitivity.value())
        self._emit_beat_enabled(self.beat_enable.isChecked())
        if self.polygon_sides is not None:
            self._emit_polygon_sides_changed()
        if self.shape_fill_mode is not None:
            self._emit_shape_fill_changed()
        if self.change_color_button is not None:
            self.changeColorChanged.emit(QColor(self._change_editor_colors["object"]))
        if getattr(self, "background_change_color_button", None) is not None:
            self.backgroundChangeColorChanged.emit(QColor(self._change_editor_colors["background"]))
        self._emit_change_visibility_mode_changed()
        if getattr(self, "background_change_visibility_mode", None) is not None:
            self._emit_change_visibility_mode_for_key("background")
        self._set_change_preview_enabled("object", self._change_editor_preview_enabled["object"], emit=True)
        self._set_change_preview_enabled("background", self._change_editor_preview_enabled["background"], emit=True)
        if getattr(self, "image_set_timing_mode", None) is not None:
            self._emit_image_set_timing_mode_changed()
        if getattr(self, "image_set_timing_translation", None) is not None:
            self._emit_image_set_timing_translation_changed(self.image_set_timing_translation.value())
        if getattr(self, "image_set_timing_pause", None) is not None:
            self._emit_image_set_timing_pause_changed(self.image_set_timing_pause.value())
        self._activate_change_transform_mode("object", self._change_editor_transform_modes["object"], emit=False)
        self._activate_change_transform_mode("background", self._change_editor_transform_modes["background"], emit=False)
        self._on_change_subtab_changed()
        self._emit_tool_for_current_tab()

    def _change_editor(self, key: str):
        return getattr(self, "_change_editors", {}).get(str(key), {})

    def _current_change_editor_key(self):
        change_subtabs = getattr(self, "change_subtabs", None)
        if change_subtabs is not None:
            current_widget = change_subtabs.currentWidget()
            if current_widget is getattr(self, "change_background_subtab", None):
                return "background"
            if current_widget is getattr(self, "change_object_subtab", None):
                return "object"
        return "background" if str(getattr(self, "_active_change_editor_key", "object")) == "background" else "object"

    def _set_active_change_editor(self, key: str, emit: bool = True):
        clean_key = "background" if str(key) == "background" else "object"
        change_subtabs = getattr(self, "change_subtabs", None)
        if change_subtabs is not None:
            target_widget = getattr(self, "change_background_subtab", None) if clean_key == "background" else getattr(self, "change_object_subtab", None)
            if target_widget is not None and change_subtabs.currentWidget() is not target_widget:
                signals_were_blocked = change_subtabs.blockSignals(True)
                change_subtabs.setCurrentWidget(target_widget)
                change_subtabs.blockSignals(signals_were_blocked)
        self._active_change_editor_key = clean_key
        self._update_apply_change_configuration_button()
        if emit:
            self.changeTargetChanged.emit(clean_key)
            self.transformModeChanged.emit(self._change_editor_transform_modes.get(clean_key, "translate"))

    def current_change_target_kind(self):
        return self._current_change_editor_key()

    def toggle_change_target_kind(self):
        next_key = "background" if self._current_change_editor_key() == "object" else "object"
        self._set_active_change_editor(next_key, emit=True)

    def current_change_visibility_mode(self, key: str = None):
        target_key = self._current_change_editor_key() if key is None else str(key)
        return clean_change_visibility_mode(self._change_editor_visibility.get(target_key, "current"))

    def current_change_preview_enabled(self, key: str = None):
        _ = key
        return True

    def _change_editor_metadata(self, key: str):
        return self._background_metadata if str(key) == "background" else self._object_metadata

    def _change_editor_loop_config(self, key: str):
        return self._selected_background_loop_timeline if str(key) == "background" else self._selected_loop_timeline

    def _set_change_editor_loop_config(self, key: str, config):
        if str(key) == "background":
            self._selected_background_loop_timeline = config
        else:
            self._selected_loop_timeline = config

    def _selected_change_editor_index(self, key: str):
        editor = self._change_editor(key)
        combo = editor.get("combo")
        idx = combo.currentData() if combo is not None else -1
        return int(idx) if isinstance(idx, int) else -1

    def _selected_change_editor_metadata(self, key: str):
        metadata = self._change_editor_metadata(key)
        index = self._selected_change_editor_index(key)
        if 0 <= index < len(metadata):
            return metadata[index]
        return {}

    def _change_transform_hint(self, key: str, mode: str):
        subject = "background" if str(key) == "background" else "object"
        if mode == "reflect":
            return f"Reflection: click once for the first mirror-line point, then click again to mirror the selected {subject}."
        if mode == "rotate":
            return f"Rotation: drag around the pivot to rotate the selected {subject}."
        if mode == "scale":
            return f"Scale: drag toward or away from the pivot to resize the selected {subject}."
        return f"Translation: drag the selected {subject} directly on the canvas to move it."

    def _activate_change_transform_mode(self, key: str, mode: str, emit: bool = True):
        editor = self._change_editor(key)
        buttons = editor.get("transform_buttons", {})
        clean_mode = mode if mode in buttons else "translate"
        self._change_editor_transform_modes[str(key)] = clean_mode
        for button_mode, button in buttons.items():
            button.blockSignals(True)
            button.setChecked(button_mode == clean_mode)
            button.blockSignals(False)
        hint = editor.get("transform_hint")
        if hint is not None:
            hint.setText(self._change_transform_hint(key, clean_mode))
        self._set_active_change_editor(key, emit=False)
        if emit:
            if getattr(self, "change_tab", None) is self.tabs.currentWidget():
                self.changeTargetChanged.emit(str(key))
                self.transformModeChanged.emit(clean_mode)

    def _set_change_editor_color(self, key: str, color: QColor, emit: bool = True):
        if not color.isValid():
            return
        editor_key = str(key)
        self._change_editor_colors[editor_key] = QColor(color)
        if editor_key == "object":
            self._change_color = QColor(color)
        editor = self._change_editor(editor_key)
        button = editor.get("color_button")
        if button is not None:
            fg = "#000000" if color.lightness() > 140 else "#FFFFFF"
            button.setText(color.name(QColor.HexRgb).upper())
            button.setStyleSheet(
                f"QPushButton {{ background-color: {color.name()}; color: {fg}; border: 1px solid #d2c8b8; border-radius: 10px; padding: 7px 10px; }}"
            )
        if not emit:
            return
        if editor_key == "background":
            self.backgroundChangeColorChanged.emit(QColor(color))
        else:
            self.changeColorChanged.emit(QColor(color))

    def _choose_change_editor_color(self, key: str):
        self._set_active_change_editor(key, emit=getattr(self, "change_tab", None) is self.tabs.currentWidget())
        editor = self._change_editor(key)
        button = editor.get("color_button")
        if button is None:
            return
        dialog = ColorWheelDialog(self._change_editor_colors.get(str(key), QColor(255, 255, 255)), self)
        anchor = button.mapToGlobal(button.rect().bottomLeft())
        dialog.move(anchor)
        if dialog.exec() == QDialog.Accepted:
            self._set_change_editor_color(key, dialog.selected_color(), emit=True)

    def _emit_change_visibility_mode_for_key(self, key: str):
        self._set_active_change_editor(key, emit=False)
        editor = self._change_editor(key)
        combo = editor.get("visibility_combo")
        if combo is None:
            return
        mode = clean_change_visibility_mode(combo.currentData())
        self._change_editor_visibility[str(key)] = mode
        if str(key) == "background":
            self.backgroundChangeVisibilityModeChanged.emit(mode)
        else:
            self._change_visibility_mode = mode
            self.changeVisibilityModeChanged.emit(mode)

    def _set_change_preview_enabled(self, key: str, enabled: bool, emit: bool = True):
        editor_key = "background" if str(key) == "background" else "object"
        _ = enabled
        clean_enabled = True
        self._change_editor_preview_enabled[editor_key] = clean_enabled
        editor = self._change_editor(editor_key)
        button = editor.get("preview_toggle")
        if button is not None:
            button.blockSignals(True)
            button.setChecked(clean_enabled)
            button.setText("Preview On" if clean_enabled else "Preview Off")
            button.blockSignals(False)
        if emit:
            if editor_key == "background":
                self.backgroundChangePreviewEnabledChanged.emit(clean_enabled)
            else:
                self.changePreviewEnabledChanged.emit(clean_enabled)

    def _emit_change_preview_enabled_for_key(self, key: str):
        self._set_active_change_editor(key, emit=False)
        self._set_change_preview_enabled(key, True, emit=True)

    def _set_change_editor_config_dirty(self, key: str, dirty: bool):
        editor_key = "background" if str(key) == "background" else "object"
        self._change_editor_config_dirty[editor_key] = bool(dirty)
        self._update_apply_change_configuration_button()

    def _update_apply_change_configuration_button(self):
        button = getattr(self, "apply_change_configuration_button", None)
        if button is None:
            return
        key = self._current_change_editor_key()
        button.setEnabled(bool(self._selected_change_editor_metadata(key)) and bool(self._change_editor_config_dirty.get(key, False)))

    def _apply_current_change_configuration(self):
        self._emit_change_loop_config(self._current_change_editor_key())

    def _on_change_subtab_changed(self, *_args):
        self._set_active_change_editor(self._current_change_editor_key(), emit=True)

    def _on_change_editor_selection_changed(self, key: str):
        editor_key = str(key)
        self._sync_change_editor_state(editor_key)
        self._set_change_editor_config_dirty(editor_key, False)
        if editor_key == "background":
            self.backgroundSelectionChanged.emit(self._selected_change_editor_index(editor_key))
        else:
            self.objectSelectionChanged.emit(self._selected_change_editor_index(editor_key))
        self._set_active_change_editor(editor_key, emit=getattr(self, "change_tab", None) is self.tabs.currentWidget())

    def _set_change_editor_entries(self, key: str, labels, selected_index, metadata):
        editor = self._change_editor(key)
        combo = editor.get("combo")
        if combo is None:
            return
        if str(key) == "background":
            self._background_metadata = list(metadata)
        else:
            self._object_metadata = list(metadata)
        combo.blockSignals(True)
        combo.clear()
        if labels:
            for index, label in enumerate(labels):
                combo.addItem(str(label), int(index))
            clamped = max(0, min(int(selected_index), len(labels) - 1)) if labels else 0
            combo.setCurrentIndex(clamped)
            combo.setEnabled(True)
        else:
            combo.addItem("No items", -1)
            combo.setCurrentIndex(0)
            combo.setEnabled(False)
        combo.blockSignals(False)
        self._sync_change_editor_state(str(key))
        self._set_change_editor_config_dirty(str(key), False)

    def set_change_object_list(self, labels, selected_index, metadata):
        self._set_change_editor_entries("object", labels, selected_index, metadata)

    def set_background_list(self, labels, selected_index, metadata):
        self._set_change_editor_entries("background", labels, selected_index, metadata)

    def _sync_change_editor_state(self, key: str, preserve_loop_config: bool = False):
        editor = self._change_editor(key)
        metadata = self._selected_change_editor_metadata(key)
        slider = editor.get("opacity_slider")
        if slider is not None:
            value = int(metadata.get("opacity_percent", 100)) if metadata else 100
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
            slider.setEnabled(bool(metadata))
            editor["opacity_value"].setText(f"{value}%")
        stage_info = editor.get("stage_info")
        state_counter = editor.get("state_counter")
        loop_count = editor.get("loop_count")
        loop_circle = editor.get("loop_circle")
        if not metadata:
            if stage_info is not None:
                stage_info.setText("No background selected" if str(key) == "background" else "No object selected")
            if state_counter is not None:
                state_counter.setText("0 states")
            if loop_count is not None:
                loop_count.blockSignals(True)
                loop_count.setCurrentIndex(max(0, loop_count.findData(default_loop_slot_count())))
                loop_count.blockSignals(False)
            empty_config = self._normalize_selected_loop_timeline({}, stage_count=0, slot_count=default_loop_slot_count())
            self._set_change_editor_loop_config(key, empty_config)
            if loop_circle is not None:
                loop_circle.set_loop(default_loop_slot_count(), empty_config["timeline_points"], 0)
            return

        stage_count = max(0, int(metadata.get("stage_count", 0)))
        slot_count = default_loop_slot_count()
        if preserve_loop_config:
            current_config = self._change_editor_loop_config(key)
            config = self._normalize_selected_loop_timeline(current_config, stage_count=stage_count, slot_count=slot_count)
        else:
            config = self._normalize_selected_loop_timeline(metadata, stage_count=stage_count, slot_count=slot_count)
        self._set_change_editor_loop_config(key, config)

        if loop_count is not None:
            loop_count.blockSignals(True)
            loop_count.setCurrentIndex(max(0, loop_count.findData(slot_count)))
            loop_count.blockSignals(False)
        if state_counter is not None:
            state_counter.setText(f"{stage_count} state" if stage_count == 1 else f"{stage_count} states")
        if stage_info is not None:
            subject = "Background" if str(key) == "background" else "Object"
            marker_count = len(config.get("timeline_points", []))
            stage_info.setText(f"{subject} selected | {stage_count} states | {marker_count} markers | {slot_count} beats")
        if loop_circle is not None:
            loop_circle.set_loop(slot_count, config["timeline_points"], stage_count)

    def _emit_change_loop_config(self, key: str):
        index = self._selected_change_editor_index(key)
        if index < 0:
            return False
        config = self._change_editor_loop_config(key)
        payload = {
            "beat_map": list(config.get("beat_map", [])),
            "beat_transitions": [self._normalize_transition_spec(value) for value in list(config.get("beat_transitions", []))],
            "timeline_points": normalize_loop_timeline_points(
                config.get("timeline_points", []),
                len(list(config.get("beat_map", []))) or default_loop_slot_count(),
                int(max(0, self._selected_change_editor_metadata(key).get("stage_count", 0))),
                beat_map=config.get("beat_map", []),
                beat_transitions=config.get("beat_transitions", []),
            ),
        }
        if str(key) == "background":
            self.backgroundSelectedLoopTimelineChanged.emit(index, payload)
        else:
            self.selectedLoopTimelineChanged.emit(index, payload)
        self._set_change_editor_config_dirty(str(key), False)
        return True

    def _timeline_stage_labels(self, key: str):
        metadata = self._selected_change_editor_metadata(key)
        stage_count = max(0, int(metadata.get("stage_count", 0)))
        stage_labels = list(metadata.get("stage_labels", []))
        while len(stage_labels) < stage_count:
            stage_labels.append(f"Stage {len(stage_labels) + 1}")
        return stage_labels[:stage_count]

    def _set_change_timeline_points(self, key: str, points):
        self._set_active_change_editor(key, emit=False)
        metadata = self._selected_change_editor_metadata(key)
        slot_count = default_loop_slot_count()
        stage_count = max(0, int(metadata.get("stage_count", 0))) if metadata else 0
        config = self._change_editor_loop_config(key)
        config["timeline_points"] = normalize_loop_timeline_points(
            points,
            slot_count,
            stage_count,
            beat_map=config.get("beat_map", []),
            beat_transitions=config.get("beat_transitions", []),
        )
        self._sync_change_editor_state(key, preserve_loop_config=True)
        self._set_change_editor_config_dirty(key, True)

    def _open_change_timeline_point_picker(self, key: str, point_index: int, local_pos: QPoint):
        self._set_active_change_editor(key, emit=getattr(self, "change_tab", None) is self.tabs.currentWidget())
        editor = self._change_editor(key)
        loop_circle = editor.get("loop_circle")
        config = self._change_editor_loop_config(key)
        points = list(config.get("timeline_points", []))
        if loop_circle is None or not (0 <= int(point_index) < len(points)):
            return
        current_value = int(points[int(point_index)].get("state", 0))
        stage_labels = self._timeline_stage_labels(key)

        menu = QMenu(loop_circle)
        if stage_labels:
            for stage_index, label in enumerate(stage_labels, start=1):
                action = menu.addAction(f"{stage_index}. {label}")
                action.setData(stage_index)
                action.setCheckable(True)
                action.setChecked(current_value == stage_index)
        else:
            unavailable = menu.addAction("No applied states yet")
            unavailable.setEnabled(False)

        selected_action = menu.exec(loop_circle.mapToGlobal(QPoint(local_pos)))
        if selected_action is None:
            return
        chosen_value = selected_action.data()
        if isinstance(chosen_value, int):
            points[int(point_index)]["state"] = int(chosen_value)
            self._set_change_timeline_points(key, points)

    def _create_change_timeline_point(self, key: str, position: float, local_pos: QPoint):
        self._set_active_change_editor(key, emit=getattr(self, "change_tab", None) is self.tabs.currentWidget())
        editor = self._change_editor(key)
        loop_circle = editor.get("loop_circle")
        if loop_circle is None:
            return

        stage_labels = self._timeline_stage_labels(key)
        menu = QMenu(loop_circle)
        if stage_labels:
            for stage_index, label in enumerate(stage_labels, start=1):
                action = menu.addAction(f"{stage_index}. {label}")
                action.setData(stage_index)
        else:
            unavailable = menu.addAction("No applied states yet")
            unavailable.setEnabled(False)

        selected_action = menu.exec(loop_circle.mapToGlobal(QPoint(local_pos)))
        if selected_action is None:
            return
        chosen_value = selected_action.data()
        if not isinstance(chosen_value, int) or chosen_value <= 0:
            return

        config = self._change_editor_loop_config(key)
        points = list(config.get("timeline_points", []))
        points.append(
            {
                "position": float(position),
                "state": int(chosen_value),
                "transition": default_timeline_transition_spec(),
            }
        )
        self._set_change_timeline_points(key, points)

    def _remove_change_timeline_point(self, key: str, point_index: int):
        self._set_active_change_editor(key, emit=getattr(self, "change_tab", None) is self.tabs.currentWidget())
        config = self._change_editor_loop_config(key)
        points = list(config.get("timeline_points", []))
        if not (0 <= int(point_index) < len(points)):
            return
        del points[int(point_index)]
        self._set_change_timeline_points(key, points)

    def _open_change_timeline_transition_picker(self, key: str, point_index: int, local_pos: QPoint):
        self._set_active_change_editor(key, emit=getattr(self, "change_tab", None) is self.tabs.currentWidget())
        editor = self._change_editor(key)
        loop_circle = editor.get("loop_circle")
        config = self._change_editor_loop_config(key)
        points = list(config.get("timeline_points", []))
        if loop_circle is None or not (0 <= int(point_index) < len(points)):
            return

        current_effect = str(points[int(point_index)].get("transition", {}).get("effect", "cut"))
        menu = QMenu(loop_circle)
        for label, effect in BEAT_TRANSITION_EFFECT_OPTIONS:
            action = menu.addAction(label)
            action.setData(effect)
            action.setCheckable(True)
            action.setChecked(current_effect == effect)

        selected_action = menu.exec(loop_circle.mapToGlobal(QPoint(local_pos)))
        if selected_action is None:
            return
        chosen_effect = str(selected_action.data() or "cut")
        points[int(point_index)]["transition"] = default_transition_spec(
            effect=chosen_effect,
            easing="linear" if clean_beat_transition_effect(chosen_effect) == "cut" else "ease_in_out",
        )
        self._set_change_timeline_points(key, points)

    def _on_change_loop_slot_count_changed(self, key: str):
        self._set_active_change_editor(key, emit=False)
        metadata = self._selected_change_editor_metadata(key)
        if not metadata:
            return
        config = self._normalize_selected_loop_timeline(
            self._change_editor_loop_config(key),
            stage_count=max(0, int(metadata.get("stage_count", 0))),
            slot_count=default_loop_slot_count(),
        )
        self._set_change_editor_loop_config(key, config)
        self._sync_change_editor_state(key, preserve_loop_config=True)
        self._set_change_editor_config_dirty(key, True)

    def export_history_state(self):
        return {
            "current_change_editor": self._current_change_editor_key(),
            "change_editor_colors": {
                key: color.name(QColor.HexRgb)
                for key, color in self._change_editor_colors.items()
            },
            "change_editor_visibility": dict(self._change_editor_visibility),
            "change_editor_preview_enabled": dict(self._change_editor_preview_enabled),
            "change_editor_transform_modes": dict(self._change_editor_transform_modes),
        }

    def import_history_state(self, state):
        payload = state if isinstance(state, dict) else {}
        colors = payload.get("change_editor_colors", {})
        visibility = payload.get("change_editor_visibility", {})
        preview_enabled = payload.get("change_editor_preview_enabled", {})
        transforms = payload.get("change_editor_transform_modes", {})
        for key in ("object", "background"):
            color_name = str(colors.get(key, self._change_editor_colors[key].name(QColor.HexRgb)))
            self._set_change_editor_color(key, QColor(color_name), emit=False)
            editor = self._change_editor(key)
            combo = editor.get("visibility_combo")
            target_mode = clean_change_visibility_mode(visibility.get(key, self._change_editor_visibility.get(key, "current")))
            self._change_editor_visibility[key] = target_mode
            if combo is not None:
                combo.blockSignals(True)
                combo.setCurrentIndex(max(0, combo.findData(target_mode)))
                combo.blockSignals(False)
            self._set_change_preview_enabled(key, True, emit=False)
            self._activate_change_transform_mode(key, str(transforms.get(key, self._change_editor_transform_modes.get(key, "translate"))), emit=False)

        current_key = str(payload.get("current_change_editor", "object"))
        self._set_active_change_editor(current_key, emit=False)

    def set_object_list(self, labels, selected_index, metadata):
        self._object_metadata = list(metadata)
        self.object_combo.blockSignals(True)
        self.object_combo.clear()

        # Show all objects EXCEPT image_set backgrounds
        object_entries = []
        for i, label in enumerate(labels):
            meta = self._object_metadata[i] if 0 <= i < len(self._object_metadata) else {}
            # Exclude image_set backgrounds, show everything else
            if not (str(meta.get("kind", "")) == "image_variant" and str(meta.get("variant_source_mode", "")) == "image_set"):
                object_entries.append((str(label), i))

        has_items = bool(object_entries)
        if has_items:
            for label, object_index in object_entries:
                self.object_combo.addItem(label, object_index)

            combo_index = 0
            for i, (_label, object_index) in enumerate(object_entries):
                if int(object_index) == int(selected_index):
                    combo_index = i
                    break
            self.object_combo.setCurrentIndex(combo_index)
        else:
            self.object_combo.addItem("No objects", -1)
            self.object_combo.setCurrentIndex(0)

        self.object_combo.setEnabled(has_items)
        self.object_combo.blockSignals(False)
        self._update_change_stage_info()
        self._sync_selected_loop_timeline()
        self._sync_image_set_matrix_controls()

    def set_beat_status(self, text: str):
        self.beat_status.setText(str(text))

    def set_audio_sources(self, sources, selected_id: str = ""):
        self.audio_source_combo.blockSignals(True)
        self.audio_source_combo.clear()

        if sources:
            for source in sources:
                self.audio_source_combo.addItem(str(source.get("label", "Audio Source")), str(source.get("id", "")))
            target_id = str(selected_id or "")
            target_index = 0
            if target_id:
                for index, source in enumerate(sources):
                    if str(source.get("id", "")) == target_id:
                        target_index = index
                        break
            self.audio_source_combo.setCurrentIndex(target_index)
        else:
            self.audio_source_combo.addItem("No audio inputs detected", "")
            self.audio_source_combo.setCurrentIndex(0)

        has_sources = bool(sources)
        self.audio_source_combo.setEnabled(has_sources)
        self.beat_enable.setEnabled(has_sources)
        self.audio_source_combo.blockSignals(False)

    def set_audio_source_note(self, text: str):
        self.audio_source_note.setText(str(text))

    def set_external_screens(self, screens, selected_index: int = 0):
        self.external_display_combo.blockSignals(True)
        self.external_display_combo.clear()

        if screens:
            for label, index in screens:
                self.external_display_combo.addItem(str(label), int(index))
            clamped_index = max(0, min(int(selected_index), len(screens) - 1))
            self.external_display_combo.setCurrentIndex(clamped_index)
        else:
            self.external_display_combo.addItem("No displays detected", -1)
            self.external_display_combo.setCurrentIndex(0)

        self.external_display_combo.setEnabled(bool(screens))
        self.external_output_button.setEnabled(bool(screens))
        self.external_display_combo.blockSignals(False)

    def set_external_output_active(self, active: bool):
        self.external_output_button.blockSignals(True)
        self.external_output_button.setChecked(bool(active))
        self.external_output_button.setText("Close Projector" if active else "Open Projector")
        self.external_output_button.blockSignals(False)

    def set_external_output_status(self, text: str):
        self.external_output_status.setText(str(text))

    def _selected_object_metadata(self):
        idx = self.object_combo.currentData()
        if not isinstance(idx, int):
            return {}
        if 0 <= idx < len(self._object_metadata):
            return self._object_metadata[idx]
        return {}

    def _selected_object_index(self):
        idx = self.object_combo.currentData()
        return int(idx) if isinstance(idx, int) else -1

    def _normalize_selected_loop_timeline(self, source, stage_count=None, slot_count=None):
        beat_map_source = []
        beat_transition_source = []
        timeline_points_source = []
        if isinstance(source, dict):
            beat_map_source = source.get("beat_map", [])
            beat_transition_source = source.get("beat_transitions", [])
            timeline_points_source = source.get("timeline_points", [])
        elif isinstance(source, (list, tuple)):
            beat_map_source = list(source)

        try:
            normalized_slot_count = max(1, int(slot_count)) if slot_count is not None else max(1, len(list(beat_map_source)) or default_loop_slot_count())
        except Exception:
            normalized_slot_count = default_loop_slot_count()

        beat_map = []
        for value in list(beat_map_source)[:normalized_slot_count]:
            try:
                clean = max(0, int(value))
            except Exception:
                clean = 0
            if stage_count is not None:
                clean = max(0, min(clean, int(stage_count))) if int(stage_count) > 0 else 0
            beat_map.append(clean)
        while len(beat_map) < normalized_slot_count:
            beat_map.append(0)

        beat_transitions = [self._normalize_transition_spec(value) for value in list(beat_transition_source)[:normalized_slot_count]]
        while len(beat_transitions) < normalized_slot_count:
            beat_transitions.append(self._default_transition_spec())

        timeline_points = normalize_loop_timeline_points(
            timeline_points_source,
            normalized_slot_count,
            0 if stage_count is None else int(max(0, stage_count)),
            beat_map=beat_map,
            beat_transitions=beat_transitions,
        )

        return {
            "beat_map": beat_map[:normalized_slot_count],
            "beat_transitions": beat_transitions[:normalized_slot_count],
            "timeline_points": timeline_points,
        }

    def _set_loop_timeline_controls_enabled(self, enabled: bool):
        enabled = bool(enabled)
        for widget in (
            getattr(self, "loop_slot_count", None),
            getattr(self, "photo_timeline_scroll", None),
            getattr(self, "image_set_timing_mode", None),
            getattr(self, "image_set_switch_time", None),
            getattr(self, "image_set_timing_translation", None),
            getattr(self, "image_set_timing_pause", None),
        ):
            if widget is not None:
                widget.setEnabled(enabled)
        for widget in getattr(self, "_timeline_slot_buttons", []):
            widget.setEnabled(enabled)
        for widget in getattr(self, "_timeline_transition_boxes", []):
            widget.setEnabled(enabled)

    def _emit_selected_loop_timeline(self):
        object_index = self._selected_object_index()
        if object_index < 0:
            return
        payload = {
            "beat_map": list(self._selected_loop_timeline.get("beat_map", [])),
            "beat_transitions": [self._normalize_transition_spec(value) for value in list(self._selected_loop_timeline.get("beat_transitions", []))],
        }
        self.selectedLoopTimelineChanged.emit(object_index, payload)

    def _rebuild_loop_timeline_table(self):
        preview_lookup = {int(item["stage_index"]): item for item in list(self._image_stage_preview_items)}
        transition_effects = [
            self._normalize_transition_spec(value).get("effect", "cut")
            for value in list(self._selected_loop_timeline.get("beat_transitions", []))
        ]
        rebuild_photo_timeline(self, preview_lookup, transition_effects)
        self._set_loop_timeline_controls_enabled(bool(self._selected_object_metadata()))

    def _sync_selected_loop_timeline(self):
        meta = self._selected_object_metadata()
        has_object = bool(meta)
        self._set_loop_timeline_controls_enabled(has_object)

        if not has_object:
            self._selected_loop_timeline = self._normalize_selected_loop_timeline({}, 0, default_loop_slot_count())
            self.loop_timeline_info.setText("Loop timeline: select an imported image set to assign pictures to beat points in the loop.")
            self.loop_slot_count.blockSignals(True)
            self.loop_slot_count.setCurrentIndex(max(0, self.loop_slot_count.findData(default_loop_slot_count())))
            self.loop_slot_count.blockSignals(False)
            self._rebuild_loop_timeline_table()
            return

        stage_count = max(0, int(meta.get("stage_count", 0)))
        slot_count = max(1, int(meta.get("slot_count", len(meta.get("beat_map", [])) or default_loop_slot_count())))
        self._selected_loop_timeline = self._normalize_selected_loop_timeline(meta, stage_count=stage_count, slot_count=slot_count)

        self.loop_slot_count.blockSignals(True)
        target_index = max(0, self.loop_slot_count.findData(slot_count))
        self.loop_slot_count.setCurrentIndex(target_index)
        self.loop_slot_count.blockSignals(False)

        self.loop_timeline_info.setText(
            "Loop timeline: drag pictures onto the beat points, click a point to assign the selected picture, and right-click a point to clear it. The last transition returns to Beat 1."
        )
        self._rebuild_loop_timeline_table()

    def _on_loop_slot_count_changed(self):
        meta = self._selected_object_metadata()
        if not meta:
            return
        stage_count = max(0, int(meta.get("stage_count", 0)))
        slot_count = int(self.loop_slot_count.currentData()) if isinstance(self.loop_slot_count.currentData(), int) else default_loop_slot_count()
        self._selected_loop_timeline = self._normalize_selected_loop_timeline(self._selected_loop_timeline, stage_count=stage_count, slot_count=slot_count)
        self._rebuild_loop_timeline_table()
        self._emit_selected_loop_timeline()

    def _on_loop_stage_changed(self, slot: int, value):
        if not (0 <= slot < len(self._selected_loop_timeline.get("beat_transitions", []))):
            return
        self._selected_loop_timeline["beat_map"][slot] = int(value) if isinstance(value, int) else 0
        self._rebuild_loop_timeline_table()
        self._emit_selected_loop_timeline()

    def _set_image_set_matrix_controls_enabled(self, enabled: bool):
        self._image_set_matrix_controls_enabled = bool(enabled)
        for widget in (
            getattr(self, "image_set_selected_preview", None),
            getattr(self, "image_set_selected_label", None),
            getattr(self, "image_set_preview_grid_host", None),
            getattr(self, "image_set_timing_mode", None),
            getattr(self, "image_set_switch_time", None),
            getattr(self, "image_set_timing_translation", None),
            getattr(self, "image_set_timing_pause", None),
        ):
            if widget is not None:
                widget.setEnabled(bool(enabled))
        self._update_image_set_timing_control_state()
        self._set_loop_timeline_controls_enabled(enabled)

    def _update_image_set_timing_control_state(self):
        if (
            getattr(self, "image_set_timing_mode", None) is None
            or getattr(self, "image_set_switch_time", None) is None
            or getattr(self, "image_set_timing_translation", None) is None
        ):
            return
        base_enabled = bool(getattr(self, "_image_set_matrix_controls_enabled", False))
        timing_mode = clean_image_set_timing_mode(self.image_set_timing_mode.currentData())
        self.image_set_switch_time.setEnabled(base_enabled and timing_mode == "manual")
        self.image_set_timing_translation.setEnabled(base_enabled and timing_mode == "average_bpm")

    def _sync_image_set_matrix_controls(self):
        meta = self._selected_object_metadata()
        uses_image_set = meta.get("kind") == "image_variant" and str(meta.get("variant_source_mode", "")) == "image_set"
        self._set_image_set_matrix_controls_enabled(uses_image_set)

        if not uses_image_set:
            self._image_stage_preview_items = []
            self._selected_photo_stage_index = 0
            rebuild_stage_preview_grid(self, [], 0, "", "")
            self.image_set_selected_preview.setPixmap(QPixmap())
            self.image_set_selected_preview.setText("No preview")
            self.image_set_selected_label.setText("Select an image set object")
            self.image_set_matrix_info.setText("Pictures are sorted by filename logic: high-hat = `u,d,h,v`, bass/melody = `w,c,n,m`, kick = `f,s`.")
            self.image_set_switch_time.blockSignals(True)
            self.image_set_switch_time.setValue(int(round(default_image_set_switch_time() * 1000.0)))
            self.image_set_switch_time.blockSignals(False)
            self.image_set_switch_time_value.setText(f"{int(round(default_image_set_switch_time() * 1000.0))} ms")
            self.image_set_timing_mode.blockSignals(True)
            self.image_set_timing_mode.setCurrentIndex(max(0, self.image_set_timing_mode.findData(default_image_set_timing_mode())))
            self.image_set_timing_mode.blockSignals(False)
            self.image_set_timing_translation.blockSignals(True)
            self.image_set_timing_translation.setValue(int(round(default_image_set_timing_translation() * 100.0)))
            self.image_set_timing_translation.blockSignals(False)
            self.image_set_timing_translation_value.setText(f"{int(round(default_image_set_timing_translation() * 100.0))}% of beat")
            self.image_set_timing_pause.blockSignals(True)
            self.image_set_timing_pause.setValue(int(round(default_image_set_timing_pause() * 100.0)))
            self.image_set_timing_pause.blockSignals(False)
            self.image_set_timing_pause_value.setText(f"{int(round(default_image_set_timing_pause() * 100.0))}% hold")
            self._update_image_set_timing_control_state()
            self.image_set_matrix_status.setText("Timeline inactive")
            self._rebuild_loop_timeline_table()
            return

        preview_items = list(meta.get("image_set_preview_items", []))
        live_codes = dict(meta.get("image_set_live_codes", {}))
        active_key = str(meta.get("image_set_live_key", "")).strip()
        target_key = str(meta.get("image_set_target_key", "")).strip()
        switch_time = max(0.0, float(meta.get("image_set_switch_time", default_image_set_switch_time())))
        timing_mode = clean_image_set_timing_mode(meta.get("image_set_timing_mode", default_image_set_timing_mode()))
        timing_translation = max(0.25, min(3.0, float(meta.get("image_set_timing_translation", default_image_set_timing_translation()))))
        timing_pause = max(0.0, min(0.95, float(meta.get("image_set_timing_pause", default_image_set_timing_pause()))))

        self._image_stage_preview_items = preview_items
        if self._selected_photo_stage_index <= 0 and preview_items:
            self._selected_photo_stage_index = int(preview_items[0]["stage_index"])
        rebuild_stage_preview_grid(self, preview_items, self._selected_photo_stage_index, active_key, target_key)
        self._select_photo_stage_preview(self._selected_photo_stage_index, rebuild_grid=False)

        self.image_set_switch_time.blockSignals(True)
        self.image_set_switch_time.setValue(int(round(switch_time * 1000.0)))
        self.image_set_switch_time.blockSignals(False)
        self.image_set_switch_time_value.setText(f"{int(round(switch_time * 1000.0))} ms")

        self.image_set_timing_mode.blockSignals(True)
        self.image_set_timing_mode.setCurrentIndex(max(0, self.image_set_timing_mode.findData(timing_mode)))
        self.image_set_timing_mode.blockSignals(False)
        self.image_set_timing_translation.blockSignals(True)
        self.image_set_timing_translation.setValue(int(round(timing_translation * 100.0)))
        self.image_set_timing_translation.blockSignals(False)
        self.image_set_timing_translation_value.setText(f"{int(round(timing_translation * 100.0))}% of beat")
        self.image_set_timing_pause.blockSignals(True)
        self.image_set_timing_pause.setValue(int(round(timing_pause * 100.0)))
        self.image_set_timing_pause.blockSignals(False)
        self.image_set_timing_pause_value.setText(f"{int(round(timing_pause * 100.0))}% hold")
        self._update_image_set_timing_control_state()

        live_code = (
            f"{live_codes.get('texture', IMAGE_SET_TEXTURE_ORDER[0])}"
            f"{live_codes.get('atmosphere', IMAGE_SET_ATMOSPHERE_ORDER[0])}"
            f"{live_codes.get('rhythm', IMAGE_SET_RHYTHM_ORDER[0])}"
        )
        self.image_set_matrix_info.setText(
            "Pictures follow the filename logic. First letter = high-hat (`u,d,h,v`), second = bass/melody (`w,c,n,m`), third = kick/snare (`f,s`)."
        )
        timing_text = (
            f"timing bpm x{timing_translation:.2f}, pause {int(round(timing_pause * 100.0))}%"
            if timing_mode == "average_bpm"
            else f"timing manual {int(round(switch_time * 1000.0))} ms, pause {int(round(timing_pause * 100.0))}%"
        )
        if target_key and target_key != active_key:
            self.image_set_matrix_status.setText(f"Live code {live_code} | active {active_key} | next {target_key} | {timing_text}")
        else:
            self.image_set_matrix_status.setText(f"Live code {live_code} | active {active_key or '-'} | {timing_text}")

        self._rebuild_loop_timeline_table()

    def _select_photo_stage_preview(self, stage_index: int, rebuild_grid: bool = True):
        self._selected_photo_stage_index = max(0, int(stage_index))
        lookup = {int(item["stage_index"]): item for item in list(self._image_stage_preview_items)}
        item = lookup.get(self._selected_photo_stage_index)
        if rebuild_grid:
            meta = self._selected_object_metadata()
            rebuild_stage_preview_grid(
                self,
                self._image_stage_preview_items,
                self._selected_photo_stage_index,
                str(meta.get("image_set_live_key", "")).strip(),
                str(meta.get("image_set_target_key", "")).strip(),
            )
        if item is None:
            self.image_set_selected_preview.setPixmap(QPixmap())
            self.image_set_selected_preview.setText("No preview")
            self.image_set_selected_label.setText("Select a picture from the set")
            return

        pixmap = QPixmap.fromImage(item["preview"])
        scaled = pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_set_selected_preview.setPixmap(scaled)
        self.image_set_selected_preview.setText("")
        self.image_set_selected_label.setText(str(item.get("tooltip", item["label"])))

    def _assign_photo_stage_to_slot(self, slot: int, stage_index: int):
        self._on_loop_stage_changed(slot, stage_index)

    def _assign_selected_photo_stage_to_slot(self, slot: int):
        if self._selected_photo_stage_index > 0:
            self._on_loop_stage_changed(slot, self._selected_photo_stage_index)

    def _clear_photo_timeline_slot(self, slot: int):
        self._on_loop_stage_changed(slot, 0)

    def _set_photo_timeline_transition(self, slot: int, effect):
        if not (0 <= slot < len(self._selected_loop_timeline.get("beat_transitions", []))):
            return
        self._selected_loop_timeline["beat_transitions"][slot] = default_transition_spec(
            effect=effect,
            easing="linear" if clean_beat_transition_effect(effect) == "cut" else "ease_in_out",
        )
        self._emit_selected_loop_timeline()

    def _make_preset_button(self, color: QColor):
        btn = QPushButton()
        btn.setFixedSize(24, 24)
        btn.setToolTip(color.name(QColor.HexRgb).upper())
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {color.name()}; border: 1px solid #d2c8b8; border-radius: 12px; }}"
        )
        btn.clicked.connect(lambda _=False, c=QColor(color): self._apply_color(c))
        return btn

    def _apply_color(self, color: QColor):
        if not color.isValid():
            return
        self._sync_object_color_ui(color)
        self.brushColorChanged.emit(QColor(self._color))

    def _load_saved_presets(self):
        if not self.PRESET_FILE.exists():
            return []
        try:
            data = json.loads(self.PRESET_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(data, list):
            return []

        unique = []
        for item in data:
            c = QColor(str(item))
            if not c.isValid():
                continue
            hex_color = c.name(QColor.HexRgb).upper()
            if hex_color not in unique:
                unique.append(hex_color)
        return unique

    def _persist_saved_presets(self):
        try:
            self.PRESET_FILE.write_text(json.dumps(self._saved_preset_hex, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _save_current_preset(self):
        hex_color = self._color.name(QColor.HexRgb).upper()
        if hex_color in self._saved_preset_hex:
            return
        self._saved_preset_hex.append(hex_color)
        self._persist_saved_presets()

    def _load_preset_popup(self):
        saved = [QColor(v) for v in self._saved_preset_hex]
        dialog = PresetPickerDialog(self._main_presets, saved, self)
        anchor = self.load_preset_button.mapToGlobal(self.load_preset_button.rect().bottomLeft())
        dialog.move(anchor)
        if dialog.exec() == QDialog.Accepted:
            self._apply_color(dialog.selected_color())

    def _update_change_stage_info(self):
        idx = self.object_combo.currentData()
        stage_counter = getattr(self, "state_counter_label", None)
        if not isinstance(idx, int) or not (0 <= idx < len(self._object_metadata)):
            self.change_stage_info.setText("No image set selected")
            if stage_counter is not None:
                stage_counter.setText("0 states")
            return
        meta = self._object_metadata[idx]
        stage_count = int(meta.get("stage_count", 0))
        if stage_counter is not None:
            stage_counter.setText(f"{stage_count} state" if stage_count == 1 else f"{stage_count} states")
        if str(meta.get("kind", "")) == "image_variant" and str(meta.get("variant_source_mode", "")) == "image_set":
            slot_count = int(meta.get("slot_count", default_loop_slot_count()))
            self.change_stage_info.setText(f"Image set selected | {stage_count} pictures | {slot_count} beat places")
            return
        self.change_stage_info.setText("Selected object is not an image set")

    def _default_transition_spec(self):
        return default_transition_spec()

    def _normalize_transition_spec(self, value):
        return normalize_transition_spec(value)

    def eventFilter(self, obj, event):
        if isinstance(obj, (QComboBox, QSlider)) and event.type() == QEvent.Wheel:
            return True
        return False

class LegacyCanvasWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_TabletTracking, True)
        self.setMouseTracking(True)

        self.img = QImage(max(1, self.width()), max(1, self.height()), QImage.Format_ARGB32_Premultiplied)
        self.img.fill(Qt.black)

        self.base_size = 20
        self.brightness = 100
        self.opacity = 255
        self.spray = 0
        self.tool = "brush"
        self.brush_style = "circle"
        self.polygon_sides = 3
        self.shape_filled = False
        self.color = QColor(255, 255, 255)
        self.drawing = False
        self.last_pos = None
        self.shape_start = None
        self.shape_current = None
        self.shape_size = 1
        self.active_input = None

    def set_base_size(self, v: int):
        self.base_size = v

    def set_opacity_percent(self, v: int):
        v = max(0, min(100, int(v)))
        self.opacity = int(round(255 * (v / 100.0)))

    def set_brightness_percent(self, v: int):
        self.brightness = max(0, min(200, int(v)))

    def set_spray(self, v: int):
        self.spray = max(0, min(100, int(v)))

    def set_brush_style(self, style: str):
        if is_development_brush_style(style):
            self.brush_style = style

    def set_color(self, color: QColor):
        if color.isValid():
            self.color = QColor(color)

    def set_shape_filled(self, filled: bool):
        self.shape_filled = bool(filled)

    def set_tool(self, mode: str):
        if mode not in ("brush", "line", "circle", "rectangle", "polygon"):
            return
        self._end_stroke(commit_shape=False)
        self.tool = mode
        self.update()

    def set_polygon_sides(self, n: int):
        if is_development_polygon_side(n):
            self.polygon_sides = n

    def apply_canvas_transform(self, rotation_deg: float, tx: float, ty: float, scale: float):
        scale = max(0.01, float(scale))
        transformed = QImage(self.img.size(), QImage.Format_ARGB32_Premultiplied)
        transformed.fill(Qt.black)

        p = QPainter(transformed)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        cx = self.img.width() / 2.0
        cy = self.img.height() / 2.0
        p.translate(cx + float(tx), cy + float(ty))
        p.rotate(float(rotation_deg))
        p.scale(scale, scale)
        p.translate(-cx, -cy)
        p.drawImage(0, 0, self.img)
        p.end()

        self.img = transformed
        self.update()

    def _stroke_size_from_pressure(self, pressure: float):
        return development_stroke_size_from_pressure(self.base_size, pressure)

    def _begin_stroke(self, pos: QPointF, size: int):
        self.drawing = True
        if self.tool == "brush":
            self.last_pos = QPointF(pos)
            self._draw_point(self.last_pos, size)
        else:
            self.shape_start = QPointF(pos)
            self.shape_current = QPointF(pos)
            self.shape_size = size

    def _extend_stroke(self, pos: QPointF, size: int):
        pos = QPointF(pos)
        if self.tool == "brush":
            if self.last_pos is None:
                self._draw_point(pos, size)
            else:
                self._draw_line(self.last_pos, pos, size)
            self.last_pos = pos
        else:
            self.shape_current = pos

    def _end_stroke(self, commit_shape: bool = True):
        if commit_shape and self.tool != "brush" and self.shape_start is not None and self.shape_current is not None:
            self._draw_shape(self.shape_start, self.shape_current, self.shape_size)

        self.drawing = False
        self.last_pos = None
        self.shape_start = None
        self.shape_current = None
        self.shape_size = 1
        self.active_input = None

    def _resize_canvas(self, w: int, h: int):
        w = max(1, w)
        h = max(1, h)
        if self.img.width() == w and self.img.height() == h:
            return

        old = self.img
        self.img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        self.img.fill(Qt.black)

        p = QPainter(self.img)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.drawImage(self.img.rect(), old, old.rect())
        p.end()

    def resizeEvent(self, e):
        self._resize_canvas(e.size().width(), e.size().height())
        super().resizeEvent(e)

    def tabletEvent(self, e: QTabletEvent):
        size = self._stroke_size_from_pressure(float(e.pressure()))

        if e.type() == QTabletEvent.TabletPress:
            self.active_input = "tablet"
            self._begin_stroke(QPointF(e.position()), size)
            e.accept()

        elif e.type() == QTabletEvent.TabletMove and self.drawing and self.active_input == "tablet":
            self._extend_stroke(QPointF(e.position()), size)
            e.accept()

        elif e.type() == QTabletEvent.TabletRelease and self.active_input == "tablet":
            self._end_stroke()
            e.accept()
        else:
            e.ignore()
            return

        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.active_input in (None, "mouse"):
            self.active_input = "mouse"
            self._begin_stroke(QPointF(e.position()), self.base_size)
            self.update()
            e.accept()
            return
        e.ignore()

    def mouseMoveEvent(self, e):
        if self.drawing and self.active_input == "mouse" and (e.buttons() & Qt.LeftButton):
            self._extend_stroke(QPointF(e.position()), self.base_size)
            self.update()
            e.accept()
            return
        e.ignore()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.active_input == "mouse":
            self._end_stroke()
            self.update()
            e.accept()
            return
        e.ignore()

    def _painter(self):
        p = QPainter(self.img)
        p.setRenderHint(QPainter.Antialiasing, True)
        return p

    def _brush_color(self, spray: bool = False):
        return development_draw_color(
            self.color,
            self.brightness,
            self.opacity,
            spray_alpha_scale=0.2 if spray else 1.0,
        )

    def _spray_factor(self):
        return development_spray_factor(self.spray)

    def _spray_spread(self, size: int):
        return development_spray_spread(size, self.spray)

    def _spray_step(self, size: int):
        return development_spray_step(size, self.spray)

    def _draw_spray_stamp(self, p: QPainter, center: QPointF, size: int):
        development_draw_spray_stamp(p, center, size, self._brush_color(), self.spray)

    def _draw_spray_line(self, p: QPainter, a: QPointF, b: QPointF, size: int):
        development_draw_spray_line(p, a, b, size, self._brush_color(), self.spray)

    def _draw_brush_stamp(self, p: QPainter, pos: QPointF, size: int):
        development_draw_brush_stamp(p, pos, size, self._brush_color(), self.brush_style)

    def _draw_brush_path(self, p: QPainter, a: QPointF, b: QPointF, size: int):
        development_draw_brush_path(p, a, b, size, self._brush_color(), self.brush_style)

    def _draw_point(self, pos: QPointF, size: int):
        p = self._painter()
        if self.spray > 0:
            self._draw_spray_stamp(p, pos, size)
        else:
            self._draw_brush_stamp(p, pos, size)
        p.end()

    def _draw_line(self, a: QPointF, b: QPointF, size: int):
        p = self._painter()
        if self.spray > 0:
            self._draw_spray_line(p, a, b, size)
        else:
            self._draw_brush_path(p, a, b, size)
        p.end()

    def _shape_pen(self, size: int, preview: bool = False):
        return development_shape_pen(self._brush_color(), size, preview=preview)

    def _regular_polygon(self, center: QPointF, vertex: QPointF):
        return development_regular_polygon(center, vertex, self.polygon_sides)

    def _draw_shape_geometry(self, p: QPainter, a: QPointF, b: QPointF):
        development_draw_shape_geometry(p, self.tool, a, b, self.polygon_sides)

    def _shape_segments(self, a: QPointF, b: QPointF, size: int):
        return development_shape_segments(self.tool, a, b, size, self.spray, self.polygon_sides)

    def _draw_shape_spray(self, p: QPainter, a: QPointF, b: QPointF, size: int):
        development_draw_shape_spray(p, self.tool, a, b, size, self._brush_color(), self.spray, self.polygon_sides)

    def _draw_shape(self, a: QPointF, b: QPointF, size: int):
        p = self._painter()
        can_fill = self.shape_filled and self.tool in ("circle", "rectangle", "polygon")
        if self.spray > 0:
            if can_fill:
                p.setPen(Qt.NoPen)
                p.setBrush(self._brush_color())
                self._draw_shape_geometry(p, a, b)
            self._draw_shape_spray(p, a, b, size)
        else:
            p.setPen(self._shape_pen(size))
            if can_fill:
                p.setBrush(self._brush_color())
            else:
                p.setBrush(Qt.NoBrush)
            self._draw_shape_geometry(p, a, b)
        p.end()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.drawImage(0, 0, self.img)
        if self.tool != "brush" and self.drawing and self.shape_start is not None and self.shape_current is not None:
            can_fill = self.shape_filled and self.tool in ("circle", "rectangle", "polygon")
            p.setPen(self._shape_pen(self.shape_size, preview=True))
            if can_fill:
                preview_fill = QColor(self._brush_color())
                preview_fill.setAlpha(max(20, int(preview_fill.alpha() * 0.35)))
                p.setBrush(preview_fill)
            else:
                p.setBrush(Qt.NoBrush)
            self._draw_shape_geometry(p, self.shape_start, self.shape_current)


class CanvasWidget(QWidget):
    objectsChanged = Signal(list, int, list)
    backgroundsChanged = Signal(list, int, list)
    mutationCommitted = Signal(str)
    selectedTextEdited = Signal()
    BEAT_TRANSITION_EFFECTS = BEAT_TRANSITION_EFFECTS
    BEAT_TRANSITION_EASINGS = BEAT_TRANSITION_EASINGS

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_TabletTracking, True)
        self.setMouseTracking(True)

        self.base_size = 20
        self.brightness = 100
        self.opacity = 255
        self.spray = 0
        self.tool = "brush"
        self.brush_style = "circle"
        self.polygon_sides = 3
        self.shape_filled = False
        self.text_value = "Text"
        self.text_size = 48
        self.color = QColor(255, 255, 255)

        self.objects = []
        self.backgrounds = []
        self.background_mix = 0.0
        self.selected_index = -1
        self.selected_background_index = -1

        self.beat_reactive = False
        self._beat_level = 0.0
        self._beat_pulse = 0.0
        self._audio_low = 0.0
        self._audio_mid = 0.0
        self._audio_high = 0.0
        self._image_set_texture_code = IMAGE_SET_TEXTURE_ORDER[0]
        self._image_set_atmosphere_code = IMAGE_SET_ATMOSPHERE_ORDER[0]
        self._image_set_rhythm_code = IMAGE_SET_RHYTHM_ORDER[0]
        self._image_set_rhythm_phase = 0
        self._beat_visual_timer = QTimer(self)
        self._beat_visual_timer.setInterval(16)
        self._beat_visual_timer.timeout.connect(self._tick_beat_visual)
        self._beat_visual_timer.start()

        self._loop_timer = QTimer(self)
        self._loop_timer.setInterval(2000)  # Check every 2 seconds
        self._loop_timer.timeout.connect(self._check_loop_advance)
        self._loop_timer.start()

        self.drawing = False
        self.shape_start = None
        self.shape_current = None
        self.shape_preview_style = None
        self.current_stroke = None
        self.active_input = None
        self._select_gesture = None
        self.select_transform_mode = "translate"
        self._reflect_anchor_world = None
        self._select_hover_pos = None
        self._rotation_pivot_ready = False
        self._scale_pivot_ready = False
        self._change_preview = None
        self._background_change_preview = None
        self._change_preview_enabled = True
        self._background_change_preview_enabled = True
        self._change_target_kind = "object"
        self._change_color = QColor(0, 0, 0)
        self._change_visibility_mode = "current"
        self._performance_mode = False
        self._beat_slot = -1
        self._beat_transition_from_slot = -1
        self._beat_transition_to_slot = -1
        self._beat_transition_started_at = 0.0
        self._beat_transition_duration = 0.0
        self._beat_transition_interval = 0.25
        self._last_beat_time = 0.0
        self._last_beat_interval = 0.25
        self._average_beat_interval = 0.0
        self._logged_first_paint = False
        self._render_background_cover_size = None
        self._delete_fade = None
        self._delete_fade_duration = 0.18
        self._delete_fade_timer = QTimer(self)
        self._delete_fade_timer.setInterval(16)
        self._delete_fade_timer.timeout.connect(self._tick_delete_fade)

    def _clone_history_value(self, value):
        if isinstance(value, dict):
            return {str(key): self._clone_history_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._clone_history_value(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self._clone_history_value(item) for item in value)
        if isinstance(value, QColor):
            return QColor(value)
        if isinstance(value, QTransform):
            return QTransform(value)
        if isinstance(value, QPointF):
            return QPointF(value)
        if isinstance(value, QRectF):
            return QRectF(value)
        if isinstance(value, QImage):
            return QImage(value)
        return value

    def export_history_state(self):
        return {
            "objects": self._clone_history_value(self.objects),
            "backgrounds": self._clone_history_value(self.backgrounds),
            "selected_index": int(self.selected_index),
            "selected_background_index": int(self.selected_background_index),
            "change_preview": self._clone_history_value(self._change_preview),
            "background_change_preview": self._clone_history_value(self._background_change_preview),
            "change_preview_enabled": bool(self._change_preview_enabled),
            "background_change_preview_enabled": bool(self._background_change_preview_enabled),
            "change_target_kind": str(self._change_target_kind),
        }

    def import_history_state(self, state):
        payload = state if isinstance(state, dict) else {}
        self._cancel_delete_fade(update=False)
        self.objects = self._clone_history_value(payload.get("objects", []))
        self.backgrounds = self._clone_history_value(payload.get("backgrounds", []))
        self.selected_index = int(payload.get("selected_index", -1))
        self.selected_background_index = int(payload.get("selected_background_index", -1))
        self._change_preview = self._clone_history_value(payload.get("change_preview"))
        self._background_change_preview = self._clone_history_value(payload.get("background_change_preview"))
        self._change_preview_enabled = True
        self._background_change_preview_enabled = True
        self._change_target_kind = str(payload.get("change_target_kind", "object"))
        self._cancel_select_gesture()
        self._clear_select_mode_state()
        self.update()
        self._emit_objects_changed()
        self._emit_backgrounds_changed()

    def resizeEvent(self, e):
        old_size = e.oldSize()
        new_size = e.size()
        if old_size.isValid() and new_size.isValid():
            self._refit_backgrounds_for_canvas_size(old_size, new_size)
        super().resizeEvent(e)

    def set_base_size(self, v: int):
        self.base_size = v

    def set_opacity_percent(self, v: int):
        v = max(0, min(100, int(v)))
        self.opacity = int(round(255 * (v / 100.0)))

    def set_brightness_percent(self, v: int):
        self.brightness = max(0, min(200, int(v)))

    def set_spray(self, v: int):
        self.spray = max(0, min(100, int(v)))

    def set_brush_style(self, style: str):
        if is_development_brush_style(style):
            self.brush_style = style

    def set_color(self, color: QColor):
        if color.isValid():
            self.color = QColor(color)
            if not self._change_color.isValid():
                self._change_color = QColor(color)

    def set_shape_filled(self, filled: bool):
        self.shape_filled = bool(filled)

    def set_text_value(self, text: str):
        text = str(text)
        selected_text_changed = False
        if 0 <= self.selected_index < len(self.objects):
            obj = self.objects[self.selected_index]
            if obj.get("kind") == "text" and obj.get("text", "") != text:
                obj["text"] = text
                selected_text_changed = True

        if text == self.text_value and not selected_text_changed:
            return

        self.text_value = text
        if selected_text_changed:
            self.update()
            self._emit_objects_changed()
            self.selectedTextEdited.emit()

    def set_text_size(self, size: int):
        self.text_size = max(8, int(size))

    def set_beat_reactive(self, enabled: bool):
        self.beat_reactive = bool(enabled)
        if not self.beat_reactive:
            self._beat_level = 0.0
            self._beat_pulse = 0.0
            self._audio_low = 0.0
            self._audio_mid = 0.0
            self._audio_high = 0.0
            self._image_set_texture_code = IMAGE_SET_TEXTURE_ORDER[0]
            self._image_set_atmosphere_code = IMAGE_SET_ATMOSPHERE_ORDER[0]
            self._image_set_rhythm_code = IMAGE_SET_RHYTHM_ORDER[0]
            self._image_set_rhythm_phase = 0
            self._beat_slot = -1
            self._clear_beat_transition()
            self._last_beat_time = 0.0
            self._average_beat_interval = 0.0
            for obj in self.objects:
                if str(obj.get("variant_source_mode", "generated")) == "image_set":
                    obj["_audio_lane_transition_from_key"] = ""
                    obj["_audio_lane_transition_to_key"] = ""
                    obj["_audio_lane_transition_started_at"] = 0.0
                    obj["_audio_lane_transition_duration"] = 0.0
                    obj["_audio_lane_transition_hold_until"] = 0.0
                    obj["_audio_lane_live_key"] = str(obj.get("variant_key", ""))
        self.update()

    def on_audio_level(self, level: float):
        if not self.beat_reactive:
            return
        level = max(0.0, min(1.0, float(level)))
        self._beat_level = (0.8 * self._beat_level) + (0.2 * level)
        self.update()

    def on_audio_bands(self, low: float, mid: float, high: float):
        if not self.beat_reactive:
            return
        low = max(0.0, min(1.0, float(low)))
        mid = max(0.0, min(1.0, float(mid)))
        high = max(0.0, min(1.0, float(high)))
        self._audio_low = (0.72 * self._audio_low) + (0.28 * low)
        self._audio_mid = (0.72 * self._audio_mid) + (0.28 * mid)
        self._audio_high = (0.72 * self._audio_high) + (0.28 * high)
        self._update_image_set_audio_axes(low, mid, high)
        self.update()

    def on_beat(self, strength: float):
        if not self.beat_reactive:
            return
        now = time.monotonic()
        self._last_beat_time = now
        previous_slot = self._beat_slot
        next_slot = self._beat_slot + 1
        interval = self._last_beat_interval
        if self._last_beat_time > 0.0:
            interval = max(0.05, now - self._last_beat_time)
            self._last_beat_interval = interval
            if self._average_beat_interval <= 1e-6:
                self._average_beat_interval = interval
            else:
                self._average_beat_interval = (0.82 * self._average_beat_interval) + (0.18 * interval)
        self._beat_pulse = max(self._beat_pulse, max(0.0, min(1.0, float(strength))))
        self._image_set_rhythm_phase = 1 - int(self._image_set_rhythm_phase)
        self._image_set_rhythm_code = IMAGE_SET_RHYTHM_ORDER[self._image_set_rhythm_phase % len(IMAGE_SET_RHYTHM_ORDER)]
        self._update_image_set_audio_axes()
        self._advance_image_set_audio_variants_on_beat(now)
        self._beat_slot = next_slot
        duration = self._beat_transition_duration_for_slot(previous_slot, interval)
        if previous_slot >= 0 and duration > 1e-6:
            self._beat_transition_from_slot = previous_slot
            self._beat_transition_to_slot = next_slot
            self._beat_transition_started_at = now
            self._beat_transition_duration = duration
            self._beat_transition_interval = interval
        else:
            self._clear_beat_transition()
        self._last_beat_time = now
        self.update()

    def _tick_beat_visual(self):
        prev_pulse = self._beat_pulse
        prev_level = self._beat_level
        had_transition = self._beat_transition_from_slot >= 0 and self._beat_transition_to_slot >= 0
        self._beat_pulse *= 0.88
        self._beat_level *= 0.96
        self._audio_low *= 0.985
        self._audio_mid *= 0.99
        self._audio_high *= 0.992
        self._update_image_set_audio_axes()
        self._beat_transition_progress()
        if (
            had_transition
            or abs(self._beat_pulse - prev_pulse) > 1e-3
            or abs(self._beat_level - prev_level) > 1e-3
            or self._audio_low > 1e-3
            or self._audio_mid > 1e-3
            or self._audio_high > 1e-3
        ):
            self.update()

    def _check_loop_advance(self):
        if self._performance_mode and time.time() - self._last_beat_time > 2.0:
            # Advance to next slot if no beat for 2 seconds
            slot_count = len(self.loop_stage_map) if hasattr(self, 'loop_stage_map') else 4
            self._beat_slot = (self._beat_slot + 1) % max(1, slot_count)
            self._trigger_beat_transition()

    def _background_color(self):
        if not self.beat_reactive:
            return QColor(0, 0, 0)

        pulse = max(0.0, min(1.0, self._beat_pulse))
        level = max(0.0, min(1.0, self._beat_level))
        low = max(0.0, min(1.0, self._audio_low))
        mid = max(0.0, min(1.0, self._audio_mid))
        high = max(0.0, min(1.0, self._audio_high))
        lift = int((70.0 * pulse) + (22.0 * level) + (28.0 * low))
        red = min(255, 8 + lift + int((95.0 * mid) + (35.0 * low)))
        green = min(255, 6 + int((42.0 * mid) + (18.0 * pulse)))
        blue = min(255, 18 + lift + int((88.0 * high) + (24.0 * mid)))
        return QColor(red, green, blue)

    def _lane_code_for_value(self, value: float, order, current_code: str, hysteresis: float = 0.06):
        if not order:
            return ""
        clamped = max(0.0, min(1.0, float(value)))
        order_list = list(order)
        if current_code in order_list:
            index = order_list.index(current_code)
        else:
            index = 0
        bucket_count = len(order_list)
        while index < (bucket_count - 1):
            upper_boundary = float(index + 1) / float(bucket_count)
            if clamped >= (upper_boundary + hysteresis):
                index += 1
                continue
            break
        while index > 0:
            lower_boundary = float(index) / float(bucket_count)
            if clamped <= (lower_boundary - hysteresis):
                index -= 1
                continue
            break
        return order_list[index]

    def _update_image_set_audio_axes(self, low_incoming: float | None = None, mid_incoming: float | None = None, high_incoming: float | None = None):
        low_driver = max(
            max(0.0, min(1.0, self._audio_low)),
            max(0.0, min(1.0, float(low_incoming))) if low_incoming is not None else 0.0,
        )
        mid_driver = max(
            max(0.0, min(1.0, self._audio_mid)),
            max(0.0, min(1.0, float(mid_incoming))) if mid_incoming is not None else 0.0,
        )
        high_driver = max(
            max(0.0, min(1.0, self._audio_high)),
            max(0.0, min(1.0, float(high_incoming))) if high_incoming is not None else 0.0,
        )
        atmosphere_driver = max(0.0, min(1.0, (0.42 * low_driver) + (0.58 * mid_driver)))
        self._image_set_texture_code = self._lane_code_for_value(
            high_driver,
            IMAGE_SET_TEXTURE_ORDER,
            self._image_set_texture_code,
        )
        self._image_set_atmosphere_code = self._lane_code_for_value(
            atmosphere_driver,
            IMAGE_SET_ATMOSPHERE_ORDER,
            self._image_set_atmosphere_code,
        )

    def _image_set_stage_entries(self, obj):
        entries = []
        stage_labels = list(obj.get("variant_stage_labels", []))
        for index, label in enumerate(stage_labels):
            axes = parse_image_set_stage_axes(label)
            if axes is None:
                continue
            snapshot = self._object_stage_snapshot(obj, index + 1)
            if snapshot is None:
                continue
            entry = dict(axes)
            entry["key"] = str(snapshot.get("variant_key", "") or label)
            entry["label"] = str(label)
            entries.append(entry)
        return entries

    def _object_uses_image_set_audio_lanes(self, obj) -> bool:
        return bool(obj.get("image_set_audio_lane_mode", False)) and str(obj.get("variant_source_mode", "generated")) == "image_set" and bool(self._image_set_stage_entries(obj))

    def _image_set_transition_spec(self):
        return default_transition_spec(effect="fade", easing="ease_in_out", duration_scale=0.0)

    def _image_set_variant_cost(self, entry, desired_texture: str, desired_atmosphere: str, desired_rhythm: str):
        cost = 0.0
        cost += abs(IMAGE_SET_TEXTURE_ORDER.index(entry["texture"]) - IMAGE_SET_TEXTURE_ORDER.index(desired_texture)) * 1.0
        cost += abs(IMAGE_SET_ATMOSPHERE_ORDER.index(entry["atmosphere"]) - IMAGE_SET_ATMOSPHERE_ORDER.index(desired_atmosphere)) * 1.0
        cost += abs(IMAGE_SET_RHYTHM_ORDER.index(entry["rhythm"]) - IMAGE_SET_RHYTHM_ORDER.index(desired_rhythm)) * 1.0
        return cost

    def _resolve_image_set_variant_key(self, obj):
        entries = self._image_set_stage_entries(obj)
        if not entries:
            return str(obj.get("variant_key", ""))

        desired_texture = self._image_set_texture_code
        desired_atmosphere = self._image_set_atmosphere_code
        desired_rhythm = self._image_set_rhythm_code
        current_key = str(obj.get("_audio_lane_live_key", obj.get("variant_key", "")))
        best_entry = None
        best_cost = None

        for entry in entries:
            cost = self._image_set_variant_cost(entry, desired_texture, desired_atmosphere, desired_rhythm)
            if entry["key"] == current_key:
                cost -= 0.15
            if best_cost is None or cost < best_cost:
                best_cost = cost
                best_entry = entry

        return str(best_entry["key"]) if best_entry is not None else str(obj.get("variant_key", ""))

    def _object_snapshot_for_image_set_key(self, obj, variant_key: str):
        target_key = str(variant_key or "").strip()
        if not target_key:
            return self._object_committed_snapshot(obj)

        stages = obj.get("stages", [])
        for stage_index, stage in enumerate(stages, start=1):
            stage_key = str(stage.get("variant_key", "") or stage.get("stage_label", "")).strip()
            if stage_key == target_key:
                snapshot = self._object_stage_snapshot(obj, stage_index)
                if snapshot is not None:
                    return snapshot

        snapshot = self._object_committed_snapshot(obj)
        snapshot["variant_key"] = target_key
        snapshot["stage_label"] = target_key
        return snapshot

    def _image_set_average_beat_interval(self):
        try:
            average_interval = float(self._average_beat_interval)
        except Exception:
            average_interval = 0.0
        if average_interval > 1e-6:
            return average_interval
        return 0.0

    def _image_set_timing_mode(self, obj):
        return clean_image_set_timing_mode(obj.get("image_set_timing_mode", default_image_set_timing_mode()))

    def _image_set_timing_translation(self, obj):
        try:
            translation = float(obj.get("image_set_timing_translation", default_image_set_timing_translation()))
        except Exception:
            translation = default_image_set_timing_translation()
        return max(0.25, min(3.0, translation))

    def _image_set_timing_pause(self, obj):
        try:
            pause = float(obj.get("image_set_timing_pause", default_image_set_timing_pause()))
        except Exception:
            pause = default_image_set_timing_pause()
        return max(0.0, min(0.95, pause))

    def _resolved_image_set_timing(self, obj):
        timing_mode = self._image_set_timing_mode(obj)
        try:
            manual_window = max(0.0, min(1.5, float(obj.get("image_set_switch_time", default_image_set_switch_time()))))
        except Exception:
            manual_window = default_image_set_switch_time()

        translation = self._image_set_timing_translation(obj)
        pause_ratio = self._image_set_timing_pause(obj)
        average_interval = self._image_set_average_beat_interval()

        if timing_mode == "average_bpm" and average_interval > 1e-6:
            total_window = max(0.0, min(4.0, average_interval * translation))
            resolved_mode = "average_bpm"
        else:
            total_window = manual_window
            resolved_mode = "manual_fallback" if timing_mode == "average_bpm" else "manual"

        pause_duration = max(0.0, min(total_window, total_window * pause_ratio))
        transition_duration = max(0.0, total_window - pause_duration)
        bpm = (60.0 / average_interval) if average_interval > 1e-6 else 0.0
        return {
            "requested_mode": timing_mode,
            "resolved_mode": resolved_mode,
            "bpm": bpm,
            "average_interval": average_interval,
            "window": total_window,
            "pause": pause_duration,
            "duration": transition_duration,
            "translation": translation,
            "pause_ratio": pause_ratio,
            "manual_window": manual_window,
        }

    def _image_set_transition_progress(self, obj):
        from_key = str(obj.get("_audio_lane_transition_from_key", "")).strip()
        to_key = str(obj.get("_audio_lane_transition_to_key", "")).strip()
        if not from_key or not to_key:
            return None

        hold_until = max(0.0, float(obj.get("_audio_lane_transition_hold_until", 0.0)))
        now = time.monotonic()
        if now < hold_until:
            return 0.0

        try:
            duration = max(0.0, float(obj.get("_audio_lane_transition_duration", 0.0)))
        except Exception:
            duration = 0.0
        if duration <= 1e-6:
            obj["_audio_lane_transition_from_key"] = ""
            obj["_audio_lane_transition_to_key"] = ""
            obj["_audio_lane_transition_started_at"] = 0.0
            obj["_audio_lane_transition_duration"] = 0.0
            obj["_audio_lane_transition_hold_until"] = 0.0
            obj["_audio_lane_live_key"] = to_key
            obj["variant_key"] = to_key
            return None

        elapsed = max(0.0, now - max(hold_until, float(obj.get("_audio_lane_transition_started_at", 0.0))))
        progress = max(0.0, min(1.0, elapsed / duration))
        if progress >= 1.0:
            obj["_audio_lane_transition_from_key"] = ""
            obj["_audio_lane_transition_to_key"] = ""
            obj["_audio_lane_transition_started_at"] = 0.0
            obj["_audio_lane_transition_duration"] = 0.0
            obj["_audio_lane_transition_hold_until"] = 0.0
            obj["_audio_lane_live_key"] = to_key
            obj["variant_key"] = to_key
            return None
        return self._ease_beat_transition("ease_in_out", progress)

    def _current_image_set_audio_variant(self, obj):
        current_key = str(obj.get("_audio_lane_live_key", obj.get("variant_key", ""))).strip()
        if not current_key:
            current_key = str(obj.get("variant_key", "")).strip()
        if not current_key:
            stage_labels = list(obj.get("variant_stage_labels", []))
            current_key = str(stage_labels[0]) if stage_labels else ""
        if current_key:
            obj["_audio_lane_live_key"] = current_key
            obj["variant_key"] = current_key
        return current_key

    def _queue_image_set_audio_variant(self, obj, desired_key: str, started_at: float | None = None):
        desired_key = str(desired_key or "").strip()
        if not desired_key:
            return self._current_image_set_audio_variant(obj)

        current_key = self._current_image_set_audio_variant(obj)
        active_to_key = str(obj.get("_audio_lane_transition_to_key", "")).strip()
        if desired_key == current_key and not active_to_key:
            return current_key
        if desired_key == active_to_key:
            return desired_key

        if started_at is None:
            started_at = time.monotonic()
        obj["_audio_lane_transition_from_key"] = current_key
        obj["_audio_lane_transition_to_key"] = desired_key
        timing = self._resolved_image_set_timing(obj)
        hold_until = float(started_at) + float(timing["pause"])
        obj["_audio_lane_transition_started_at"] = hold_until
        obj["_audio_lane_transition_hold_until"] = hold_until
        obj["_audio_lane_transition_duration"] = float(timing["duration"])
        obj["_audio_lane_live_key"] = desired_key
        obj["variant_key"] = desired_key
        return desired_key

    def _advance_image_set_audio_variants_on_beat(self, started_at: float | None = None):
        for obj in self.objects:
            if not self._object_uses_image_set_audio_lanes(obj):
                continue
            desired_key = self._resolve_image_set_variant_key(obj)
            self._queue_image_set_audio_variant(obj, desired_key, started_at=started_at)

    def _ensure_image_set_audio_variant(self, obj):
        return self._current_image_set_audio_variant(obj)

    def set_tool(self, mode: str):
        if mode not in ("brush", "line", "circle", "rectangle", "polygon", "text", "select", "change", "beat"):
            return
        if self._performance_mode and mode in ("brush", "line", "circle", "rectangle", "polygon", "text", "change"):
            mode = "select"
        self._cancel_select_gesture()
        self._clear_select_mode_state()
        self._end_stroke(commit_shape=False)
        self.tool = mode
        self.update()

    def set_performance_mode(self, enabled: bool):
        enabled = bool(enabled)
        if enabled == self._performance_mode:
            return
        self._performance_mode = enabled
        self._cancel_select_gesture()
        self._clear_select_mode_state()
        self._end_stroke(commit_shape=False)
        if self._performance_mode and self.tool in ("brush", "line", "circle", "rectangle", "polygon", "text", "change"):
            self.tool = "select"
        self.update()

    def set_polygon_sides(self, n: int):
        if is_development_polygon_side(n):
            self.polygon_sides = n

    def set_selected_object(self, index: int):
        if 0 <= int(index) < len(self.objects):
            new_index = int(index)
        else:
            new_index = -1
        if new_index == self.selected_index:
            return
        self.selected_index = new_index
        self._clear_select_mode_state()
        self._clear_change_preview()
        self.update()
        self._emit_objects_changed()

    def set_selected_background(self, index: int):
        if 0 <= int(index) < len(self.backgrounds):
            new_index = int(index)
        else:
            new_index = -1
        if new_index == self.selected_background_index:
            return
        self.selected_background_index = new_index
        self._clear_select_mode_state()
        self._clear_background_change_preview()
        self.update()
        self._emit_backgrounds_changed()

    def _selected_delete_target(self):
        if self.tool == "change" and self._change_target_kind == "background":
            if 0 <= self.selected_background_index < len(self.backgrounds):
                return "background", self.selected_background_index
            return None, -1
        if 0 <= self.selected_index < len(self.objects):
            return "object", self.selected_index
        if 0 <= self.selected_background_index < len(self.backgrounds):
            return "background", self.selected_background_index
        return None, -1

    def _cancel_delete_fade(self, update: bool = True):
        if self._delete_fade_timer.isActive():
            self._delete_fade_timer.stop()
        had_fade = self._delete_fade is not None
        self._delete_fade = None
        if had_fade and update:
            self.update()

    def _tick_delete_fade(self):
        fade = self._delete_fade
        if fade is None:
            self._delete_fade_timer.stop()
            return
        elapsed = time.monotonic() - float(fade.get("started_at", 0.0))
        duration = max(0.01, float(fade.get("duration", self._delete_fade_duration)))
        if elapsed >= duration:
            self._cancel_delete_fade(update=True)
            return
        self.update()

    def _start_delete_fade(self, kind: str, obj, snapshot):
        if obj is None or snapshot is None:
            self._cancel_delete_fade(update=False)
            return
        self._cancel_delete_fade(update=False)
        self._delete_fade = {
            "kind": "background" if str(kind) == "background" else "object",
            "object": self._clone_history_value(obj),
            "snapshot": self._clone_history_value(snapshot),
            "started_at": time.monotonic(),
            "duration": float(self._delete_fade_duration),
        }
        self._delete_fade_timer.start()
        self.update()

    def delete_selected_scene_item(self):
        target_kind, index = self._selected_delete_target()
        if target_kind is None:
            return False
        collection = self.backgrounds if target_kind == "background" else self.objects
        if not (0 <= index < len(collection)):
            return False

        obj = collection[index]
        if target_kind == "background":
            snapshot = self._background_visual_snapshot(obj, index, include_change_preview=True)
        else:
            snapshot = self._object_visual_snapshot(obj, index, include_change_preview=True)
        self._start_delete_fade(target_kind, obj, snapshot)

        collection.pop(index)
        self._cancel_select_gesture()
        self._clear_select_mode_state()

        if target_kind == "background":
            self._clear_background_change_preview()
            self.selected_background_index = min(index, len(self.backgrounds) - 1) if self.backgrounds else -1
            self._emit_backgrounds_changed()
        else:
            self._clear_change_preview()
            self.selected_index = min(index, len(self.objects) - 1) if self.objects else -1
            self._emit_objects_changed()

        self.update()
        self.mutationCommitted.emit(f"delete_{target_kind}")
        return True

    def set_change_target_kind(self, kind: str):
        clean_kind = "background" if str(kind) == "background" else "object"
        if clean_kind == self._change_target_kind:
            return
        self._change_target_kind = clean_kind
        self._cancel_select_gesture()
        self._clear_select_mode_state()
        self.update()

    def set_active_change_visibility_mode(self, mode: str):
        self._change_visibility_mode = clean_change_visibility_mode(mode)

    def set_change_preview_enabled(self, kind: str, enabled: bool):
        _ = enabled
        if str(kind) == "background":
            clean_enabled = True
            if clean_enabled == self._background_change_preview_enabled:
                return
            self._background_change_preview_enabled = clean_enabled
            self.update()
            return
        clean_enabled = True
        if clean_enabled == self._change_preview_enabled:
            return
        self._change_preview_enabled = clean_enabled
        self.update()

    def set_select_transform_mode(self, mode: str):
        if mode not in ("translate", "rotate", "reflect", "scale"):
            return
        if mode == self.select_transform_mode:
            return
        self.select_transform_mode = mode
        self._cancel_select_gesture()
        self._clear_select_mode_state()
        self.update()

    def set_change_opacity_percent(self, value: int):
        if not (0 <= self.selected_index < len(self.objects)):
            return
        preview = self._ensure_change_preview(self.selected_index)
        if preview is None:
            return
        alpha = int(round(255 * max(0, min(100, int(value))) / 100.0))
        if preview["color"].alpha() != alpha:
            preview["color"].setAlpha(alpha)
            self.update()
            self.mutationCommitted.emit("object_preview_opacity")

    def set_change_color(self, color: QColor):
        if not color.isValid():
            return
        self._change_color = QColor(color)
        if self._change_target_kind == "background":
            if not (0 <= self.selected_background_index < len(self.backgrounds)):
                return
            preview = self._ensure_background_change_preview(self.selected_background_index)
            if preview is not None:
                preview_color = QColor(color)
                self._apply_change_visibility_to_color(preview_color, self.backgrounds[self.selected_background_index])
                if preview["color"].rgba() != preview_color.rgba():
                    preview["color"] = preview_color
                    self.update()
                    self.mutationCommitted.emit("background_preview_color")
            return
        if 0 <= self.selected_index < len(self.objects):
            preview = self._ensure_change_preview(self.selected_index)
            if preview is not None:
                preview_color = QColor(color)
                preview_color.setAlpha(preview["color"].alpha())
                self._apply_change_visibility_to_color(preview_color, self.objects[self.selected_index])
                if preview["color"].rgba() != preview_color.rgba():
                    preview["color"] = preview_color
                    self.update()
                    self.mutationCommitted.emit("object_preview_color")

    def set_change_visibility_mode(self, mode: str):
        mode = clean_change_visibility_mode(mode)
        if mode == self._change_visibility_mode:
            return
        self._change_visibility_mode = mode
        if self._change_target_kind == "background":
            if 0 <= self.selected_background_index < len(self.backgrounds):
                preview = self._ensure_background_change_preview(self.selected_background_index)
                if preview is not None:
                    old_rgba = preview["color"].rgba()
                    self._apply_change_visibility_to_color(preview["color"], self.backgrounds[self.selected_background_index])
                    if preview["color"].rgba() != old_rgba:
                        self.update()
                        self.mutationCommitted.emit("background_preview_visibility")
            return
        if 0 <= self.selected_index < len(self.objects):
            preview = self._ensure_change_preview(self.selected_index)
            if preview is not None:
                old_rgba = preview["color"].rgba()
                self._apply_change_visibility_to_color(preview["color"], self.objects[self.selected_index])
                if preview["color"].rgba() != old_rgba:
                    self.update()
                    self.mutationCommitted.emit("object_preview_visibility")

    def set_image_variant_params(self, params):
        if self.tool != "change":
            return
        if not (0 <= self.selected_index < len(self.objects)):
            return
        obj = self.objects[self.selected_index]
        if obj.get("kind") != "image_variant":
            return
        if str(obj.get("variant_source_mode", "generated")) == "image_set":
            return

        preview = self._ensure_change_preview(self.selected_index)
        if preview is None:
            return
        preview["variant_params"] = normalize_image_variant_params(params)
        self.update()

    def set_image_set_switch_time(self, value: float):
        if not (0 <= self.selected_index < len(self.objects)):
            return
        obj = self.objects[self.selected_index]
        if obj.get("kind") != "image_variant":
            return
        if str(obj.get("variant_source_mode", "generated")) != "image_set":
            return
        try:
            switch_time = max(0.0, min(1.5, float(value)))
        except Exception:
            switch_time = default_image_set_switch_time()
        if abs(float(obj.get("image_set_switch_time", default_image_set_switch_time())) - switch_time) < 1e-6:
            return
        obj["image_set_switch_time"] = switch_time
        self._emit_objects_changed()

    def set_image_set_timing_mode(self, mode: str):
        if not (0 <= self.selected_index < len(self.objects)):
            return
        obj = self.objects[self.selected_index]
        if obj.get("kind") != "image_variant":
            return
        if str(obj.get("variant_source_mode", "generated")) != "image_set":
            return
        clean_mode = clean_image_set_timing_mode(mode)
        if clean_mode == str(obj.get("image_set_timing_mode", default_image_set_timing_mode())):
            return
        obj["image_set_timing_mode"] = clean_mode
        self._emit_objects_changed()

    def set_image_set_timing_translation(self, value: float):
        if not (0 <= self.selected_index < len(self.objects)):
            return
        obj = self.objects[self.selected_index]
        if obj.get("kind") != "image_variant":
            return
        if str(obj.get("variant_source_mode", "generated")) != "image_set":
            return
        try:
            translation = max(0.25, min(3.0, float(value)))
        except Exception:
            translation = default_image_set_timing_translation()
        if abs(float(obj.get("image_set_timing_translation", default_image_set_timing_translation())) - translation) < 1e-6:
            return
        obj["image_set_timing_translation"] = translation
        self._emit_objects_changed()

    def set_image_set_timing_pause(self, value: float):
        if not (0 <= self.selected_index < len(self.objects)):
            return
        obj = self.objects[self.selected_index]
        if obj.get("kind") != "image_variant":
            return
        if str(obj.get("variant_source_mode", "generated")) != "image_set":
            return
        try:
            pause = max(0.0, min(0.95, float(value)))
        except Exception:
            pause = default_image_set_timing_pause()
        if abs(float(obj.get("image_set_timing_pause", default_image_set_timing_pause())) - pause) < 1e-6:
            return
        obj["image_set_timing_pause"] = pause
        self._emit_objects_changed()

    def import_image_variant(self, path: str, prepared=None):
        path = str(path or "").strip()
        if not path:
            return False, "No image path provided."

        image = QImage(path) if prepared is None else prepared[0]
        if image.isNull():
            return False, "The selected file could not be loaded as an image."

        core_image, samples = prepared if prepared is not None else self._prepare_image_variant_source(image)
        if core_image.isNull() or not samples:
            return False, "The imported image does not contain enough visible content to build a stable core."

        width = float(max(1, core_image.width()))
        height = float(max(1, core_image.height()))
        rect = self._fit_image_variant_rect(width, height)

        base_variant = default_image_variant_params()
        base_transform = QTransform()
        base_transform.translate(float(max(1, self.width())) * 0.5, float(max(1, self.height())) * 0.5)
        stages = [
            self._make_stage_snapshot(base_transform, QColor(255, 255, 255), variant_params=params)
            for params in default_image_variant_stage_presets()
        ]

        obj = {
            "kind": "image_variant",
            "name": Path(path).name,
            "source_path": path,
            "core_image": core_image,
            "variant_samples": samples,
            "rect": rect,
            "color": QColor(255, 255, 255),
            "base_color": QColor(255, 255, 255),
            "transform": QTransform(base_transform),
            "pivot": None,
            "variant_params": base_variant,
            "variant_source_mode": "generated",
            "variant_key": "",
            "variant_stage_labels": [f"Stage {index + 1}" for index in range(len(stages))],
            "stages": stages,
            "beat_map": default_sequential_stage_map(len(stages)),
            "beat_transitions": [
                default_transition_spec(effect="cut", easing="linear")
                for _ in range(default_loop_slot_count())
            ],
        }
        existing = next((item for item in self.objects if item.get("kind") == "image_variant"), None)
        if existing is not None:
            for key in ("name", "source_path", "core_image", "variant_samples"):
                existing[key] = obj[key]
            self.selected_index = self.objects.index(existing)
        else:
            self.objects.append(obj)
            self.selected_index = len(self.objects) - 1
            self._clear_change_preview()
        self._emit_objects_changed()
        self.update()
        self.mutationCommitted.emit("import_object")
        return True, f"Imported {Path(path).name}"

    def import_background_image(self, path: str, prepared=None, slot=None):
        path = str(path or "").strip()
        if not path:
            return False, "No background image path provided."

        image = QImage(path) if prepared is None else prepared
        if image.isNull():
            return False, "The selected background could not be loaded as an image."

        if max(image.width(), image.height()) > 2048:
            image = image.scaled(2048, 2048, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        normalized = image.convertToFormat(QImage.Format_ARGB32)
        width = float(max(1, normalized.width()))
        height = float(max(1, normalized.height()))
        rect = self._fit_background_rect(width, height)

        base_transform = QTransform()
        base_transform.translate(float(max(1, self.width())) * 0.5, float(max(1, self.height())) * 0.5)
        base_variant = default_image_variant_params()
        variant_key = ""

        obj = {
            "kind": "background_variant",
            "is_background": True,
            "name": Path(path).name,
            "source_path": path,
            "core_image": QImage(),
            "variant_samples": [],
            "variant_shell_images": {"base": normalized},
            "rect": rect,
            "color": QColor(255, 255, 255),
            "base_color": QColor(255, 255, 255),
            "transform": QTransform(base_transform),
            "pivot": None,
            "variant_params": base_variant,
            "variant_source_mode": "single_image",
            "image_set_audio_lane_mode": False,
            "variant_key": variant_key,
            "variant_stage_labels": [],
            "stages": [],
            "beat_map": default_loop_stage_map(),
            "beat_transitions": [
                default_transition_spec(effect="cut", easing="linear")
                for _ in range(default_loop_slot_count())
            ],
        }
        slot = min(1, max(0, self.selected_background_index if slot is None else int(slot)))
        existing = next((item for i, item in enumerate(self.backgrounds) if item.get("background_slot", i) == slot), None)
        obj["background_slot"] = slot
        if existing is not None:
            for key in ("name", "source_path", "variant_shell_images"):
                existing[key] = obj[key]
            self.selected_background_index = self.backgrounds.index(existing)
        else:
            self.backgrounds.append(obj)
            self.selected_background_index = len(self.backgrounds) - 1
            self._clear_background_change_preview()
        self._emit_backgrounds_changed()
        self.update()
        self.mutationCommitted.emit("import_background")
        return True, f"Imported background {Path(path).name}"

    def import_image_variant_set(self, folder_path: str):
        folder = Path(str(folder_path or "").strip())
        if not folder.is_dir():
            return False, "No image set folder was selected."

        image_paths = list_image_set_files(str(folder))
        if len(image_paths) < 1:
            return False, "No image files found."

        core_path = choose_image_set_core_path(image_paths)
        core_image, shell_images, stage_labels = self._prepare_image_set_source(image_paths, core_path=core_path)
        if core_image is None or core_image.isNull() or not shell_images or not stage_labels:
            return False, "The selected folder could not be converted into a shared core and switchable shells."

        width = float(max(1, core_image.width()))
        height = float(max(1, core_image.height()))
        rect = self._fit_image_variant_rect(width, height)

        base_transform = QTransform()
        base_transform.translate(float(max(1, self.width())) * 0.5, float(max(1, self.height())) * 0.5)
        base_variant = default_image_variant_params()
        stages = [
            self._make_stage_snapshot(
                base_transform,
                QColor(255, 255, 255),
                variant_params=base_variant,
                variant_key=label,
                stage_label=label,
            )
            for label in stage_labels
        ]
        beat_map = default_image_set_beat_map(stage_labels)
        current_variant = stage_labels[0]

        obj = {
            "kind": "image_variant",
            "name": folder.name or "Image Set",
            "source_path": str(folder),
            "core_image": core_image,
            "variant_samples": [],
            "variant_shell_images": shell_images,
            "rect": rect,
            "color": QColor(255, 255, 255),
            "base_color": QColor(255, 255, 255),
            "transform": QTransform(base_transform),
            "pivot": None,
            "variant_params": base_variant,
            "variant_source_mode": "image_set",
            "image_set_audio_lane_mode": False,
            "variant_key": current_variant,
            "image_set_switch_time": default_image_set_switch_time(),
            "image_set_timing_mode": default_image_set_timing_mode(),
            "image_set_timing_translation": default_image_set_timing_translation(),
            "image_set_timing_pause": default_image_set_timing_pause(),
            "_audio_lane_live_key": current_variant,
            "_audio_lane_transition_from_key": "",
            "_audio_lane_transition_to_key": "",
            "_audio_lane_transition_started_at": 0.0,
            "_audio_lane_transition_duration": 0.0,
            "_audio_lane_transition_hold_until": 0.0,
            "variant_stage_labels": list(stage_labels),
            "stages": stages,
            "beat_map": beat_map,
            "beat_transitions": [
                default_transition_spec(effect="cut", easing="linear")
                for _ in range(len(beat_map))
            ],
        }
        self.objects.append(obj)
        self.selected_index = len(self.objects) - 1
        self._clear_change_preview()
        self._emit_objects_changed()
        self.update()
        self.mutationCommitted.emit("import_object_set")

        label_preview = ", ".join(stage_labels[:4])
        if len(stage_labels) > 4:
            label_preview += ", ..."
        return True, f"Imported image set {folder.name} with stages: {label_preview}"

    def import_background_images(self, folder_path: str):
        folder = Path(str(folder_path or "").strip())
        if not folder.is_dir():
            return False, "No background folder was selected."

        image_paths = list_image_set_files(str(folder))
        if len(image_paths) < 1:
            return False, "No image files found."

        # Load and normalize all images
        images = []
        for path in image_paths:
            image = QImage(str(path))
            if image.isNull():
                continue
            images.append(image)
        
        if not images:
            return False, "No valid images found in the selected folder."

        # Normalize all images to the same size (use first image as reference)
        target_width = max(1, images[0].width())
        target_height = max(1, images[0].height())
        
        normalized_images = []
        for image in images:
            if image.width() != target_width or image.height() != target_height:
                normalized = image.scaled(target_width, target_height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            else:
                normalized = QImage(image)
            normalized_images.append(normalized.convertToFormat(QImage.Format_ARGB32))

        # Create stage labels and shell images mapping
        stage_labels = [f"bg_{i+1}" for i in range(len(normalized_images))]
        shell_images = {label: img for label, img in zip(stage_labels, normalized_images)}
        
        # Create a transparent core image
        core_image = QImage(target_width, target_height, QImage.Format_ARGB32)
        core_image.fill(QColor(0, 0, 0, 0))

        width = float(max(1, core_image.width()))
        height = float(max(1, core_image.height()))
        rect = self._fit_background_rect(width, height)

        base_transform = QTransform()
        base_transform.translate(float(max(1, self.width())) * 0.5, float(max(1, self.height())) * 0.5)
        base_variant = default_image_variant_params()
        stages = [
            self._make_stage_snapshot(
                base_transform,
                QColor(255, 255, 255),
                variant_params=base_variant,
                variant_key=label,
                stage_label=label,
            )
            for label in stage_labels
        ]
        
        # Create simple sequential beat map
        beat_map = list(range(1, len(stage_labels) + 1))
        current_variant = stage_labels[0]

        obj = {
            "kind": "background_variant",
            "is_background": True,
            "name": folder.name or "Background Set",
            "source_path": str(folder),
            "core_image": core_image,
            "variant_samples": [],
            "variant_shell_images": shell_images,
            "rect": rect,
            "color": QColor(255, 255, 255),
            "base_color": QColor(255, 255, 255),
            "transform": QTransform(base_transform),
            "pivot": None,
            "variant_params": base_variant,
            "variant_source_mode": "image_set",
            "image_set_audio_lane_mode": False,
            "variant_key": current_variant,
            "image_set_switch_time": default_image_set_switch_time(),
            "image_set_timing_mode": default_image_set_timing_mode(),
            "image_set_timing_translation": default_image_set_timing_translation(),
            "image_set_timing_pause": default_image_set_timing_pause(),
            "_audio_lane_live_key": current_variant,
            "_audio_lane_transition_from_key": "",
            "_audio_lane_transition_to_key": "",
            "_audio_lane_transition_started_at": 0.0,
            "_audio_lane_transition_duration": 0.0,
            "_audio_lane_transition_hold_until": 0.0,
            "variant_stage_labels": list(stage_labels),
            "stages": stages,
            "beat_map": beat_map,
            "beat_transitions": [
                default_transition_spec(effect="cut", easing="linear")
                for _ in range(len(beat_map))
            ],
        }
        self.backgrounds.append(obj)
        self.selected_background_index = len(self.backgrounds) - 1
        self._clear_background_change_preview()
        self._emit_backgrounds_changed()
        self.update()
        self.mutationCommitted.emit("import_background_set")

        label_preview = ", ".join(stage_labels[:4])
        if len(stage_labels) > 4:
            label_preview += ", ..."
        return True, f"Imported background set {folder.name} with {len(stage_labels)} images: {label_preview}"

    def _apply_preview_stage_to_object(self, obj, preview):
        committed_transform = self._object_base_transform(obj)
        committed_color = self._object_committed_color(obj)
        committed_variant_params = self._object_committed_variant_params(obj)
        if (
            self._transforms_close(preview["transform"], committed_transform)
            and preview["color"].rgba() == committed_color.rgba()
            and self._variant_params_close(preview.get("variant_params"), committed_variant_params)
        ):
            return

        snapshot = self._make_stage_snapshot(
            preview["transform"],
            preview["color"],
            variant_params=preview.get("variant_params"),
            variant_key=preview.get("variant_key", ""),
            stage_label=preview.get("stage_label", "") or preview.get("variant_key", ""),
        )
        obj.setdefault("stages", []).append(snapshot)
        stage_labels = list(obj.get("variant_stage_labels", []))
        while len(stage_labels) < (len(obj["stages"]) - 1):
            stage_labels.append(f"Stage {len(stage_labels) + 1}")
        next_stage_label = str(snapshot.get("stage_label", "") or f"Stage {len(stage_labels) + 1}")
        stage_labels.append(next_stage_label)
        obj["variant_stage_labels"] = stage_labels
        obj["transform"] = QTransform(snapshot["transform"])
        obj["color"] = QColor(snapshot["color"])
        obj["variant_params"] = normalize_image_variant_params(snapshot.get("variant_params"))
        obj["variant_key"] = str(snapshot.get("variant_key", obj.get("variant_key", "")))
        return True

    def apply_change_stage(self):
        if self._performance_mode:
            return
        if self._change_target_kind == "background":
            self.apply_background_change_stage()
            return
        preview = self._change_preview
        index = self.selected_index
        if preview is not None and not (0 <= index < len(self.objects)):
            preview_index = int(preview.get("object_index", -1))
            if 0 <= preview_index < len(self.objects):
                index = preview_index
                self.selected_index = preview_index
        if not (0 <= index < len(self.objects)):
            return
        preview = self._ensure_change_preview(index)
        if preview is None:
            return

        obj = self.objects[index]
        if not self._apply_preview_stage_to_object(obj, preview):
            return
        self._clear_change_preview()
        self.update()
        self._emit_objects_changed()
        self.mutationCommitted.emit("apply_object_state")

    def apply_background_change_stage(self):
        if self._performance_mode:
            return
        preview = self._background_change_preview
        index = self.selected_background_index
        if preview is not None and not (0 <= index < len(self.backgrounds)):
            preview_index = int(preview.get("background_index", -1))
            if 0 <= preview_index < len(self.backgrounds):
                index = preview_index
                self.selected_background_index = preview_index
        if not (0 <= index < len(self.backgrounds)):
            return
        preview = self._ensure_background_change_preview(index)
        if preview is None:
            return
        obj = self.backgrounds[index]
        if not self._apply_preview_stage_to_object(obj, preview):
            return
        self._clear_background_change_preview()
        self.update()
        self._emit_backgrounds_changed()
        self.mutationCommitted.emit("apply_background_state")

    def _clear_saved_stages(self, obj):
        if obj is None:
            return False
        slot_count = default_loop_slot_count()
        next_beat_map = default_loop_stage_map(slot_count)
        next_transitions = default_transition_specs(slot_count)
        current_beat_map = list(obj.get("beat_map", []))
        current_transitions = [self._normalize_transition_spec(value) for value in list(obj.get("beat_transitions", default_transition_specs(self._object_loop_slot_count(obj))))]
        current_points = normalize_loop_timeline_points(
            obj.get("timeline_points", []),
            max(1, len(current_beat_map) or len(current_transitions) or default_loop_slot_count()),
            len(obj.get("stages", [])),
            beat_map=current_beat_map,
            beat_transitions=current_transitions,
        )
        next_points = normalize_loop_timeline_points(
            [],
            slot_count,
            0,
            beat_map=next_beat_map,
            beat_transitions=next_transitions,
        )
        changed = (
            bool(obj.get("stages", []))
            or bool(obj.get("variant_stage_labels", []))
            or current_beat_map != next_beat_map
            or current_transitions != next_transitions
            or current_points != next_points
        )
        if not changed:
            return False
        obj["stages"] = []
        obj["variant_stage_labels"] = []
        obj["beat_map"] = list(next_beat_map)
        obj["beat_transitions"] = list(next_transitions)
        obj["timeline_points"] = list(next_points)
        return True

    def reset_change_stages(self):
        if self._performance_mode:
            return
        if self._change_target_kind == "background":
            self.reset_background_change_stages()
            return
        preview = self._change_preview
        index = self.selected_index
        if preview is not None and not (0 <= index < len(self.objects)):
            preview_index = int(preview.get("object_index", -1))
            if 0 <= preview_index < len(self.objects):
                index = preview_index
                self.selected_index = preview_index
        if not (0 <= index < len(self.objects)):
            return
        if not self._clear_saved_stages(self.objects[index]):
            return
        self.update()
        self._emit_objects_changed()
        self.mutationCommitted.emit("reset_object_stages")

    def reset_background_change_stages(self):
        if self._performance_mode:
            return
        preview = self._background_change_preview
        index = self.selected_background_index
        if preview is not None and not (0 <= index < len(self.backgrounds)):
            preview_index = int(preview.get("background_index", -1))
            if 0 <= preview_index < len(self.backgrounds):
                index = preview_index
                self.selected_background_index = preview_index
        if not (0 <= index < len(self.backgrounds)):
            return
        if not self._clear_saved_stages(self.backgrounds[index]):
            return
        self.update()
        self._emit_backgrounds_changed()
        self.mutationCommitted.emit("reset_background_stages")

    def reset_change_preview(self):
        if self._change_target_kind == "background":
            if self._background_change_preview is None:
                return
            self._clear_background_change_preview()
            self.update()
            self.mutationCommitted.emit("reset_background_preview")
            return
        if self._change_preview is None:
            return
        self._clear_change_preview()
        self.update()
        self._emit_objects_changed()
        self.mutationCommitted.emit("reset_object_preview")

    def set_object_loop_timeline(self, index: int, config):
        if not (0 <= int(index) < len(self.objects)):
            return
        obj = self.objects[int(index)]
        row = config if isinstance(config, dict) else {}
        beat_map_values = row.get("beat_map", [])
        beat_transition_values = row.get("beat_transitions", obj.get("beat_transitions", default_transition_specs(self._object_loop_slot_count(obj))))
        slot_count = max(
            1,
            len(list(beat_map_values)) if isinstance(beat_map_values, (list, tuple)) and beat_map_values else len(list(beat_transition_values)) if isinstance(beat_transition_values, (list, tuple)) and beat_transition_values else len(obj.get("beat_map", [])) or default_loop_slot_count(),
        )

        clean = []
        stage_count = len(obj.get("stages", []))
        for value in list(beat_map_values)[:slot_count]:
            try:
                clean_value = max(0, int(value))
            except Exception:
                clean_value = 0
            clean.append(max(0, min(clean_value, stage_count)) if stage_count > 0 else 0)
        while len(clean) < slot_count:
            clean.append(0)

        transitions = [self._normalize_transition_spec(value) for value in list(beat_transition_values)[:slot_count]]
        while len(transitions) < slot_count:
            transitions.append(self._default_transition_spec())
        timeline_points = normalize_loop_timeline_points(
            row.get("timeline_points", obj.get("timeline_points", [])),
            slot_count,
            stage_count,
            beat_map=clean,
            beat_transitions=transitions,
        )

        current_map = list(obj.get("beat_map", []))
        current_transitions = [self._normalize_transition_spec(value) for value in list(obj.get("beat_transitions", []))]
        current_timeline_points = normalize_loop_timeline_points(
            obj.get("timeline_points", []),
            slot_count,
            stage_count,
            beat_map=current_map,
            beat_transitions=current_transitions,
        )
        if clean == current_map and transitions == current_transitions and timeline_points == current_timeline_points:
            return

        obj["beat_map"] = clean
        obj["beat_transitions"] = transitions
        obj["timeline_points"] = timeline_points
        self._emit_objects_changed()
        self.update()
        self.mutationCommitted.emit("object_loop_changed")

    def set_background_loop_timeline(self, index: int, config):
        if not (0 <= int(index) < len(self.backgrounds)):
            return
        obj = self.backgrounds[int(index)]
        row = config if isinstance(config, dict) else {}
        beat_map_values = row.get("beat_map", [])
        beat_transition_values = row.get("beat_transitions", obj.get("beat_transitions", default_transition_specs(self._object_loop_slot_count(obj))))
        slot_count = max(
            1,
            len(list(beat_map_values)) if isinstance(beat_map_values, (list, tuple)) and beat_map_values else len(list(beat_transition_values)) if isinstance(beat_transition_values, (list, tuple)) and beat_transition_values else len(obj.get("beat_map", [])) or default_loop_slot_count(),
        )

        clean = []
        stage_count = len(obj.get("stages", []))
        for value in list(beat_map_values)[:slot_count]:
            try:
                clean_value = max(0, int(value))
            except Exception:
                clean_value = 0
            clean.append(max(0, min(clean_value, stage_count)) if stage_count > 0 else 0)
        while len(clean) < slot_count:
            clean.append(0)

        transitions = [self._normalize_transition_spec(value) for value in list(beat_transition_values)[:slot_count]]
        while len(transitions) < slot_count:
            transitions.append(self._default_transition_spec())
        timeline_points = normalize_loop_timeline_points(
            row.get("timeline_points", obj.get("timeline_points", [])),
            slot_count,
            stage_count,
            beat_map=clean,
            beat_transitions=transitions,
        )

        current_map = list(obj.get("beat_map", []))
        current_transitions = [self._normalize_transition_spec(value) for value in list(obj.get("beat_transitions", []))]
        current_timeline_points = normalize_loop_timeline_points(
            obj.get("timeline_points", []),
            slot_count,
            stage_count,
            beat_map=current_map,
            beat_transitions=current_transitions,
        )
        if clean == current_map and transitions == current_transitions and timeline_points == current_timeline_points:
            return

        obj["beat_map"] = clean
        obj["beat_transitions"] = transitions
        obj["timeline_points"] = timeline_points
        self._emit_backgrounds_changed()
        self.update()
        self.mutationCommitted.emit("background_loop_changed")

    def _clear_beat_transition(self):
        self._beat_transition_from_slot = -1
        self._beat_transition_to_slot = -1
        self._beat_transition_started_at = 0.0
        self._beat_transition_duration = 0.0
        self._beat_transition_interval = self._last_beat_interval

    def _default_transition_spec(self):
        return default_transition_spec()

    def _normalize_transition_spec(self, value):
        return normalize_transition_spec(value)

    def _object_loop_slot_count(self, obj):
        if not isinstance(obj, dict):
            return default_loop_slot_count()
        beat_map = obj.get("beat_map", [])
        beat_transitions = obj.get("beat_transitions", [])
        beat_map_count = len(beat_map) if isinstance(beat_map, (list, tuple)) and beat_map else 0
        beat_transition_count = len(beat_transitions) if isinstance(beat_transitions, (list, tuple)) and beat_transitions else 0
        return max(1, beat_map_count or beat_transition_count or default_loop_slot_count())

    def _object_timeline_points(self, obj):
        if not isinstance(obj, dict):
            return []
        slot_count = self._object_loop_slot_count(obj)
        stage_count = len(obj.get("stages", []))
        return normalize_loop_timeline_points(
            obj.get("timeline_points", []),
            slot_count,
            stage_count,
            beat_map=obj.get("beat_map", []),
            beat_transitions=obj.get("beat_transitions", []),
        )

    def _current_loop_phase(self, slot_count: int):
        if not self.beat_reactive or self._beat_slot < 0:
            return None
        try:
            clean_slot_count = max(1, int(slot_count))
        except Exception:
            clean_slot_count = default_loop_slot_count()
        interval = self._average_beat_interval if self._average_beat_interval > 1e-6 else self._last_beat_interval
        interval = max(0.08, float(interval or 0.25))
        elapsed = max(0.0, time.monotonic() - self._last_beat_time) if self._last_beat_time > 0.0 else 0.0
        progress = max(0.0, min(1.0, elapsed / interval))
        return (float(self._beat_slot) + progress) % float(clean_slot_count)

    def _timeline_segment_state(self, obj):
        points = self._object_timeline_points(obj)
        if not points:
            return None

        slot_count = self._object_loop_slot_count(obj)
        phase = self._current_loop_phase(slot_count)
        if phase is None:
            return None

        if len(points) == 1:
            snapshot = self._object_stage_snapshot(obj, int(points[0]["state"])) or self._object_committed_snapshot(obj)
            return {
                "snapshot": snapshot,
                "start_snapshot": snapshot,
                "end_snapshot": snapshot,
                "spec": default_timeline_transition_spec(),
                "progress": 1.0,
                "transition_active": False,
            }

        total = float(max(1, slot_count))
        for index, point in enumerate(points):
            next_point = points[(index + 1) % len(points)]
            start_position = float(point["position"])
            end_position = float(next_point["position"])
            span = (end_position - start_position) % total
            if span <= TIMELINE_POSITION_EPSILON:
                span = total
            distance = (float(phase) - start_position) % total
            if distance < span or abs(distance - span) < TIMELINE_POSITION_EPSILON:
                if abs(distance - span) < TIMELINE_POSITION_EPSILON and distance > TIMELINE_POSITION_EPSILON:
                    continue
                spec = self._normalize_transition_spec(point.get("transition", default_timeline_transition_spec()))
                start_snapshot = self._object_stage_snapshot(obj, int(point["state"])) or self._object_committed_snapshot(obj)
                end_snapshot = self._object_stage_snapshot(obj, int(next_point["state"])) or self._object_committed_snapshot(obj)
                progress = max(0.0, min(1.0, distance / span)) if span > TIMELINE_POSITION_EPSILON else 1.0
                active = spec["effect"] != "cut" and progress > TIMELINE_POSITION_EPSILON and progress < (1.0 - TIMELINE_POSITION_EPSILON)
                if spec["effect"] == "cut":
                    snapshot = end_snapshot if progress >= (1.0 - TIMELINE_POSITION_EPSILON) else start_snapshot
                elif progress >= (1.0 - TIMELINE_POSITION_EPSILON):
                    snapshot = end_snapshot
                elif progress <= TIMELINE_POSITION_EPSILON:
                    snapshot = start_snapshot
                else:
                    snapshot = self._interpolate_snapshot(start_snapshot, end_snapshot, progress)
                return {
                    "snapshot": snapshot,
                    "start_snapshot": start_snapshot,
                    "end_snapshot": end_snapshot,
                    "spec": spec,
                    "progress": progress,
                    "transition_active": active,
                }

        snapshot = self._object_stage_snapshot(obj, int(points[0]["state"])) or self._object_committed_snapshot(obj)
        return {
            "snapshot": snapshot,
            "start_snapshot": snapshot,
            "end_snapshot": snapshot,
            "spec": default_timeline_transition_spec(),
            "progress": 1.0,
            "transition_active": False,
        }

    def _object_slot_index_for_step(self, obj, step_index: int):
        if step_index < 0:
            return -1
        slot_count = self._object_loop_slot_count(obj)
        if slot_count <= 0:
            return -1
        return int(step_index) % slot_count

    def _object_transition_spec(self, obj, slot_index: int):
        if slot_index < 0:
            return self._default_transition_spec()
        transitions = obj.get("beat_transitions", default_transition_specs(self._object_loop_slot_count(obj)))
        if not (0 <= slot_index < len(transitions)):
            return self._default_transition_spec()
        return self._normalize_transition_spec(transitions[slot_index])

    def _any_non_cut_beat_transition(self, slot_index: int):
        if slot_index < 0:
            return False
        for obj in self.objects:
            if self._object_transition_spec(obj, slot_index)["effect"] != "cut":
                return True
        return False

    def _beat_transition_duration_for_spec(self, spec, interval: float):
        spec = self._normalize_transition_spec(spec)
        if spec["effect"] == "cut":
            return 0.0
        try:
            scale = max(0.0, float(spec.get("duration_scale", default_transition_duration_scale(spec["effect"]))))
        except Exception:
            scale = default_transition_duration_scale(spec["effect"])
        if scale <= 1e-6:
            return 0.0
        return max(0.08, min(0.75, max(0.05, float(interval)) * scale))

    def _beat_transition_duration_for_slot(self, slot_index: int, interval: float):
        if slot_index < 0:
            return 0.0
        duration = 0.0
        for obj in self.objects:
            local_slot = self._object_slot_index_for_step(obj, slot_index)
            duration = max(duration, self._beat_transition_duration_for_spec(self._object_transition_spec(obj, local_slot), interval))
        return duration

    def _beat_transition_progress(self):
        if self._beat_transition_from_slot < 0 or self._beat_transition_to_slot < 0 or self._beat_transition_duration <= 1e-6:
            return None
        elapsed = max(0.0, time.monotonic() - self._beat_transition_started_at)
        progress = max(0.0, min(1.0, elapsed / self._beat_transition_duration))
        if progress >= 1.0:
            self._clear_beat_transition()
            return None
        return progress

    def _beat_transition_progress_for_spec(self, spec):
        if self._beat_transition_from_slot < 0 or self._beat_transition_to_slot < 0:
            return None
        spec = self._normalize_transition_spec(spec)
        duration = self._beat_transition_duration_for_spec(spec, self._beat_transition_interval)
        if duration <= 1e-6:
            return 1.0
        elapsed = max(0.0, time.monotonic() - self._beat_transition_started_at)
        progress = max(0.0, min(1.0, elapsed / duration))
        return self._ease_beat_transition(spec["easing"], progress)

    def _ease_beat_transition(self, mode: str, value: float):
        t = max(0.0, min(1.0, float(value)))
        if mode == "linear":
            return t
        if mode == "ease_in":
            return t * t
        if mode == "ease_out":
            return 1.0 - ((1.0 - t) * (1.0 - t))
        if mode == "ease_in_out":
            if t < 0.5:
                return 2.0 * t * t
            return 1.0 - (pow(-2.0 * t + 2.0, 2.0) / 2.0)
        return 1.0

    def _cancel_select_gesture(self):
        self._select_gesture = None
        if self.tool in ("change", "select"):
            self.active_input = None

    def _clear_select_mode_state(self):
        self._reflect_anchor_world = None
        self._select_hover_pos = None
        self._rotation_pivot_ready = False
        self._scale_pivot_ready = False

    def _clear_change_preview(self):
        self._change_preview = None

    def _clear_background_change_preview(self):
        self._background_change_preview = None

    def _prepare_image_variant_source(self, image: QImage):
        src = QImage(image)
        max_dim = max(1, max(src.width(), src.height()))
        if max_dim > 1600:
            src = src.scaled(
                int(round(src.width() * (1600.0 / max_dim))),
                int(round(src.height() * (1600.0 / max_dim))),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        src = src.convertToFormat(QImage.Format_ARGB32)
        width = max(1, src.width())
        height = max(1, src.height())

        meaningful_alpha = False
        probe_step_x = max(1, width // 48)
        probe_step_y = max(1, height // 48)
        for y in range(0, height, probe_step_y):
            for x in range(0, width, probe_step_x):
                alpha = src.pixelColor(x, y).alpha()
                if 0 < alpha < 250:
                    meaningful_alpha = True
                    break
            if meaningful_alpha:
                break

        core = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        core.fill(Qt.transparent)
        target_samples = 4200
        stride = max(1, int(math.sqrt((width * height) / float(target_samples))))
        samples = []

        for y in range(height):
            for x in range(width):
                color = src.pixelColor(x, y)
                if meaningful_alpha:
                    alpha = color.alpha()
                else:
                    alpha = max(color.red(), color.green(), color.blue())
                    if alpha < 14:
                        alpha = 0
                    else:
                        alpha = min(255, int(round(alpha * 1.35)))

                if alpha <= 0:
                    continue

                core_color = QColor(color.red(), color.green(), color.blue(), alpha)
                core.setPixelColor(x, y, core_color)

                if (x % stride) != 0 or (y % stride) != 0:
                    continue

                luminance = (
                    (0.2126 * color.red())
                    + (0.7152 * color.green())
                    + (0.0722 * color.blue())
                ) / 255.0
                size_bias = 0.72 + (luminance * 1.05)
                nx = ((x + 0.5) / float(width)) - 0.5
                ny = ((y + 0.5) / float(height)) - 0.5
                samples.append((nx, ny, size_bias, core_color.rgba()))

        rng = random.Random((width * 1009) ^ (height * 9176) ^ len(samples))
        rng.shuffle(samples)
        if len(samples) > 5200:
            samples = samples[:5200]
        return core, samples

    def _fit_image_variant_rect(self, width: float, height: float):
        width = float(max(1.0, width))
        height = float(max(1.0, height))
        fit_width = max(240.0, float(max(1, self.width())) * 0.56)
        fit_height = max(180.0, float(max(1, self.height())) * 0.62)
        scale = min(fit_width / width, fit_height / height, 1.0)
        display_width = max(32.0, width * scale)
        display_height = max(32.0, height * scale)
        return QRectF(-(display_width * 0.5), -(display_height * 0.5), display_width, display_height)

    def _fit_background_rect(self, width: float, height: float):
        width = float(max(1.0, width))
        height = float(max(1.0, height))
        canvas_width = float(max(1, self.width()))
        canvas_height = float(max(1, self.height()))
        scale = max(canvas_width / width, canvas_height / height)
        display_width = max(canvas_width, width * scale)
        display_height = max(canvas_height, height * scale)
        return QRectF(-(display_width * 0.5), -(display_height * 0.5), display_width, display_height)

    def _background_source_size(self, obj):
        shell_images = obj.get("variant_shell_images", {})
        image = None
        if isinstance(shell_images, dict):
            variant_key = str(obj.get("variant_key", "")).strip()
            image = shell_images.get(variant_key)
            if image is None or image.isNull():
                for candidate in shell_images.values():
                    if candidate is not None and not candidate.isNull():
                        image = candidate
                        break
        if (image is None or image.isNull()) and isinstance(obj.get("core_image"), QImage):
            candidate = obj.get("core_image")
            if candidate is not None and not candidate.isNull():
                image = candidate
        if image is None or image.isNull():
            rect = QRectF(obj.get("rect", QRectF()))
            if rect.width() > 0.0 and rect.height() > 0.0:
                return float(rect.width()), float(rect.height())
            return 1.0, 1.0
        return float(max(1, image.width())), float(max(1, image.height()))

    def _translated_transform(self, transform: QTransform, tx: float, ty: float):
        delta = QTransform()
        delta.translate(float(tx), float(ty))
        return QTransform(transform) * delta

    def _refit_backgrounds_for_canvas_size(self, old_size, new_size):
        try:
            old_width = float(max(1, old_size.width()))
            old_height = float(max(1, old_size.height()))
            new_width = float(max(1, new_size.width()))
            new_height = float(max(1, new_size.height()))
        except Exception:
            return

        if abs(new_width - old_width) < 1e-6 and abs(new_height - old_height) < 1e-6:
            return

        delta_x = (new_width - old_width) * 0.5
        delta_y = (new_height - old_height) * 0.5
        changed = False

        for index, obj in enumerate(self.backgrounds):
            if str(obj.get("kind", "")) != "background_variant":
                continue
            width, height = self._background_source_size(obj)
            obj["rect"] = self._fit_background_rect(width, height)
            obj["transform"] = self._translated_transform(obj.get("transform", QTransform()), delta_x, delta_y)
            for stage in obj.get("stages", []):
                if isinstance(stage, dict):
                    stage["transform"] = self._translated_transform(stage.get("transform", QTransform()), delta_x, delta_y)
            if self._background_change_preview is not None and self._background_change_preview.get("background_index") == index:
                self._background_change_preview["transform"] = self._translated_transform(
                    self._background_change_preview.get("transform", QTransform()),
                    delta_x,
                    delta_y,
                )
            changed = True

        if changed:
            self.update()
            self._emit_backgrounds_changed()

    def _prepare_image_set_source(self, paths, core_path=None):
        path_list = [Path(path) for path in list(paths)]
        if not path_list:
            return None, {}, []

        images = []
        for path in path_list:
            image = QImage(str(path))
            if image.isNull():
                continue
            images.append((path, image))
        if not images:
            return None, {}, []

        max_dim = max(max(1, max(image.width(), image.height())) for _path, image in images)
        if max_dim > 1600:
            scale = 1600.0 / float(max_dim)
            resized = []
            for path, image in images:
                resized.append(
                    (
                        path,
                        image.scaled(
                            int(round(image.width() * scale)),
                            int(round(image.height() * scale)),
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation,
                        ),
                    )
                )
            images = resized

        base_path = Path(core_path) if core_path else choose_image_set_core_path([path for path, _image in images])
        base_image = None
        for path, image in images:
            if path == base_path:
                base_image = QImage(image)
                break
        if base_image is None:
            base_path, base_image = images[0]

        target_width = max(1, int(base_image.width()))
        target_height = max(1, int(base_image.height()))
        normalized = []
        for path, image in images:
            current = QImage(image)
            if current.width() != target_width or current.height() != target_height:
                current = current.scaled(target_width, target_height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            normalized.append((path, current.convertToFormat(QImage.Format_ARGB32)))

        base_image = next(QImage(image) for path, image in normalized if path == base_path)
        raw_sets = [(path, image.constBits().tobytes()) for path, image in normalized]
        size_in_bytes = target_width * target_height * 4
        core_data = bytearray(size_in_bytes)
        shell_data = {path: bytearray(size_in_bytes) for path, _image in normalized}
        base_raw = base_image.constBits().tobytes()
        soft_threshold = 56.0
        hard_threshold = 112.0

        for offset in range(0, size_in_bytes, 4):
            blue_values = [raw[offset] for _path, raw in raw_sets]
            green_values = [raw[offset + 1] for _path, raw in raw_sets]
            red_values = [raw[offset + 2] for _path, raw in raw_sets]
            spread = max(
                max(blue_values) - min(blue_values),
                max(green_values) - min(green_values),
                max(red_values) - min(red_values),
            )

            if spread <= soft_threshold:
                core_alpha = 255
            elif spread >= hard_threshold:
                core_alpha = 0
            else:
                blend = 1.0 - ((spread - soft_threshold) / (hard_threshold - soft_threshold))
                core_alpha = max(0, min(255, int(round(255.0 * blend))))
            shell_alpha = 255 - core_alpha

            if core_alpha > 0:
                core_data[offset] = base_raw[offset]
                core_data[offset + 1] = base_raw[offset + 1]
                core_data[offset + 2] = base_raw[offset + 2]
                core_data[offset + 3] = core_alpha

            if shell_alpha <= 0:
                continue

            for path, raw in raw_sets:
                shell_bytes = shell_data[path]
                shell_bytes[offset] = raw[offset]
                shell_bytes[offset + 1] = raw[offset + 1]
                shell_bytes[offset + 2] = raw[offset + 2]
                shell_bytes[offset + 3] = shell_alpha

        core_image = QImage(target_width, target_height, QImage.Format_ARGB32)
        core_bits = core_image.bits()
        core_bits[:size_in_bytes] = bytes(core_data)

        shell_images = {}
        stage_labels = []
        for path, _image in normalized:
            shell_image = QImage(target_width, target_height, QImage.Format_ARGB32)
            shell_bits = shell_image.bits()
            shell_bits[:size_in_bytes] = bytes(shell_data[path])
            shell_images[path.stem] = shell_image
            stage_labels.append(path.stem)

        return core_image, shell_images, stage_labels

    def _make_stage_snapshot(self, transform: QTransform, color: QColor, variant_params=None, variant_key: str = "", stage_label: str = ""):
        return {
            "transform": QTransform(transform),
            "color": QColor(color),
            "variant_params": normalize_image_variant_params(variant_params),
            "variant_key": str(variant_key or ""),
            "stage_label": str(stage_label or ""),
        }

    def _lerp_color(self, start: QColor, end: QColor, t: float):
        return development_lerp_color(start, end, t)

    def _lerp_transform(self, start: QTransform, end: QTransform, t: float):
        return QTransform(
            start.m11() + ((end.m11() - start.m11()) * t),
            start.m12() + ((end.m12() - start.m12()) * t),
            start.m13() + ((end.m13() - start.m13()) * t),
            start.m21() + ((end.m21() - start.m21()) * t),
            start.m22() + ((end.m22() - start.m22()) * t),
            start.m23() + ((end.m23() - start.m23()) * t),
            start.m31() + ((end.m31() - start.m31()) * t),
            start.m32() + ((end.m32() - start.m32()) * t),
            start.m33() + ((end.m33() - start.m33()) * t),
        )

    def _interpolate_snapshot(self, start_snapshot, end_snapshot, t: float):
        clamped = max(0.0, min(1.0, float(t)))
        if clamped <= 0.0:
            return self._make_stage_snapshot(
                start_snapshot["transform"],
                start_snapshot["color"],
                variant_params=start_snapshot.get("variant_params"),
                variant_key=start_snapshot.get("variant_key", ""),
                stage_label=start_snapshot.get("stage_label", ""),
            )
        if clamped >= 1.0:
            return self._make_stage_snapshot(
                end_snapshot["transform"],
                end_snapshot["color"],
                variant_params=end_snapshot.get("variant_params"),
                variant_key=end_snapshot.get("variant_key", ""),
                stage_label=end_snapshot.get("stage_label", ""),
            )
        variant_key = start_snapshot.get("variant_key", "") if clamped < 0.5 else end_snapshot.get("variant_key", "")
        stage_label = start_snapshot.get("stage_label", "") if clamped < 0.5 else end_snapshot.get("stage_label", "")
        return {
            "transform": self._lerp_transform(start_snapshot["transform"], end_snapshot["transform"], clamped),
            "color": self._lerp_color(start_snapshot["color"], end_snapshot["color"], clamped),
            "variant_params": self._lerp_image_variant_params(
                start_snapshot.get("variant_params"),
                end_snapshot.get("variant_params"),
                clamped,
            ),
            "variant_key": str(variant_key or ""),
            "stage_label": str(stage_label or ""),
        }

    def _snapshot_with_alpha_scale(self, snapshot, alpha_scale: float):
        scaled = self._make_stage_snapshot(
            snapshot["transform"],
            snapshot["color"],
            variant_params=snapshot.get("variant_params"),
            variant_key=snapshot.get("variant_key", ""),
            stage_label=snapshot.get("stage_label", ""),
        )
        color = QColor(scaled["color"])
        color.setAlpha(max(0, min(255, int(round(color.alpha() * max(0.0, float(alpha_scale)))))))
        scaled["color"] = color
        return scaled

    def _transition_clip_rect(self, mode: str, progress: float, entering: bool):
        t = max(0.0, min(1.0, float(progress)))
        width = float(max(1, self.width()))
        height = float(max(1, self.height()))
        if mode == "wipe_horizontal":
            if entering:
                return QRectF(0.0, 0.0, width * t, height)
            return QRectF(width * t, 0.0, width * (1.0 - t), height)
        if mode == "wipe_vertical":
            if entering:
                return QRectF(0.0, 0.0, width, height * t)
            return QRectF(0.0, height * t, width, height * (1.0 - t))
        return None

    def _draw_fade_transition(self, p: QPainter, obj, start_snapshot, end_snapshot, progress: float):
        self._draw_snapshot_object(p, obj, self._snapshot_with_alpha_scale(start_snapshot, 1.0 - progress))
        self._draw_snapshot_object(p, obj, self._snapshot_with_alpha_scale(end_snapshot, progress))

    def _draw_wipe_transition(self, p: QPainter, obj, start_snapshot, end_snapshot, mode: str, progress: float):
        self._draw_snapshot_object(p, obj, start_snapshot, clip_rect=self._transition_clip_rect(mode, progress, False))
        self._draw_snapshot_object(p, obj, end_snapshot, clip_rect=self._transition_clip_rect(mode, progress, True))

    def _draw_scanline_transition(self, p: QPainter, obj, start_snapshot, end_snapshot, spec, progress: float):
        params = spec.get("params", {})
        direction = str(params.get("direction", "horizontal")).strip().lower()
        if direction not in ("horizontal", "vertical"):
            direction = "horizontal"

        try:
            band_px = max(4.0, float(params.get("band_px", 24)))
        except Exception:
            band_px = 24.0

        try:
            glow = max(0.0, min(1.0, float(params.get("glow", 0.25))))
        except Exception:
            glow = 0.25

        wipe_mode = "wipe_horizontal" if direction == "horizontal" else "wipe_vertical"
        self._draw_wipe_transition(p, obj, start_snapshot, end_snapshot, wipe_mode, progress)

        width = float(max(1, self.width()))
        height = float(max(1, self.height()))
        edge = (width if direction == "horizontal" else height) * max(0.0, min(1.0, float(progress)))
        half_band = band_px * 0.5

        if direction == "horizontal":
            band_start = max(0.0, edge - half_band)
            band_end = min(width, edge + half_band)
            band_rect = QRectF(band_start, 0.0, max(0.0, band_end - band_start), height)
            line_rect = QRectF(max(0.0, edge - 1.5), 0.0, min(3.0, max(0.0, width - max(0.0, edge - 1.5))), height)
        else:
            band_start = max(0.0, edge - half_band)
            band_end = min(height, edge + half_band)
            band_rect = QRectF(0.0, band_start, width, max(0.0, band_end - band_start))
            line_rect = QRectF(0.0, max(0.0, edge - 1.5), width, min(3.0, max(0.0, height - max(0.0, edge - 1.5))))

        if band_rect.width() <= 0.0 or band_rect.height() <= 0.0:
            return

        self._draw_snapshot_object(
            p,
            obj,
            self._snapshot_with_alpha_scale(end_snapshot, 0.2 + (0.25 * glow)),
            clip_rect=band_rect,
        )

        p.save()
        p.setClipRect(band_rect)
        p.fillRect(band_rect, QColor(255, 255, 255, int(round(40 + (70 * glow)))))
        p.fillRect(line_rect, QColor(255, 255, 255, int(round(110 + (110 * glow)))))
        p.restore()

    def _draw_transition_effect(self, p: QPainter, obj, start_snapshot, end_snapshot, spec, progress: float):
        spec = self._normalize_transition_spec(spec)
        effect = spec["effect"]
        progress = max(0.0, min(1.0, float(progress)))

        if effect == "cut" or progress >= 1.0:
            self._draw_snapshot_object(p, obj, end_snapshot)
            return
        if effect == "interpolate":
            self._draw_snapshot_object(p, obj, self._interpolate_snapshot(start_snapshot, end_snapshot, progress))
            return
        if effect == "fade":
            self._draw_fade_transition(p, obj, start_snapshot, end_snapshot, progress)
            return
        if effect in ("wipe_horizontal", "wipe_vertical"):
            self._draw_wipe_transition(p, obj, start_snapshot, end_snapshot, effect, progress)
            return
        if effect == "scanline_reconstruct":
            self._draw_scanline_transition(p, obj, start_snapshot, end_snapshot, spec, progress)
            return

        self._draw_snapshot_object(p, obj, self._interpolate_snapshot(start_snapshot, end_snapshot, progress))

    def _object_committed_color(self, obj):
        color = obj.get("color", obj.get("base_color", QColor(255, 255, 255)))
        return QColor(color)

    def _object_committed_variant_params(self, obj):
        return normalize_image_variant_params(obj.get("variant_params"))

    def _object_stage_snapshot(self, obj, stage_index: int):
        if stage_index <= 0:
            return None
        stages = obj.get("stages", [])
        if 1 <= stage_index <= len(stages):
            stage = stages[stage_index - 1]
            return self._make_stage_snapshot(
                stage["transform"],
                stage["color"],
                variant_params=stage.get("variant_params"),
                variant_key=stage.get("variant_key", ""),
                stage_label=stage.get("stage_label", ""),
            )
        return None

    def _object_committed_snapshot(self, obj):
        return self._make_stage_snapshot(
            self._object_base_transform(obj),
            self._object_committed_color(obj),
            variant_params=self._object_committed_variant_params(obj),
            variant_key=obj.get("variant_key", ""),
            stage_label=obj.get("variant_key", ""),
        )

    def _object_snapshot_for_beat_slot(self, obj, slot_index: int):
        beat_map = obj.get("beat_map", default_loop_stage_map(self._object_loop_slot_count(obj)))
        if not (0 <= slot_index < len(beat_map)):
            return self._object_committed_snapshot(obj)
        snapshot = self._object_stage_snapshot(obj, int(beat_map[slot_index]))
        if snapshot is not None:
            return snapshot
        return self._object_committed_snapshot(obj)

    def _object_snapshot_for_beat_step(self, obj, step_index: int):
        slot_index = self._object_slot_index_for_step(obj, step_index)
        return self._object_snapshot_for_beat_slot(obj, slot_index)

    def _object_visual_snapshot(self, obj, index: int, include_change_preview: bool = True):
        if include_change_preview and self._change_preview_enabled and self._change_preview is not None and self._change_preview.get("object_index") == index:
            return self._make_stage_snapshot(
                self._change_preview["transform"],
                self._change_preview["color"],
                variant_params=self._change_preview.get("variant_params"),
                variant_key=self._change_preview.get("variant_key", ""),
                stage_label=self._change_preview.get("stage_label", ""),
            )

        if self.beat_reactive and self._object_uses_image_set_audio_lanes(obj):
            active_key = self._ensure_image_set_audio_variant(obj)
            if active_key:
                progress = self._image_set_transition_progress(obj)
                if progress is not None:
                    from_key = str(obj.get("_audio_lane_transition_from_key", "")).strip()
                    to_key = str(obj.get("_audio_lane_transition_to_key", "")).strip()
                    if from_key and to_key:
                        start_snapshot = self._object_snapshot_for_image_set_key(obj, from_key)
                        end_snapshot = self._object_snapshot_for_image_set_key(obj, to_key)
                        return self._interpolate_snapshot(start_snapshot, end_snapshot, progress)
                return self._object_snapshot_for_image_set_key(obj, active_key)

        timeline_state = self._timeline_segment_state(obj)
        if timeline_state is not None:
            return timeline_state["snapshot"]

        if self.beat_reactive and self._beat_slot >= 0:
            if self._beat_transition_from_slot >= 0 and self._beat_transition_to_slot >= 0:
                spec = self._object_transition_spec(obj, self._object_slot_index_for_step(obj, self._beat_transition_from_slot))
                start_snapshot = self._object_snapshot_for_beat_step(obj, self._beat_transition_from_slot)
                end_snapshot = self._object_snapshot_for_beat_step(obj, self._beat_transition_to_slot)
                if spec["effect"] == "cut":
                    return end_snapshot
                progress = self._beat_transition_progress_for_spec(spec)
                if progress is not None and progress < 1.0:
                    return self._interpolate_snapshot(start_snapshot, end_snapshot, progress)
                return end_snapshot
            return self._object_snapshot_for_beat_step(obj, self._beat_slot)

        return self._object_committed_snapshot(obj)

    def _background_visual_snapshot(self, obj, index: int, include_change_preview: bool = True):
        if include_change_preview and self._background_change_preview_enabled and self._background_change_preview is not None and self._background_change_preview.get("background_index") == index:
            return self._make_stage_snapshot(
                self._background_change_preview["transform"],
                self._background_change_preview["color"],
                variant_params=self._background_change_preview.get("variant_params"),
                variant_key=self._background_change_preview.get("variant_key", ""),
                stage_label=self._background_change_preview.get("stage_label", ""),
            )

        timeline_state = self._timeline_segment_state(obj)
        if timeline_state is not None:
            return timeline_state["snapshot"]

        if self.beat_reactive and self._beat_slot >= 0:
            if self._beat_transition_from_slot >= 0 and self._beat_transition_to_slot >= 0:
                spec = self._object_transition_spec(obj, self._object_slot_index_for_step(obj, self._beat_transition_from_slot))
                start_snapshot = self._object_snapshot_for_beat_step(obj, self._beat_transition_from_slot)
                end_snapshot = self._object_snapshot_for_beat_step(obj, self._beat_transition_to_slot)
                if spec["effect"] == "cut":
                    return end_snapshot
                progress = self._beat_transition_progress_for_spec(spec)
                if progress is not None and progress < 1.0:
                    return self._interpolate_snapshot(start_snapshot, end_snapshot, progress)
                return end_snapshot
            return self._object_snapshot_for_beat_step(obj, self._beat_slot)

        return self._object_committed_snapshot(obj)

    def _ensure_change_preview(self, index: int = None):
        if index is None:
            index = self.selected_index
        if not (0 <= index < len(self.objects)):
            self._change_preview = None
            return None

        if self._change_preview is None or self._change_preview.get("object_index") != index:
            snapshot = self._object_committed_snapshot(self.objects[index])
            self._change_preview = {
                "object_index": index,
                "transform": QTransform(snapshot["transform"]),
                "color": QColor(snapshot["color"]),
                "variant_params": normalize_image_variant_params(snapshot.get("variant_params")),
                "variant_key": str(snapshot.get("variant_key", "")),
                "stage_label": str(snapshot.get("stage_label", "")),
            }
            self._apply_change_visibility_to_color(self._change_preview["color"], self.objects[index])
        return self._change_preview

    def _ensure_background_change_preview(self, index: int = None):
        if index is None:
            index = self.selected_background_index
        if not (0 <= index < len(self.backgrounds)):
            self._background_change_preview = None
            return None

        if self._background_change_preview is None or self._background_change_preview.get("background_index") != index:
            snapshot = self._object_committed_snapshot(self.backgrounds[index])
            self._background_change_preview = {
                "background_index": index,
                "transform": QTransform(snapshot["transform"]),
                "color": QColor(snapshot["color"]),
                "variant_params": normalize_image_variant_params(snapshot.get("variant_params")),
                "variant_key": str(snapshot.get("variant_key", "")),
                "stage_label": str(snapshot.get("stage_label", "")),
            }
            self._apply_change_visibility_to_color(self._background_change_preview["color"], self.backgrounds[index])
        return self._background_change_preview

    def _change_visibility_alpha(self, obj, mode: str = None):
        _ = (obj, mode)
        return 255

    def _apply_change_visibility_to_color(self, color: QColor, obj):
        if color is None or obj is None:
            return
        # Opacity belongs to the state color; keep its explicitly chosen alpha.
        return

    def _variant_params_close(self, a, b):
        left = normalize_image_variant_params(a)
        right = normalize_image_variant_params(b)
        return (
            abs(left["stroke_scale"] - right["stroke_scale"]) < 1e-6
            and abs(left["stroke_angle"] - right["stroke_angle"]) < 1e-6
            and abs(left["density"] - right["density"]) < 1e-6
            and abs(left["shell_opacity"] - right["shell_opacity"]) < 1e-6
            and left["palette_mode"] == right["palette_mode"]
            and abs(left["palette_mix"] - right["palette_mix"]) < 1e-6
        )

    def _lerp_image_variant_params(self, start_params, end_params, t: float):
        start = normalize_image_variant_params(start_params)
        end = normalize_image_variant_params(end_params)
        mix = max(0.0, min(1.0, float(t)))
        palette_mode = start["palette_mode"] if mix < 0.5 else end["palette_mode"]
        return default_image_variant_params(
            stroke_scale=start["stroke_scale"] + ((end["stroke_scale"] - start["stroke_scale"]) * mix),
            stroke_angle=start["stroke_angle"] + ((end["stroke_angle"] - start["stroke_angle"]) * mix),
            density=start["density"] + ((end["density"] - start["density"]) * mix),
            shell_opacity=start["shell_opacity"] + ((end["shell_opacity"] - start["shell_opacity"]) * mix),
            palette_mode=palette_mode,
            palette_mix=start["palette_mix"] + ((end["palette_mix"] - start["palette_mix"]) * mix),
        )

    def _transforms_close(self, a: QTransform, b: QTransform):
        return (
            abs(a.m11() - b.m11()) < 1e-6
            and abs(a.m12() - b.m12()) < 1e-6
            and abs(a.m13() - b.m13()) < 1e-6
            and abs(a.m21() - b.m21()) < 1e-6
            and abs(a.m22() - b.m22()) < 1e-6
            and abs(a.m23() - b.m23()) < 1e-6
            and abs(a.m31() - b.m31()) < 1e-6
            and abs(a.m32() - b.m32()) < 1e-6
            and abs(a.m33() - b.m33()) < 1e-6
        )

    def _transformed_snapshot(self, transform: QTransform, rotation_deg: float, tx: float, ty: float, scale: float, pivot_world: QPointF):
        delta = QTransform()
        delta.translate(pivot_world.x() + float(tx), pivot_world.y() + float(ty))
        delta.rotate(float(rotation_deg))
        delta.scale(max(0.01, float(scale)), max(0.01, float(scale)))
        delta.translate(-pivot_world.x(), -pivot_world.y())
        return QTransform(transform) * delta

    def _object_base_transform(self, obj):
        return obj.get("transform", QTransform())

    def _object_pivot_local(self, obj):
        pivot = obj.get("pivot")
        if isinstance(pivot, QPointF):
            return QPointF(pivot)

        bounds = self._object_bounds_local(obj)
        if bounds.width() > 0.0 and bounds.height() > 0.0:
            return bounds.center()
        return QPointF(0.0, 0.0)

    def _object_pivot_world(self, obj, index: int = -1, display: bool = False):
        if display and index >= 0:
            transform = self._object_visual_snapshot(obj, index)["transform"]
        else:
            transform = self._object_base_transform(obj)
        return transform.map(self._object_pivot_local(obj))

    def _background_pivot_world(self, obj, index: int = -1, display: bool = False):
        if display and index >= 0:
            transform = self._background_visual_snapshot(obj, index)["transform"]
        else:
            transform = self._object_base_transform(obj)
        return transform.map(self._object_pivot_local(obj))

    def _scene_collection(self, kind: str):
        return self.backgrounds if str(kind) == "background" else self.objects

    def _selected_scene_index(self, kind: str):
        return self.selected_background_index if str(kind) == "background" else self.selected_index

    def _ensure_preview_for_kind(self, kind: str, index: int = None):
        return self._ensure_background_change_preview(index) if str(kind) == "background" else self._ensure_change_preview(index)

    def _clear_preview_for_kind(self, kind: str):
        if str(kind) == "background":
            self._clear_background_change_preview()
        else:
            self._clear_change_preview()

    def _pivot_world_for_kind(self, kind: str, obj, index: int, display: bool = False):
        if str(kind) == "background":
            return self._background_pivot_world(obj, index, display=display)
        return self._object_pivot_world(obj, index, display=display)

    def _set_object_pivot_world(self, index: int, pos: QPointF):
        if not (0 <= index < len(self.objects)):
            return

        obj = self.objects[index]
        current_transform = self._object_visual_snapshot(obj, index)["transform"] if self.tool == "change" else self._object_base_transform(obj)
        inverse, invertible = current_transform.inverted()
        obj["pivot"] = inverse.map(pos) if invertible else QPointF(pos)
        self.update()

    def _apply_transform_to_object(
        self,
        index: int,
        rotation_deg: float,
        tx: float,
        ty: float,
        scale: float,
        pivot_world: QPointF = None,
    ):
        if not (0 <= index < len(self.objects)):
            return

        obj = self.objects[index]
        if pivot_world is None:
            pivot_world = self._object_pivot_world(obj)
        else:
            pivot_world = QPointF(pivot_world)

        delta = QTransform()
        delta.translate(pivot_world.x() + float(tx), pivot_world.y() + float(ty))
        delta.rotate(float(rotation_deg))
        delta.scale(max(0.01, float(scale)), max(0.01, float(scale)))
        delta.translate(-pivot_world.x(), -pivot_world.y())
        obj["transform"] = self._object_base_transform(obj) * delta

    def _prepend_transform_to_object(self, index: int, delta: QTransform):
        if not (0 <= index < len(self.objects)):
            return
        self.objects[index]["transform"] = self._object_base_transform(self.objects[index]) * delta

    def _reflection_transform(self, a: QPointF, b: QPointF):
        dx = b.x() - a.x()
        dy = b.y() - a.y()
        if math.hypot(dx, dy) < 1e-6:
            return None

        angle_deg = math.degrees(math.atan2(dy, dx))
        delta = QTransform()
        delta.translate(a.x(), a.y())
        delta.rotate(angle_deg)
        delta.scale(1.0, -1.0)
        delta.rotate(-angle_deg)
        delta.translate(-a.x(), -a.y())
        return delta

    def _rotation_angle_from(self, pivot: QPointF, pos: QPointF):
        return math.atan2(pos.y() - pivot.y(), pos.x() - pivot.x())

    def _angle_delta_deg(self, start_angle: float, end_angle: float):
        delta = math.degrees(end_angle - start_angle)
        while delta <= -180.0:
            delta += 360.0
        while delta > 180.0:
            delta -= 360.0
        return delta

    def _begin_select_gesture(self, pos: QPointF):
        self._select_hover_pos = QPointF(pos)
        target_kind = self._change_target_kind
        collection = self._scene_collection(target_kind)
        selected_index = self._selected_scene_index(target_kind)
        picked = self._pick_object_at(pos) if target_kind == "object" else selected_index

        if self.select_transform_mode == "translate":
            if target_kind == "object":
                if picked >= 0:
                    self.set_selected_object(picked)
                    self._ensure_change_preview(picked)
                    self._select_gesture = {
                        "mode": "pending_translate",
                        "object_index": picked,
                        "target_kind": target_kind,
                        "press_pos": QPointF(pos),
                        "last_pos": QPointF(pos),
                    }
                    return True

                self.set_selected_object(-1)
                self._select_gesture = None
                return False

            if not (0 <= selected_index < len(collection)):
                self._select_gesture = None
                return False
            self._ensure_background_change_preview(selected_index)
            self._select_gesture = {
                "mode": "pending_translate",
                "object_index": selected_index,
                "target_kind": target_kind,
                "press_pos": QPointF(pos),
                "last_pos": QPointF(pos),
            }
            return True

        if target_kind == "object" and not (0 <= self.selected_index < len(self.objects)) and picked >= 0:
            self.set_selected_object(picked)

        selected_index = self._selected_scene_index(target_kind)
        if not (0 <= selected_index < len(collection)):
            if target_kind == "object":
                self.set_selected_object(-1)
            self._select_gesture = None
            return False

        if self.select_transform_mode == "rotate":
            self._ensure_preview_for_kind(target_kind, selected_index)
            pivot = self._pivot_world_for_kind(target_kind, collection[selected_index], selected_index, display=True)
            self._select_gesture = {
                "mode": "rotate",
                "object_index": selected_index,
                "target_kind": target_kind,
                "press_pos": QPointF(pos),
                "last_pos": QPointF(pos),
                "pivot_world": pivot,
                "last_angle": self._rotation_angle_from(pivot, pos),
            }
            return True

        if self.select_transform_mode == "scale":
            self._ensure_preview_for_kind(target_kind, selected_index)
            pivot = self._pivot_world_for_kind(target_kind, collection[selected_index], selected_index, display=True)
            radius = math.hypot(pos.x() - pivot.x(), pos.y() - pivot.y())
            self._select_gesture = {
                "mode": "scale",
                "object_index": selected_index,
                "target_kind": target_kind,
                "press_pos": QPointF(pos),
                "last_pos": QPointF(pos),
                "pivot_world": pivot,
                "last_radius": max(1e-6, radius),
            }
            return True

        if self.select_transform_mode == "reflect":
            self._ensure_preview_for_kind(target_kind, selected_index)
            self._select_gesture = {
                "mode": "pending_reflect_point",
                "object_index": selected_index,
                "target_kind": target_kind,
                "press_pos": QPointF(pos),
                "last_pos": QPointF(pos),
            }
            return True

        self._select_gesture = None
        return False

    def _update_select_gesture(self, pos: QPointF):
        if self._select_gesture is None:
            return False

        gesture = self._select_gesture
        self._select_hover_pos = QPointF(pos)
        move_dx = pos.x() - gesture["press_pos"].x()
        move_dy = pos.y() - gesture["press_pos"].y()
        moved_far_enough = math.hypot(move_dx, move_dy) >= 6.0

        if gesture["mode"] in ("pending_translate", "translate"):
            if gesture["mode"] == "pending_translate" and moved_far_enough:
                gesture["mode"] = "translate"

            if gesture["mode"] == "translate":
                delta_x = pos.x() - gesture["last_pos"].x()
                delta_y = pos.y() - gesture["last_pos"].y()
                if abs(delta_x) > 1e-6 or abs(delta_y) > 1e-6:
                    target_kind = gesture.get("target_kind", "object")
                    preview = self._ensure_preview_for_kind(target_kind, gesture["object_index"])
                    if preview is not None:
                        collection = self._scene_collection(target_kind)
                        pivot = self._pivot_world_for_kind(target_kind, collection[gesture["object_index"]], gesture["object_index"], display=True)
                        preview["transform"] = self._transformed_snapshot(preview["transform"], 0.0, delta_x, delta_y, 1.0, pivot)
                    gesture["last_pos"] = QPointF(pos)
                    self.update()
                return True
            return False

        if gesture["mode"] in ("rotate",):
            pivot_world = QPointF(gesture["pivot_world"])
            current_angle = self._rotation_angle_from(pivot_world, pos)
            delta_deg = self._angle_delta_deg(gesture["last_angle"], current_angle)
            if abs(delta_deg) > 1e-6:
                preview = self._ensure_preview_for_kind(gesture.get("target_kind", "object"), gesture["object_index"])
                if preview is not None:
                    preview["transform"] = self._transformed_snapshot(
                        preview["transform"],
                        delta_deg,
                        0.0,
                        0.0,
                        1.0,
                        pivot_world,
                    )
                gesture["last_angle"] = current_angle
                gesture["last_pos"] = QPointF(pos)
                self.update()
            return True
            return False

        if gesture["mode"] in ("scale",):
            pivot_world = QPointF(gesture["pivot_world"])
            current_radius = math.hypot(pos.x() - pivot_world.x(), pos.y() - pivot_world.y())
            last_radius = max(1e-6, float(gesture.get("last_radius", current_radius)))
            scale_ratio = max(0.01, current_radius / last_radius)
            if abs(scale_ratio - 1.0) > 1e-4:
                preview = self._ensure_preview_for_kind(gesture.get("target_kind", "object"), gesture["object_index"])
                if preview is not None:
                    preview["transform"] = self._transformed_snapshot(
                        preview["transform"],
                        0.0,
                        0.0,
                        0.0,
                        scale_ratio,
                        pivot_world,
                    )
                gesture["last_radius"] = max(1e-6, current_radius)
                gesture["last_pos"] = QPointF(pos)
                self.update()
            return True
            return False

        if gesture["mode"] == "pending_reflect_point":
            self.update()
            return moved_far_enough

        return False

    def _finish_select_gesture(self, pos: QPointF):
        if self._select_gesture is None:
            return False

        gesture = self._select_gesture
        self._cancel_select_gesture()
        self._select_hover_pos = QPointF(pos)
        target_kind = gesture.get("target_kind", "object")

        if gesture["mode"] in ("translate", "rotate", "scale"):
            self.update()
            self.mutationCommitted.emit(f"{target_kind}_preview_transform")
            return True

        if gesture["mode"] == "pending_reflect_point":
            collection = self._scene_collection(target_kind)
            selected_index = gesture.get("object_index", self._selected_scene_index(target_kind))
            if not (0 <= selected_index < len(collection)):
                self._clear_select_mode_state()
                self.update()
                return False

            pos = QPointF(pos)
            if self._reflect_anchor_world is None:
                self._reflect_anchor_world = QPointF(pos)
                self.update()
                return True

            delta = self._reflection_transform(self._reflect_anchor_world, pos)
            if delta is None:
                self._reflect_anchor_world = QPointF(pos)
                self.update()
                return True

            preview = self._ensure_preview_for_kind(target_kind, selected_index)
            if preview is not None:
                preview["transform"] = QTransform(preview["transform"]) * delta
            self._clear_select_mode_state()
            self.update()
            self.mutationCommitted.emit(f"{target_kind}_preview_transform")
            return True

        self.update()
        return gesture["mode"] == "pending_translate"

    def _object_display_transform(self, obj, index: int):
        if obj.get("kind") == "background_variant":
            return self._background_visual_snapshot(obj, index)["transform"]
        return self._object_visual_snapshot(obj, index)["transform"]

    def refresh_object_list(self):
        self._emit_objects_changed()

    def refresh_background_list(self):
        self._emit_backgrounds_changed()

    def _emit_objects_changed(self):
        labels = [self._object_label(i, obj) for i, obj in enumerate(self.objects)]
        metadata = [self._object_metadata(obj) for obj in self.objects]
        for index, obj in enumerate(self.objects):
            preview = self._change_preview
            color = preview["color"] if preview is not None and preview.get("object_index") == index else self._object_committed_color(obj)
            metadata[index]["opacity_percent"] = int(round(color.alphaF() * 100))
        self.objectsChanged.emit(labels, self.selected_index, metadata)

    def _emit_backgrounds_changed(self):
        labels = [self._object_label(i, obj) for i, obj in enumerate(self.backgrounds)]
        metadata = [self._object_metadata(obj) for obj in self.backgrounds]
        self.backgroundsChanged.emit(labels, self.selected_background_index, metadata)

    def _image_set_stage_preview_image(self, obj, label: str):
        core_image = obj.get("core_image")
        shell_images = obj.get("variant_shell_images", {})
        shell_image = shell_images.get(str(label), None) if isinstance(shell_images, dict) else None
        if core_image is None or core_image.isNull():
            return QImage()

        width = max(1, int(core_image.width()))
        height = max(1, int(core_image.height()))
        composed = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        composed.fill(Qt.black)

        painter = QPainter(composed)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        if shell_image is not None and not shell_image.isNull():
            painter.drawImage(0, 0, shell_image)
        painter.drawImage(0, 0, core_image)
        painter.end()
        return composed.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _image_set_stage_preview_items(self, obj):
        stage_labels = list(obj.get("variant_stage_labels", []))
        items = []
        for stage_index, label in enumerate(stage_labels, start=1):
            axes = parse_image_set_stage_axes(label) or {}
            tooltip = f'{label} | high-hat {axes.get("texture", "-")} | bass {axes.get("atmosphere", "-")} | kick {axes.get("rhythm", "-")}'
            items.append(
                {
                    "stage_index": stage_index,
                    "label": str(label),
                    "preview": self._image_set_stage_preview_image(obj, label),
                    "tooltip": tooltip,
                    "texture": str(axes.get("texture", "")),
                    "atmosphere": str(axes.get("atmosphere", "")),
                    "rhythm": str(axes.get("rhythm", "")),
                }
            )

        def sort_key(item):
            texture = item.get("texture", "")
            atmosphere = item.get("atmosphere", "")
            rhythm = item.get("rhythm", "")
            texture_index = IMAGE_SET_TEXTURE_ORDER.index(texture) if texture in IMAGE_SET_TEXTURE_ORDER else len(IMAGE_SET_TEXTURE_ORDER)
            atmosphere_index = IMAGE_SET_ATMOSPHERE_ORDER.index(atmosphere) if atmosphere in IMAGE_SET_ATMOSPHERE_ORDER else len(IMAGE_SET_ATMOSPHERE_ORDER)
            rhythm_index = IMAGE_SET_RHYTHM_ORDER.index(rhythm) if rhythm in IMAGE_SET_RHYTHM_ORDER else len(IMAGE_SET_RHYTHM_ORDER)
            return (texture_index, atmosphere_index, rhythm_index, item["label"])

        return sorted(items, key=sort_key)

    def _object_metadata(self, obj):
        slot_count = self._object_loop_slot_count(obj)
        beat_map = list(obj.get("beat_map", []))[:slot_count]
        while len(beat_map) < slot_count:
            beat_map.append(0)
        beat_transitions = [self._normalize_transition_spec(value) for value in list(obj.get("beat_transitions", default_transition_specs(slot_count)))[:slot_count]]
        while len(beat_transitions) < slot_count:
            beat_transitions.append(self._default_transition_spec())
        stage_count = len(obj.get("stages", []))
        stage_labels = list(obj.get("variant_stage_labels", []))
        while len(stage_labels) < stage_count:
            stage_labels.append(f"Stage {len(stage_labels) + 1}")
        timeline_points = normalize_loop_timeline_points(
            obj.get("timeline_points", []),
            slot_count,
            stage_count,
            beat_map=beat_map,
            beat_transitions=beat_transitions,
        )
        return {
            "kind": obj.get("kind", ""),
            "stage_count": stage_count,
            "slot_count": slot_count,
            "beat_map": beat_map,
            "beat_transitions": beat_transitions,
            "timeline_points": timeline_points,
            "variant_params": normalize_image_variant_params(obj.get("variant_params")),
            "variant_source_mode": str(obj.get("variant_source_mode", "generated")),
            "stage_labels": stage_labels,
            "image_set_switch_time": max(0.0, float(obj.get("image_set_switch_time", default_image_set_switch_time()))),
            "image_set_timing_mode": self._image_set_timing_mode(obj),
            "image_set_timing_translation": self._image_set_timing_translation(obj),
            "image_set_timing_pause": self._image_set_timing_pause(obj),
            "image_set_live_codes": {
                "texture": self._image_set_texture_code,
                "atmosphere": self._image_set_atmosphere_code,
                "rhythm": self._image_set_rhythm_code,
            },
            "image_set_live_key": str(obj.get("_audio_lane_live_key", obj.get("variant_key", ""))),
            "image_set_target_key": str(obj.get("_audio_lane_transition_to_key", "")),
            "image_set_preview_items": self._image_set_stage_preview_items(obj)
            if str(obj.get("kind", "")) == "image_variant" and str(obj.get("variant_source_mode", "")) == "image_set"
            else [],
        }

    def _object_label(self, index: int, obj):
        if obj["kind"] == "stroke":
            label = DEVELOPMENT_BRUSH_STYLE_LABELS.get(obj.get("brush_style", "circle"), "Brush")
        elif obj["kind"] == "text":
            preview = str(obj.get("text", "")).replace("\n", " ")
            preview = preview[:18] + ("..." if len(preview) > 18 else "")
            label = f'Text "{preview}"'
        elif obj["kind"] == "background_variant":
            label = f'Background "{str(obj.get("name", "Background"))[:18]}"'
        elif obj["kind"] == "image_variant":
            label = f'Image "{str(obj.get("name", "Variant"))[:18]}"'
        else:
            tool = obj.get("tool", "")
            if tool == "polygon":
                label = f"{DEVELOPMENT_SHAPE_TOOL_LABELS.get(tool, 'Polygon')} ({obj.get('polygon_sides', 3)})"
            else:
                label = DEVELOPMENT_SHAPE_TOOL_LABELS.get(tool, "Shape")
        stage_count = len(obj.get("stages", []))
        if stage_count > 0:
            label = f"{label} [S{stage_count}]"
        return f"{index + 1}. {label}"

    def _current_draw_color(self):
        return development_draw_color(self.color, self.brightness, self.opacity)

    def _place_text(self, pos: QPointF):
        text = str(self.text_value)
        if text == "":
            return False

        obj = {
            "kind": "text",
            "text": text,
            "pos": QPointF(pos),
            "size": max(8, int(self.text_size)),
            "color": self._current_draw_color(),
            "base_color": self._current_draw_color(),
            "transform": QTransform(),
            "pivot": None,
            "stages": [],
            "beat_map": default_loop_stage_map(),
            "beat_transitions": default_transition_specs(),
        }
        self.objects.append(obj)
        self.selected_index = len(self.objects) - 1
        self._emit_objects_changed()
        self.update()
        self.mutationCommitted.emit("create_text")
        return True

    def _stroke_size_from_pressure(self, pressure: float):
        return development_stroke_size_from_pressure(self.base_size, pressure)

    def _begin_stroke(self, pos: QPointF, size: int):
        self.drawing = True
        if self.tool == "brush":
            self.current_stroke = {
                "kind": "stroke",
                "points": [QPointF(pos)],
                "sizes": [max(1, int(size))],
                "color": self._current_draw_color(),
                "base_color": self._current_draw_color(),
                "spray": self.spray,
                "brush_style": self.brush_style,
                "transform": QTransform(),
                "pivot": None,
                "stages": [],
                "beat_map": default_loop_stage_map(),
                "beat_transitions": default_transition_specs(),
            }
        else:
            self.shape_start = QPointF(pos)
            self.shape_current = QPointF(pos)
            self.shape_preview_style = {
                "tool": self.tool,
                "size": max(1, int(size)),
                "color": self._current_draw_color(),
                "spray": self.spray,
                "filled": self.shape_filled,
                "polygon_sides": self.polygon_sides,
                "transform": QTransform(),
                "pivot": None,
            }

    def _extend_stroke(self, pos: QPointF, size: int):
        pos = QPointF(pos)
        if self.tool == "brush":
            if self.current_stroke is not None:
                self.current_stroke["points"].append(pos)
                self.current_stroke["sizes"].append(max(1, int(size)))
        else:
            self.shape_current = pos

    def _end_stroke(self, commit_shape: bool = True):
        created = False
        if self.tool == "brush":
            if commit_shape and self.current_stroke is not None and self.current_stroke["points"]:
                self.objects.append(self.current_stroke)
                self.selected_index = len(self.objects) - 1
                self._emit_objects_changed()
                created = True
        elif commit_shape and self.shape_start is not None and self.shape_current is not None and self.shape_preview_style is not None:
            obj = {
                "kind": "shape",
                "tool": self.shape_preview_style["tool"],
                "a": QPointF(self.shape_start),
                "b": QPointF(self.shape_current),
                "size": self.shape_preview_style["size"],
                "color": QColor(self.shape_preview_style["color"]),
                "base_color": QColor(self.shape_preview_style["color"]),
                "spray": self.shape_preview_style["spray"],
                "filled": self.shape_preview_style["filled"],
                "polygon_sides": self.shape_preview_style["polygon_sides"],
                "transform": QTransform(),
                "pivot": None,
                "stages": [],
                "beat_map": default_loop_stage_map(),
                "beat_transitions": default_transition_specs(),
            }
            self.objects.append(obj)
            self.selected_index = len(self.objects) - 1
            self._emit_objects_changed()
            created = True

        self.drawing = False
        self.shape_start = None
        self.shape_current = None
        self.shape_preview_style = None
        self.current_stroke = None
        self.active_input = None
        self.update()
        if created:
            self.mutationCommitted.emit("create_draw_object")

    def tabletEvent(self, e: QTabletEvent):
        if self.tool in ("select", "change", "beat"):
            e.ignore()
            return

        size = self._stroke_size_from_pressure(float(e.pressure()))
        pos = QPointF(e.position())

        if e.type() == QTabletEvent.TabletPress:
            if self.tool == "text":
                self.active_input = None
                if self._place_text(pos):
                    e.accept()
                else:
                    e.ignore()
                return
            self.active_input = "tablet"
            self._begin_stroke(pos, size)
            e.accept()
        elif e.type() == QTabletEvent.TabletMove and self.active_input == "tablet":
            if self.drawing:
                self._extend_stroke(pos, size)
                e.accept()
            else:
                e.ignore()
                return
        elif e.type() == QTabletEvent.TabletRelease and self.active_input == "tablet":
            self._end_stroke()
            e.accept()
        else:
            e.ignore()
            return

        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            if self.tool == "change" and self._change_target_kind == "background":
                e.ignore()
                return
            picked = self._pick_object_at(QPointF(e.position()))
            self.set_selected_object(picked)
            e.accept()
            return

        if e.button() == Qt.LeftButton and self.active_input in (None, "mouse"):
            if self.tool == "beat":
                e.ignore()
                return
            if self.tool == "select":
                self.set_selected_object(self._pick_object_at(QPointF(e.position())))
                self.update()
                e.accept()
                return
            if self.tool == "change":
                started = self._begin_select_gesture(QPointF(e.position()))
                self.active_input = "mouse" if started else None
                self.update()
                e.accept()
                return
            if self.tool == "text":
                self.active_input = None
                if self._place_text(QPointF(e.position())):
                    e.accept()
                else:
                    e.ignore()
                return
            self.active_input = "mouse"
            self._begin_stroke(QPointF(e.position()), self.base_size)
            self.update()
            e.accept()
            return
        e.ignore()

    def mouseMoveEvent(self, e):
        if self.tool == "change":
            self._select_hover_pos = QPointF(e.position())
            if self.select_transform_mode in ("reflect", "scale"):
                self.update()

        if self.active_input == "mouse" and (e.buttons() & Qt.LeftButton):
            if self.tool == "change":
                self._update_select_gesture(QPointF(e.position()))
                e.accept()
                return
            if self.drawing:
                self._extend_stroke(QPointF(e.position()), self.base_size)
                self.update()
                e.accept()
                return
        e.ignore()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.active_input == "mouse":
            if self.tool == "change":
                self._finish_select_gesture(QPointF(e.position()))
            else:
                self._end_stroke()
            e.accept()
            return
        e.ignore()

    def leaveEvent(self, e):
        if self.tool == "change" and self._select_hover_pos is not None:
            self._select_hover_pos = None
            if self.select_transform_mode in ("reflect", "scale"):
                self.update()
        super().leaveEvent(e)

    def _spray_factor(self, spray: int):
        return development_spray_factor(spray)

    def _spray_spread(self, size: int, spray: int):
        return development_spray_spread(size, spray)

    def _spray_step(self, size: int, spray: int):
        return development_spray_step(size, spray)

    def _spray_color(self, color: QColor):
        return development_spray_color(color)

    def _draw_spray_stamp(self, p: QPainter, center: QPointF, size: int, color: QColor, spray: int):
        development_draw_spray_stamp(p, center, size, color, spray)

    def _draw_spray_line(self, p: QPainter, a: QPointF, b: QPointF, size: int, color: QColor, spray: int):
        development_draw_spray_line(p, a, b, size, color, spray)

    def _smoothed_stroke_samples(self, points, sizes):
        return development_smoothed_stroke_samples(points, sizes, self.base_size)

    def _draw_brush_stamp(self, p: QPainter, pos: QPointF, size: int, color: QColor, style: str):
        development_draw_brush_stamp(p, pos, size, color, style)

    def _draw_brush_path(self, p: QPainter, a: QPointF, b: QPointF, size: int, color: QColor, style: str):
        development_draw_brush_path(p, a, b, size, color, style)

    def _shape_pen(self, color: QColor, size: int, preview: bool = False):
        return development_shape_pen(color, size, preview=preview)

    def _regular_polygon(self, center: QPointF, vertex: QPointF, sides: int):
        return development_regular_polygon(center, vertex, sides)

    def _draw_shape_geometry(self, p: QPainter, tool: str, a: QPointF, b: QPointF, sides: int):
        development_draw_shape_geometry(p, tool, a, b, sides)

    def _shape_segments(self, tool: str, a: QPointF, b: QPointF, size: int, spray: int, sides: int):
        return development_shape_segments(tool, a, b, size, spray, sides)

    def _draw_shape_spray(self, p: QPainter, tool: str, a: QPointF, b: QPointF, size: int, color: QColor, spray: int, sides: int):
        development_draw_shape_spray(p, tool, a, b, size, color, spray, sides)

    def _text_font(self, size: int):
        font = QFont(self.font())
        font.setPixelSize(max(8, int(size)))
        return font

    def _text_layout(self, obj):
        text = str(obj.get("text", ""))
        pos = QPointF(obj.get("pos", QPointF()))
        font = self._text_font(int(obj.get("size", self.text_size)))
        metrics = QFontMetricsF(font)
        measured_text = text if text else " "
        raw_rect = metrics.boundingRect(measured_text)
        bounds = QRectF(
            pos.x(),
            pos.y(),
            max(1.0, raw_rect.width()),
            max(1.0, raw_rect.height()),
        )
        draw_pos = QPointF(pos.x() - raw_rect.left(), pos.y() - raw_rect.top())
        return text, font, bounds, draw_pos

    def _draw_stroke_object(self, p: QPainter, obj):
        points = obj.get("points", [])
        sizes = obj.get("sizes", [])
        if not points:
            return

        color = QColor(obj.get("color", QColor(255, 255, 255)))
        spray = int(obj.get("spray", 0))
        style = obj.get("brush_style", "circle")

        if len(points) == 1:
            size = max(1, int(sizes[0] if sizes else obj.get("size", self.base_size)))
            if spray > 0:
                self._draw_spray_stamp(p, points[0], size, color, spray)
            else:
                self._draw_brush_stamp(p, points[0], size, color, style)
            return

        samples = self._smoothed_stroke_samples(points, sizes)
        for pos, size in samples:
            if spray > 0:
                self._draw_spray_stamp(p, pos, size, color, spray)
            else:
                self._draw_brush_stamp(p, pos, size, color, style)

    def _draw_shape_object(self, p: QPainter, obj, preview: bool = False):
        tool = obj.get("tool", "line")
        a = obj.get("a", QPointF())
        b = obj.get("b", QPointF())
        size = max(1, int(obj.get("size", self.base_size)))
        color = QColor(obj.get("color", QColor(255, 255, 255)))
        spray = int(obj.get("spray", 0))
        filled = bool(obj.get("filled", False))
        sides = int(obj.get("polygon_sides", 3))

        can_fill = filled and tool in ("circle", "rectangle", "polygon")
        if preview:
            p.setPen(self._shape_pen(color, size, preview=True))
            if can_fill:
                fill = QColor(color)
                fill.setAlpha(max(20, int(fill.alpha() * 0.35)))
                p.setBrush(fill)
            else:
                p.setBrush(Qt.NoBrush)
            self._draw_shape_geometry(p, tool, a, b, sides)
            return

        if spray > 0:
            if can_fill:
                p.setPen(Qt.NoPen)
                p.setBrush(color)
                self._draw_shape_geometry(p, tool, a, b, sides)
            self._draw_shape_spray(p, tool, a, b, size, color, spray, sides)
            return

        p.setPen(self._shape_pen(color, size))
        p.setBrush(color if can_fill else Qt.NoBrush)
        self._draw_shape_geometry(p, tool, a, b, sides)

    def _draw_text_object(self, p: QPainter, obj):
        text, font, _, draw_pos = self._text_layout(obj)
        if text == "":
            return
        color = QColor(obj.get("color", QColor(255, 255, 255)))
        p.setPen(color)
        p.setFont(font)
        p.drawText(draw_pos, text)

    def _draw_image_variant_object(self, p: QPainter, obj):
        development_draw_image_variant_object(
            p,
            obj,
            self._audio_low,
            self._audio_mid,
            self._audio_high,
            self._beat_pulse,
        )

    def _draw_object_body(self, p: QPainter, obj, preview: bool = False):
        if obj.get("kind") == "stroke":
            self._draw_stroke_object(p, obj)
        elif obj.get("kind") == "shape":
            self._draw_shape_object(p, obj, preview=preview)
        elif obj.get("kind") == "text":
            self._draw_text_object(p, obj)
        elif obj.get("kind") == "image_variant":
            self._draw_image_variant_object(p, obj)

    def _draw_snapshot_object(self, p: QPainter, obj, snapshot=None, preview: bool = False, clip_rect: QRectF = None):
        draw_obj = dict(obj)
        if snapshot is not None:
            draw_obj["transform"] = QTransform(snapshot["transform"])
            draw_obj["color"] = QColor(snapshot["color"])
            draw_obj["variant_params"] = normalize_image_variant_params(snapshot.get("variant_params"))
            draw_obj["variant_key"] = str(snapshot.get("variant_key", obj.get("variant_key", "")))
        p.save()
        if clip_rect is not None and clip_rect.width() > 0.0 and clip_rect.height() > 0.0:
            p.setClipRect(clip_rect)
        p.setTransform(self._object_base_transform(draw_obj), True)
        self._draw_object_body(p, draw_obj, preview=preview)
        p.restore()

    def _draw_object(self, p: QPainter, obj, index: int = -1, preview: bool = False, include_change_preview: bool = True):
        if preview or index < 0:
            self._draw_snapshot_object(p, obj, preview=preview)
            return

        if self.beat_reactive and self._object_uses_image_set_audio_lanes(obj):
            active_key = self._ensure_image_set_audio_variant(obj)
            progress = self._image_set_transition_progress(obj)
            if progress is not None:
                from_key = str(obj.get("_audio_lane_transition_from_key", "")).strip()
                to_key = str(obj.get("_audio_lane_transition_to_key", "")).strip()
                if from_key and to_key:
                    spec = self._image_set_transition_spec()
                    start_snapshot = self._object_snapshot_for_image_set_key(obj, from_key)
                    end_snapshot = self._object_snapshot_for_image_set_key(obj, to_key)
                    self._draw_transition_effect(p, obj, start_snapshot, end_snapshot, spec, progress)
                    return
            if active_key:
                self._draw_snapshot_object(p, obj, self._object_snapshot_for_image_set_key(obj, active_key))
                return

        timeline_state = self._timeline_segment_state(obj)
        if timeline_state is not None:
            if timeline_state["transition_active"]:
                self._draw_transition_effect(
                    p,
                    obj,
                    timeline_state["start_snapshot"],
                    timeline_state["end_snapshot"],
                    timeline_state["spec"],
                    timeline_state["progress"],
                )
                return
            self._draw_snapshot_object(p, obj, timeline_state["snapshot"])
            return

        if (
            self.beat_reactive
            and self._beat_transition_from_slot >= 0
            and self._beat_transition_to_slot >= 0
        ):
            if self._beat_transition_progress() is not None:
                spec = self._object_transition_spec(obj, self._object_slot_index_for_step(obj, self._beat_transition_from_slot))
                start_snapshot = self._object_snapshot_for_beat_step(obj, self._beat_transition_from_slot)
                end_snapshot = self._object_snapshot_for_beat_step(obj, self._beat_transition_to_slot)
                progress = self._beat_transition_progress_for_spec(spec)
                if progress is not None:
                    self._draw_transition_effect(p, obj, start_snapshot, end_snapshot, spec, progress)
                    return

        self._draw_snapshot_object(p, obj, self._object_visual_snapshot(obj, index, include_change_preview=include_change_preview))

    def _draw_background_object(self, p: QPainter, obj, index: int = -1, include_change_preview: bool = True):
        timeline_state = self._timeline_segment_state(obj)
        if timeline_state is not None:
            if timeline_state["transition_active"]:
                self._draw_background_transition_effect(
                    p,
                    obj,
                    timeline_state["start_snapshot"],
                    timeline_state["end_snapshot"],
                    timeline_state["spec"],
                    timeline_state["progress"],
                )
                return
            self._draw_background_snapshot(p, obj, timeline_state["snapshot"])
            return

        if (
            self.beat_reactive
            and self._beat_transition_from_slot >= 0
            and self._beat_transition_to_slot >= 0
        ):
            if self._beat_transition_progress() is not None:
                spec = self._object_transition_spec(obj, self._object_slot_index_for_step(obj, self._beat_transition_from_slot))
                start_snapshot = self._object_snapshot_for_beat_step(obj, self._beat_transition_from_slot)
                end_snapshot = self._object_snapshot_for_beat_step(obj, self._beat_transition_to_slot)
                progress = self._beat_transition_progress_for_spec(spec)
                if progress is not None:
                    self._draw_background_transition_effect(p, obj, start_snapshot, end_snapshot, spec, progress)
                    return

        self._draw_background_snapshot(p, obj, self._background_visual_snapshot(obj, index, include_change_preview=include_change_preview))

    def _draw_background_snapshot(self, p: QPainter, obj, snapshot, clip_rect: QRectF = None, opacity_scale: float = 1.0):
        variant_key = str(snapshot.get("variant_key", obj.get("variant_key", ""))) if snapshot else str(obj.get("variant_key", ""))
        shell_images = obj.get("variant_shell_images", {})
        image = shell_images.get(variant_key) if isinstance(shell_images, dict) and variant_key in shell_images else None
        if image is None and isinstance(shell_images, dict) and shell_images:
            image = next(iter(shell_images.values()))
        if image is None or image.isNull():
            return

        transform = QTransform(snapshot["transform"]) if snapshot is not None else self._object_base_transform(obj)
        color = QColor(snapshot["color"]) if snapshot is not None else self._object_committed_color(obj)
        rect = QRectF(obj.get("rect", QRectF()))
        rect = self._background_render_rect(rect)

        p.save()
        if clip_rect is not None and clip_rect.width() > 0.0 and clip_rect.height() > 0.0:
            p.setClipRect(clip_rect)
        p.setOpacity(p.opacity() * max(0.0, min(1.0, (color.alpha() / 255.0) * float(opacity_scale))))
        p.setTransform(transform, True)
        p.drawImage(rect, image)
        p.restore()

    def _background_render_rect(self, rect: QRectF):
        base_rect = QRectF(rect)
        if base_rect.isNull():
            return base_rect
        cover_size = self._render_background_cover_size
        if cover_size is None:
            return base_rect
        try:
            cover_width = float(max(1.0, cover_size.width()))
            cover_height = float(max(1.0, cover_size.height()))
        except Exception:
            return base_rect
        scale = max(
            cover_width / max(1.0, base_rect.width()),
            cover_height / max(1.0, base_rect.height()),
        )
        if scale <= 1.0 + 1e-6:
            return base_rect
        center = base_rect.center()
        expanded = QRectF(base_rect)
        expanded.setSize(QSizeF(base_rect.width() * scale, base_rect.height() * scale))
        expanded.moveCenter(center)
        return expanded

    def _draw_background_transition_effect(self, p: QPainter, obj, start_snapshot, end_snapshot, spec, progress):
        spec = self._normalize_transition_spec(spec)
        effect = spec.get("effect", "cut")
        progress = max(0.0, min(1.0, float(progress)))
        if effect == "cut" or progress >= 1.0:
            self._draw_background_snapshot(p, obj, end_snapshot)
            return
        if effect == "interpolate":
            self._draw_background_snapshot(p, obj, self._interpolate_snapshot(start_snapshot, end_snapshot, progress))
            return
        if effect == "fade":
            self._draw_background_snapshot(p, obj, start_snapshot, opacity_scale=1.0 - progress)
            self._draw_background_snapshot(p, obj, end_snapshot, opacity_scale=progress)
            return
        if effect in ("wipe_horizontal", "wipe_vertical"):
            self._draw_background_snapshot(p, obj, start_snapshot, clip_rect=self._transition_clip_rect(effect, progress, False))
            self._draw_background_snapshot(p, obj, end_snapshot, clip_rect=self._transition_clip_rect(effect, progress, True))
            return
        self._draw_background_snapshot(p, obj, self._interpolate_snapshot(start_snapshot, end_snapshot, progress))

    def _blend_images(self, img1: QImage, img2: QImage, progress: float):
        # Simple blend for interpolation
        if img1.size() != img2.size():
            # Resize img2 to img1 size
            img2 = img2.scaled(img1.size())
        result = QImage(img1.size(), QImage.Format_ARGB32)
        result.fill(Qt.transparent)
        painter = QPainter(result)
        painter.setOpacity(1.0 - progress)
        painter.drawImage(0, 0, img1)
        painter.setOpacity(progress)
        painter.drawImage(0, 0, img2)
        painter.end()
        return result

    def _draw_image_scaled(self, p: QPainter, image: QImage, canvas_rect: QRectF):
        scaled_rect = QRectF(0, 0, image.width(), image.height())
        scaled_rect.moveCenter(canvas_rect.center())
        scale_x = canvas_rect.width() / image.width()
        scale_y = canvas_rect.height() / image.height()
        scale = max(scale_x, scale_y)
        scaled_rect.setSize(QSizeF(image.width() * scale, image.height() * scale))
        scaled_rect.moveCenter(canvas_rect.center())
        p.drawImage(scaled_rect, image)

    def _object_bounds_local(self, obj):
        if obj.get("kind") == "stroke":
            points = obj.get("points", [])
            if not points:
                return QRectF()
            min_x = min(pt.x() for pt in points)
            max_x = max(pt.x() for pt in points)
            min_y = min(pt.y() for pt in points)
            max_y = max(pt.y() for pt in points)
            sizes = obj.get("sizes", [])
            max_size = max(sizes) if sizes else int(obj.get("size", self.base_size))
            padding = max(1.0, max_size * 0.5)
            spray = int(obj.get("spray", 0))
            if spray > 0:
                padding = max(padding, self._spray_spread(max_size, spray))
            return QRectF(
                min_x - padding,
                min_y - padding,
                max(1.0, (max_x - min_x) + (2.0 * padding)),
                max(1.0, (max_y - min_y) + (2.0 * padding)),
            )

        if obj.get("kind") == "text":
            _, _, bounds, _ = self._text_layout(obj)
            return bounds.adjusted(-2.0, -2.0, 2.0, 2.0)

        if obj.get("kind") == "image_variant":
            rect = QRectF(obj.get("rect", QRectF()))
            if rect.isNull():
                return QRectF()
            return rect.adjusted(-4.0, -4.0, 4.0, 4.0)

        if obj.get("kind") == "background_variant":
            rect = QRectF(obj.get("rect", QRectF()))
            if rect.isNull():
                return QRectF()
            return rect.adjusted(-4.0, -4.0, 4.0, 4.0)

        tool = obj.get("tool", "line")
        a = obj.get("a", QPointF())
        b = obj.get("b", QPointF())
        if tool == "circle":
            radius = math.hypot(b.x() - a.x(), b.y() - a.y())
            rect = QRectF(a.x() - radius, a.y() - radius, radius * 2.0, radius * 2.0)
        elif tool == "rectangle" or tool == "line":
            rect = QRectF(a, b).normalized()
        elif tool == "polygon":
            poly = self._regular_polygon(a, b, int(obj.get("polygon_sides", 3)))
            rect = poly.boundingRect() if poly.count() > 0 else QRectF(a, QSize(1, 1))
        else:
            rect = QRectF(a, QSize(1, 1))

        size = max(1, int(obj.get("size", self.base_size)))
        padding = max(1.0, size * 0.5)
        spray = int(obj.get("spray", 0))
        if spray > 0:
            padding = max(padding, self._spray_spread(size, spray))
        return rect.adjusted(-padding, -padding, padding, padding)

    def _object_bounds_world(self, obj, index: int = -1, display: bool = False):
        local = self._object_bounds_local(obj)
        if local.isNull():
            return QRectF()
        transform = self._object_display_transform(obj, index) if display else self._object_base_transform(obj)
        corners = [local.topLeft(), local.topRight(), local.bottomRight(), local.bottomLeft()]
        mapped = [transform.map(pt) for pt in corners]
        min_x = min(pt.x() for pt in mapped)
        max_x = max(pt.x() for pt in mapped)
        min_y = min(pt.y() for pt in mapped)
        max_y = max(pt.y() for pt in mapped)
        return QRectF(min_x, min_y, max(1.0, max_x - min_x), max(1.0, max_y - min_y))

    def _pick_object_at(self, pos: QPointF):
        for i in range(len(self.objects) - 1, -1, -1):
            hit_rect = self._object_bounds_world(self.objects[i], i, display=True).adjusted(-4.0, -4.0, 4.0, 4.0)
            if hit_rect.contains(pos):
                return i
        return -1

    def _draw_selection_outline(self, p: QPainter):
        if self._change_target_kind == "background":
            if not (0 <= self.selected_background_index < len(self.backgrounds)):
                return
            obj = self.backgrounds[self.selected_background_index]
            rect = self._object_bounds_world(obj, self.selected_background_index, display=True)
            pivot = self._background_pivot_world(obj, self.selected_background_index, display=True)
        else:
            if not (0 <= self.selected_index < len(self.objects)):
                return
            obj = self.objects[self.selected_index]
            rect = self._object_bounds_world(obj, self.selected_index, display=True)
            pivot = self._object_pivot_world(obj, self.selected_index, display=True)
        if rect.isNull():
            return
        p.save()
        p.setPen(QPen(QColor(255, 215, 0), 1, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawRect(rect)
        c = rect.center()
        p.setPen(QPen(QColor(255, 215, 0, 160), 1, Qt.DotLine))
        p.drawLine(c, pivot)
        p.setPen(QPen(QColor(255, 215, 0), 1))
        p.drawEllipse(c, 3, 3)
        p.drawEllipse(pivot, 4, 4)
        p.drawLine(QPointF(pivot.x() - 8.0, pivot.y()), QPointF(pivot.x() + 8.0, pivot.y()))
        p.drawLine(QPointF(pivot.x(), pivot.y() - 8.0), QPointF(pivot.x(), pivot.y() + 8.0))
        p.restore()

    def _draw_transform_guide(self, p: QPainter):
        if self.tool != "change":
            return

        if self.select_transform_mode == "reflect":
            if self._reflect_anchor_world is None:
                return

            start = QPointF(self._reflect_anchor_world)
            end = QPointF(self._select_hover_pos) if self._select_hover_pos is not None else QPointF(start)

            p.save()
            p.setPen(QPen(QColor(0, 200, 255, 180), 1, Qt.DashLine))
            p.drawLine(start, end)
            p.setPen(QPen(QColor(0, 200, 255), 1))
            p.setBrush(QColor(0, 200, 255, 60))
            p.drawEllipse(start, 4, 4)
            p.drawEllipse(end, 4, 4)
            p.restore()
            return

        if self.select_transform_mode == "scale" and self._scale_pivot_ready:
            if self._change_target_kind == "background":
                if not (0 <= self.selected_background_index < len(self.backgrounds)):
                    return
                pivot = self._background_pivot_world(self.backgrounds[self.selected_background_index], self.selected_background_index, display=True)
            else:
                if not (0 <= self.selected_index < len(self.objects)):
                    return
                pivot = self._object_pivot_world(self.objects[self.selected_index], self.selected_index, display=True)
            end = QPointF(self._select_hover_pos) if self._select_hover_pos is not None else QPointF(pivot)

            p.save()
            p.setPen(QPen(QColor(120, 255, 120, 180), 1, Qt.DashLine))
            p.drawLine(pivot, end)
            p.setPen(QPen(QColor(120, 255, 120), 1))
            p.setBrush(QColor(120, 255, 120, 60))
            p.drawEllipse(pivot, 4, 4)
            p.drawEllipse(end, 4, 4)
            p.restore()

    def _draw_delete_fade(self, p: QPainter):
        fade = self._delete_fade
        if not isinstance(fade, dict):
            return
        obj = fade.get("object")
        snapshot = fade.get("snapshot")
        if not isinstance(obj, dict) or not isinstance(snapshot, dict):
            return

        duration = max(0.01, float(fade.get("duration", self._delete_fade_duration)))
        progress = min(1.0, max(0.0, (time.monotonic() - float(fade.get("started_at", 0.0))) / duration))
        alpha_scale = 1.0 - progress
        if alpha_scale <= 0.0:
            return

        faded_snapshot = self._snapshot_with_alpha_scale(snapshot, alpha_scale)
        if str(fade.get("kind", "object")) == "background":
            self._draw_background_snapshot(p, obj, faded_snapshot)
        else:
            self._draw_snapshot_object(p, obj, faded_snapshot)

    def projector_region(self):
        """One quarter by area: centered half width and half height."""
        return QRectF(self.width() * .25, self.height() * .25, self.width() * .5, self.height() * .5)

    def render_scene(
        self,
        p: QPainter,
        target_rect: QRectF = None,
        include_overlays: bool = True,
        include_live_editor_state: bool = True,
        projector: bool = False,
    ):
        source_rect = QRectF(0.0, 0.0, max(1.0, float(self.width())), max(1.0, float(self.height())))
        if target_rect is None or target_rect.isNull():
            target_rect = QRectF(source_rect)
        else:
            target_rect = QRectF(target_rect)

        if projector:
            source_rect = self.projector_region()
        scale = min(
            target_rect.width() / max(1.0, source_rect.width()),
            target_rect.height() / max(1.0, source_rect.height()),
        )
        scale = max(1e-6, scale)
        viewport_width = source_rect.width() * scale
        viewport_height = source_rect.height() * scale
        viewport = QRectF(
            target_rect.x() + ((target_rect.width() - viewport_width) * 0.5),
            target_rect.y() + ((target_rect.height() - viewport_height) * 0.5),
            viewport_width,
            viewport_height,
        )

        # Separate backgrounds and regular objects
        backgrounds = self.backgrounds
        regular_objects = [obj for obj in self.objects if not obj.get("is_background")]

        p.save()
        p.fillRect(target_rect, Qt.black)
        p.setClipRect(target_rect)
        p.translate(target_rect.x() if projector else viewport.x(), target_rect.y() if projector else viewport.y())
        p.scale(target_rect.width() / source_rect.width() if projector else scale, target_rect.height() / source_rect.height() if projector else scale)
        p.translate(-source_rect.x(), -source_rect.y())
        p.fillRect(source_rect, self._background_color())
        self._render_background_cover_size = QSizeF(
            max(1.0, float(self.width())),
            max(1.0, float(self.height())),
        )

        # Draw background objects first
        for i, obj in sorted(enumerate(backgrounds), key=lambda pair: pair[1].get("background_slot", pair[0])):
            p.save()
            # A remains the base; B's opacity gives a direct A-to-B crossfade.
            slot = obj.get("background_slot", i)
            p.setOpacity(self.background_mix if slot == 1 else (1.0 if len(backgrounds) > 1 else 1.0 - self.background_mix))
            self._draw_background_object(p, obj, index=i, include_change_preview=include_live_editor_state)
            p.restore()

        # Draw regular objects
        for i, obj in enumerate(regular_objects):
            self._draw_object(p, obj, index=self.objects.index(obj), include_change_preview=include_live_editor_state)

        self._draw_delete_fade(p)

        if include_overlays:
            p.save()
            p.setPen(QPen(QColor(120, 210, 240), 1, Qt.DashLine))
            p.drawRect(self.projector_region())
            p.restore()
            if not self.objects and not self.backgrounds and not self.drawing:
                p.save()
                hint_rect = QRectF(source_rect)
                title_font = QFont("Segoe UI", 20, QFont.Bold)
                body_font = QFont("Segoe UI", 11)

                p.setPen(QColor(240, 244, 247, 220))
                p.setFont(title_font)
                title_rect = QRectF(hint_rect.left() + 40.0, hint_rect.center().y() - 54.0, hint_rect.width() - 80.0, 36.0)
                p.drawText(title_rect, Qt.AlignHCenter | Qt.AlignVCenter, "Ready")

                p.setPen(QColor(205, 215, 222, 210))
                p.setFont(body_font)
                body_rect = QRectF(hint_rect.left() + 80.0, hint_rect.center().y() - 6.0, hint_rect.width() - 160.0, 84.0)
                p.drawText(
                    body_rect,
                    Qt.AlignHCenter | Qt.TextWordWrap,
                    "Open Object > Image to import an object, or import a background image.\nUse Change to build the object state loop.",
                )
                p.restore()
            self._draw_selection_outline(p)
            self._draw_transform_guide(p)

        # Keep transient drawing feedback on the editor canvas only.
        if include_live_editor_state and self.drawing and self.current_stroke is not None:
            self._draw_object(p, self.current_stroke)
        elif include_live_editor_state and self.drawing and self.shape_start is not None and self.shape_current is not None and self.shape_preview_style is not None:
            preview_obj = {
                "kind": "shape",
                "tool": self.shape_preview_style["tool"],
                "a": QPointF(self.shape_start),
                "b": QPointF(self.shape_current),
                "size": self.shape_preview_style["size"],
                "color": QColor(self.shape_preview_style["color"]),
                "spray": self.shape_preview_style["spray"],
                "filled": self.shape_preview_style["filled"],
                "polygon_sides": self.shape_preview_style["polygon_sides"],
                "transform": QTransform(),
                "pivot": None,
            }
            self._draw_object(p, preview_obj, preview=True)

        self._render_background_cover_size = None
        p.restore()

    def paintEvent(self, _):
        if not self._logged_first_paint:
            self._logged_first_paint = True
            log_startup_event("CanvasWidget first paint")
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        self.render_scene(p, QRectF(self.rect()), include_overlays=True)


class ImagePreparationThread(QThread):
    prepared = Signal(object, str)

    def __init__(self, path, background, parent=None):
        super().__init__(parent)
        self.path, self.background = path, background

    def run(self):
        try:
            image = QImage(self.path)
            if image.isNull():
                raise ValueError("The selected file could not be loaded as an image.")
            if self.background:
                if max(image.width(), image.height()) > 2048:
                    image = image.scaled(2048, 2048, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                result = image.convertToFormat(QImage.Format_ARGB32)
            else:
                result = CanvasWidget._prepare_image_variant_source(None, image)
                if result[0].isNull() or not result[1]:
                    raise ValueError("The image does not contain enough visible content.")
            self.prepared.emit(result, "")
        except Exception as exc:
            self.prepared.emit(None, str(exc))


class ExternalCanvasWindow(QWidget):
    closed = Signal()

    def __init__(self, canvas: CanvasWidget):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self._canvas = canvas
        self.setWindowTitle(f"{APP_NAME} Output")
        self.setStyleSheet("background-color: black;")
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(16)
        self._refresh_timer.timeout.connect(self._refresh_frame)
        self._refresh_timer.start()

    def _refresh_frame(self):
        if self.isVisible():
            self.update()

    def show_on_screen(self, screen):
        self.winId()
        handle = self.windowHandle()
        if screen is None or screen not in QGuiApplication.screens():
            return
        if handle is not None and handle.screen() is not screen:
            handle.setScreen(screen)
        geometry = screen.geometry()
        if self.geometry() != geometry:
            self.setGeometry(geometry)
        if not self.isFullScreen():
            self.showFullScreen()
        self.raise_()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        self._canvas.render_scene(
            p,
            QRectF(self.rect()),
            include_overlays=False,
            include_live_editor_state=False,
            projector=True,
        )

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
            e.accept()
            return
        super().keyPressEvent(e)

    def closeEvent(self, e):
        log_startup_event("ExternalCanvasWindow closeEvent")
        self.closed.emit()
        super().closeEvent(e)


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        splitter = QSplitter(Qt.Horizontal)
        icon = load_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        self.beat_detector = BeatDetector(self)
        self.media_devices = QMediaDevices(self)
        self.canvas = CanvasWidget()
        self.external_output_window = ExternalCanvasWindow(self.canvas)
        if not icon.isNull():
            self.external_output_window.setWindowIcon(icon)
        self.controls = ControlPanel()
        self._audio_refresh_timer = QTimer(self)
        self._audio_refresh_timer.setSingleShot(True)
        self._audio_refresh_timer.setInterval(500)
        self._audio_refresh_timer.timeout.connect(self._refresh_audio_sources)
        self._audio_refresh_in_progress = False
        self._history = []
        self._history_index = -1
        self._restoring_history = False
        self._text_history_pending = False
        self.controls.toolChanged.connect(self.canvas.set_tool)
        self.controls.polygonSidesChanged.connect(self.canvas.set_polygon_sides)
        self.controls.shapeFilledChanged.connect(self.canvas.set_shape_filled)
        self.controls.brushStyleChanged.connect(self.canvas.set_brush_style)
        self.controls.brushColorChanged.connect(self.canvas.set_color)
        self.controls.brushSizeChanged.connect(self.canvas.set_base_size)
        self.controls.brushBrightnessChanged.connect(self.canvas.set_brightness_percent)
        self.controls.brushOpacityChanged.connect(self.canvas.set_opacity_percent)
        self.controls.brushSprayChanged.connect(self.canvas.set_spray)
        self.controls.textValueChanged.connect(self.canvas.set_text_value)
        self.controls.textSizeChanged.connect(self.canvas.set_text_size)
        self.controls.importImageRequested.connect(self._import_image_variant)
        self.controls.importBackgroundRequested.connect(self._import_background_image)
        self.controls.backgroundImportRequested.connect(self._import_background_image)
        for slot, button in enumerate(self.controls.background_slot_buttons):
            button.clicked.connect(lambda checked=False, index=slot: self._import_background_image(index))
        self.controls.background_mix_slider.valueChanged.connect(self._set_background_mix)
        self.canvas.backgroundsChanged.connect(self._refresh_background_slots)
        self.controls.imageVariantParamsChanged.connect(self.canvas.set_image_variant_params)
        self.controls.beatEnabledChanged.connect(self.canvas.set_beat_reactive)
        self.controls.beatEnabledChanged.connect(self.beat_detector.set_enabled)
        self.controls.audioSourceChanged.connect(self.beat_detector.set_audio_source)
        self.controls.refreshAudioSourcesRequested.connect(self._refresh_audio_sources)
        self.controls.beatSensitivityChanged.connect(self.beat_detector.set_sensitivity)
        self.controls.externalOutputToggled.connect(self._set_external_output_enabled)
        self.controls.externalDisplayChanged.connect(self._set_external_display_index)
        self.controls.refreshExternalDisplaysRequested.connect(self._refresh_external_screens)
        self.controls.objectSelectionChanged.connect(self.canvas.set_selected_object)
        self.controls.backgroundSelectionChanged.connect(self.canvas.set_selected_background)
        self.controls.changeTargetChanged.connect(self._set_change_target)
        self.controls.changeOpacityChanged.connect(self.canvas.set_change_opacity_percent)
        self.controls.changeColorChanged.connect(lambda color: self._apply_change_color("object", color))
        self.controls.backgroundChangeColorChanged.connect(lambda color: self._apply_change_color("background", color))
        self.controls.changeVisibilityModeChanged.connect(lambda mode: self._apply_change_visibility_mode("object", mode))
        self.controls.backgroundChangeVisibilityModeChanged.connect(lambda mode: self._apply_change_visibility_mode("background", mode))
        self.controls.changePreviewEnabledChanged.connect(lambda enabled: self._apply_change_preview_enabled("object", enabled))
        self.controls.backgroundChangePreviewEnabledChanged.connect(lambda enabled: self._apply_change_preview_enabled("background", enabled))
        self.controls.imageSetSwitchTimeChanged.connect(self.canvas.set_image_set_switch_time)
        self.controls.imageSetTimingModeChanged.connect(self.canvas.set_image_set_timing_mode)
        self.controls.imageSetTimingTranslationChanged.connect(self.canvas.set_image_set_timing_translation)
        self.controls.imageSetTimingPauseChanged.connect(self.canvas.set_image_set_timing_pause)
        self.controls.selectedLoopTimelineChanged.connect(self.canvas.set_object_loop_timeline)
        self.controls.backgroundSelectedLoopTimelineChanged.connect(self.canvas.set_background_loop_timeline)
        self.controls.transformModeChanged.connect(self._set_transform_mode)
        self.controls.applyStageRequested.connect(self._apply_object_state)
        self.controls.backgroundApplyStageRequested.connect(self._apply_background_state)
        self.controls.resetStagePreviewRequested.connect(lambda: self._reset_change_preview("object"))
        self.controls.backgroundResetStagePreviewRequested.connect(lambda: self._reset_change_preview("background"))
        self.controls.resetStagesRequested.connect(self._reset_object_stages)
        self.controls.backgroundResetStagesRequested.connect(self._reset_background_stages)
        self.canvas.objectsChanged.connect(self.controls.set_change_object_list)
        self.canvas.backgroundsChanged.connect(self.controls.set_background_list)
        self.canvas.mutationCommitted.connect(self._record_history_state)
        self.canvas.selectedTextEdited.connect(self._mark_text_history_pending)
        self.controls.text_input.textEdited.connect(lambda _text: self._mark_text_history_pending())
        self.controls.text_input.editingFinished.connect(self._commit_pending_text_history)
        self.beat_detector.beatDetected.connect(self.canvas.on_beat)
        self.beat_detector.levelChanged.connect(self.canvas.on_audio_level)
        self.beat_detector.bandLevelsChanged.connect(self.canvas.on_audio_bands)
        self.beat_detector.stateChanged.connect(self.controls.set_beat_status)
        self.external_output_window.closed.connect(self._on_external_output_closed)

        app = QGuiApplication.instance()
        if app is not None:
            self._display_refresh_timer = QTimer(self)
            self._display_refresh_timer.setSingleShot(True)
            self._display_refresh_timer.setInterval(250)
            self._display_refresh_timer.timeout.connect(self._refresh_external_screens)
            app.screenAdded.connect(lambda _screen: self._display_refresh_timer.start())
            app.screenRemoved.connect(lambda _screen: self._display_refresh_timer.start())
        self.media_devices.audioInputsChanged.connect(self._schedule_audio_sources_refresh)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        self._external_display_index = 0

        splitter.addWidget(self.canvas)
        splitter.addWidget(self.controls)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([810, 390])

        self.setCentralWidget(splitter)
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1200, 700)
        QTimer.singleShot(0, self._finish_startup)

    def _finish_startup(self):
        log_startup_event("Main._finish_startup begin")
        try:
            self._refresh_audio_sources()
            log_startup_event("Audio sources refreshed")
            self.controls.sync_defaults()
            log_startup_event("Controls synced")
            self.canvas.refresh_object_list()
            self.canvas.refresh_background_list()
            log_startup_event("Canvas object/background lists refreshed")
            self._refresh_external_screens()
            log_startup_event("External screens refreshed")
            self._reset_history()
        except Exception:
            log_startup_event("Exception during Main._finish_startup\n" + traceback.format_exc().rstrip())
            raise

    def _schedule_audio_sources_refresh(self):
        self._audio_refresh_timer.start()

    def _set_transform_mode(self, mode: str):
        """Set the canvas to change tool with the specified transform mode"""
        # First switch to change tool (for object transformation)
        if hasattr(self.canvas, 'set_tool'):
            self.canvas.set_tool("change")
        # Then set the transform mode
        if hasattr(self.canvas, 'set_select_transform_mode'):
            self.canvas.set_select_transform_mode(mode)
        self._set_change_target(self.controls.current_change_target_kind())

    def _set_change_target(self, kind: str):
        self.canvas.set_change_target_kind(kind)
        self.canvas.set_active_change_visibility_mode(self.controls.current_change_visibility_mode(kind))

    def _apply_object_state(self):
        self._set_change_target("object")
        self.canvas.apply_change_stage()
        self.controls.set_beat_status("State saved")

    def _apply_background_state(self):
        self._set_change_target("background")
        self.canvas.apply_background_change_stage()
        self.controls.set_beat_status("Background state saved")

    def _reset_change_preview(self, kind: str):
        self._set_change_target(kind)
        self.canvas.reset_change_preview()

    def _reset_object_stages(self):
        self._set_change_target("object")
        self.canvas.reset_change_stages()
        self.controls.set_beat_status("Object states reset")

    def _reset_background_stages(self):
        self._set_change_target("background")
        self.canvas.reset_background_change_stages()
        self.controls.set_beat_status("Background states reset")

    def _apply_change_color(self, kind: str, color: QColor):
        self._set_change_target(kind)
        self.canvas.set_change_color(color)

    def _apply_change_visibility_mode(self, kind: str, mode: str):
        self._set_change_target(kind)
        self.canvas.set_change_visibility_mode(mode)

    def _apply_change_preview_enabled(self, kind: str, enabled: bool):
        self._set_change_target(kind)
        self.canvas.set_change_preview_enabled(kind, enabled)

    def _import_image_variant(self):
        self._prepare_replacement(False)

    def _import_background_image(self, slot=None):
        self._prepare_replacement(True, slot)

    def _prepare_replacement(self, background, slot=None):
        if any(worker.isRunning() for worker in getattr(self, "_image_workers", set())):
            self.controls.set_beat_status("Image preparation is still finishing; please try again shortly.")
            return
        if getattr(self, "_image_dialog", None) is not None:
            self._image_dialog.raise_()
            return
        if background and slot is None:
            index = self.canvas.selected_background_index
            slot = self.canvas.backgrounds[index].get("background_slot", index) if 0 <= index < len(self.canvas.backgrounds) else 0
        if background:
            index = next((i for i, obj in enumerate(self.canvas.backgrounds) if obj.get("background_slot", i) == slot), -1)
            if index >= 0:
                self.canvas.set_selected_background(index)
        path, _ = QFileDialog.getOpenFileName(self, "Choose replacement image", str(Path.home()), "Images (*.png *.jpg *.jpeg *.bmp *.webp *.gif)")
        if not path:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Prepare Background " + ("A" if slot == 0 else "B") if background else "Prepare Object Image")
        layout = QVBoxLayout(dialog)
        preview = QLabel("Preparing image; current scene continues…")
        layout.addWidget(preview)
        buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        apply = buttons.button(QDialogButtonBox.Apply)
        apply.setEnabled(False)
        layout.addWidget(buttons)
        self._image_dialog = dialog
        worker = ImagePreparationThread(path, background, self)
        self._image_worker = worker
        self._image_workers = getattr(self, "_image_workers", set())
        self._image_workers.add(worker)
        pending = {}
        def ready(result, error):
            if self._image_dialog is not dialog:
                return
            if error:
                preview.setText(error)
                return
            pending["image"] = result
            image = result if background else result[0]
            preview.setPixmap(QPixmap.fromImage(image).scaled(320, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            apply.setEnabled(True)
        def commit():
            result = pending.get("image")
            if result is None:
                return
            if background:
                ok, message = self.canvas.import_background_image(path, result, slot)
            else:
                ok, message = self.canvas.import_image_variant(path, result)
            self.controls.set_beat_status(message)
            if ok:
                self._reset_history()  # Release superseded source assets from undo history.
                self._refresh_background_slots()
                dialog.accept()
        def finished(_):
            self._image_dialog = None
            pending.clear()
            dialog.deleteLater()
        apply.clicked.connect(commit)
        buttons.rejected.connect(dialog.reject)
        dialog.finished.connect(finished)
        worker.prepared.connect(ready)
        worker.finished.connect(lambda: self._image_workers.discard(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()
        dialog.show()

    def _refresh_background_slots(self, *_):
        for slot, button in enumerate(self.controls.background_slot_buttons):
            item = next((obj for i, obj in enumerate(self.canvas.backgrounds) if obj.get("background_slot", i) == slot), None)
            button.setText("Background " + ("A" if slot == 0 else "B") + "\n" + (item["name"] if item else "Choose image…"))
            image = next(iter(item.get("variant_shell_images", {}).values()), QImage()) if item else QImage()
            button.setIcon(QIcon(QPixmap.fromImage(image).scaled(140, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)) if not image.isNull() else QIcon())
            button.setIconSize(QSize(140, 80))

    def _set_background_mix(self, value):
        self.canvas.background_mix = value / 100.0
        self.controls.background_mix_label.setText(f"A {100-value}% / B {value}%")
        self.canvas.update()

    def _capture_history_state(self):
        return {
            "canvas": self.canvas.export_history_state(),
            "controls": self.controls.export_history_state(),
        }

    def _reset_history(self):
        self._history = [self._capture_history_state()]
        self._history_index = 0
        self._text_history_pending = False

    def _record_history_state(self, _reason: str = ""):
        if self._restoring_history:
            return
        snapshot = self._capture_history_state()
        self._history = self._history[: self._history_index + 1]
        self._history.append(snapshot)
        if len(self._history) > 150:
            self._history = self._history[-150:]
        self._history_index = len(self._history) - 1
        self._text_history_pending = False

    def _restore_history_snapshot(self, index: int):
        if not (0 <= int(index) < len(self._history)):
            return
        self._restoring_history = True
        try:
            snapshot = self._history[int(index)]
            self.canvas.import_history_state(snapshot.get("canvas", {}))
            self.controls.import_history_state(snapshot.get("controls", {}))
            self._set_change_target(self.controls.current_change_target_kind())
        finally:
            self._restoring_history = False

    def undo_scene(self):
        if self._history_index <= 0:
            return
        self._history_index -= 1
        self._restore_history_snapshot(self._history_index)

    def redo_scene(self):
        if self._history_index >= (len(self._history) - 1):
            return
        self._history_index += 1
        self._restore_history_snapshot(self._history_index)

    def _mark_text_history_pending(self):
        if self._restoring_history:
            return
        self._text_history_pending = True

    def _commit_pending_text_history(self):
        if self._text_history_pending:
            self._record_history_state("text_edit")

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            return True
        if event.type() == QEvent.KeyPress and event.modifiers() & Qt.ControlModifier:
            key = event.key()
            focus = QApplication.focusWidget()
            if key == Qt.Key_S:
                self.controls.toggle_change_target_kind()
                return True
            if key == Qt.Key_D:
                if isinstance(focus, (QLineEdit,)):
                    return False
                self._commit_pending_text_history()
                if self.canvas.delete_selected_scene_item():
                    return True
                return False
            if key in (Qt.Key_Z, Qt.Key_R):
                if isinstance(focus, (QLineEdit,)):
                    return False
                if key == Qt.Key_Z:
                    self.undo_scene()
                else:
                    self.redo_scene()
                return True
        return super().eventFilter(obj, event)

    def _refresh_audio_sources(self):
        if self._audio_refresh_in_progress:
            return
        self._audio_refresh_in_progress = True
        log_startup_event("Audio source refresh begin")
        try:
            sources = available_audio_sources()
            selected_id = preferred_audio_source_id(sources, self.beat_detector.audio_source_id())
            self.controls.set_audio_sources(sources, selected_id)
            self.beat_detector.set_audio_source(selected_id)
            has_system_source = any(source.get("role") == "system" for source in sources)
            has_soundcard_source = any(source.get("backend") == AUDIO_SOURCE_BACKEND_SOUNDCARD for source in sources)
            if not sources:
                note = "No audio inputs were detected. Connect a microphone or enable a sound-card/system loopback source for internal audio capture."
            elif has_soundcard_source:
                note = "Sound-card loopback source detected. Select a 'System / Sound Card' entry to react directly to the computer's own output."
            elif has_system_source:
                note = "Loopback-capable input detected. Select it here to react to internal/system audio instead of a microphone."
            else:
                note = "Microphone/input sources detected. Internal/system audio will need Stereo Mix, a virtual cable, or another loopback-capable capture input."
            self.controls.set_audio_source_note(note)
            log_startup_event("Audio source refresh complete")
        except Exception:
            log_startup_event("Audio source refresh failed\n" + traceback.format_exc())
            self.controls.set_audio_source_note("Audio refresh failed. Try Refresh Sources again.")
        finally:
            self._audio_refresh_in_progress = False

    def _screen_entries(self):
        screens = QGuiApplication.screens()
        primary = QGuiApplication.primaryScreen()
        entries = []
        for index, screen in enumerate(screens):
            geometry = screen.geometry()
            label = f"{index + 1}. {screen.name()} ({geometry.width()}x{geometry.height()})"
            if screen is primary:
                label = f"{label} [Primary]"
            entries.append((label, index))
        return entries

    def _refresh_external_screens(self):
        if getattr(self, "_display_refresh_in_progress", False):
            return
        self._display_refresh_in_progress = True
        log_startup_event("Display refresh begin")
        try:
            current_screens = QGuiApplication.screens()
            output_visible = self.external_output_window.isVisible()
            handle = self.external_output_window.windowHandle()
            active_screen = handle.screen() if output_visible and handle is not None else None
            if active_screen in current_screens:
                self._external_display_index = current_screens.index(active_screen)
            screens = self._screen_entries()
            if screens:
                self._external_display_index = max(0, min(self._external_display_index, len(screens) - 1))
                selected_label = screens[self._external_display_index][0]
                status = f"External output live on {selected_label}." if output_visible else f"Ready for external output on {selected_label}. Press Esc on the fullscreen window to close it."
            else:
                self._external_display_index = -1
                status = "No displays detected."
            self.controls.set_external_screens(screens, self._external_display_index)
            self.controls.set_external_output_status(status)
            # Enumeration must not recreate or reposition an existing fullscreen window.
            if output_visible and not screens:
                self.external_output_window.close()
            log_startup_event("Display refresh complete")
        except Exception:
            log_startup_event("Display refresh failed\n" + traceback.format_exc())
            self.controls.set_external_output_status("Display refresh failed. Try Refresh Displays again.")
        finally:
            self._display_refresh_in_progress = False

    def _set_external_display_index(self, index: int):
        self._external_display_index = int(index)
        screens = self._screen_entries()
        if 0 <= self._external_display_index < len(screens):
            self.controls.set_external_output_status(
                f"Ready for external output on {screens[self._external_display_index][0]}. Press Esc on the fullscreen window to close it."
            )
        if self.external_output_window.isVisible():
            self._show_external_output()

    def _show_external_output(self):
        screens = QGuiApplication.screens()
        if not screens:
            self.controls.set_external_output_active(False)
            self.controls.set_external_output_status("No displays detected.")
            return

        self._external_display_index = max(0, min(self._external_display_index, len(screens) - 1))
        screen = screens[self._external_display_index]
        self.external_output_window.show_on_screen(screen)
        geometry = screen.geometry()
        self.controls.set_external_output_active(True)
        self.controls.set_external_output_status(
            f"External output live on {screen.name()} ({geometry.width()}x{geometry.height()}). Press Esc on the fullscreen window to close it."
        )

    def _set_external_output_enabled(self, enabled: bool):
        if enabled:
            self._show_external_output()
            return
        self.external_output_window.close()

    def _on_external_output_closed(self):
        screens = self._screen_entries()
        self.controls.set_external_output_active(False)
        if 0 <= self._external_display_index < len(screens):
            self.controls.set_external_output_status(
                f"Ready for external output on {screens[self._external_display_index][0]}. Press Esc on the fullscreen window to close it."
            )
        else:
            self.controls.set_external_output_status("External output off")

    def closeEvent(self, e):
        log_startup_event("Main closeEvent")
        for worker in getattr(self, "_image_workers", set()):
            worker.wait()
        self.external_output_window.close()
        self.beat_detector.stop()
        super().closeEvent(e)

if __name__ == "__main__":
    log_startup_event("Process start")
    if len(sys.argv) >= 3 and sys.argv[1] == "--soundcard-worker":
        log_startup_event("Launching soundcard worker")
        raise SystemExit(run_soundcard_worker(sys.argv[2]))
    log_startup_event("Creating QApplication")
    app = QApplication([])
    app.aboutToQuit.connect(lambda: log_startup_event("QApplication aboutToQuit"))
    log_startup_event("QApplication created")
    icon = load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
        log_startup_event("Application icon applied")
    log_startup_event("Constructing Main window")
    w = Main()
    log_startup_event("Main window constructed")
    w.show()
    log_startup_event("Main window shown")
    exit_code = app.exec()
    log_startup_event(f"app.exec returned {exit_code}")
