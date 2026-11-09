"""Domain-validated physiological feature extraction using NeuroKit2 and SciPy."""
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from scipy import signal
from .sensor_integration_service import ValidatedSensorStream
from ..schemas.physiological_features import (
    ExtractedFeature,
    Core14Features,
    PhysiologicalFeatureReport,
    MeasurementStatus,
    HRVStatus,
    HRVDiagnosticReport
)

class FeatureExtractionService:
    """Multi-rate physiological signal feature extraction engine."""

    def __init__(self, ultra_short_hrv_threshold_seconds: float = 300.0):
        self.ultra_short_threshold = ultra_short_hrv_threshold_seconds

    def extract_features(
        self,
        streams: Dict[str, ValidatedSensorStream],
        astronaut_id: str = "UNKNOWN",
        session_id: str = "UNKNOWN"
    ) -> PhysiologicalFeatureReport:
        """Extract both the Core 14 ML features and extended clinical features."""
        all_features: List[ExtractedFeature] = []
        warnings: List[str] = []

        max_duration = 0.0
        for s in streams.values():
            if s.duration_seconds > max_duration:
                max_duration = s.duration_seconds

        ecg_features, hrv_diagnostics = self._extract_ecg_features(streams.get("ECG"))
        all_features.extend(ecg_features)
        if hrv_diagnostics and hrv_diagnostics.processing_warnings:
            warnings.extend(hrv_diagnostics.processing_warnings)

        eda_features = self._extract_eda_features(streams.get("EDA"))
        all_features.extend(eda_features)

        resp_features = self._extract_resp_features(streams.get("RESP"))
        all_features.extend(resp_features)

        temp_features = self._extract_temp_features(streams.get("TEMP"))
        all_features.extend(temp_features)

        emg_features = self._extract_emg_features(streams.get("EMG"))
        all_features.extend(emg_features)

        acc_features = self._extract_acc_features(streams.get("ACC"))
        all_features.extend(acc_features)

        feature_map = {f.feature_name: f.value for f in all_features}
        core14 = self._build_core14(feature_map)

        has_valid_core = core14 is not None
        if not has_valid_core:
            missing = [k for k in [
                "hr_mean_bpm", "hr_std_bpm", "hrv_rmssd_ms", "hrv_sdnn_ms",
                "eda_mean", "eda_std", "eda_iqr", "resp_rate_bpm", "resp_std",
                "temp_mean", "temp_std", "emg_rms", "acc_magnitude_mean", "acc_magnitude_std"
            ] if k not in feature_map]
            warnings.append(f"Incomplete Core-14 feature set. Missing: {', '.join(missing)}")
        for f in all_features:
            if f.measurement_status != MeasurementStatus.AVAILABLE:
                warnings.append(f"{f.feature_name} has status {f.measurement_status.value}: {f.status_reason or 'non-nominal status'}")

        return PhysiologicalFeatureReport(
            astronaut_id=astronaut_id,
            session_id=session_id,
            window_duration_seconds=max_duration,
            core_features=core14,
            all_features=all_features,
            extraction_warnings=warnings,
            hrv_diagnostics=hrv_diagnostics,
            has_valid_core14=has_valid_core
        )

    def _extract_ecg_features(self, stream: Optional[ValidatedSensorStream]) -> Tuple[List[ExtractedFeature], Optional[HRVDiagnosticReport]]:
        """Extract cardiac parameters, ultra-short-term HRV metrics, and comprehensive HRV diagnostic report."""
        if stream is None:
            return [], None

        if len(stream.data) == 0:
            diag = HRVDiagnosticReport(
                ecg_sampling_rate=0.0,
                ecg_duration_seconds=0.0,
                total_r_peaks_detected=0,
                valid_r_peaks=0,
                total_rr_intervals=0,
                valid_nn_intervals=0,
                invalid_interval_count=0,
                hrv_status=HRVStatus.INSUFFICIENT_R_PEAKS,
                processing_warnings=["Empty ECG signal array."],
                calculation_validity=False
            )
            return [], diag

        fs = float(stream.sampling_rate)
        duration = float(stream.duration_seconds)
        raw = np.asarray(stream.data, dtype=np.float64)

        if fs <= 0.0:
            diag = HRVDiagnosticReport(
                ecg_sampling_rate=fs,
                ecg_duration_seconds=duration,
                total_r_peaks_detected=0,
                valid_r_peaks=0,
                total_rr_intervals=0,
                valid_nn_intervals=0,
                invalid_interval_count=0,
                hrv_status=HRVStatus.INVALID_ECG_SIGNAL,
                processing_warnings=["Invalid non-positive ECG sampling frequency."],
                calculation_validity=False
            )
            return [], diag

        if np.any(np.isnan(raw)) or np.any(np.isinf(raw)):
            diag = HRVDiagnosticReport(
                ecg_sampling_rate=fs,
                ecg_duration_seconds=duration,
                total_r_peaks_detected=0,
                valid_r_peaks=0,
                total_rr_intervals=0,
                valid_nn_intervals=0,
                invalid_interval_count=0,
                hrv_status=HRVStatus.INVALID_ECG_SIGNAL,
                processing_warnings=["ECG signal contains NaN or Inf values violating signal integrity."],
                calculation_validity=False
            )
            return [], diag

        is_exploratory = duration < self.ultra_short_threshold
        features: List[ExtractedFeature] = []
        hrv_warnings: List[str] = []

        min_distance = max(1, int(fs * 0.25))
        pks, _ = signal.find_peaks(raw, distance=min_distance, prominence=0.3)

        if len(pks) == 0:
            diag = HRVDiagnosticReport(
                ecg_sampling_rate=fs,
                ecg_duration_seconds=duration,
                total_r_peaks_detected=0,
                valid_r_peaks=0,
                total_rr_intervals=0,
                valid_nn_intervals=0,
                invalid_interval_count=0,
                hrv_status=HRVStatus.DETECTION_FAILURE,
                processing_warnings=["No R-peaks detected matching prominence threshold."],
                calculation_validity=False
            )
            return features, diag

        if len(pks) < 3:
            hrv_warnings.append("Insufficient R-peaks (< 3) to compute successive interval differences.")
            diag = HRVDiagnosticReport(
                ecg_sampling_rate=fs,
                ecg_duration_seconds=duration,
                total_r_peaks_detected=len(pks),
                valid_r_peaks=len(pks),
                total_rr_intervals=max(0, len(pks) - 1),
                valid_nn_intervals=0,
                invalid_interval_count=0,
                hrv_status=HRVStatus.INSUFFICIENT_R_PEAKS,
                processing_warnings=hrv_warnings,
                calculation_validity=False
            )
            return features, diag

        rr_samples = np.diff(pks)
        rr_sec = rr_samples / fs
        rr_ms = rr_sec * 1000.0

        valid_nn = np.array([r for r in rr_ms if 270.0 <= r <= 2000.0], dtype=np.float64)
        invalid_count = int(len(rr_ms) - len(valid_nn))

        if len(valid_nn) == 0:
            hrv_warnings.append("All detected RR intervals fell outside plausible physiological limits (270-2000 ms).")
            diag = HRVDiagnosticReport(
                ecg_sampling_rate=fs,
                ecg_duration_seconds=duration,
                total_r_peaks_detected=len(pks),
                valid_r_peaks=len(pks),
                total_rr_intervals=len(rr_ms),
                valid_nn_intervals=0,
                invalid_interval_count=invalid_count,
                hrv_status=HRVStatus.INVALID_INTERVALS,
                processing_warnings=hrv_warnings,
                calculation_validity=False
            )
            features.append(ExtractedFeature(
                feature_name="hr_mean_bpm",
                value=0.0,
                unit="bpm",
                sensor_source="ECG",
                time_window_seconds=duration,
                extraction_method="Peak-to-Peak R-Peak Inversion",
                quality_status=stream.status,
                validity_status="INVALID",
                measurement_status=MeasurementStatus.INVALID,
                status_reason="All detected RR intervals are non-physiological."
            ))
            return features, diag

        if len(valid_nn) < 2:
            hrv_warnings.append("Insufficient valid NN intervals (< 2) to compute successive differences.")
            hr_single = float(60000.0 / valid_nn[0])
            diag = HRVDiagnosticReport(
                ecg_sampling_rate=fs,
                ecg_duration_seconds=duration,
                total_r_peaks_detected=len(pks),
                valid_r_peaks=len(pks),
                total_rr_intervals=len(rr_ms),
                valid_nn_intervals=len(valid_nn),
                invalid_interval_count=invalid_count,
                mean_rr_ms=float(valid_nn[0]),
                median_rr_ms=float(valid_nn[0]),
                hrv_status=HRVStatus.INSUFFICIENT_RR_INTERVALS,
                processing_warnings=hrv_warnings,
                calculation_validity=False
            )
            features.append(ExtractedFeature(
                feature_name="hr_mean_bpm",
                value=hr_single,
                unit="bpm",
                sensor_source="ECG",
                time_window_seconds=duration,
                extraction_method="Peak-to-Peak R-Peak Inversion",
                quality_status=stream.status,
                validity_status="VALID",
                measurement_status=MeasurementStatus.AVAILABLE
            ))
            return features, diag

        nn_diff = np.diff(valid_nn)
        rmssd = float(np.sqrt(np.mean(nn_diff ** 2)))
        sdnn = float(np.std(valid_nn))
        mean_rr = float(np.mean(valid_nn))
        median_rr = float(np.median(valid_nn))
        pnn50 = float(np.sum(np.abs(nn_diff) > 50.0) / len(nn_diff) * 100.0)
        hr_bpm = 60000.0 / valid_nn
        hr_mean = float(np.mean(hr_bpm))
        hr_std = float(np.std(hr_bpm))

        if rmssd < 1e-4 or np.all(np.abs(nn_diff) < 1e-4):
            hrv_status = HRVStatus.ZERO_VARIABILITY
            rmssd_status = MeasurementStatus.INSUFFICIENT_VARIANCE
            rmssd_validity = "INVALID"
            rmssd_reason = "Constant RR intervals and zero variability were observed in this input. The signal is unsuitable for meaningful HRV interpretation. This observation alone does not establish the physiological cause."
            calculation_validity = True
            hrv_warnings.append(rmssd_reason)
        elif invalid_count > len(valid_nn):
            hrv_status = HRVStatus.INVALID_INTERVALS
            rmssd_status = MeasurementStatus.INVALID
            rmssd_validity = "INVALID"
            rmssd_reason = f"High invalid interval ratio ({invalid_count}/{len(rr_ms)} intervals outside 270-2000 ms)."
            calculation_validity = False
            hrv_warnings.append(rmssd_reason)
        else:
            hrv_status = HRVStatus.VALID
            rmssd_status = MeasurementStatus.AVAILABLE
            rmssd_validity = "VALID"
            rmssd_reason = None
            calculation_validity = True

        diag = HRVDiagnosticReport(
            ecg_sampling_rate=fs,
            ecg_duration_seconds=duration,
            total_r_peaks_detected=len(pks),
            valid_r_peaks=len(pks),
            total_rr_intervals=len(rr_ms),
            valid_nn_intervals=len(valid_nn),
            invalid_interval_count=invalid_count,
            mean_rr_ms=mean_rr,
            median_rr_ms=median_rr,
            sdnn_ms=sdnn,
            rmssd_ms=rmssd,
            hrv_status=hrv_status,
            detection_algorithm="SciPy find_peaks (Pan-Tompkins heuristic)",
            processing_warnings=hrv_warnings,
            calculation_validity=calculation_validity
        )

        features.append(ExtractedFeature(
            feature_name="hr_mean_bpm",
            value=hr_mean,
            unit="bpm",
            sensor_source="ECG",
            time_window_seconds=duration,
            extraction_method="Peak-to-Peak R-Peak Inversion",
            quality_status=stream.status,
            validity_status="VALID",
            measurement_status=MeasurementStatus.AVAILABLE,
            exploratory_ultra_short_term=False
        ))
        features.append(ExtractedFeature(
            feature_name="hr_std_bpm",
            value=hr_std,
            unit="bpm",
            sensor_source="ECG",
            time_window_seconds=duration,
            extraction_method="Standard deviation of instantaneous HR",
            quality_status=stream.status,
            validity_status="VALID",
            measurement_status=MeasurementStatus.AVAILABLE,
            exploratory_ultra_short_term=False
        ))
        features.append(ExtractedFeature(
            feature_name="hrv_rmssd_ms",
            value=rmssd,
            unit="ms",
            sensor_source="ECG",
            time_window_seconds=duration,
            extraction_method="Root Mean Square of Successive RR Differences (Autonomic Regulation Metric)",
            quality_status=stream.status,
            validity_status=rmssd_validity,
            measurement_status=rmssd_status,
            status_reason=rmssd_reason,
            exploratory_ultra_short_term=is_exploratory
        ))
        features.append(ExtractedFeature(
            feature_name="hrv_sdnn_ms",
            value=sdnn,
            unit="ms",
            sensor_source="ECG",
            time_window_seconds=duration,
            extraction_method="Standard Deviation of NN Intervals",
            quality_status=stream.status,
            validity_status=rmssd_validity,
            measurement_status=rmssd_status,
            status_reason=rmssd_reason,
            exploratory_ultra_short_term=is_exploratory
        ))
        features.append(ExtractedFeature(
            feature_name="mean_rr_ms",
            value=mean_rr,
            unit="ms",
            sensor_source="ECG",
            time_window_seconds=duration,
            extraction_method="Mean inter-beat interval",
            quality_status=stream.status,
            validity_status="VALID",
            measurement_status=MeasurementStatus.AVAILABLE,
            exploratory_ultra_short_term=is_exploratory
        ))
        features.append(ExtractedFeature(
            feature_name="pnn50",
            value=pnn50,
            unit="percent",
            sensor_source="ECG",
            time_window_seconds=duration,
            extraction_method="Percentage of successive RR differences > 50ms",
            quality_status=stream.status,
            validity_status="VALID",
            exploratory_ultra_short_term=is_exploratory
        ))
        return features, diag

    def _extract_eda_features(self, stream: Optional[ValidatedSensorStream]) -> List[ExtractedFeature]:
        """Extract electrodermal tonic and phasic sympathetic features."""
        if stream is None or len(stream.data) == 0:
            return []

        raw = np.asarray(stream.data, dtype=np.float64)
        duration = stream.duration_seconds
        features: List[ExtractedFeature] = []

        eda_mean = float(np.mean(raw))
        eda_std = float(np.std(raw))
        eda_iqr = float(np.percentile(raw, 75) - np.percentile(raw, 25))
        eda_median = float(np.median(raw))

        features.append(ExtractedFeature(
            feature_name="eda_mean",
            value=eda_mean,
            unit="uS",
            sensor_source="EDA",
            time_window_seconds=duration,
            extraction_method="Empirical mean skin conductance",
            quality_status=stream.status,
            validity_status="VALID"
        ))
        features.append(ExtractedFeature(
            feature_name="eda_std",
            value=eda_std,
            unit="uS",
            sensor_source="EDA",
            time_window_seconds=duration,
            extraction_method="Standard deviation of skin conductance",
            quality_status=stream.status,
            validity_status="VALID"
        ))
        features.append(ExtractedFeature(
            feature_name="eda_iqr",
            value=eda_iqr,
            unit="uS",
            sensor_source="EDA",
            time_window_seconds=duration,
            extraction_method="Interquartile Range (Q75 - Q25)",
            quality_status=stream.status,
            validity_status="VALID"
        ))
        features.append(ExtractedFeature(
            feature_name="eda_median",
            value=eda_median,
            unit="uS",
            sensor_source="EDA",
            time_window_seconds=duration,
            extraction_method="Median skin conductance",
            quality_status=stream.status,
            validity_status="VALID"
        ))
        return features

    def _extract_resp_features(self, stream: Optional[ValidatedSensorStream]) -> List[ExtractedFeature]:
        """Extract respiratory mechanics and respiration rate."""
        if stream is None or len(stream.data) == 0:
            return []

        raw = np.asarray(stream.data, dtype=np.float64)
        fs = stream.sampling_rate
        duration = stream.duration_seconds
        features: List[ExtractedFeature] = []

        min_distance = max(1, int(fs * 1.5))
        r_pks, _ = signal.find_peaks(raw, distance=min_distance, prominence=0.5)

        if duration > 0 and len(r_pks) > 0:
            resp_rate = float(len(r_pks) * (60.0 / duration))
            rate_status = MeasurementStatus.AVAILABLE
            rate_validity = "VALID"
            rate_reason = None
        else:
            resp_rate = 0.0
            rate_status = MeasurementStatus.INSUFFICIENT_DATA
            rate_validity = "INVALID"
            rate_reason = "Insufficient respiratory oscillations detected to compute breathing rate."

        resp_std = float(np.std(raw))

        features.append(ExtractedFeature(
            feature_name="resp_rate_bpm",
            value=resp_rate,
            unit="breaths/min",
            sensor_source="RESP",
            time_window_seconds=duration,
            extraction_method="Thoracic expansion peak detection",
            quality_status=stream.status,
            validity_status=rate_validity,
            measurement_status=rate_status,
            status_reason=rate_reason
        ))
        features.append(ExtractedFeature(
            feature_name="resp_std",
            value=resp_std,
            unit="mV",
            sensor_source="RESP",
            time_window_seconds=duration,
            extraction_method="Thoracic respiration amplitude variability",
            quality_status=stream.status,
            validity_status="VALID"
        ))
        return features

    def _extract_temp_features(self, stream: Optional[ValidatedSensorStream]) -> List[ExtractedFeature]:
        """Extract skin thermometry and rate of thermal change."""
        if stream is None or len(stream.data) == 0:
            return []

        raw = np.asarray(stream.data, dtype=np.float64)
        duration = stream.duration_seconds
        features: List[ExtractedFeature] = []

        t_mean = float(np.mean(raw))
        t_std = float(np.std(raw))
        t_median = float(np.median(raw))
        t_min = float(np.min(raw))
        t_max = float(np.max(raw))

        if duration > 1.0:
            rate_c_min = float((raw[-1] - raw[0]) / (duration / 60.0))
        else:
            rate_c_min = 0.0

        features.append(ExtractedFeature(
            feature_name="temp_mean",
            value=t_mean,
            unit="C",
            sensor_source="TEMP",
            time_window_seconds=duration,
            extraction_method="Mean skin surface temperature",
            quality_status=stream.status,
            validity_status="VALID"
        ))
        features.append(ExtractedFeature(
            feature_name="temp_std",
            value=t_std,
            unit="C",
            sensor_source="TEMP",
            time_window_seconds=duration,
            extraction_method="Standard deviation of skin temperature",
            quality_status=stream.status,
            validity_status="VALID"
        ))
        features.append(ExtractedFeature(
            feature_name="temp_rate_of_change_c_min",
            value=rate_c_min,
            unit="C/min",
            sensor_source="TEMP",
            time_window_seconds=duration,
            extraction_method="End-to-end first order thermal derivative",
            quality_status=stream.status,
            validity_status="VALID"
        ))
        return features

    def _extract_emg_features(self, stream: Optional[ValidatedSensorStream]) -> List[ExtractedFeature]:
        """Extract electromyographic muscular activation metrics."""
        if stream is None or len(stream.data) == 0:
            return []

        raw = np.asarray(stream.data, dtype=np.float64)
        duration = stream.duration_seconds
        features: List[ExtractedFeature] = []

        emg_rms = float(np.sqrt(np.mean(raw ** 2)))
        emg_mav = float(np.mean(np.abs(raw)))

        features.append(ExtractedFeature(
            feature_name="emg_rms",
            value=emg_rms,
            unit="mV",
            sensor_source="EMG",
            time_window_seconds=duration,
            extraction_method="Root Mean Square of muscular potential",
            quality_status=stream.status,
            validity_status="VALID"
        ))
        features.append(ExtractedFeature(
            feature_name="emg_mav",
            value=emg_mav,
            unit="mV",
            sensor_source="EMG",
            time_window_seconds=duration,
            extraction_method="Mean Absolute Value of muscular potential",
            quality_status=stream.status,
            validity_status="VALID"
        ))
        return features

    def _extract_acc_features(self, stream: Optional[ValidatedSensorStream]) -> List[ExtractedFeature]:
        """Extract tri-axial inertial and movement context features."""
        if stream is None or len(stream.data) == 0:
            return []

        raw = np.asarray(stream.data, dtype=np.float64)
        duration = stream.duration_seconds
        features: List[ExtractedFeature] = []

        if raw.ndim == 2 and raw.shape[1] >= 3:
            mag = np.sqrt(np.sum(raw[:, :3] ** 2, axis=1))
        elif raw.ndim == 1:
            mag = np.abs(raw)
        else:
            mag = np.sqrt(np.sum(raw.reshape(len(raw), -1) ** 2, axis=1))

        acc_mag_mean = float(np.mean(mag))
        acc_mag_std = float(np.std(mag))

        features.append(ExtractedFeature(
            feature_name="acc_magnitude_mean",
            value=acc_mag_mean,
            unit="g",
            sensor_source="ACC",
            time_window_seconds=duration,
            extraction_method="Mean Euclidean norm of tri-axial acceleration",
            quality_status=stream.status,
            validity_status="VALID"
        ))
        features.append(ExtractedFeature(
            feature_name="acc_magnitude_std",
            value=acc_mag_std,
            unit="g",
            sensor_source="ACC",
            time_window_seconds=duration,
            extraction_method="Standard deviation of acceleration magnitude",
            quality_status=stream.status,
            validity_status="VALID"
        ))
        return features

    def _build_core14(self, feature_map: Dict[str, float]) -> Optional[Core14Features]:
        """Construct validated Core14Features object if all 14 features are present."""
        required = [
            "hr_mean_bpm", "hr_std_bpm", "hrv_rmssd_ms", "hrv_sdnn_ms",
            "eda_mean", "eda_std", "eda_iqr", "resp_rate_bpm", "resp_std",
            "temp_mean", "temp_std", "emg_rms", "acc_magnitude_mean", "acc_magnitude_std"
        ]
        for key in required:
            if key not in feature_map or np.isnan(feature_map[key]):
                return None
        return Core14Features(
            hr_mean_bpm=feature_map["hr_mean_bpm"],
            hr_std_bpm=feature_map["hr_std_bpm"],
            hrv_rmssd_ms=feature_map["hrv_rmssd_ms"],
            hrv_sdnn_ms=feature_map["hrv_sdnn_ms"],
            eda_mean=feature_map["eda_mean"],
            eda_std=feature_map["eda_std"],
            eda_iqr=feature_map["eda_iqr"],
            resp_rate_bpm=feature_map["resp_rate_bpm"],
            resp_std=feature_map["resp_std"],
            temp_mean=feature_map["temp_mean"],
            temp_std=feature_map["temp_std"],
            emg_rms=feature_map["emg_rms"],
            acc_magnitude_mean=feature_map["acc_magnitude_mean"],
            acc_magnitude_std=feature_map["acc_magnitude_std"]
        )
