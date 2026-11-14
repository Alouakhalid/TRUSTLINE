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

export async function configureSimulator(
  scenario: string,
  astronautId?: string,
  randomSeed?: number
): Promise<boolean> {
  try {
    const res = await fetch('/simulator/configure', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario, astronaut_id: astronautId, random_seed: randomSeed }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function startSimulator(scenario = 'SCENARIO_A_REST', astronautId?: string): Promise<boolean> {
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

export async function generateSimulatorStep(
  seed?: number,
  scenario?: string,
  astronautId?: string
): Promise<Record<string, unknown> | null> {
  try {
    const params = new URLSearchParams();
    if (seed !== undefined) params.set('seed', String(seed));
    if (scenario) params.set('scenario', scenario);
    if (astronautId) params.set('astronaut_id', astronautId);
    const qs = params.toString();
    const url = qs ? `/simulator/step?${qs}` : '/simulator/step';
    const res = await fetch(url, { method: 'POST' });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export async function randomizeSimulator(astronautId?: string): Promise<Record<string, unknown> | null> {
  try {
    const params = new URLSearchParams();
    if (astronautId) params.set('astronaut_id', astronautId);
    const qs = params.toString();
    const url = qs ? `/simulator/random-state?${qs}` : '/simulator/random-state';
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
