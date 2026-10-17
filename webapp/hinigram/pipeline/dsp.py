"""Signal processing primitives: clean the phase, pick a transmitter, estimate the rate.

Every function here is a pure function of numpy arrays and a sample rate, so the detector is
exercised by numbers rather than by a running server. The thresholds and window sizes are the
design record's (§7.1); where a value is a judgement call, the docstring says so.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, hilbert, sosfiltfilt

from hinigram.pipeline.frames import Window

#: The respiratory band, in Hz. 0.2-0.5 Hz is 12-30 breaths per minute.
BAND_LO = 0.2
BAND_HI = 0.5

#: Anything above this frequency is treated as movement, not breathing.
MOTION_HZ = 3.0

#: A residual RMS above this (radians of phase) counts as movement. Calibrated against the
#: simulator's gain range; a quiet station never approaches it.
MOTION_RMS = 0.25

#: Hampel filter: a seven-sample window at three robust standard deviations.
HAMPEL_WINDOW = 7
HAMPEL_SIGMA = 3.0


def hampel(x: np.ndarray, window: int = HAMPEL_WINDOW, n_sigma: float = HAMPEL_SIGMA) -> np.ndarray:
    """Replace isolated spikes with the local median.

    Phase unwrapping produces occasional jumps of a few radians. A moving average smears them
    across the whole window; a median-based test removes them and leaves the rest untouched.
    """
    if window < 3 or window % 2 == 0:
        raise ValueError("window must be an odd number of at least 3")
    values = np.asarray(x, dtype=np.float64)
    if values.shape[0] < window:
        return values.copy()
    pad = window // 2
    padded = np.pad(values, pad, mode="edge")
    frames = np.lib.stride_tricks.sliding_window_view(padded, window)
    median = np.median(frames, axis=1)
    deviation = np.median(np.abs(frames - median[:, None]), axis=1)
    threshold = n_sigma * 1.4826 * deviation
    is_outlier = np.abs(values - median) > threshold
    return np.where(is_outlier, median, values)


def unwrap_channels(phase: np.ndarray) -> np.ndarray:
    """Unwrap every subcarrier's phase along time, column by column."""
    values = np.asarray(phase, dtype=np.float64)
    if values.ndim == 1:
        return np.unwrap(values)
    return np.unwrap(values, axis=0)


def first_component(series: np.ndarray) -> np.ndarray:
    """Project an ``(n, channels)`` phase matrix onto its first principal component.

    The sign is fixed by correlating with the first channel, because the SVD's sign is
    arbitrary and a flipped component would flip every downstream phase by pi.
    """
    values = np.asarray(series, dtype=np.float64)
    if values.ndim == 1:
        return values.copy()
    if values.shape[1] == 1:
        return values[:, 0].copy()
    centred = values - values.mean(axis=0)
    _, _, right = np.linalg.svd(centred, full_matrices=False)
    component = centred @ right[0]
    reference = values[:, 0] - values[:, 0].mean()
    if np.std(reference) > 0 and np.corrcoef(component, reference)[0, 1] < 0:
        component = -component
    return component


def bandpass(
    x: np.ndarray,
    fs: float,
    lo: float = BAND_LO,
    hi: float = BAND_HI,
    order: int = 4,
) -> np.ndarray:
    """Zero-phase Butterworth bandpass: the respiratory band and nothing else."""
    values = np.asarray(x, dtype=np.float64)
    nyquist = fs / 2.0
    if not 0 < lo < hi < nyquist:
        raise ValueError(f"band {lo}-{hi} Hz is not inside 0-{nyquist} Hz")
    sos = butter(order, [lo, hi], btype="bandpass", fs=fs, output="sos")
    padlen = 3 * (2 * sos.shape[0] + 1)
    if values.shape[0] <= padlen:
        return np.zeros_like(values)
    return sosfiltfilt(sos, values)


def band_snr(x: np.ndarray, fs: float, lo: float = BAND_LO, hi: float = BAND_HI) -> float:
    """Fraction of the signal's power that falls inside the respiratory band.

    This is the criterion for choosing which transmitter to analyse: the person's chest is
    closest to one of the three, and the strongest in-band modulation is the one worth reading.
    """
    values = np.asarray(x, dtype=np.float64)
    if values.shape[0] < 8:
        return 0.0
    centred = values - values.mean()
    windowed = centred * np.hanning(centred.shape[0])
    spectrum = np.abs(np.fft.rfft(windowed)) ** 2
    frequencies = np.fft.rfftfreq(centred.shape[0], d=1.0 / fs)
    in_band = (frequencies >= lo) & (frequencies <= hi)
    total = spectrum[1:].sum()
    if total <= 0:
        return 0.0
    return float(spectrum[in_band].sum() / total)


def best_transmitter(
    windows: dict[str, Window],
) -> tuple[str, np.ndarray, float] | None:
    """Choose the transmitter with the strongest respiratory modulation.

    Returns the name, its bandpassed series, and the in-band SNR; None when no transmitter has
    two seconds of data, which is the honest answer for a station nobody is standing at.
    """
    best: tuple[str, np.ndarray, float] | None = None
    for name in sorted(windows):
        window = windows[name]
        if window.t.shape[0] < 2 * window.fs:
            continue
        component = first_component(unwrap_channels(window.phase))
        snr = band_snr(component, window.fs)
        if best is None or snr > best[2]:
            best = (name, bandpass(component, window.fs), snr)
    return best


def estimate_rr(
    x: np.ndarray,
    fs: float,
    lo: float = BAND_LO,
    hi: float = BAND_HI,
) -> tuple[float, int]:
    """Breathing rate in breaths per minute, and how many breaths the window contains.

    The peak of the windowed spectrum is refined by parabolic interpolation: at a 30 s window
    the raw bin spacing is 2 bpm, which is twice the accuracy the station promises.
    """
    values = np.asarray(x, dtype=np.float64)
    n = values.shape[0]
    if n < 4:
        raise ValueError("need at least four samples to estimate a rate")
    windowed = (values - values.mean()) * np.hanning(n)
    padded = np.fft.rfft(windowed, n=n * 8)
    magnitude = np.abs(padded)
    frequencies = np.fft.rfftfreq(n * 8, d=1.0 / fs)
    in_band = np.flatnonzero((frequencies >= lo) & (frequencies <= hi))
    if in_band.size == 0:
        raise ValueError("band contains no frequency bins")
    peak = int(in_band[np.argmax(magnitude[in_band])])
    offset = 0.0
    if 0 < peak < magnitude.shape[0] - 1:
        left = np.log(magnitude[peak - 1] + 1e-12)
        centre = np.log(magnitude[peak] + 1e-12)
        right = np.log(magnitude[peak + 1] + 1e-12)
        denominator = left - 2 * centre + right
        if denominator != 0:
            offset = 0.5 * (left - right) / denominator
    spacing = frequencies[1] - frequencies[0]
    peak_hz = frequencies[peak] + offset * spacing
    crossings = int(np.sum((values[:-1] <= 0) & (values[1:] > 0)))
    return float(peak_hz * 60.0), crossings


def _high_pass_residual(x: np.ndarray, fs: float, thresh_hz: float) -> np.ndarray:
    """Everything faster than ``thresh_hz``: the moving-average residual."""
    width = max(3, int(round(fs / thresh_hz)))
    if width % 2 == 0:
        width += 1
    if x.shape[0] < width:
        return np.zeros_like(x)
    padded = np.pad(x, width // 2, mode="reflect")
    baseline = np.convolve(padded, np.ones(width) / width, mode="valid")
    return x - baseline[: x.shape[0]]


def motion_seconds(
    window: Window,
    thresh_hz: float = MOTION_HZ,
    rms_thresh: float = MOTION_RMS,
) -> float:
    """How many half-second blocks of this window contain movement."""
    series = window.phase.mean(axis=1)
    residual = _high_pass_residual(series, window.fs, thresh_hz)
    block = max(1, int(round(window.fs * 0.5)))
    blocks = residual.shape[0] // block
    if blocks == 0:
        return 0.0
    rms = np.sqrt(np.mean(residual[: blocks * block].reshape(blocks, block) ** 2, axis=1))
    return float(np.count_nonzero(rms > rms_thresh) * 0.5)


def _rolling_rms(x: np.ndarray, width: int) -> np.ndarray:
    if x.shape[0] < width or width < 1:
        return np.zeros(1)
    kernel = np.ones(width) / width
    return np.sqrt(np.convolve(x**2, kernel, mode="valid"))


def flat_seconds(x: np.ndarray, fs: float, floor_ratio: float = 0.25) -> float:
    """The longest stretch where the breathing amplitude collapses.

    A breath pause is not an absence of samples: the phase goes on wobbling with noise, at a
    fraction of the amplitude a breath produces. The threshold is relative to this window's own
    median envelope, so a quiet person with small breaths is not read as an apnea.
    """
    values = np.asarray(x, dtype=np.float64)
    width = max(3, int(round(fs)))
    envelope = _rolling_rms(values, width)
    if envelope.size < 2:
        return 0.0
    median = float(np.median(envelope))
    if median <= 0:
        return 0.0
    below = envelope < floor_ratio * median
    longest = 0
    run = 0
    for is_below in below:
        run = run + 1 if is_below else 0
        longest = max(longest, run)
    return float(longest / fs)


def decimate(t: np.ndarray, x: np.ndarray, hz: float = 10.0) -> tuple[np.ndarray, np.ndarray]:
    """Thin a series to roughly ``hz`` for transport, keeping the first sample."""
    t_values = np.asarray(t, dtype=np.float64)
    x_values = np.asarray(x, dtype=np.float64)
    if t_values.shape[0] < 2:
        return t_values.copy(), x_values.copy()
    deltas = np.diff(t_values)
    median_dt_s = float(np.median(deltas)) / 1000.0
    if median_dt_s <= 0:
        return t_values.copy(), x_values.copy()
    step = max(1, int(round(1.0 / (hz * median_dt_s))))
    return t_values[::step], x_values[::step]


def rms_db(x: np.ndarray) -> float:
    """Root-mean-square level in decibels, floored so silence is a number and not -inf."""
    values = np.asarray(x, dtype=np.float64)
    if values.size == 0:
        return -120.0
    rms = float(np.sqrt(np.mean(values**2)))
    return float(20.0 * np.log10(rms + 1e-12))


def hilbert_phase(x: np.ndarray) -> np.ndarray:
    """Instantaneous phase of a narrowband signal, via the analytic signal."""
    return np.angle(hilbert(np.asarray(x, dtype=np.float64)))
