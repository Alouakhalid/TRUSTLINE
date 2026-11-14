import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { DigitalTwin } from '@/features/twin3d';
import { HOTSPOTS, DiagnosticMode } from '@/features/twin3d/components/AstronautModel';
import { useTelemetry } from '@/features/telemetry';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { useAuth } from '@/features/auth';
import {
  Activity, RotateCw, ExternalLink, Eye, Layers,
  PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen,
  Maximize2, Crosshair, ChevronRight, CheckCircle2, Shield
} from 'lucide-react';

export default function TwinPage() {
  const { astronautId } = useAuth();
  const navigate = useNavigate();
  const { readings, multiAgentDecision } = useTelemetry(true);
  const [manualHealthStatus, setManualHealthStatus] = useState<'nominal' | 'warning' | 'critical'>('nominal');
  const [diagnosticMode, setDiagnosticMode] = useState<DiagnosticMode>('suit');
  const [selectedHotspot, setSelectedHotspot] = useState<string | null>('ecg');
  const [viewMode, setViewMode] = useState<'3d' | '2d'>('3d');
  const [showLeftDrawer, setShowLeftDrawer] = useState(true);
  const [showRightInspector, setShowRightInspector] = useState(true);

  // Sync health status with multiAgentDecision if present, otherwise manual toggle
  const healthStatus = multiAgentDecision?.overall_risk || manualHealthStatus;
  const activeSpot = HOTSPOTS.find((h) => h.id === selectedHotspot) || HOTSPOTS[0];

  const getSpotValue = (spotId: string) => {
    if (spotId === 'ecg') {
      return readings?.get('heart_rate')?.value ?? readings?.get('hr')?.value ?? readings?.get('HR')?.value;
    }
    if (spotId === 'respiration') {
      return readings?.get('respiration')?.value ?? readings?.get('resp')?.value;
    }
    if (spotId === 'temp') {
      return readings?.get('temperature')?.value ?? readings?.get('core_temp')?.value ?? readings?.get('temp')?.value;
    }
    if (spotId === 'spo2') {
      return readings?.get('spo2')?.value ?? readings?.get('SPO2')?.value;
    }
    if (spotId === 'eda') {
      return readings?.get('eda')?.value ?? readings?.get('EDA')?.value;
    }
    if (spotId === 'imu') {
      return readings?.get('imu')?.value ?? readings?.get('IMU')?.value;
    }
    return readings?.get(spotId)?.value;
  };

  const activeVal = getSpotValue(activeSpot.id);
  const displayActive = activeVal !== undefined ? (typeof activeVal === 'number' ? activeVal.toFixed(1) : String(activeVal)) : activeSpot.nominalValue;
  const activeStatus = readings?.get(activeSpot.id)?.status || healthStatus;

  return (
    <div className="twin-fullpage-viewport">
      {/* 3D Scene or 2D Diagram full bleed */}
      {viewMode === '3d' ? (
        <DigitalTwin
          healthStatus={healthStatus}
          diagnosticMode={diagnosticMode}
          onDiagnosticModeChange={setDiagnosticMode}
          selectedHotspot={selectedHotspot}
          onSelectHotspot={(id) => setSelectedHotspot(id)}
          showOverlayHud={false}
          className="twin-fullpage-canvas"
          readings={readings}
          multiAgentDecision={multiAgentDecision}
        />
      ) : (
        <div
          style={{
            height: '100%',
            width: '100%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'radial-gradient(circle at center, #101317 0%, #0A0C0E 100%)',
            position: 'relative',
          }}
        >
          <div
            style={{
              width: '260px',
              height: '460px',
              border: '1px solid var(--color-hairline)',
              borderRadius: '130px 130px 60px 60px',
              position: 'relative',
              background: 'rgba(16, 19, 23, 0.65)',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.45)',
            }}
          >
            {/* Visual Hotspots */}
            {HOTSPOTS.map((h, i) => (
              <button
                key={h.id}
                type="button"
                onClick={() => setSelectedHotspot(h.id)}
                style={{
                  position: 'absolute',
                  top: `${20 + i * 12}%`,
                  left: i % 2 === 0 ? '30%' : '70%',
                  width: '18px',
                  height: '18px',
                  borderRadius: '50%',
                  background: selectedHotspot === h.id ? '#EDE7DC' : '#101317',
                  border: `2px solid ${h.accent === 'amber' ? 'var(--color-amber)' : 'var(--color-teal)'}`,
                  cursor: 'pointer',
                  transform: 'translate(-50%, -50%)',
                  padding: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                title={h.name}
              >
                <span
                  style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    background: h.accent === 'amber' ? 'var(--color-amber)' : 'var(--color-teal)',
                  }}
                />
              </button>
            ))}
          </div>
          <div className="dark-label" style={{ marginTop: '20px', letterSpacing: '0.14em' }}>
            [ 2D HIGH-CONTRAST SCHEMATIC MODE // CREW {astronautId || 'AST-001'} ]
          </div>
        </div>
      )}

      {/* TOP FLOATING HUD BAR */}
      <div
        className="twin-hud-overlay"
        style={{
          top: 14,
          left: 16,
          right: 16,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '10px',
        }}
      >
        {/* Left identity & Title */}
        <div
          className="twin-hud-glass"
          style={{
            padding: '8px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <span className="dot-indicator dot-teal" />
          <div>
            <div className="dark-label" style={{ fontSize: '9.5px', marginBottom: '2px' }}>
              [ MISSION // BIO-TWIN COCKPIT // EXP-72 ]
            </div>
            <h1
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: '15px',
                fontWeight: 700,
                color: 'var(--color-ink)',
                margin: 0,
                letterSpacing: '-0.02em',
              }}
            >
              Articulated Astronaut Digital Twin
            </h1>
          </div>
          <div className="rule-teal" style={{ height: '24px', width: '1px', margin: '0 4px' }} />
          <span
            className="dark-label"
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              color: 'var(--color-ink-secondary)',
            }}
          >
            CREW: {astronautId || 'AST-001'}
          </span>
        </div>

        {/* Center Diagnostic & Health Controls */}
        <div
          className="twin-hud-glass"
          style={{
            padding: '6px 10px',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          {/* Diagnostic Mode Toggles */}
          <div style={{ display: 'flex', background: 'var(--color-ground)', borderRadius: 'var(--radius-xs)', padding: '2px', border: '1px solid var(--color-hairline)' }}>
            <button
              type="button"
              onClick={() => setDiagnosticMode('suit')}
              className={`badge badge--sm ${diagnosticMode === 'suit' ? 'badge--info' : 'badge--outline'}`}
              style={{ cursor: 'pointer', border: 'none', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <Eye size={11} /> EVA SUIT
            </button>
            <button
              type="button"
              onClick={() => setDiagnosticMode('wireframe')}
              className={`badge badge--sm ${diagnosticMode === 'wireframe' ? 'badge--info' : 'badge--outline'}`}
              style={{ cursor: 'pointer', border: 'none', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <Layers size={11} /> WIREFRAME
            </button>
            <button
              type="button"
              onClick={() => setDiagnosticMode('telemetry')}
              className={`badge badge--sm ${diagnosticMode === 'telemetry' ? 'badge--info' : 'badge--outline'}`}
              style={{ cursor: 'pointer', border: 'none', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <Activity size={11} /> TELEMETRY
            </button>
          </div>

          <div className="rule-amber" style={{ height: '18px', width: '1px', margin: '0 4px' }} />

          {/* Health Status Overrides */}
          <Button
            variant={healthStatus === 'nominal' ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setManualHealthStatus('nominal')}
            style={{ fontSize: '11px', padding: '4px 8px' }}
          >
            <span className="dot-indicator dot-teal" style={{ marginRight: '5px' }} />
            Nominal
          </Button>
          <Button
            variant={healthStatus === 'warning' ? 'secondary' : 'ghost'}
            size="sm"
            onClick={() => setManualHealthStatus('warning')}
            style={{ fontSize: '11px', padding: '4px 8px' }}
          >
            <span className="dot-indicator dot-amber" style={{ marginRight: '5px' }} />
            Warning
          </Button>
          <Button
            variant={healthStatus === 'critical' ? 'danger' : 'ghost'}
            size="sm"
            onClick={() => setManualHealthStatus('critical')}
            style={{ fontSize: '11px', padding: '4px 8px' }}
          >
            Critical
          </Button>
        </div>

        {/* Right Mode Switch & HUD Drawers Toggles */}
        <div
          className="twin-hud-glass"
          style={{
            padding: '6px 10px',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <div style={{ display: 'flex', background: 'var(--color-ground)', borderRadius: 'var(--radius-xs)', padding: '2px', border: '1px solid var(--color-hairline)' }}>
            <button
              type="button"
              className={`badge badge--sm ${viewMode === '3d' ? 'badge--info' : 'badge--outline'}`}
              onClick={() => setViewMode('3d')}
              style={{ cursor: 'pointer', border: 'none' }}
            >
              3D Bio-Twin
            </button>
            <button
              type="button"
              className={`badge badge--sm ${viewMode === '2d' ? 'badge--info' : 'badge--outline'}`}
              onClick={() => setViewMode('2d')}
              style={{ cursor: 'pointer', border: 'none' }}
            >
              2D Schematic
            </button>
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowLeftDrawer(!showLeftDrawer)}
            title="Toggle Sensor Directory"
            style={{ padding: '4px 6px' }}
          >
            {showLeftDrawer ? <PanelLeftClose size={15} /> : <PanelLeftOpen size={15} />}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowRightInspector(!showRightInspector)}
            title="Toggle Sensor Inspector"
            style={{ padding: '4px 6px' }}
          >
            {showRightInspector ? <PanelRightClose size={15} /> : <PanelRightOpen size={15} />}
          </Button>
        </div>
      </div>

      {/* LEFT FLOATING HUD DRAWER: Anatomical Sensors */}
      {showLeftDrawer && (
        <div
          className="twin-hud-overlay"
          style={{
            top: 78,
            left: 16,
            width: '260px',
            maxHeight: 'calc(100% - 130px)',
            overflowY: 'auto',
          }}
        >
          <div className="twin-hud-glass" style={{ padding: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span className="dot-indicator dot-teal" />
                <span className="dark-label" style={{ fontSize: '10.5px' }}>
                  6 TELEMETRY ZONES
                </span>
              </div>
              <Badge variant="outline" size="sm">
                LIVE 100Hz
              </Badge>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {HOTSPOTS.map((h) => {
                const isSelected = selectedHotspot === h.id;
                const liveVal = getSpotValue(h.id);
                const displayVal = liveVal !== undefined ? (typeof liveVal === 'number' ? liveVal.toFixed(1) : String(liveVal)) : h.nominalValue;
                const spotStatus = readings?.get(h.id)?.status || healthStatus;

                return (
                  <div
                    key={h.id}
                    onClick={() => setSelectedHotspot(h.id)}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '8px 10px',
                      borderRadius: 'var(--radius-xs)',
                      background: isSelected ? 'rgba(46, 107, 114, 0.16)' : 'var(--color-ground)',
                      border: `1px solid ${isSelected ? 'var(--color-teal)' : 'var(--color-hairline)'}`,
                      borderLeft: `3px solid ${spotStatus === 'critical' ? '#B42828' : h.accent === 'amber' ? 'var(--color-amber)' : 'var(--color-teal)'}`,
                      cursor: 'pointer',
                      transition: 'background var(--duration-fast)',
                    }}
                  >
                    <div>
                      <div
                        style={{
                          fontSize: '12px',
                          fontWeight: 600,
                          color: isSelected ? 'var(--color-ink)' : 'var(--color-ink-secondary)',
                          fontFamily: 'var(--font-body)',
                        }}
                      >
                        {h.name}
                      </div>
                      <div className="dark-label" style={{ fontSize: '9.5px', marginTop: '2px' }}>
                        {h.code}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <span
                        style={{
                          fontSize: '13px',
                          fontFamily: 'var(--font-mono)',
                          fontWeight: 700,
                          color: spotStatus === 'critical' ? '#FF5555' : h.accent === 'amber' ? 'var(--color-amber)' : 'var(--color-teal)',
                        }}
                      >
                        {displayVal}
                      </span>
                      <span style={{ fontSize: '10px', color: 'var(--color-muted)', marginLeft: '3px' }}>
                        {h.unit}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* RIGHT FLOATING HUD INSPECTOR: Active Hotspot */}
      {showRightInspector && activeSpot && (
        <div
          className="twin-hud-overlay"
          style={{
              top: 78,
              right: 16,
              width: '320px',
              maxHeight: 'calc(100% - 130px)',
              overflowY: 'auto',
            }}
          >
            <div className="twin-hud-glass" style={{ padding: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Activity size={16} style={{ color: activeStatus === 'critical' ? '#FF5555' : activeSpot.accent === 'amber' ? 'var(--color-amber)' : 'var(--color-teal)' }} />
                  <span className="dark-label" style={{ fontSize: '11px', color: 'var(--color-ink)' }}>
                    {activeSpot.code} // {activeSpot.name}
                  </span>
                </div>
                <Badge variant={activeStatus === 'nominal' ? 'success' : activeStatus === 'warning' ? 'warning' : 'danger'} size="sm">
                  <span className={`dot-indicator ${activeStatus === 'nominal' ? 'dot-teal' : 'dot-amber'}`} style={{ marginRight: '4px' }} />
                  {activeStatus.toUpperCase()}
                </Badge>
              </div>

              {/* Reading Card */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'baseline',
                  padding: '12px 14px',
                  background: 'var(--color-ground)',
                  border: '1px solid var(--color-hairline)',
                  borderRadius: 'var(--radius-xs)',
                  marginBottom: '12px',
                }}
              >
                <div>
                  <div className="dark-label" style={{ fontSize: '9.5px' }}>TELEMETRY READING</div>
                  <div
                    style={{
                      fontFamily: 'var(--font-display)',
                      fontSize: '32px',
                      fontWeight: 800,
                      fontVariantNumeric: 'tabular-nums',
                      marginTop: '2px',
                      color: 'var(--color-ink)',
                      letterSpacing: '-0.02em',
                    }}
                  >
                    {displayActive}
                    <span className="vital-unit" style={{ fontSize: '13px', marginLeft: '6px' }}>
                      {activeSpot.unit}
                    </span>
                  </div>
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => navigate('/vitals')}
                  icon={<ExternalLink size={13} />}
                  style={{ fontSize: '11px' }}
                >
                  Waveform
                </Button>
              </div>

              {/* Anatomical Placement */}
              <div style={{ fontSize: '12px', color: 'var(--color-ink-secondary)', marginBottom: '12px' }}>
                <span className="dark-label" style={{ display: 'block', fontSize: '9.5px', marginBottom: '3px' }}>
                  ANATOMICAL PLACEMENT
                </span>
                {activeSpot.anatomicalLocation}
              </div>

              {/* Multi-Agent Clinical Evaluation */}
              {multiAgentDecision && (
                <div
                  style={{
                    padding: '10px 12px',
                    background: 'rgba(10, 12, 14, 0.75)',
                    border: `1px solid ${healthStatus === 'critical' ? '#B42828' : healthStatus === 'warning' ? 'var(--color-amber)' : 'var(--color-hairline)'}`,
                    borderLeft: `3px solid ${healthStatus === 'critical' ? '#B42828' : healthStatus === 'warning' ? 'var(--color-amber)' : 'var(--color-teal)'}`,
                    borderRadius: 'var(--radius-xs)',
                    marginBottom: '12px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <span className="dark-label" style={{ fontSize: '9.5px', color: 'var(--color-teal)' }}>
                      [ SQA // PHA // RAA SYNTHESIS ]
                    </span>
                    <Badge variant={healthStatus === 'nominal' ? 'success' : healthStatus === 'warning' ? 'warning' : 'danger'} size="sm">
                      {healthStatus.toUpperCase()}
                    </Badge>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--color-ink)', lineHeight: 1.4 }}>
                    {multiAgentDecision.decision_note}
                  </div>
                  {multiAgentDecision.active_faults && multiAgentDecision.active_faults.length > 0 && (
                    <div style={{ marginTop: '6px', fontSize: '10px', color: 'var(--color-amber)', fontFamily: 'var(--font-mono)' }}>
                      ACTIVE FAULTS: {multiAgentDecision.active_faults.join(', ')}
                    </div>
                  )}
                </div>
              )}

            {/* NASA Standard Bounds */}
            <div
              style={{
                padding: '8px 10px',
                background: 'rgba(10, 12, 14, 0.7)',
                border: '1px solid var(--color-hairline)',
                borderRadius: 'var(--radius-xs)',
                fontSize: '11px',
                fontFamily: 'var(--font-mono)',
                color: 'var(--color-muted)',
                marginBottom: '10px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--color-ink-secondary)', marginBottom: '2px' }}>
                <Shield size={12} style={{ color: 'var(--color-teal)' }} />
                NASA-STD-3001 Vol 1 §4.2 Bounds
              </div>
              <div>Nominal Baseline: CRC-32 Verified / 0.0% Packet Drop</div>
            </div>

            <div className="dark-label" style={{ fontSize: '9.5px', color: 'var(--color-muted)' }}>
              CLICK ANY HOTSPOT ON THE 3D AVATAR TO SWITCH SENSORS
            </div>
          </div>
        </div>
      )}

      {/* BOTTOM FLOATING CONTROLS & HINTS STRIP */}
      <div
        className="twin-hud-overlay"
        style={{
          bottom: 12,
          left: 16,
          right: 16,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '8px',
        }}
      >
        <div
          className="twin-hud-glass"
          style={{
            padding: '6px 12px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '10.5px',
            color: 'var(--color-muted)',
          }}
        >
          <RotateCw size={12} style={{ color: 'var(--color-teal)' }} />
          <span className="dark-label" style={{ fontSize: '9.5px' }}>
            ORBIT: DRAG TO ROTATE • SCROLL TO ZOOM • RIGHT-DRAG TO PAN • CLICK TO INSPECT
          </span>
        </div>

        {/* Hotspot quick jumper pills */}
        <div
          className="twin-hud-glass"
          style={{
            padding: '4px 8px',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          <span className="dark-label" style={{ fontSize: '9px', marginRight: '4px', color: 'var(--color-muted)' }}>
            QUICK FOCUS:
          </span>
          {HOTSPOTS.map((h) => (
            <button
              key={h.id}
              type="button"
              onClick={() => setSelectedHotspot(h.id)}
              className={`badge badge--sm ${selectedHotspot === h.id ? 'badge--info' : 'badge--outline'}`}
              style={{
                cursor: 'pointer',
                border: 'none',
                padding: '2px 6px',
                fontSize: '9.5px',
                fontFamily: 'var(--font-mono)',
              }}
            >
              {h.id.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
