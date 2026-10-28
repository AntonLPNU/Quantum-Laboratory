import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, PanelBottomClose, PanelBottomOpen, Play, Save, SlidersHorizontal } from 'lucide-react';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import { ApiConnectionError, api, type ApiEnvelope } from './api';
import { SceneCanvas } from './components/SceneCanvas';
import { TopBar } from './components/TopBar';
import { ToolRail } from './components/ToolRail';
import { Inspector } from './components/Inspector';
import { Timeline, type TimelineData } from './components/Timeline';
import { modes, schematicSpins, type Spin } from './data/mockData';
import { usePlayback } from './hooks/usePlayback';
import { ScientificDocumentation } from './components/ScientificDocumentation';
import { ParameterHelp } from './components/ParameterHelp';
import { MathInline } from './components/Math';

type Mode = 'model' | 'interaction' | 'receiver' | 'analyzer' | 'validation' | 'docs';
type StateResult = { density_matrix: unknown; n_spins: number; pair: number[]; spin_observables: { site: number; bloch: { x: number; y: number; z: number } }[] };
type Envelope = ApiEnvelope<any>;
const schedule = (value: number) => ({ kind: 'constant', parameters: [value], edges_s: [], values: [] });
const times = (duration: number, count = 41) => Array.from({ length: count }, (_, i) => duration * i / (count - 1));

/** Selects concise result fields for display without modifying the Python response or recomputing physics. */
function summarize(envelope: Envelope): Record<string, unknown> {
  const value = envelope.result;
  if (!value || typeof value !== 'object') return { value };
  const keys = ['n_spins', 'pair', 'spin_observables', 'model', 'state_name', 'concurrence', 'chsh_maximal', 'chsh_fixed', 'theoretical_chsh', 'sampled_chsh', 'sampled_chsh_standard_error', 'correlator', 'status', 'metrics', 'diagnostics', 'reproduction_status', 'valid_trials', 'source_rows', 'source_sha256', 'interpretation', 'exact', 'sample', 'sampling_analysis', 'statistical_criteria', 'power_preflight', 'positive_control_preflight', 'preregistration_hash', 'record_name', 'parameters', 'standard_errors', 'residual_sum_squares', 'degrees_of_freedom', 'back_action', 'observations_are_paired', 'reduced_density_matrix', 'keep_order', 'comparison'];
  const result: Record<string, unknown> = {};
  for (const key of keys) if (key in value) result[key] = value[key];
  if (value.results?.diagnostics) result.diagnostics = value.results.diagnostics;
  if (value.results?.completed !== undefined) result.completed = value.results.completed;
  if (value.scenarios) result.scenarios = Object.fromEntries(Object.entries(value.scenarios).map(([name, item]: [string, any]) => [name, { status: item.status, times_s: item.times_s, trace_distance: item.trace_distance }]));
  if (value.hensen_2015 || value.hensen_2016) result.year_specific = { hensen_2015: value.hensen_2015, hensen_2016: value.hensen_2016, combined_summary: value.combined_summary };
  return result;
}

/** Adapts Python-produced plot arrays and static formula labels to the presentation chart contract. */
function chartData(envelope: Envelope | null): TimelineData | undefined {
  const value = envelope?.result;
  if (!value) return undefined;
  const plot = value.plot_data;
  if (plot?.time_s && plot?.series) {
    const [scenario, sites] = Object.entries(plot.series)[0] ?? [];
    const [site, values] = sites && typeof sites === 'object' ? Object.entries(sites)[0] ?? [] : [];
    if (Array.isArray(values)) return { label: `Середнє σz · ${scenario} · спін ${site}`, formula: '\\langle\\sigma_z^{(i)}\\rangle', values: values.map(Number), times: plot.time_s.map(Number), unit: 'с', kind: 'точні очікувані значення' };
  }
  const observables = value.results?.observables;
  if (observables && Array.isArray(value.configuration?.times_s)) {
    const found = Object.entries(observables).find(([name]) => name.toLowerCase().includes('sigma_z') || name.toLowerCase().endsWith('_z'))?.[1] as any;
    if (Array.isArray(found)) return { label: 'TFIM середнє σz · спін 0', formula: '\\langle\\sigma_z^{(0)}\\rangle', values: found.map((row: any) => Array.isArray(row) ? Number(row[0]) : Number(row)), times: value.configuration.times_s.map(Number), unit: 'с', kind: 'чисельна еволюція Python' };
  }
  if (Array.isArray(value.concurrence) && Array.isArray(value.lambdas_a)) return { label: `Concurrence · λB = ${Array.isArray(value.lambdas_b) ? Number(value.lambdas_b[0]).toPrecision(3) : '—'}`, formula: 'C(\\lambda_A,\\lambda_B)', values: value.concurrence.map((row: any[]) => Number(row[0])), times: value.lambdas_a.map(Number), unit: 'λA', kind: 'точна сітка затухання' };
  return undefined;
}

/** Main UI state coordinator; delegates numerical calculations to the local Python API. */
export function App() {
  const [mode, setMode] = useState<Mode>('model');
  const [documentationTopic, setDocumentationTopic] = useState('overview');
  const [connected, setConnected] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [scienceOpen, setScienceOpen] = useState(false), [toolsOpen, setToolsOpen] = useState(false), [inspectorOpen, setInspectorOpen] = useState(false), [timelineOpen, setTimelineOpen] = useState(false);
  const [scienceExpanded, setScienceExpanded] = useState(false);
  const [selected, setSelected] = useState(0), [n, setN] = useState(5), [pair, setPair] = useState<[number, number]>([0, 2]), [bell, setBell] = useState('singlet');
  const [shots, setShots] = useState(2000), [seed, setSeed] = useState(42), [lambdaA, setLambdaA] = useState(0), [lambdaB, setLambdaB] = useState(0);
  const [keepSites, setKeepSites] = useState<number[]>([0, 2]), [showDensity, setShowDensity] = useState(false);
  const [keepChoice, setKeepChoice] = useState(1);
  const [J, setJ] = useState(100000), [h, setH] = useState(200000), [duration, setDuration] = useState(1e-6);
  const [rotationSite, setRotationSite] = useState(0), [rotationAxis, setRotationAxis] = useState<'x' | 'y' | 'z'>('z'), [rotationAngle, setRotationAngle] = useState(0.25);
  const [fitOmega, setFitOmega] = useState(1000000);
  const [sequenceSite1, setSequenceSite1] = useState(0), [sequenceSite2, setSequenceSite2] = useState(0), [sequenceDeltaT, setSequenceDeltaT] = useState(1e-7);
  const [state, setState] = useState<StateResult | null>(null), [last, setLast] = useState<Envelope | null>(null);
  const [trajectory, setTrajectory] = useState<{ times: number[]; states: unknown[][] } | null>(null);
  const [controls, setControls] = useState<OrbitControlsImpl | null>(null), [fps, setFps] = useState(0);
  const [tool, setTool] = useState<'orbit' | 'pan' | 'zoom'>('orbit'), [camera, setCamera] = useState<'orbit' | 'fly'>('orbit');
  const [viewport, setViewport] = useState({ width: window.innerWidth, height: window.innerHeight });
  const [records, setRecords] = useState<string[]>([]), [recordName, setRecordName] = useState('');
  const [compareLeft, setCompareLeft] = useState(''), [compareRight, setCompareRight] = useState('');
  const [comparison, setComparison] = useState<Envelope | null>(null);
  const [playIndex, setPlayIndex] = useState(0);
  const playback = usePlayback();
  const onControlsReady = useCallback((value: OrbitControlsImpl | null) => setControls(value), []);
  const modeLabel = modes.find(item => item.id === mode)?.label ?? 'Модель';
  const spins = useMemo<Spin[]>(() => schematicSpins.slice(0, n).map((item, i) => {
    const bloch = state?.spin_observables[i]?.bloch;
    const vector: readonly [number, number, number] = bloch ? [bloch.x, bloch.y, bloch.z] : [0, 0, 0];
    return { ...item, coordinate: `схема ${i + 1}`, state: 'ρ із Python', expectation: vector[2].toFixed(5), bloch: vector };
  }), [n, state]);
  const selectedSpin = spins[selected] ?? spins[0];
  const graph = useMemo(() => chartData(last), [last]);
  const request = useCallback(async <T = any,>(route: string, body?: unknown): Promise<T> => {
    try {
      const result = await api<T>(route, body);
      setConnected(true);
      return result;
    } catch (error) {
      if (error instanceof ApiConnectionError) setConnected(false);
      throw error;
    }
  }, []);

  const showTrajectoryIndex = useCallback(async (index: number) => {
    setPlayIndex(index);
    const raw = trajectory?.states[index];
    if (!raw) return;
    try {
      const inspected = await request<Envelope>('/api/state/inspect', { density_matrix: raw });
      setState({ density_matrix: raw, n_spins: inspected.result.n_spins, pair, spin_observables: inspected.result.spin_observables });
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }, [trajectory, pair, request]);

  useEffect(() => {
    let active = true;
    request('/api/health').catch(e => active && setError(e.message));
    request<Envelope>('/api/state', { n_spins: 5, pair: [0, 2], bell: 'singlet' }).then(result => {
      if (active) { setState(result.result); setLast(result); setConnected(true); }
    }).catch(e => active && setError(e.message));
    const resize = () => setViewport({ width: innerWidth, height: innerHeight });
    addEventListener('resize', resize);
    return () => { active = false; removeEventListener('resize', resize); };
  }, [request]);

  useEffect(() => {
    if (!playback.playing || !graph) return;
    let i = playIndex;
    const timer = setInterval(() => { i = i >= graph.values.length - 1 ? 0 : i + 1; void showTrajectoryIndex(i); }, 250);
    return () => clearInterval(timer);
  }, [playback.playing, graph, playIndex, showTrajectoryIndex]);

  const run = async (route: string, body: Record<string, unknown>) => {
    setBusy(true); setError('');
    try { const result = await request<Envelope>(route, body); setLast(result); setTrajectory(null); setPlayIndex(0); setTimelineOpen(Boolean(chartData(result))); return result; }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); return null; }
    finally { setBusy(false); }
  };
  const reconnect = async () => {
    setBusy(true); setError('');
    try { await request('/api/health'); setConnected(true); }
    catch (e) { setConnected(false); setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  const prepare = async () => {
    const result = await run('/api/state', { n_spins: n, pair, bell });
    if (result) setState(result.result);
  };
  const changeRegisterSize = (size: number) => {
    setN(size);
    setState(null);
    setTrajectory(null);
    setLast(null);
    setSelected(0);
    setPair(([a, b]) => [Math.min(a, size - 1), Math.min(b, size - 1)]);
    setKeepSites(current => current.filter(site => site < size));
    setKeepChoice(current => Math.min(current, size - 1));
  };
  const moveKeepSite = (index: number, offset: number) => setKeepSites(current => {
    const target = index + offset;
    if (target < 0 || target >= current.length) return current;
    const reordered = [...current];
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
    return reordered;
  });
  const applyRotation = async () => {
    if (!state) return;
    const axis = rotationAxis === 'x' ? [1, 0, 0] : rotationAxis === 'y' ? [0, 1, 0] : [0, 0, 1];
    const result = await run('/api/state/operation', { density_matrix: state.density_matrix, site: rotationSite, axis, angle_rad: rotationAngle });
    if (!result) return;
    try {
      const inspected = await request<Envelope>('/api/state/inspect', { density_matrix: result.result.density_matrix });
      setState({ ...state, density_matrix: result.result.density_matrix, spin_observables: inspected.result.spin_observables });
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };
  const runMeasurement = () => run('/api/run/state', { state_name: bell, shots, seed, dephasing_a: lambdaA, dephasing_b: lambdaB });
  const reduceState = () => state && run('/api/state/reduce', { density_matrix: state.density_matrix, keep: keepSites });
  const runChsh = () => run('/api/run/chsh', { state_name: bell, shots_per_setting: shots, seed, dephasing_a: lambdaA, dephasing_b: lambdaB });
  const runDamping = () => run('/api/run/phase-damping', { state_name: bell, values_a: Array.from({ length: 21 }, (_, i) => i / 20), values_b: [lambdaB], seed });
  const runSignaling = () => run('/api/run/signaling', { shots, seed, sender_dephasing: lambdaA, receiver_dephasing: lambdaB });
  const runObservable = () => state && run('/api/analyze/observable', { density_matrix: state.density_matrix, site: selected, pauli: 'sigma_z', shots, seed });
  const runSpectrum = () => graph && run('/api/analyze/spectrum', { times_s: graph.times, values: graph.values, window: 'hann' });
  const runFit = () => graph && run('/api/analyze/sinusoid', { times_s: graph.times, values: graph.values, model: 'sinusoid', initial_parameters: { omega_rad_s: fitOmega } });
  const runSequential = () => state && run('/api/analyze/sequential', {
    state_at_t1: state.density_matrix, site_1: sequenceSite1, site_2: sequenceSite2,
    pauli_1: 'sigma_z', pauli_2: 'sigma_z', J, h, delta_time_s: sequenceDeltaT, shots, seed,
  });
  const runTfim = async () => {
    const grid = times(duration);
    const response = await run('/api/run/tfim', { n_spins: n, J, h_schedule: schedule(h), initial_state: state?.density_matrix, times_s: grid, sources: ['SRC-015', 'SRC-016', 'SRC-017', 'SRC-018', 'SRC-019'], solver_options: { save_states_at: grid.map((_, i) => i) } });
    if (response?.result?.results?.snapshots) setTrajectory({ times: grid, states: Object.keys(response.result.results.snapshots).sort((a, b) => Number(a) - Number(b)).map(key => response.result.results.snapshots[key]) });
  };
  const stage5bConfig = () => ({ n_spins: Math.max(3, n), J, h_schedule: schedule(h), times_s: times(duration, 21), local_controls: { 1: schedule(0.03 * Math.max(1, Math.abs(h))) }, primary_observable: { site: 1, pauli: 'sigma_z' }, sources: ['SRC-020', 'SRC-021', 'SRC-022', 'SRC-023', 'SRC-024', 'SRC-025', 'SRC-026'] });
  const runReceiver = async () => {
    const config = stage5bConfig();
    const response = await run('/api/run/stage5b', config);
    const scenario = response?.result?.scenarios?.reference;
    if (scenario?.full_states) setTrajectory({ times: scenario.times_s.map(Number), states: scenario.full_states });
  };
  const runHensen = (year: 2015 | 2016) => run(`/api/run/hensen-${year}`, {});
  const refreshRecords = async () => {
    try {
      const next = (await request<{ records: string[] }>('/api/experiments')).records;
      setRecords(next);
      setCompareLeft(current => current && next.includes(current) ? current : next[0] ?? '');
      setCompareRight(current => current && next.includes(current) ? current : next.find(name => name !== (next[0] ?? '')) ?? '');
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };
  useEffect(() => { void refreshRecords(); }, []);
  const loadSavedStage5b = async () => { setBusy(true); setError(''); try { setLast(await request<Envelope>('/api/stage5b/locked-result')); setTrajectory(null); setTimelineOpen(false); } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); } };
  const saveRecord = async () => {
    if (!last) { setError('Спочатку створіть стан або запустіть розрахунок.'); return; }
    const protocol = last.route.includes('stage5b') ? 'stage5b_quantum_domino' : last.route.includes('tfim') ? 'tfim' : last.route.includes('hensen') ? 'scientific_validation' : last.route.includes('phase-damping') ? 'phase_damping_sweep' : last.route.includes('chsh') ? 'chsh' : last.route.includes('signaling') ? 'signaling_control' : 'state_measurement';
    const savedCore = last.result?.configuration && protocol === 'tfim' ? last.result.configuration : last.configuration;
    const configuration = { ...savedCore, protocol, ...(protocol === 'stage5b_quantum_domino' ? { sources: stage5bConfig().sources } : {}) };
    const results = protocol === 'tfim' && last.result?.results ? last.result.results : last.result;
    setBusy(true);
    try { const saved = await request<{ files: { json: string } }>('/api/experiments/save', { configuration, results }); setRecordName(saved.files.json); await refreshRecords(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  const loadRecord = async () => {
    if (!recordName) return;
    setBusy(true);
    try { const saved = await request<any>(`/api/experiments/${encodeURIComponent(recordName)}`); setLast({ kind: 'збережений науковий запис', route: '/api/experiments', configuration: saved.configuration, provenance: { engine: 'JSON record', application_version: saved.metadata?.application_version ?? '' }, result: saved.results }); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  const downloadText = (text: string, mime: string, filename: string) => {
    const url = URL.createObjectURL(new Blob([text], { type: mime }));
    const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const exportJson = async () => {
    if (!recordName) { setError('Спершу збережіть розрахунок, щоб експортувати повний відтворюваний JSON.'); return; }
    try {
      const saved = await request<any>(`/api/experiments/${encodeURIComponent(recordName)}`);
      downloadText(JSON.stringify(saved, null, 2), 'application/json', recordName);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };
  const exportCsv = async () => {
    if (!recordName) { setError('Спершу збережіть розрахунок, щоб створити відтворюваний CSV.'); return; }
    try {
      const csvName = recordName.replace(/\.json$/i, '.csv');
      const response = await request<{ csv: string }>(`/api/experiments/csv/${encodeURIComponent(csvName)}`);
      downloadText(response.csv, 'text/csv;charset=utf-8', csvName);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };
  const compareRecords = async () => {
    setBusy(true); setError(''); setComparison(null);
    try { setComparison(await request<Envelope>('/api/experiments/compare', { left: compareLeft, right: compareRight })); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  const focus = () => {
    if (!controls || !selectedSpin) return;
    const target = selectedSpin.position, offset = controls.object.position.clone().sub(controls.target);
    controls.target.set(...target); controls.object.position.set(target[0] + offset.x, target[1] + offset.y, target[2] + offset.z); controls.update();
  };
  const resetCamera = () => { if (controls) { controls.target.set(0, 0, 0); controls.object.position.set(0, 1.4, 9.4); controls.update(); } };
  const chooseMode = (next: string) => { setMode(next as Mode); setScienceOpen(next !== 'model'); setToolsOpen(false); };
  const openDocumentation = (topic: string) => { setDocumentationTopic(topic); setMode('docs'); setScienceOpen(false); setToolsOpen(false); };

  if (mode === 'docs') return <main className="app-shell documentation-shell">
    <TopBar mode={mode} onModeChange={chooseMode} onSave={saveRecord} onReconnect={reconnect} connected={connected} busy={busy} />
    <ScientificDocumentation initialTopic={documentationTopic} onClose={() => setMode('model')} />
  </main>;


  const toggleScience = () => {
    const opening = !scienceOpen; setScienceOpen(opening); setToolsOpen(false);
    if (opening && viewport.width <= 1100) { setInspectorOpen(false); setTimelineOpen(false); }
  };
  const toggleTimeline = () => {
    const opening = !timelineOpen; setTimelineOpen(opening);
    if (opening && (viewport.width <= 1100 || (scienceExpanded && viewport.width <= 1440))) { setScienceOpen(false); setInspectorOpen(false); setToolsOpen(false); }
  };
  return <main className="app-shell">
    <TopBar mode={mode} onModeChange={chooseMode} onSave={saveRecord} onReconnect={reconnect} connected={connected} busy={busy} />
    <div className={`workspace${viewport.width <= 1440 || viewport.height <= 800 ? ' compact-panels' : ''}${viewport.width <= 1100 ? ' tabbed-panels' : ''}${scienceOpen ? ' science-panel-open' : ''}`} data-layout={viewport.width <= 1100 ? 'tabs' : viewport.width <= 1440 || viewport.height <= 800 ? 'compact' : 'wide'}>
      <div className="canvas-wrap" data-testid="scene-workspace"><SceneCanvas selectedSpin={`q${selected}`} onSelectSpin={id => { setSelected(Number(id.slice(1))); setInspectorOpen(true); if (viewport.width <= 1100 || (scienceExpanded && viewport.width <= 1440)) { setScienceOpen(false); setTimelineOpen(false); } }} spins={spins} entangledPair={pair} interactionOn={J !== 0} tool={tool} cameraMode={camera} hideCaption={toolsOpen || scienceOpen || inspectorOpen || timelineOpen} onControlsReady={onControlsReady} onFps={setFps} /></div>
      <div className="view-toolbar" aria-label="Керування камерою"><span className="toolbar-group-label">КАМЕРА</span><button className={camera === 'orbit' && tool === 'orbit' ? 'view-tool selected' : 'view-tool'} onClick={() => { setCamera('orbit'); setTool('orbit'); }}>◎ <span>Orbit</span></button><button className={camera === 'orbit' && tool === 'pan' ? 'view-tool selected' : 'view-tool'} onClick={() => { setCamera('orbit'); setTool('pan'); }}>↔ <span>Pan</span></button><button className={camera === 'orbit' && tool === 'zoom' ? 'view-tool selected' : 'view-tool'} onClick={() => { setCamera('orbit'); setTool('zoom'); }}>⌕ <span>Zoom</span></button><button className={camera === 'fly' ? 'view-tool selected' : 'view-tool'} onClick={() => setCamera(camera === 'fly' ? 'orbit' : 'fly')}>✥ <span>Fly</span></button><button className="view-tool" onClick={focus}>⌖ <span>Focus</span></button><button className="view-tool" onClick={resetCamera}>⟳ <span>Reset</span></button></div>
      <div className="scene-status"><span className="live-dot" /> {connected ? 'PYTHON SCIENTIFIC CORE' : 'ЯДРО НЕ ПІДКЛЮЧЕНО'} <span className="status-separator">/</span> {n} СПІНІВ <span className="status-separator">/</span> СХЕМА, НЕ ГЕОМЕТРІЯ <span className="fps-chip" data-testid="scene-fps">FPS {fps || '…'}</span></div>
      <button className={`science-edge${scienceOpen ? ' active' : ''}`} onClick={toggleScience}><SlidersHorizontal size={15} /> Наукові інструменти <span>{scienceOpen ? 'Згорнути' : modeLabel}</span></button>
      <ToolRail open={toolsOpen} onToggle={() => { setToolsOpen(v => !v); setScienceOpen(false); }} tool={tool} onTool={setTool} cameraMode={camera} onCameraMode={setCamera} onFocus={focus} onReset={resetCamera} onOpenInspector={() => setInspectorOpen(true)} onOpenCharts={() => setTimelineOpen(true)} />
      {scienceOpen && <aside className={`science-drawer${scienceExpanded ? ' expanded' : ''}`} aria-label={`Наукові інструменти ${modeLabel}`}><div className="drawer-head"><span>{modeLabel.toUpperCase()}</span><div className="drawer-actions"><button className="drawer-size" aria-label={scienceExpanded ? 'Зменшити панель інструментів' : 'Розгорнути панель інструментів'} onClick={() => { if (!scienceExpanded && viewport.width <= 1440) { setInspectorOpen(false); setTimelineOpen(false); } setScienceExpanded(value => !value); }}>{scienceExpanded ? 'Зменшити' : 'Розгорнути'}</button><button aria-label="Згорнути інструменти" onClick={() => setScienceOpen(false)}>×</button></div></div>
        {mode === 'model' && state && <section className="science-section"><label>ρ ТА ЧАСТКОВИЙ СЛІД · PYTHON</label><button className="secondary-action" onClick={() => setShowDensity(value => !value)}>{showDensity ? 'ЗГОРНУТИ ρ' : 'ПОКАЗАТИ ПОВНУ ρ'}</button>{showDensity && <pre>{JSON.stringify(state.density_matrix, null, 1)}</pre>}<label>Додати фактор у ρ_keep<select aria-label="Додати фактор у ρ_keep" value={keepChoice} onChange={e => setKeepChoice(Number(e.target.value))}>{Array.from({ length: n }, (_, i) => <option key={i} value={i}>Спін {i}</option>)}</select></label><button className="secondary-action" disabled={keepSites.includes(keepChoice)} onClick={() => setKeepSites(current => current.includes(keepChoice) ? current : [...current, keepChoice])}>ДОДАТИ СПІН</button><ol className="keep-order" aria-label="Порядок факторів редукованого стану">{keepSites.map((site, index) => <li key={site}><span>Фактор {index + 1} · спін {site}</span><button aria-label={`Перемістити спін ${site} вгору`} disabled={index === 0} onClick={() => moveKeepSite(index, -1)}>↑</button><button aria-label={`Перемістити спін ${site} вниз`} disabled={index === keepSites.length - 1} onClick={() => moveKeepSite(index, 1)}>↓</button><button aria-label={`Вилучити спін ${site}`} onClick={() => setKeepSites(current => current.filter(value => value !== site))}>×</button></li>)}</ol><button className="secondary-action" disabled={busy || !keepSites.length} onClick={reduceState}>ОБЧИСЛИТИ РЕДУКОВАНИЙ СТАН</button></section>}
        {mode === 'model' && <section className="science-section"><label>КОНСТРУКТОР СТАНУ</label><label>Кількість спінів<select value={n} onChange={e => changeRegisterSize(Number(e.target.value))}><option value={2}>2</option><option value={3}>3</option><option value={4}>4</option><option value={5}>5</option><option value={6}>6</option></select></label><label>Стан Белла<select value={bell} onChange={e => setBell(e.target.value)}><option value="singlet">Singlet |ψ⁻⟩</option><option value="psi_plus">|ψ⁺⟩</option><option value="phi_plus">|φ⁺⟩</option><option value="phi_minus">|φ⁻⟩</option></select></label><div className="field-pair"><label>Пара, перший<select value={pair[0]} onChange={e => setPair([Number(e.target.value), pair[1]])}>{Array.from({ length: n }, (_, i) => <option key={i} value={i}>Спін {i}</option>)}</select></label><label>Пара, другий<select value={pair[1]} onChange={e => setPair([pair[0], Number(e.target.value)])}>{Array.from({ length: n }, (_, i) => <option key={i} value={i}>Спін {i}</option>)}</select></label></div><button className="primary-action" disabled={busy || pair[0] === pair[1]} onClick={prepare}>ПІДГОТУВАТИ СТАН · PYTHON</button><p className="micro-note">Вузли схематичні; матриця густини, заплутана пара й локальні вектори обчислюються ядром.</p></section>}
        {mode === 'interaction' && <><section className="science-section"><label>ЛОКАЛЬНЕ ОБЕРТАННЯ</label><label>Спін<select value={rotationSite} onChange={e => setRotationSite(Number(e.target.value))}>{spins.map((item, i) => <option key={item.id} value={i}>{item.label} · {i}</option>)}</select></label><label>Вісь Паулі<select value={rotationAxis} onChange={e => setRotationAxis(e.target.value as 'x' | 'y' | 'z')}><option value="x">σₓ</option><option value="y">σᵧ</option><option value="z">σ_z</option></select></label><label>Кут, рад<input type="number" step="0.05" value={rotationAngle} onChange={e => setRotationAngle(Number(e.target.value))} /></label><button className="secondary-action" disabled={busy || !state} onClick={applyRotation}>ЗАСТОСУВАТИ В PYTHON</button></section><section className="science-section"><div className="help-row"><span>ВИМІРЮВАННЯ · BELLS</span><ParameterHelp parameter="Concurrence" onOpenTopic={openDocumentation} /></div><label>Повтори на налаштування<input type="number" min="1" max="1000000" value={shots} onChange={e => setShots(Number(e.target.value))} /></label><label>Seed<input type="number" min="0" value={seed} onChange={e => setSeed(Number(e.target.value))} /></label><div className="field-pair"><label>λ A<input type="range" min="0" max="1" step="0.01" value={lambdaA} onChange={e => setLambdaA(Number(e.target.value))} /><code>{lambdaA.toFixed(2)}</code></label><label>λ B<input type="range" min="0" max="1" step="0.01" value={lambdaB} onChange={e => setLambdaB(Number(e.target.value))} /><code>{lambdaB.toFixed(2)}</code></label></div><div className="help-row"><MathInline latex="\lambda_A,\lambda_B" label="Незалежні параметри затухання A та B" /><ParameterHelp parameter="λ" onOpenTopic={openDocumentation} /></div><div className="formula-chip"><MathInline latex="\rho_{01}\mapsto(1-\lambda)\rho_{01}" label="Затухання позадіагональних елементів" /></div><button className="primary-action" disabled={busy} onClick={runMeasurement}>ВИМІРЯТИ</button><div className="help-row"><span>CHSH · FIXED ТА S MAX</span><ParameterHelp parameter="CHSH S" onOpenTopic={openDocumentation} /></div><button className="secondary-action" disabled={busy} onClick={runChsh}>ЗАПУСТИТИ РОЗРАХУНОК CHSH</button><button className="secondary-action" disabled={busy} onClick={runDamping}>СІТКА ФАЗОВОГО ЗАТУХАННЯ</button><label>NO-SIGNALING: тільки маргіналь B</label><button className="secondary-action" disabled={busy} onClick={runSignaling}>ПЕРЕВІРИТИ ЗА ВИБІРКОЮ</button></section></>}
        {mode === 'receiver' && <><section className="science-section"><label>TFIM · OPEN BOUNDARY CONDITIONS</label><div className="formula-chip"><MathInline latex="\frac{H}{\hbar}=-J\sum_i\sigma_i^z\sigma_{i+1}^z-h\sum_i\sigma_i^x" label="Відкритий TFIM гамільтоніан" /></div><label>J (s⁻¹)<input type="number" value={J} onChange={e => setJ(Number(e.target.value))} /></label><ParameterHelp parameter="J" onOpenTopic={openDocumentation} /><label>h (s⁻¹)<input type="number" value={h} onChange={e => setH(Number(e.target.value))} /></label><ParameterHelp parameter="h" onOpenTopic={openDocumentation} /><label>Тривалість (s)<input type="number" min="1e-9" step="1e-7" value={duration} onChange={e => setDuration(Number(e.target.value))} /></label><button className="primary-action" disabled={busy || !state} onClick={runTfim}>ЧАСОВА ЕВОЛЮЦІЯ TFIM</button></section><section className="science-section"><label>DYNAMIC RECEIVER · КВАНТОВЕ ДОМІНО</label><label>Розмір системи<select value={n} onChange={e => changeRegisterSize(Number(e.target.value))}>{[3, 4, 5, 6].map(size => <option key={size} value={size}>{size} спіни</option>)}</select></label><p className="micro-note">Три Stage 5B сценарії. Позитивний контроль — локальне поле 0,03|h| на приймачі (приклад, не калібрування).</p><button className="primary-action" disabled={busy} onClick={runReceiver}>ЗАПУСТИТИ СЦЕНАРІЇ</button></section></>}
        {mode === 'analyzer' && <><section className="science-section"><div className="help-row"><span>АНАЛІЗ ВІДХИЛЕНЬ</span><ParameterHelp parameter="Trace Distance" onOpenTopic={openDocumentation} /></div><p className="micro-note">Точні очікування окремо від незалежних вибірок. Спектр і fit застосовуються тільки до наявної рівномірної часової сітки; частота задається явно.</p><button className="primary-action" disabled={busy} onClick={runReceiver}>ТРАЄКТОРІЇ ПРИЙМАЧА · ТОЧНІ</button><button className="secondary-action" disabled={busy} onClick={runSignaling}>NO-SIGNALING · ВИБІРКОВИЙ ТЕСТ</button><button className="secondary-action" disabled={busy || !state} onClick={runObservable}>ЛОКАЛЬНА ⟨σz⟩ · ТОЧНО + ВИБІРКА</button><button className="secondary-action" disabled={busy || !graph || graph.unit !== 'с'} onClick={runSpectrum}>СПЕКТР НАЯВНОГО ЧАСОВОГО РЯДУ</button><label>Фіксована ω для синусоїдальної моделі (рад/с)<input type="number" min="0.000001" value={fitOmega} onChange={e => setFitOmega(Number(e.target.value))} /></label><button className="secondary-action" disabled={busy || !graph || graph.unit !== 'с'} onClick={runFit}>FIT ЗА ВКАЗАНОЮ ω</button></section><section className="science-section"><label>ПОСЛІДОВНІ ВИМІРЮВАННЯ · З BACK-ACTION</label><div className="field-pair"><label>Спін у t₁<select aria-label="Спін у t₁" value={sequenceSite1} onChange={e => setSequenceSite1(Number(e.target.value))}>{spins.map((item, i) => <option key={item.id} value={i}>Спін {i}</option>)}</select></label><label>Спін у t₂<select aria-label="Спін у t₂" value={sequenceSite2} onChange={e => setSequenceSite2(Number(e.target.value))}>{spins.map((item, i) => <option key={item.id} value={i}>Спін {i}</option>)}</select></label></div><label>Інтервал Δt (с)<input type="number" min="0" step="1e-8" value={sequenceDeltaT} onChange={e => setSequenceDeltaT(Number(e.target.value))} /></label><p className="micro-note">Перше вимірювання проєктує стан за правилом Людерса. Пари результатів походять з незалежних підготовок; між t₁ і t₂ діє сталий відкритий TFIM.</p><button className="secondary-action" disabled={busy || !state} onClick={runSequential}>ПОСЛІДОВНИЙ ТЕСТ · ТОЧНО + ВИБІРКА</button></section><section className="science-section"><label>ВІДТВОРЮВАНІ ЗАПИСИ</label><button className="secondary-action" disabled={busy} onClick={loadSavedStage5b}>ЗАВАНТАЖИТИ ЗБЕРЕЖЕНИЙ STAGE 5B АНАЛІЗ</button><button className="secondary-action" onClick={refreshRecords}>ОНОВИТИ СПИСОК</button><select aria-label="Збережені експерименти" value={recordName} onChange={e => setRecordName(e.target.value)}><option value="">Оберіть запис</option>{records.map(name => <option key={name}>{name}</option>)}</select><button className="secondary-action" disabled={!recordName || busy} onClick={loadRecord}>ЗАВАНТАЖИТИ JSON</button><button className="secondary-action" disabled={!recordName || busy} onClick={exportJson}>ЕКСПОРТ JSON</button><button className="secondary-action" disabled={!recordName || busy} onClick={exportCsv}>ЕКСПОРТ CSV</button><div className="field-pair"><label>Перший запис для порівняння<select aria-label="Перший запис для порівняння" value={compareLeft} onChange={e => setCompareLeft(e.target.value)}><option value="">Оберіть перший запис</option>{records.map(name => <option key={name}>{name}</option>)}</select></label><label>Другий запис для порівняння<select aria-label="Другий запис для порівняння" value={compareRight} onChange={e => setCompareRight(e.target.value)}><option value="">Оберіть другий запис</option>{records.map(name => <option key={name}>{name}</option>)}</select></label></div><button className="secondary-action" disabled={busy || !compareLeft || !compareRight || compareLeft === compareRight} onClick={compareRecords}>ПОРІВНЯТИ ЗАПИСИ</button><p className="micro-note">Порівняння описове: конфігурації та спільні скалярні результати. Воно не перераховує фізику й не виконує статистичний тест.</p>{comparison && <><label>ПОРІВНЯННЯ · {comparison.kind}</label><pre>{JSON.stringify(summarize(comparison), null, 2)}</pre></>}</section></>}
        {mode === 'validation' && <section className="science-section"><label>HENSEN · АНАЛІЗ ОПУБЛІКОВАНИХ ДАНИХ</label><p className="micro-note">Переобробка джерельних файлів із перевіркою SHA-256. Це не симуляція установки і не оцінка її параметрів.</p><button className="primary-action" disabled={busy} onClick={() => runHensen(2015)}>HENSEN 2015</button><button className="secondary-action" disabled={busy} onClick={() => runHensen(2016)}>HENSEN 2016 · OLD / NEW APD</button><button className="secondary-action" disabled={busy} onClick={() => run('/api/run/hensen-compare', {})}>ПОРІВНЯТИ ОКРЕМІ РОКИ</button></section>}
        {error && <div className="api-error" role="alert"><AlertCircle size={15} />{error}</div>}
        {busy && <div className="micro-note">Python виконує запит…</div>}
        {last && <section className="science-section result-section"><label>РЕЗУЛЬТАТ · {last.kind}</label><pre>{JSON.stringify(summarize(last), null, 2)}</pre><button className="secondary-action" onClick={saveRecord}><Save size={14} /> ЗБЕРЕГТИ ЗАПИС</button></section>}
      </aside>}
      <Inspector open={inspectorOpen} onClose={() => setInspectorOpen(false)} onOpen={() => { setInspectorOpen(true); if (viewport.width <= 1100 || (scienceExpanded && viewport.width <= 1440)) { setScienceOpen(false); setTimelineOpen(false); } }} onExpand={() => { if (viewport.width <= 1440) { setScienceOpen(false); setTimelineOpen(false); } }} spin={selectedSpin} registerSize={n} kind={last?.kind ?? 'точний стан'} />
      <div className="demo-ribbon"><span className="ribbon-dot" />Схема вузлів; фізичні величини обчислює Python</div>
      <button className="timeline-edge" aria-label={timelineOpen ? 'Згорнути часову панель' : 'Відкрити часову панель'} onClick={toggleTimeline}>{timelineOpen ? <PanelBottomClose size={16} /> : <PanelBottomOpen size={16} />}<span>{timelineOpen ? 'Згорнути графік' : 'Час і графік'}</span></button>
      <Timeline open={timelineOpen} onToggle={toggleTimeline} onExpand={() => { if (viewport.width <= 1440) { setScienceOpen(false); setInspectorOpen(false); } }} playing={playback.playing} onPlay={() => playback.setPlaying(v => !v)} index={playIndex} onIndex={showTrajectoryIndex} data={graph} />
      <footer className="workspace-footer"><span><span className={`mini-dot${connected ? '' : ' disconnected'}`} /> {connected ? 'PYTHON CORE ONLINE' : 'PYTHON CORE OFFLINE'}</span><span>{last ? `${last.kind} · ${last.provenance.engine}` : 'Розрахунок ще не запускався'}</span><button onClick={() => { setTimelineOpen(true); playback.setPlaying(v => !v); }} disabled={!graph}>{playback.playing ? 'Пауза' : 'Відтворити'} <Play size={12} /></button></footer>
    </div>
  </main>;
}
