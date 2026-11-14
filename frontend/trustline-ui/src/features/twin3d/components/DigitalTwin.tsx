import { Suspense, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { useReducedMotion } from '@/shared/hooks/useMediaQuery';
import { AstronautModel, DiagnosticMode } from './AstronautModel';
import { StudioLights } from './StudioLights';
import { Layers, Eye, Activity, RotateCcw } from 'lucide-react';

interface DigitalTwinProps {
  healthStatus?: 'nominal' | 'warning' | 'critical';
  selectedHotspot?: string | null;
  onSelectHotspot?: (id: string) => void;
  diagnosticMode?: DiagnosticMode;
  onDiagnosticModeChange?: (mode: DiagnosticMode) => void;
  showOverlayHud?: boolean;
  className?: string;
  readings?: Map<string, any>;
  multiAgentDecision?: any;
}

export function DigitalTwin({
  healthStatus = 'nominal',
  selectedHotspot,
  onSelectHotspot,
  diagnosticMode: controlledDiagnosticMode,
  onDiagnosticModeChange,
  showOverlayHud = true,
  className = '',
  readings,
  multiAgentDecision,
}: DigitalTwinProps) {
  const reducedMotion = useReducedMotion();
  const [internalMode, setInternalMode] = useState<DiagnosticMode>('suit');
  const diagnosticMode = controlledDiagnosticMode ?? internalMode;
  const setDiagnosticMode = onDiagnosticModeChange ?? setInternalMode;

  return (
    <div className={`twin3d-container ${className}`} role="img" aria-label="3D Digital Twin of astronaut">
      {/* Top Dark Label Bar */}
      {showOverlayHud && (
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          zIndex: 10,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 14px',
          background: 'rgba(10, 12, 14, 0.75)',
          backdropFilter: 'blur(8px)',
          borderBottom: '1px solid var(--color-hairline)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="dot-indicator dot-teal" />
          <span className="dark-label" style={{ color: 'var(--color-ink)' }}>
            BIO-TWIN // ARTICULATED ANATOMICAL MODEL
          </span>
        </div>

        {/* Diagnostic Mode Toggles */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <button
            type="button"
            onClick={() => setDiagnosticMode('suit')}
            className={`btn-sm ${diagnosticMode === 'suit' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ fontSize: '10px', padding: '3px 8px', minHeight: '26px' }}
          >
            <Eye size={12} style={{ marginRight: '4px' }} />
            EVA SUIT
          </button>
          <button
            type="button"
            onClick={() => setDiagnosticMode('wireframe')}
            className={`btn-sm ${diagnosticMode === 'wireframe' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ fontSize: '10px', padding: '3px 8px', minHeight: '26px' }}
          >
            <Layers size={12} style={{ marginRight: '4px' }} />
            WIREFRAME
          </button>
          <button
            type="button"
            onClick={() => setDiagnosticMode('telemetry')}
            className={`btn-sm ${diagnosticMode === 'telemetry' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ fontSize: '10px', padding: '3px 8px', minHeight: '26px' }}
          >
            <Activity size={12} style={{ marginRight: '4px' }} />
            TELEMETRY
          </button>
        </div>
      </div>
      )}

      <Canvas
        dpr={[1, 1.5]}
        camera={{ position: [0, 0.8, 4.2], fov: 36 }}
        frameloop={reducedMotion ? 'demand' : 'always'}
        gl={{ antialias: true, powerPreference: 'high-performance' }}
      >
        <Suspense fallback={null}>
          <StudioLights />
          <AstronautModel
            healthStatus={healthStatus}
            selectedHotspot={selectedHotspot}
            onSelectHotspot={onSelectHotspot}
            diagnosticMode={diagnosticMode}
            readings={readings}
            multiAgentDecision={multiAgentDecision}
          />
          <OrbitControls
            autoRotate={!selectedHotspot}
            autoRotateSpeed={0.4}
            enableZoom={true}
            enablePan={true}
            minDistance={2.5}
            maxDistance={7}
            minPolarAngle={Math.PI / 4}
            maxPolarAngle={Math.PI / 1.6}
          />
        </Suspense>
      </Canvas>

      {/* Bottom Status Rule */}
      {showOverlayHud && (
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          zIndex: 10,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 14px',
          background: 'rgba(10, 12, 14, 0.75)',
          borderTop: '1px solid var(--color-hairline)',
        }}
      >
        <span className="dark-label" style={{ fontSize: '9.5px' }}>
          6 SENSOR HOTSPOTS ACTIVE • CLICK TO INSPECT
        </span>
        <span className="dark-label" style={{ fontSize: '9.5px', color: 'var(--color-teal)' }}>
          MODE: {diagnosticMode.toUpperCase()}
        </span>
      </div>
      )}
    </div>
  );
}
