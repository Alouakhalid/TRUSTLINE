export const ROLES = {
  ASTRONAUT: 'ASTRONAUT',
  MEDICAL_OFFICER: 'MEDICAL_OFFICER',
  ADMINISTRATOR: 'ADMINISTRATOR',
} as const;

export type Role = (typeof ROLES)[keyof typeof ROLES];

export const NAMESPACES = ['SQA', 'PHA', 'RAA', 'MEDICAL_RAG'] as const;
export type Namespace = (typeof NAMESPACES)[number];

export const SENSOR_TYPES = [
  'ecg',
  'heart_rate',
  'spo2',
  'blood_pressure',
  'temperature',
  'respiration',
  'eda',
  'emg',
  'imu',
  'eeg',
] as const;

export const RISK_LEVELS = ['NOMINAL', 'ADVISORY', 'WARNING', 'ALARM'] as const;
export type RiskLevel = (typeof RISK_LEVELS)[number];

export const WS_BASE = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`;
