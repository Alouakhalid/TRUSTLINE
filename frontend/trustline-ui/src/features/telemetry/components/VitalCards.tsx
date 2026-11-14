import { HeartPulse, Droplets, Thermometer, Activity, Wind, Zap, Brain } from 'lucide-react';
import { Card, CardContent } from '@/shared/components/Card';
import { Badge } from '@/shared/components/Badge';
import { Skeleton } from '@/shared/components/Skeleton';

const SENSOR_CONFIG: Record<string, { icon: typeof HeartPulse; label: string; unit: string }> = {
  heart_rate: { icon: HeartPulse, label: 'Heart Rate', unit: 'bpm' },
  spo2: { icon: Droplets, label: 'SpO₂', unit: '%' },
  temperature: { icon: Thermometer, label: 'Core Temp', unit: '°C' },
  blood_pressure: { icon: Activity, label: 'Blood Pressure', unit: 'mmHg' },
  respiration: { icon: Wind, label: 'Respiration', unit: 'br/min' },
  eda: { icon: Zap, label: 'EDA', unit: 'μS' },
  eeg: { icon: Brain, label: 'EEG', unit: 'μV' },
};

interface SensorReading {
  sensor_type: string;
  value: number;
  unit: string;
  status: 'nominal' | 'warning' | 'critical';
}

interface VitalCardsProps {
  readings: Map<string, SensorReading>;
  className?: string;
}

export function VitalCards({ readings, className = '' }: VitalCardsProps) {
  const sensors = Object.keys(SENSOR_CONFIG);

  return (
    <div className={`portal-grid ${className}`}>
      {sensors.map((sensorType) => {
        const config = SENSOR_CONFIG[sensorType];
        const reading = readings.get(sensorType);
        const Icon = config.icon;

        return (
          <Card key={sensorType} className="vital-card" variant="default">
            <CardContent>
              <div className="vital-icon"><Icon size={24} /></div>
              {reading ? (
                <>
                  <div className="vital-value">
                    {typeof reading.value === 'number' ? reading.value.toFixed(1) : reading.value}
                    <span className="vital-unit">{reading.unit || config.unit}</span>
                  </div>
                  <div className="vital-label">{config.label}</div>
                  <Badge
                    variant={reading.status === 'nominal' ? 'success' : reading.status === 'warning' ? 'warning' : 'danger'}
                    size="sm"
                  >
                    {reading.status.toUpperCase()}
                  </Badge>
                </>
              ) : (
                <>
                  <Skeleton width="60%" height={32} />
                  <div className="vital-label">{config.label}</div>
                  <Badge variant="outline" size="sm">WAITING</Badge>
                </>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
