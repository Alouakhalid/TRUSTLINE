"""Generates deterministic raw biosignal files for demonstration and testing."""
import json
from pathlib import Path
import numpy as np

def generate_signals(output_root: Path):
    duration_sec = 60.0
    rng = np.random.RandomState(42)

    ecg_dir = output_root / "raw_signals" / "ECG"
    ecg_dir.mkdir(parents=True, exist_ok=True)
    fs_ecg = 700.0
    n_ecg = int(duration_sec * fs_ecg)
    t_ecg = np.linspace(0.0, duration_sec, n_ecg, endpoint=False)
    hr_hz = 1.2
    ecg_sig = 0.1 * np.sin(2 * np.pi * hr_hz * t_ecg)
    beat_indices = np.arange(0, n_ecg, int(fs_ecg / hr_hz))
    for b in beat_indices:
        if b + 15 < n_ecg:
            ecg_sig[b : b + 15] += 1.5 * np.array([0.1, 0.3, 0.8, 1.4, 1.0, 0.4, -0.3, -0.5, 0.0, 0.1, 0.2, 0.3, 0.2, 0.1, 0.0])
    ecg_sig += 0.02 * rng.randn(n_ecg)
    np.save(str(ecg_dir / "ecg.npy"), ecg_sig.astype(np.float32))
    np.save(str(ecg_dir / "ecg_timestamps.npy"), t_ecg.astype(np.float64))

    eda_dir = output_root / "raw_signals" / "EDA"
    eda_dir.mkdir(parents=True, exist_ok=True)
    fs_eda = 4.0
    n_eda = int(duration_sec * fs_eda)
    t_eda = np.linspace(0.0, duration_sec, n_eda, endpoint=False)
    tonic = 4.5 + 0.3 * np.sin(2 * np.pi * 0.01 * t_eda)
    phasic = np.zeros(n_eda)
    for p in [20, 60, 120, 180]:
        if p + 10 < n_eda:
            phasic[p : p + 10] += 0.8 * np.exp(-np.linspace(0, 3, 10))
    eda_sig = tonic + phasic + 0.01 * rng.randn(n_eda)
    np.save(str(eda_dir / "eda.npy"), eda_sig.astype(np.float32))
    np.save(str(eda_dir / "eda_timestamps.npy"), t_eda.astype(np.float64))

    resp_dir = output_root / "raw_signals" / "RESP"
    resp_dir.mkdir(parents=True, exist_ok=True)
    fs_resp = 700.0
    n_resp = int(duration_sec * fs_resp)
    t_resp = np.linspace(0.0, duration_sec, n_resp, endpoint=False)
    resp_sig = 2.0 * np.sin(2 * np.pi * 0.25 * t_resp) + 0.05 * rng.randn(n_resp)
    np.save(str(resp_dir / "resp.npy"), resp_sig.astype(np.float32))
    np.save(str(resp_dir / "resp_timestamps.npy"), t_resp.astype(np.float64))

    emg_dir = output_root / "raw_signals" / "EMG"
    emg_dir.mkdir(parents=True, exist_ok=True)
    fs_emg = 700.0
    n_emg = int(duration_sec * fs_emg)
    t_emg = np.linspace(0.0, duration_sec, n_emg, endpoint=False)
    emg_sig = 0.05 * rng.randn(n_emg)
    for burst_start in [10000, 25000]:
        if burst_start + 2000 < n_emg:
            emg_sig[burst_start : burst_start + 2000] += 0.4 * rng.randn(2000)
    np.save(str(emg_dir / "emg.npy"), emg_sig.astype(np.float32))
    np.save(str(emg_dir / "emg_timestamps.npy"), t_emg.astype(np.float64))

    acc_dir = output_root / "raw_signals" / "ACC"
    acc_dir.mkdir(parents=True, exist_ok=True)
    fs_acc = 700.0
    n_acc = int(duration_sec * fs_acc)
    t_acc = np.linspace(0.0, duration_sec, n_acc, endpoint=False)
    acc_sig = np.zeros((n_acc, 3), dtype=np.float32)
    acc_sig[:, 0] = 0.02 * rng.randn(n_acc)
    acc_sig[:, 1] = 0.02 * rng.randn(n_acc)
    acc_sig[:, 2] = 0.98 + 0.02 * rng.randn(n_acc)
    np.save(str(acc_dir / "acc.npy"), acc_sig)
    np.save(str(acc_dir / "acc_timestamps.npy"), t_acc.astype(np.float64))

    temp_dir = output_root / "raw_signals" / "TEMP"
    temp_dir.mkdir(parents=True, exist_ok=True)
    fs_temp = 700.0
    n_temp = int(duration_sec * fs_temp)
    t_temp = np.linspace(0.0, duration_sec, n_temp, endpoint=False)
    temp_sig = 34.2 + 0.1 * np.sin(2 * np.pi * 0.005 * t_temp) + 0.005 * rng.randn(n_temp)
    np.save(str(temp_dir / "temp.npy"), temp_sig.astype(np.float32))
    np.save(str(temp_dir / "temp_timestamps.npy"), t_temp.astype(np.float64))

    manifest = {
        "metadata": {
            "astronaut_id": "AST-001",
            "session_id": "SESSION-001",
            "recording_id": "REC-001",
            "data_source": "wearable_sensors",
            "device_id": "TRUSTLINE-BIOHARNESS-V1",
            "environment": "analog_spaceflight_habitat"
        },
        "signals": {
            "ECG": {
                "file": "raw_signals/ECG/ecg.npy",
                "sampling_rate": 700.0,
                "unit": "mV",
                "timestamp_file": "raw_signals/ECG/ecg_timestamps.npy",
                "channels": 1
            },
            "EDA": {
                "file": "raw_signals/EDA/eda.npy",
                "sampling_rate": 4.0,
                "unit": "uS",
                "timestamp_file": "raw_signals/EDA/eda_timestamps.npy",
                "channels": 1
            },
            "RESP": {
                "file": "raw_signals/RESP/resp.npy",
                "sampling_rate": 700.0,
                "unit": "mV",
                "timestamp_file": "raw_signals/RESP/resp_timestamps.npy",
                "channels": 1
            },
            "EMG": {
                "file": "raw_signals/EMG/emg.npy",
                "sampling_rate": 700.0,
                "unit": "mV",
                "timestamp_file": "raw_signals/EMG/emg_timestamps.npy",
                "channels": 1
            },
            "ACC": {
                "file": "raw_signals/ACC/acc.npy",
                "sampling_rate": 700.0,
                "unit": "g",
                "timestamp_file": "raw_signals/ACC/acc_timestamps.npy",
                "channels": 3
            },
            "TEMP": {
                "file": "raw_signals/TEMP/temp.npy",
                "sampling_rate": 700.0,
                "unit": "C",
                "timestamp_file": "raw_signals/TEMP/temp_timestamps.npy",
                "channels": 1
            }
        }
    }

    manifest_path = output_root / "input" / "astronaut_health_data.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

if __name__ == "__main__":
    target = Path(__file__).resolve().parent
    generate_signals(target)
    print("Signals and manifest generated successfully at:", target)
