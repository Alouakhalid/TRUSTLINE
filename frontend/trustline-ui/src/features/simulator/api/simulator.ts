export async function fetchSimulatorStatus(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch('/simulator/status');
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export async function fetchSimulatorScenarios(): Promise<Array<{ id: string; value: string; label: string }>> {
  try {
    const res = await fetch('/simulator/scenarios');
    return res.ok ? await res.json() : [];
  } catch {
    return [];
  }
}

export async function startSimulator(scenario = 'SCENARIO_A_REST', astronautId = 'AST-001'): Promise<boolean> {
  try {
    const res = await fetch('/simulator/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario, astronaut_id: astronautId }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function stopSimulator(): Promise<boolean> {
  try {
    const res = await fetch('/simulator/stop', { method: 'POST' });
    return res.ok;
  } catch {
    return false;
  }
}

export async function generateSimulatorStep(seed?: number): Promise<Record<string, unknown> | null> {
  try {
    const url = seed ? `/simulator/step?seed=${seed}` : '/simulator/step';
    const res = await fetch(url, { method: 'POST' });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export async function injectSimulatorFault(faultType: string, targetSensor?: string, severity = 1.0): Promise<boolean> {
  try {
    const res = await fetch('/simulator/fault', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fault_type: faultType, target_sensor: targetSensor, severity }),
    });
    return res.ok;
  } catch {
    return false;
  }
}
