import { useState, useEffect, useCallback, useRef } from 'react';
import { Play, Pause, Square, AlertTriangle, RefreshCw, Dice5, ShieldCheck, Zap } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import { Card, CardHeader, CardContent } from '@/shared/components/Card';
import { Badge } from '@/shared/components/Badge';
import { useAuthStore } from '@/features/auth/stores/auth-store';
import {
  fetchSimulatorScenarios,
  fetchSimulatorStatus,
  configureSimulator,
  startSimulator,
  stopSimulator,
  generateSimulatorStep,
  randomizeSimulator,
  injectSimulatorFault,
} from '../api/simulator';

const FAULTS = [
  { id: 'FLATLINE', label: 'Flatline', desc: 'Zero amplitude sensor drop' },
  { id: 'DRIFT', label: 'Baseline Drift', desc: 'Continuous DC baseline wander' },
  { id: 'CLIPPING', label: 'ADC Clipping', desc: 'Signal saturation at rails' },
  { id: 'NOISE', label: 'Gaussian Noise', desc: 'High-frequency EM interference' },
  { id: 'PACKET_LOSS', label: 'Packet Loss', desc: 'Simulated RF telemetry drop' },
];

interface SimulatorPanelProps {
  className?: string;
}

export function SimulatorPanel({ className = '' }: SimulatorPanelProps) {
  const { astronautId } = useAuthStore();
  const effectiveAstronautId = astronautId || 'AST-002';
  const [isRunning, setIsRunning] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [scenarios, setScenarios] = useState<Array<{ id: string; value: string; label: string }>>([]);
  const [selectedScenario, setSelectedScenario] = useState('SCENARIO_A_REST');
  const [activeFaults, setActiveFaults] = useState<Set<string>>(new Set());
  const [statusMessage, setStatusMessage] = useState('Simulation idle');
  const [randomSeed, setRandomSeed] = useState<number>(42);
  const [stepCount, setStepCount] = useState(0);
  const [lastPacketInfo, setLastPacketInfo] = useState<string>('');
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetchSimulatorScenarios().then((list) => {
      if (list.length > 0) {
        setScenarios(list);
      }
    });
    fetchSimulatorStatus().then((st) => {
      if (st) {
        const isRun = Boolean(st.is_running);
        setIsRunning(isRun);
        if (st.current_scenario) setSelectedScenario(st.current_scenario as string);
        if (isRun) {
          setStatusMessage(`Simulation streaming in background (${st.current_scenario})`);
        }
      }
    });

    const statusPoller = setInterval(() => {
      fetchSimulatorStatus().then((st) => {
        if (st) {
          setIsRunning(Boolean(st.is_running));
        }
      });
    }, 3000);

    return () => {
      clearInterval(statusPoller);
    };
  }, []);

  const runStep = useCallback(async (seedVal?: number, scenVal?: string) => {
    const targetScen = scenVal || selectedScenario;
    const res = await generateSimulatorStep(seedVal, targetScen, effectiveAstronautId);
    if (res) {
      setStepCount((c) => c + 1);
      setLastPacketInfo(`${res.packets_generated} packets synthesized via coupled ODE models.`);
      const scen = (res.scenario as string) || targetScen;
      setStatusMessage(`Active State: ${scen.replace('SCENARIO_', '')} (Propagated to 3D & Vitals)`);
    }
  }, [selectedScenario, effectiveAstronautId]);

  const handleScenarioChange = async (newScen: string) => {
    setSelectedScenario(newScen);
    setStatusMessage(`Configuring: ${newScen.replace('SCENARIO_', '')}...`);
    await configureSimulator(newScen, effectiveAstronautId, randomSeed);
    await runStep(randomSeed, newScen);
  };

  const handleStart = async () => {
    const ok = await startSimulator(selectedScenario, effectiveAstronautId);
    if (ok) {
      setIsRunning(true);
      setIsPaused(false);
      setStatusMessage(`Running in background: ${selectedScenario}`);
      await runStep(randomSeed, selectedScenario);
    }
  };

  const handlePause = async () => {
    if (isRunning) {
      await stopSimulator();
      setIsRunning(false);
      setIsPaused(true);
      setStatusMessage('Simulation Paused');
    } else {
      await handleStart();
      setIsPaused(false);
    }
  };

  const handleStop = async () => {
    await stopSimulator();
    setIsRunning(false);
    setIsPaused(false);
    setActiveFaults(new Set());
    setStatusMessage('Simulation stopped');
  };

  const handleRandomize = async () => {
    const newSeed = Math.floor(Math.random() * 900000) + 100000;
    setRandomSeed(newSeed);
    setStatusMessage(`Randomizing physiological state (Seed: ${newSeed})...`);
    const res = await randomizeSimulator(effectiveAstronautId);
    if (res) {
      setStepCount((c) => c + 1);
      const scen = (res.scenario as string) || selectedScenario;
      setSelectedScenario(scen);
      setStatusMessage(`Randomized to ${scen.replace('SCENARIO_', '')} (Seed: ${newSeed})`);
      setLastPacketInfo(`${res.packets_generated} packets synthesized via coupled ODE models.`);
    }
  };

  const toggleFault = async (faultId: string) => {
    const next = new Set(activeFaults);
    if (next.has(faultId)) {
      next.delete(faultId);
    } else {
      next.add(faultId);
      await injectSimulatorFault(faultId, undefined, 1.0);
    }
    setActiveFaults(next);
    await runStep(randomSeed, selectedScenario);
  };

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  return (
    <Card className={`simulator-panel deck-card ${className}`}>
      <CardHeader>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="dot-indicator dot-amber" />
            <Zap size={18} style={{ color: 'var(--color-amber)' }} />
            <div>
              <div className="dark-label" style={{ fontSize: '9.5px', marginBottom: '2px' }}>[ SYNTHETIC PHYSIOLOGY // FLIGHT SCENARIOS ]</div>
              <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--color-ink)' }}>
                Physiological Scenario Generator
              </h3>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            <Badge variant="outline" size="sm" style={{ borderStyle: 'dashed' }}>
              DEMO / SYNTHETIC ISOLATED
            </Badge>
            <Badge variant={isRunning ? (isPaused ? 'warning' : 'success') : 'outline'}>
              <span className={`dot-indicator ${isRunning ? (isPaused ? 'dot-amber' : 'dot-teal') : 'dot-bone'}`} style={{ marginRight: '4px' }} />
              {isRunning ? (isPaused ? 'PAUSED' : 'ACTIVE') : 'IDLE'}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Scenario Selection */}
          <div>
            <label className="input-label" htmlFor="scenario-select">
              Operational Flight Scenario
            </label>
            <select
              id="scenario-select"
              className="input-field"
              value={selectedScenario}
              onChange={(e) => handleScenarioChange(e.target.value)}
              disabled={isRunning}
            >
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label} ({s.value})
                </option>
              ))}
            </select>
          </div>

          {/* Seed and Step Controls */}
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: '160px' }}>
              <label className="input-label" htmlFor="seed-input">Random Seed</label>
              <input
                id="seed-input"
                type="number"
                className="input-field"
                value={randomSeed}
                onChange={(e) => setRandomSeed(Number(e.target.value))}
                disabled={isRunning}
                style={{ fontFamily: 'var(--font-mono)' }}
              />
            </div>
            <div style={{ paddingTop: '20px', display: 'flex', gap: '8px' }}>
              <Button
                variant="secondary"
                size="md"
                onClick={handleRandomize}
                disabled={isRunning}
                icon={<Dice5 size={16} />}
              >
                Randomize
              </Button>
              <Button
                variant="secondary"
                size="md"
                onClick={() => runStep(randomSeed)}
                icon={<RefreshCw size={16} />}
              >
                Single Step
              </Button>
            </div>
          </div>

          {/* Transport Controls */}
          <div style={{ display: 'flex', gap: '8px' }}>
            <Button
              variant="primary"
              size="md"
              onClick={handleStart}
              disabled={isRunning}
              icon={<Play size={16} />}
            >
              Start Stream
            </Button>
            <Button
              variant="secondary"
              size="md"
              onClick={handlePause}
              disabled={!isRunning}
              icon={<Pause size={16} />}
            >
              {isPaused ? 'Resume' : 'Pause'}
            </Button>
            <Button
              variant="danger"
              size="md"
              onClick={handleStop}
              disabled={!isRunning}
              icon={<Square size={16} />}
            >
              Stop
            </Button>
          </div>

          {/* Fault Injection */}
          <div>
            <p className="input-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <AlertTriangle size={14} style={{ color: 'var(--color-amber)' }} />
              Dynamic Hardware Fault Injection
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '6px' }}>
              {FAULTS.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  className={`badge badge--sm ${activeFaults.has(f.id) ? 'badge--danger' : 'badge--outline'}`}
                  onClick={() => toggleFault(f.id)}
                  style={{ cursor: 'pointer', minHeight: '28px' }}
                  title={f.desc}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {/* Real-time Status / Telemetry Feedback */}
          <div style={{ padding: '12px 14px', background: 'var(--color-ground-secondary)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--color-hairline)', fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
            <div style={{ color: 'var(--color-ink)' }}>STATUS: {statusMessage}</div>
            <div style={{ color: 'var(--color-teal)', marginTop: '4px' }}>
              STEPS GENERATED: {stepCount} {lastPacketInfo && `· ${lastPacketInfo}`}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
