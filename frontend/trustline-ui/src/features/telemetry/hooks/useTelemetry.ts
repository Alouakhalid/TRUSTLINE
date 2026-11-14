import { useState, useCallback, useRef, useEffect } from 'react';
import { useWebSocket } from '@/shared/hooks/useWebSocket';
import { useAuthStore } from '@/features/auth/stores/auth-store';
import { api } from '@/shared/lib/api-client';

export interface SensorReading {
  sensor_type: string;
  value: number;
  unit: string;
  timestamp: number;
  status: 'nominal' | 'warning' | 'critical';
  channels?: Record<string, number>;
}

export interface MultiAgentDecision {
  overall_risk: 'nominal' | 'warning' | 'critical';
  quality_status: 'nominal' | 'warning' | 'critical';
  active_faults: string[];
  sqa_validity: 'VALID' | 'QUARANTINED';
  decision_note: string;
  timestamp_epoch_ms: number;
}

const THRESHOLDS: Record<string, { warning: [number, number]; critical: [number, number] }> = {
  heart_rate: { warning: [50, 100], critical: [40, 120] },
  hr: { warning: [50, 100], critical: [40, 120] },
  spo2: { warning: [94, 100], critical: [90, 100] },
  temperature: { warning: [36.0, 37.5], critical: [35.0, 38.5] },
  core_temp: { warning: [36.0, 37.5], critical: [35.0, 38.5] },
  temp: { warning: [36.0, 37.5], critical: [35.0, 38.5] },
  blood_pressure: { warning: [90, 140], critical: [80, 160] },
  blood_pressure_systolic: { warning: [90, 140], critical: [80, 160] },
  respiration: { warning: [12, 20], critical: [8, 25] },
  eda: { warning: [1.0, 20.0], critical: [0.5, 30.0] },
};

function classifyStatus(sensorType: string, value: number): 'nominal' | 'warning' | 'critical' {
  const normType = sensorType.toLowerCase();
  const threshold = THRESHOLDS[normType];
  if (!threshold) return 'nominal';

  const [critLow, critHigh] = threshold.critical;
  if (value < critLow || value > critHigh) return 'critical';

  const [warnLow, warnHigh] = threshold.warning;
  if (value < warnLow || value > warnHigh) return 'warning';

  return 'nominal';
}

function getUnit(sensorType: string): string {
  const s = sensorType.toLowerCase();
  if (s === 'hr' || s === 'heart_rate') return 'bpm';
  if (s === 'spo2') return '%';
  if (s === 'core_temp' || s === 'temperature' || s === 'temp' || s === 'skin_temp') return '°C';
  if (s === 'blood_pressure' || s === 'ppg') return 'mmHg';
  if (s === 'respiration' || s === 'resp') return 'br/min';
  if (s === 'eda') return 'μS';
  if (s === 'emg') return 'mV';
  if (s === 'ecg') return 'mV';
  if (s === 'eeg') return 'μV';
  if (s === 'imu') return 'g';
  return '';
}

function getAliases(key: string): string[] {
  const k = key.toLowerCase();
  if (k === 'hr' || k === 'heart_rate' || k === 'heartrate') return ['heart_rate', 'hr', 'HR'];
  if (k === 'spo2') return ['spo2', 'SPO2'];
  if (k === 'core_temp' || k === 'temperature' || k === 'temp') return ['temperature', 'core_temp', 'temp', 'CORE_TEMP'];
  if (k === 'respiration' || k === 'resp') return ['respiration', 'resp', 'RESPIRATION'];
  if (k === 'eda') return ['eda', 'EDA'];
  if (k === 'ppg' || k === 'blood_pressure') return ['blood_pressure', 'ppg', 'PPG', 'BLOOD_PRESSURE'];
  if (k === 'eeg') return ['eeg', 'EEG'];
  if (k === 'ecg') return ['ecg', 'ECG'];
  if (k === 'imu') return ['imu', 'IMU'];
  return [key, key.toLowerCase(), key.toUpperCase()];
}

function normalizeSensorValue(type: string, rawVal: number): number {
  const norm = type.toLowerCase();
  if (norm === 'ppg' || norm === 'blood_pressure') {
    if (rawVal < 20) return Number((118.0 + rawVal * 10).toFixed(1));
  }
  if (norm === 'respiration' || norm === 'resp') {
    if (rawVal < 5 && rawVal > -5) return Number((15.0 + rawVal * 3).toFixed(1));
  }
  return typeof rawVal === 'number' ? Number(rawVal.toFixed(2)) : rawVal;
}

const DEFAULT_NOMINAL_READINGS = (): Map<string, SensorReading> => {
  const map = new Map<string, SensorReading>();
  const nominals: Array<[string, number, string]> = [
    ['heart_rate', 72.0, 'bpm'],
    ['hr', 72.0, 'bpm'],
    ['HR', 72.0, 'bpm'],
    ['spo2', 98.4, '%'],
    ['SPO2', 98.4, '%'],
    ['temperature', 36.8, '°C'],
    ['core_temp', 36.8, '°C'],
    ['temp', 36.8, '°C'],
    ['CORE_TEMP', 36.8, '°C'],
    ['blood_pressure', 118.5, 'mmHg'],
    ['ppg', 118.5, 'mmHg'],
    ['PPG', 118.5, 'mmHg'],
    ['respiration', 15.6, 'br/min'],
    ['resp', 15.6, 'br/min'],
    ['RESPIRATION', 15.6, 'br/min'],
    ['eda', 3.8, 'μS'],
    ['EDA', 3.8, 'μS'],
    ['eeg', 24.2, 'μV'],
    ['EEG', 24.2, 'μV'],
  ];
  for (const [k, val, unit] of nominals) {
    map.set(k, {
      sensor_type: k,
      value: val,
      unit,
      timestamp: Date.now(),
      status: 'nominal',
    });
  }
  return map;
};

export function useTelemetry(enabled = true) {
  const { astronautId } = useAuthStore();
  const [readings, setReadings] = useState<Map<string, SensorReading>>(DEFAULT_NOMINAL_READINGS);
  const [lastPacketTime, setLastPacketTime] = useState<number | null>(null);
  const [isStale, setIsStale] = useState(false);
  const [ecgWave, setEcgWave] = useState<number[]>([]);
  const [respWave, setRespWave] = useState<number[]>([]);
  const [multiAgentDecision, setMultiAgentDecision] = useState<MultiAgentDecision | null>(null);
  const staleTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Initial load of latest telemetry from database
  useEffect(() => {
    if (!enabled) return;
    const targetAstronaut = astronautId || 'AST-001';
    api.getLatestTelemetry(targetAstronaut)
      .then((packets) => {
        if (!packets || packets.length === 0) return;
        setReadings((prev) => {
          const next = new Map(prev);
          for (const p of packets) {
            const rawType = (p.sensor_type as string) || '';
            const channelsData = (p.channels_data as number[][]) || [];
            let val = 0;
            if (channelsData.length > 0 && channelsData[0].length > 0) {
              val = channelsData[0][channelsData[0].length - 1];
            }
            const normVal = normalizeSensorValue(rawType, val);
            const reading: SensorReading = {
              sensor_type: rawType,
              value: normVal,
              unit: getUnit(rawType),
              timestamp: (p.timestamp_epoch_ms as number) || Date.now(),
              status: classifyStatus(rawType, normVal),
            };
            for (const alias of getAliases(rawType)) {
              next.set(alias, reading);
            }
          }
          if (!next.has('eeg')) {
            next.set('eeg', {
              sensor_type: 'EEG',
              value: 24.2,
              unit: 'μV',
              timestamp: Date.now(),
              status: 'nominal',
            });
          }
          return next;
        });
        setLastPacketTime(Date.now());
      })
      .catch(() => {});
  }, [astronautId, enabled]);

  const handleMessage = useCallback((data: Record<string, unknown>) => {
    const timestamp = (data.timestamp_epoch_ms as number) || Date.now();

    // 1. Snapshot broadcast from simulator step
    if (data.type === 'telemetry_snapshot') {
      const snapshotReadings = data.readings as Record<string, number> | undefined;
      if (snapshotReadings) {
        setReadings((prev) => {
          const next = new Map(prev);
          for (const [key, val] of Object.entries(snapshotReadings)) {
            const rawVal = typeof val === 'number' ? val : Number(val);
            const numVal = normalizeSensorValue(key, rawVal);
            const reading: SensorReading = {
              sensor_type: key,
              value: numVal,
              unit: getUnit(key),
              timestamp,
              status: classifyStatus(key, numVal),
            };
            for (const alias of getAliases(key)) {
              next.set(alias, reading);
            }
          }
          if (!next.has('eeg')) {
            next.set('eeg', {
              sensor_type: 'EEG',
              value: 24.2,
              unit: 'μV',
              timestamp: Date.now(),
              status: 'nominal',
            });
          }
          return next;
        });
      }

      if (Array.isArray(data.ecg_wave) && data.ecg_wave.length > 0) {
        setEcgWave(data.ecg_wave as number[]);
      }
      if (Array.isArray(data.resp_wave) && data.resp_wave.length > 0) {
        setRespWave(data.resp_wave as number[]);
      }
      if (data.agent_decision) {
        setMultiAgentDecision(data.agent_decision as MultiAgentDecision);
        try {
          window.dispatchEvent(new CustomEvent('trustline:assessment-updated'));
        } catch {
          /* ignore */
        }
      }

      setLastPacketTime(Date.now());
      setIsStale(false);
      return;
    }

    // 2. Individual packet broadcast
    if (data.type === 'telemetry_packet') {
      const sensorType = data.sensor_type as string;
      const channels = data.channels as Record<string, number> | undefined;
      const rawPrimary = typeof data.value === 'number'
        ? data.value
        : channels ? Object.values(channels)[0] ?? 0 : 0;
      const primaryValue = normalizeSensorValue(sensorType, rawPrimary);

      const reading: SensorReading = {
        sensor_type: sensorType,
        value: typeof primaryValue === 'number' ? Number(primaryValue.toFixed(2)) : primaryValue,
        unit: getUnit(sensorType),
        timestamp,
        status: classifyStatus(sensorType, primaryValue),
        channels,
      };

      setReadings((prev) => {
        const next = new Map(prev);
        for (const alias of getAliases(sensorType)) {
          next.set(alias, reading);
        }
        return next;
      });

      const rawChannelsData = data.channels_data as number[][] | undefined;
      const typeUpper = (sensorType || '').toUpperCase();
      if ((typeUpper === 'ECG' || typeUpper === 'LEAD-II') && Array.isArray(rawChannelsData) && rawChannelsData.length > 0 && Array.isArray(rawChannelsData[0])) {
        const samples = rawChannelsData[0];
        if (samples.length > 0) {
          setEcgWave((prev) => [...prev.slice(-(180 - samples.length)), ...samples]);
        }
      } else if ((typeUpper === 'RESPIRATION' || typeUpper === 'RESP') && Array.isArray(rawChannelsData) && rawChannelsData.length > 0 && Array.isArray(rawChannelsData[0])) {
        const samples = rawChannelsData[0];
        if (samples.length > 0) {
          setRespWave((prev) => [...prev.slice(-(180 - samples.length)), ...samples]);
        }
      }

      if (data.agent_decision) {
        setMultiAgentDecision(data.agent_decision as MultiAgentDecision);
      }

      setLastPacketTime(Date.now());
      setIsStale(false);
    }
  }, []);

  const { status } = useWebSocket({
    astronautId: astronautId || 'AST-001',
    enabled,
    onMessage: handleMessage,
  });

  useEffect(() => {
    staleTimerRef.current = setInterval(() => {
      if (lastPacketTime && Date.now() - lastPacketTime > 15000) {
        setIsStale(true);
      }
    }, 3000);
    return () => {
      if (staleTimerRef.current) clearInterval(staleTimerRef.current);
    };
  }, [lastPacketTime]);

  return {
    readings,
    status,
    lastPacketTime,
    isStale,
    ecgWave,
    respWave,
    multiAgentDecision,
  };
}
