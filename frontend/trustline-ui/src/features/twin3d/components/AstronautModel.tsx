import { useRef, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import { Sphere, Capsule, RoundedBox, Cylinder, Torus, Html } from '@react-three/drei';
import * as THREE from 'three';
import { useReducedMotion } from '@/shared/hooks/useMediaQuery';

export interface Hotspot {
  id: string;
  code: string;
  name: string;
  position: [number, number, number];
  unit: string;
  nominalValue: string;
  anatomicalLocation: string;
  accent: 'teal' | 'amber';
}

export const HOTSPOTS: Hotspot[] = [
  { id: 'ecg', code: 'ECG-01', name: 'Lead-II Precordial Electrodes', position: [-0.12, 1.12, 0.22], unit: 'bpm', nominalValue: '72', anatomicalLocation: 'Precordial 4th intercostal thoracic', accent: 'teal' },
  { id: 'respiration', code: 'RESP-02', name: 'Thoracic Respiratory Bands', position: [0.10, 0.82, 0.21], unit: 'br/min', nominalValue: '16', anatomicalLocation: 'Bilateral costal rib margin', accent: 'amber' },
  { id: 'temp', code: 'TEMP-03', name: 'Supraclavicular Thermometry', position: [0.08, 1.48, 0.12], unit: '°C', nominalValue: '36.8', anatomicalLocation: 'Left supraclavicular thermal window', accent: 'teal' },
  { id: 'spo2', code: 'SPO2-04', name: 'Radial Pulse Oximetry', position: [-0.60, 0.60, 0.08], unit: '%', nominalValue: '98', anatomicalLocation: 'Left radial artery optical array', accent: 'teal' },
  { id: 'eda', code: 'EDA-05', name: 'Palmar Electrodermal Activity', position: [0.60, 0.60, 0.08], unit: 'μS', nominalValue: '4.2', anatomicalLocation: 'Right thenar eminence skin contact', accent: 'amber' },
  { id: 'imu', code: 'IMU-06', name: 'Center-of-Mass IMU Bracket', position: [0.0, 0.36, 0.19], unit: 'g', nominalValue: '0.01', anatomicalLocation: 'Sacral L5-S1 microgravity center', accent: 'teal' },
];

export type DiagnosticMode = 'suit' | 'wireframe' | 'telemetry';

interface AstronautModelProps {
  healthStatus?: 'nominal' | 'warning' | 'critical';
  selectedHotspot?: string | null;
  onSelectHotspot?: (id: string) => void;
  diagnosticMode?: DiagnosticMode;
  readings?: Map<string, any>;
  multiAgentDecision?: any;
}

const PALETTE = {
  suitMatte: '#14181F',
  suitTrim: '#222933',
  suitBone: '#EDE7DC',
  metalDark: '#0A0C0E',
  goldVisor: '#0F1216',
  teal: '#2E6B72',
  amber: '#E8913C',
  alert: '#B42828',
  hairline: 'rgba(237, 231, 220, 0.13)',
};

export function AstronautModel({
  healthStatus = 'nominal',
  selectedHotspot,
  onSelectHotspot,
  diagnosticMode = 'suit',
  readings,
  multiAgentDecision,
}: AstronautModelProps) {
  const groupRef = useRef<THREE.Group>(null);
  const scanlineRef = useRef<THREE.Mesh>(null);
  const chestRef = useRef<THREE.Group>(null);
  const cardiacNodeRef = useRef<THREE.Mesh>(null);
  const [pulseScale, setPulseScale] = useState(1.0);
  const reducedMotion = useReducedMotion();
  const [hovered, setHovered] = useState<string | null>(null);

  const isWireframe = diagnosticMode === 'wireframe';
  const isTelemetry = diagnosticMode === 'telemetry';

  // Live physiological rates from readings
  const liveHr = readings?.get('heart_rate')?.value || readings?.get('hr')?.value || readings?.get('HR')?.value || 72;
  const liveResp = readings?.get('respiration')?.value || readings?.get('resp')?.value || 16;

  // Telemetry node pulse
  useFrame(({ clock }) => {
    if (!groupRef.current || reducedMotion) return;
    const t = clock.elapsedTime;
    // Microgravity idle floating
    groupRef.current.position.y = Math.sin(t * 0.4) * 0.04;
    groupRef.current.rotation.y = Math.sin(t * 0.2) * 0.03;

    // Laser scanline traversing vertically
    if (scanlineRef.current) {
      scanlineRef.current.position.y = 0.5 + Math.sin(t * 1.2) * 1.1;
    }

    // Dynamic Thoracic Respiration breathing expansion (Speed coupled to liveResp)
    if (chestRef.current) {
      const respBreath = Math.sin(t * (liveResp / 60) * Math.PI * 2);
      const breathScale = 1.0 + respBreath * 0.028;
      chestRef.current.scale.set(breathScale, 1.0 + respBreath * 0.016, breathScale);
    }

    // Dynamic Cardiac Rhythm Pulse (Speed coupled to liveHr)
    if (cardiacNodeRef.current) {
      const isCrit = healthStatus === 'critical';
      const cardiacFreq = isCrit ? 0.0 : (liveHr / 60) * Math.PI * 2;
      const pulse = cardiacFreq > 0 ? (Math.sin(t * cardiacFreq) > 0.5 ? 1.35 : 1.0) : 1.0;
      cardiacNodeRef.current.scale.set(pulse, pulse, pulse);
    }
  });

  // Primary suit material
  const suitMaterial = new THREE.MeshStandardMaterial({
    color: isWireframe ? '#2E6B72' : PALETTE.suitMatte,
    roughness: isWireframe ? 0.2 : 0.45,
    metalness: isWireframe ? 0.8 : 0.2,
    wireframe: isWireframe,
  });

  // Secondary trim / collar / joint material
  const trimMaterial = new THREE.MeshStandardMaterial({
    color: isWireframe ? '#E8913C' : PALETTE.suitTrim,
    roughness: 0.5,
    metalness: 0.3,
    wireframe: isWireframe,
  });

  // Warm bone suit highlights
  const boneMaterial = new THREE.MeshStandardMaterial({
    color: PALETTE.suitBone,
    roughness: 0.3,
    metalness: 0.1,
    wireframe: isWireframe,
  });

  // Visor material: dark reflective with subtle gold/teal luster
  const visorMaterial = new THREE.MeshStandardMaterial({
    color: PALETTE.goldVisor,
    roughness: 0.08,
    metalness: 0.95,
  });

  return (
    <group ref={groupRef}>
      {/* ========================================================
          1. HEAD & CRANIAL HELMET
          ======================================================== */}
      {/* Outer Helmet Dome */}
      <Sphere args={[0.33, 32, 32]} position={[0, 1.82, 0]} material={suitMaterial} />

      {/* Gold Reflective Visor */}
      <Sphere args={[0.26, 32, 16]} position={[0, 1.86, 0.11]} rotation={[0.1, 0, 0]} material={visorMaterial} />

      {/* Visor Hairline Accent Ring */}
      <Torus args={[0.262, 0.006, 16, 32]} position={[0, 1.86, 0.11]} rotation={[Math.PI / 2 + 0.1, 0, 0]}>
        <meshBasicMaterial color={PALETTE.teal} />
      </Torus>

      {/* Helmet Neck Collar Ring */}
      <Torus args={[0.31, 0.03, 16, 32]} position={[0, 1.56, 0]} rotation={[Math.PI / 2, 0, 0]} material={trimMaterial} />

      {/* Bilateral Comms / Telemetry Pods */}
      <RoundedBox args={[0.08, 0.12, 0.10]} radius={0.02} position={[-0.34, 1.82, 0]} material={trimMaterial} />
      <RoundedBox args={[0.08, 0.12, 0.10]} radius={0.02} position={[0.34, 1.82, 0]} material={trimMaterial} />

      {/* ========================================================
          2. THORACIC BREASTPLATE & TORSO (BREATHING & PULSE)
          ======================================================== */}
      <group ref={chestRef}>
        {/* Upper Pectoral Contoured Breastplate */}
        <RoundedBox args={[0.66, 0.50, 0.38]} radius={0.08} position={[0, 1.20, 0]} material={suitMaterial} />

        {/* Bone Chest Inlay Accent */}
        <RoundedBox args={[0.42, 0.22, 0.02]} radius={0.02} position={[0, 1.28, 0.195]} material={boneMaterial} />

        {/* Sternal Telemetry Seam Rule */}
        <Cylinder args={[0.004, 0.004, 0.42, 8]} position={[0, 1.20, 0.198]}>
          <meshBasicMaterial color={healthStatus === 'critical' ? PALETTE.alert : healthStatus === 'warning' ? PALETTE.amber : PALETTE.teal} />
        </Cylinder>

        {/* Live Cardiac Rhythm Pulsator Node */}
        <Sphere ref={cardiacNodeRef} args={[0.016, 16, 16]} position={[-0.08, 1.20, 0.205]}>
          <meshBasicMaterial color={healthStatus === 'critical' ? PALETTE.alert : healthStatus === 'warning' ? PALETTE.amber : PALETTE.teal} />
        </Sphere>

        {/* Bilateral Clavicle Harness Straps */}
        <RoundedBox args={[0.10, 0.36, 0.04]} radius={0.01} position={[-0.22, 1.34, 0.17]} rotation={[0, 0, -0.1]} material={trimMaterial} />
        <RoundedBox args={[0.10, 0.36, 0.04]} radius={0.01} position={[0.22, 1.34, 0.17]} rotation={[0, 0, 0.1]} material={trimMaterial} />

        {/* Mid-Thoracic Ribcage Respiration Bands */}
        <Torus args={[0.34, 0.012, 8, 32]} position={[0, 0.98, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <meshBasicMaterial color={isTelemetry ? PALETTE.amber : '#2E3846'} />
        </Torus>
        <Torus args={[0.33, 0.012, 8, 32]} position={[0, 0.86, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <meshBasicMaterial color={isTelemetry ? PALETTE.amber : '#2E3846'} />
        </Torus>

        {/* Abdominal Core Plates */}
        <RoundedBox args={[0.56, 0.36, 0.32]} radius={0.06} position={[0, 0.76, 0]} material={suitMaterial} />

        {/* Pelvic Bio-Harness / Waist Band */}
        <RoundedBox args={[0.54, 0.26, 0.34]} radius={0.04} position={[0, 0.44, 0]} material={trimMaterial} />
        <Torus args={[0.30, 0.02, 16, 32]} position={[0, 0.44, 0]} rotation={[Math.PI / 2, 0, 0]} material={trimMaterial} />
      </group>

      {/* ========================================================
          3. ARTICULATED ARMS & TACTICAL GAUNTLETS
          ======================================================== */}
      {/* Left Shoulder Deltoid Bell */}
      <Sphere args={[0.15, 16, 16]} position={[-0.48, 1.28, 0]} material={trimMaterial} />
      {/* Left Bicep Compression Sleeve */}
      <Capsule args={[0.085, 0.28, 8, 16]} position={[-0.52, 1.02, 0]} rotation={[0, 0, 0.16]} material={suitMaterial} />
      {/* Left Elbow Joint Ring */}
      <Torus args={[0.088, 0.016, 8, 16]} position={[-0.55, 0.82, 0]} rotation={[0, 0, 0.16]} material={trimMaterial} />
      {/* Left Forearm Gauntlet */}
      <Capsule args={[0.08, 0.28, 8, 16]} position={[-0.58, 0.62, 0.04]} rotation={[0, 0, 0.12]} material={suitMaterial} />
      {/* Left Wrist Pulse Oximeter Optical Band */}
      <Torus args={[0.084, 0.01, 8, 16]} position={[-0.60, 0.46, 0.06]} rotation={[0, 0, 0.12]}>
        <meshBasicMaterial color={PALETTE.teal} />
      </Torus>
      {/* Left Tactical Glove Hand */}
      <RoundedBox args={[0.07, 0.12, 0.08]} radius={0.02} position={[-0.61, 0.36, 0.07]} material={trimMaterial} />

      {/* Right Shoulder Deltoid Bell */}
      <Sphere args={[0.15, 16, 16]} position={[0.48, 1.28, 0]} material={trimMaterial} />
      {/* Right Bicep Compression Sleeve */}
      <Capsule args={[0.085, 0.28, 8, 16]} position={[0.52, 1.02, 0]} rotation={[0, 0, -0.16]} material={suitMaterial} />
      {/* Right Elbow Joint Ring */}
      <Torus args={[0.088, 0.016, 8, 16]} position={[0.55, 0.82, 0]} rotation={[0, 0, -0.16]} material={trimMaterial} />
      {/* Right Forearm Gauntlet */}
      <Capsule args={[0.08, 0.28, 8, 16]} position={[0.58, 0.62, 0.04]} rotation={[0, 0, -0.12]} material={suitMaterial} />
      {/* Right Wrist EDA Band */}
      <Torus args={[0.084, 0.01, 8, 16]} position={[0.60, 0.46, 0.06]} rotation={[0, 0, -0.12]}>
        <meshBasicMaterial color={PALETTE.amber} />
      </Torus>
      {/* Right Tactical Glove Hand */}
      <RoundedBox args={[0.07, 0.12, 0.08]} radius={0.02} position={[0.61, 0.36, 0.07]} material={trimMaterial} />

      {/* ========================================================
          4. ARTICULATED LEGS & EVA BOOTS
          ======================================================== */}
      {/* Left Femoral Compression Thigh */}
      <Capsule args={[0.115, 0.44, 8, 16]} position={[-0.18, 0.05, 0]} material={suitMaterial} />
      {/* Left Knee Bio-Hinge Joint */}
      <Cylinder args={[0.11, 0.11, 0.08, 16]} position={[-0.18, -0.26, 0]} rotation={[0, 0, Math.PI / 2]} material={trimMaterial} />
      {/* Left Calf / Tibial Sleeve */}
      <Capsule args={[0.10, 0.42, 8, 16]} position={[-0.18, -0.58, 0]} material={suitMaterial} />
      {/* Left Ankle Seal Ring */}
      <Torus args={[0.104, 0.018, 8, 16]} position={[-0.18, -0.84, 0]} rotation={[Math.PI / 2, 0, 0]} material={trimMaterial} />
      {/* Left EVA Magnetic Grip Boot */}
      <RoundedBox args={[0.16, 0.16, 0.32]} radius={0.03} position={[-0.18, -0.96, 0.06]} material={trimMaterial} />

      {/* Right Femoral Compression Thigh */}
      <Capsule args={[0.115, 0.44, 8, 16]} position={[0.18, 0.05, 0]} material={suitMaterial} />
      {/* Right Knee Bio-Hinge Joint */}
      <Cylinder args={[0.11, 0.11, 0.08, 16]} position={[0.18, -0.26, 0]} rotation={[0, 0, Math.PI / 2]} material={trimMaterial} />
      {/* Right Calf / Tibial Sleeve */}
      <Capsule args={[0.10, 0.42, 8, 16]} position={[0.18, -0.58, 0]} material={suitMaterial} />
      {/* Right Ankle Seal Ring */}
      <Torus args={[0.104, 0.018, 8, 16]} position={[0.18, -0.84, 0]} rotation={[Math.PI / 2, 0, 0]} material={trimMaterial} />
      {/* Right EVA Magnetic Grip Boot */}
      <RoundedBox args={[0.16, 0.16, 0.32]} radius={0.03} position={[0.18, -0.96, 0.06]} material={trimMaterial} />

      {/* ========================================================
          5. BACKPACK PLSS (PRIMARY LIFE SUPPORT SYSTEM)
          ======================================================== */}
      {/* Main Backpack Chassis */}
      <RoundedBox args={[0.50, 0.74, 0.26]} radius={0.05} position={[0, 1.05, -0.28]} material={trimMaterial} />

      {/* Dual O2 / N2 Manifold Pressure Regulators */}
      <Cylinder args={[0.055, 0.055, 0.09, 16]} position={[-0.14, 1.46, -0.28]} material={suitMaterial} />
      <Cylinder args={[0.055, 0.055, 0.09, 16]} position={[0.14, 1.46, -0.28]} material={suitMaterial} />

      {/* Spinal Fiber-Optic Telemetry Bus (Vertical Node Array) */}
      {[1.32, 1.18, 1.04, 0.90, 0.76].map((yPos, i) => (
        <Sphere key={`spine-${i}`} args={[0.015, 8, 8]} position={[0, yPos, -0.16]}>
          <meshBasicMaterial color={i % 2 === 0 ? PALETTE.teal : PALETTE.amber} />
        </Sphere>
      ))}

      {/* ========================================================
          6. DIAGNOSTIC LASER SCANLINE SWEEP
          ======================================================== */}
      <Torus
        ref={scanlineRef}
        args={[0.62, 0.005, 8, 48]}
        position={[0, 0.8, 0]}
        rotation={[Math.PI / 2, 0, 0]}
      >
        <meshBasicMaterial color={PALETTE.teal} transparent opacity={0.65} />
      </Torus>

      {/* ========================================================
          7. INTERACTIVE SENSOR HOTSPOTS WITH DARK LABEL HUD
          ======================================================== */}
      {HOTSPOTS.map((spot) => {
        const isSelected = selectedHotspot === spot.id;
        const isHovered = hovered === spot.id;
        const scale = isSelected ? 1.5 : isHovered ? 1.25 : 1.0;

        // Retrieve live telemetry value
        const liveVal = readings?.get(spot.id)?.value ?? (
          spot.id === 'ecg' ? (readings?.get('heart_rate')?.value ?? readings?.get('HR')?.value) :
          spot.id === 'respiration' ? readings?.get('respiration')?.value :
          spot.id === 'temp' ? (readings?.get('temperature')?.value ?? readings?.get('core_temp')?.value) :
          spot.id === 'spo2' ? readings?.get('spo2')?.value :
          spot.id === 'eda' ? readings?.get('eda')?.value :
          spot.id === 'imu' ? readings?.get('imu')?.value : undefined
        );
        const displayVal = liveVal !== undefined ? (typeof liveVal === 'number' ? liveVal.toFixed(1) : String(liveVal)) : spot.nominalValue;
        const spotStatus = readings?.get(spot.id)?.status || healthStatus;
        const isCritical = spotStatus === 'critical' || (spot.id === 'ecg' && healthStatus === 'critical');
        const accentColor = isCritical ? PALETTE.alert : spot.accent === 'amber' ? PALETTE.amber : PALETTE.teal;

        return (
          <group key={spot.id} position={spot.position}>
            {/* Outer Concentric Hairline Ring */}
            <Torus args={[0.055 * scale, 0.004, 8, 24]} rotation={[0, 0, 0]}>
              <meshBasicMaterial color={accentColor} transparent opacity={isSelected ? 1.0 : isCritical ? 0.9 : 0.6} />
            </Torus>

            {/* Central Precision Sensor Beacon Pin */}
            <Sphere
              args={[0.035 * scale, 16, 16]}
              onClick={(e) => {
                e.stopPropagation();
                onSelectHotspot?.(spot.id);
              }}
              onPointerOver={(e) => {
                e.stopPropagation();
                setHovered(spot.id);
                document.body.style.cursor = 'pointer';
              }}
              onPointerOut={(e) => {
                e.stopPropagation();
                setHovered(null);
                document.body.style.cursor = 'default';
              }}
            >
              <meshBasicMaterial color={isSelected ? '#FFFFFF' : accentColor} />
            </Sphere>

            {/* Dark Label Tooltip */}
            {(isSelected || isHovered) && (
              <Html distanceFactor={7} position={[0, 0.12, 0]}>
                <div
                  style={{
                    background: '#101317',
                    border: `1px solid ${isCritical ? PALETTE.alert : 'rgba(237, 231, 220, 0.18)'}`,
                    borderRadius: '3px',
                    padding: '6px 10px',
                    color: '#EDE7DC',
                    fontFamily: 'var(--font-body)',
                    fontSize: '11px',
                    lineHeight: 1.4,
                    whiteSpace: 'nowrap',
                    pointerEvents: 'none',
                    transform: 'translate3d(-50%, -100%, 0)',
                    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.65)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                    <span
                      style={{
                        display: 'inline-block',
                        width: '5px',
                        height: '5px',
                        borderRadius: '50%',
                        background: accentColor,
                      }}
                    />
                    <span style={{ textTransform: 'uppercase', letterSpacing: '0.12em', fontWeight: 600, fontSize: '10px', color: '#9EA5A8' }}>
                      {spot.code} // {spot.anatomicalLocation}
                    </span>
                  </div>
                  <div style={{ fontWeight: 600, fontSize: '12px' }}>
                    {spot.name}: <span style={{ color: accentColor, fontFamily: 'var(--font-mono)' }}>{displayVal} {spot.unit}</span>
                  </div>
                  <div style={{ fontSize: '9.5px', color: isCritical ? '#FF5555' : '#6C7378', textTransform: 'uppercase', letterSpacing: '0.10em', marginTop: '2px' }}>
                    STATUS: {spotStatus.toUpperCase()} [TELEMETRY_LIVE]
                  </div>
                </div>
              </Html>
            )}
          </group>
        );
      })}
    </group>
  );
}

