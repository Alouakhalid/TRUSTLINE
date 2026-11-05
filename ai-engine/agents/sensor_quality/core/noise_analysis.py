"""Sampling-rate-aware, sensor-specific noise and interference analysis."""
from typing import List, Tuple
import numpy as np
from scipy import signal
from ..schemas.signal_schema import SensorStreamData, IssueSeverity
from ..schemas.output_schema import DetectedIssue
from ..explainability.reason_codes import ReasonCode
from ..explainability.evidence_extractor import EvidenceExtractor

class NoiseAnalyzer:
    """Computes signal-specific noise contamination and spectral anomalies."""

    def __init__(self, powerline_frequencies: List[float] = [50.0, 60.0]):
        self.powerline_frequencies = powerline_frequencies

    def analyze_noise(self, stream: SensorStreamData) -> Tuple[float, List[DetectedIssue]]:
        issues: List[DetectedIssue] = []
        fs = stream.sampling_rate
        data = np.asarray(stream.data)

        if len(data) < int(fs * 2.0) or fs <= 0:
            return 0.05, issues

        if data.ndim > 1:
            signal_1d = data[:, 0]
        else:
            signal_1d = data

        clean_indices = np.where(~(np.isnan(signal_1d) | np.isinf(signal_1d)))[0]
        if len(clean_indices) < int(fs * 2.0):
            return 0.90, issues

        clean_signal = signal_1d[clean_indices]
        sensor = stream.sensor.upper()
        noise_index = 0.05

        if sensor == "ECG":
            noise_index, ecg_issues = self._analyze_ecg_noise(clean_signal, fs, stream.sensor)
            issues.extend(ecg_issues)
        elif sensor == "EDA":
            noise_index, eda_issues = self._analyze_eda_noise(clean_signal, fs, stream.sensor)
            issues.extend(eda_issues)
        elif sensor == "RESP":
            noise_index, resp_issues = self._analyze_resp_noise(clean_signal, fs, stream.sensor)
            issues.extend(resp_issues)
        elif sensor == "EMG":
            noise_index, emg_issues = self._analyze_emg_noise(clean_signal, fs, stream.sensor)
            issues.extend(emg_issues)
        elif sensor == "TEMP":
            noise_index, temp_issues = self._analyze_temp_noise(clean_signal, fs, stream.sensor)
            issues.extend(temp_issues)
        elif sensor == "ACC":
            noise_index, acc_issues = self._analyze_acc_noise(clean_signal, fs, stream.sensor)
            issues.extend(acc_issues)
        else:
            noise_index = 0.10

        return float(min(1.0, max(0.0, noise_index))), issues

    def _analyze_ecg_noise(self, sig: np.ndarray, fs: float, sensor: str) -> Tuple[float, List[DetectedIssue]]:
        issues = []
        nperseg = min(len(sig), int(fs * 4.0))
        freqs, psd = signal.welch(sig - np.mean(sig), fs=fs, nperseg=nperseg)
        total_power = np.sum(psd) if np.sum(psd) > 0 else 1e-12

        low_mask = freqs < 0.5
        wander_power = np.sum(psd[low_mask])
        wander_ratio = float(wander_power / total_power)

        if wander_ratio > 0.40:
            evidence = EvidenceExtractor.build_evidence(
                metric_name="baseline_wander_power_ratio",
                measured_value=wander_ratio,
                threshold_value=0.40,
                units="ratio",
                confidence=0.90
            )
            issues.append(DetectedIssue(
                reason_code=ReasonCode.ECG_BASELINE_WANDER.value,
                sensor=sensor,
                severity=IssueSeverity.MODERATE,
                evidence=[evidence],
                method="Welch spectral power integration (<0.5 Hz)",
                explanation=f"Excessive baseline wander detected ({wander_ratio:.2%} of total spectral power below 0.5 Hz).",
                recommended_handling="Apply high-pass Butterworth filter with 0.5 Hz cutoff."
            ))

        pl_power = 0.0
        for pl_f in self.powerline_frequencies:
            if fs > pl_f * 2.0:
                pl_mask = (freqs >= pl_f - 1.0) & (freqs <= pl_f + 1.0)
                pl_power += np.sum(psd[pl_mask])
        pl_ratio = float(pl_power / total_power)

        if pl_ratio > 0.15:
            evidence = EvidenceExtractor.build_evidence(
                metric_name="powerline_interference_ratio",
                measured_value=pl_ratio,
                threshold_value=0.15,
                units="ratio",
                confidence=0.95
            )
            issues.append(DetectedIssue(
                reason_code=ReasonCode.ECG_POWERLINE_INTERFERENCE.value,
                sensor=sensor,
                severity=IssueSeverity.MODERATE,
                evidence=[evidence],
                method="Narrowband spectral integration (50/60 Hz)",
                explanation=f"Powerline electromagnetic interference identified ({pl_ratio:.2%} of total power).",
                recommended_handling="Apply IIR notch filter at local mains frequency (50/60 Hz)."
            ))

        hf_mask = freqs > 45.0
        hf_power = np.sum(psd[hf_mask]) if fs > 90.0 else 0.0
        hf_ratio = float(hf_power / total_power)

        if hf_ratio > 0.35:
            evidence = EvidenceExtractor.build_evidence(
                metric_name="high_frequency_noise_ratio",
                measured_value=hf_ratio,
                threshold_value=0.35,
                units="ratio",
                confidence=0.85
            )
            issues.append(DetectedIssue(
                reason_code=ReasonCode.ECG_HIGH_FREQUENCY_NOISE.value,
                sensor=sensor,
                severity=IssueSeverity.LOW,
                evidence=[evidence],
                method="High-band spectral density evaluation (>45 Hz)",
                explanation=f"High frequency electromyographic noise contamination detected ({hf_ratio:.2%} power).",
                recommended_handling="Apply low-pass filter at 40 Hz cutoff."
            ))

        noise_index = wander_ratio * 0.4 + pl_ratio * 0.4 + hf_ratio * 0.2
        return noise_index, issues

    def _analyze_eda_noise(self, sig: np.ndarray, fs: float, sensor: str) -> Tuple[float, List[DetectedIssue]]:
        issues = []
        diffs = np.abs(np.diff(sig))
        diff_threshold = 2.0
        discontinuities = np.where(diffs > diff_threshold)[0]
        disc_ratio = float(len(discontinuities)) / float(len(sig))

        if len(discontinuities) > 0:
            evidence = EvidenceExtractor.build_evidence(
                metric_name="discontinuity_count",
                measured_value=float(len(discontinuities)),
                threshold_value=1.0,
                units="count",
                confidence=0.95
            )
            issues.append(DetectedIssue(
                reason_code=ReasonCode.EDA_SUDDEN_DISCONTINUITY.value,
                sensor=sensor,
                severity=IssueSeverity.HIGH if len(discontinuities) > 5 else IssueSeverity.MODERATE,
                evidence=[evidence],
                method="Step derivative thresholding",
                explanation=f"Identified {len(discontinuities)} abrupt conductance jumps exceeding {diff_threshold} uS.",
                recommended_handling="Interpolate sharp discontinuities or label affected window invalid."
            ))

        noise_index = min(1.0, disc_ratio * 20.0 + 0.05)
        return noise_index, issues

    def _analyze_resp_noise(self, sig: np.ndarray, fs: float, sensor: str) -> Tuple[float, List[DetectedIssue]]:
        issues = []
        nperseg = min(len(sig), int(fs * 8.0))
        freqs, psd = signal.welch(sig - np.mean(sig), fs=fs, nperseg=nperseg)
        total_power = np.sum(psd) if np.sum(psd) > 0 else 1e-12

        resp_band = (freqs >= 0.1) & (freqs <= 0.8)
        resp_power = np.sum(psd[resp_band])
        resp_ratio = float(resp_power / total_power)

        if resp_ratio < 0.20:
            evidence = EvidenceExtractor.build_evidence(
                metric_name="respiratory_band_power_ratio",
                measured_value=resp_ratio,
                threshold_value=0.20,
                units="ratio",
                confidence=0.85
            )
            issues.append(DetectedIssue(
                reason_code=ReasonCode.RESP_BASELINE_INSTABILITY.value,
                sensor=sensor,
                severity=IssueSeverity.MODERATE,
                evidence=[evidence],
                method="Physiological respiratory band spectral power (0.1-0.8 Hz)",
                explanation=f"Low physiological breathing power detected ({resp_ratio:.2%} in 0.1-0.8 Hz band).",
                recommended_handling="Inspect chest band tension and placement."
            ))

        noise_index = max(0.05, 1.0 - resp_ratio)
        return noise_index, issues

    def _analyze_emg_noise(self, sig: np.ndarray, fs: float, sensor: str) -> Tuple[float, List[DetectedIssue]]:
        issues = []
        rms = float(np.sqrt(np.mean(sig ** 2)))
        noise_index = 0.05
        return noise_index, issues

    def _analyze_temp_noise(self, sig: np.ndarray, fs: float, sensor: str) -> Tuple[float, List[DetectedIssue]]:
        issues = []
        diffs = np.abs(np.diff(sig))
        dt = 1.0 / fs if fs > 0 else 1.0
        rate_of_change = diffs / dt
        max_rate = float(np.max(rate_of_change)) if len(rate_of_change) > 0 else 0.0
        threshold_rate = 0.50

        if max_rate > threshold_rate:
            evidence = EvidenceExtractor.build_evidence(
                metric_name="max_temp_rate_of_change",
                measured_value=max_rate,
                threshold_value=threshold_rate,
                units="C/sec",
                confidence=0.95
            )
            issues.append(DetectedIssue(
                reason_code=ReasonCode.TEMP_IMPLAUSIBLE_RATE_OF_CHANGE.value,
                sensor=sensor,
                severity=IssueSeverity.HIGH,
                evidence=[evidence],
                method="Thermal derivative inspection",
                explanation=f"Thermal rate of change ({max_rate:.2f} C/s) exceeds biological skin limits ({threshold_rate:.2f} C/s).",
                recommended_handling="Verify thermal sensor surface contact."
            ))

        noise_index = min(1.0, max(0.05, (max_rate / 2.0)))
        return noise_index, issues

    def _analyze_acc_noise(self, sig: np.ndarray, fs: float, sensor: str) -> Tuple[float, List[DetectedIssue]]:
        issues = []
        noise_index = 0.05
        return noise_index, issues
