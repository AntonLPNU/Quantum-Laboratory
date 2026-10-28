import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiMock = vi.hoisted(() => vi.fn());
vi.mock('./api', async (importOriginal) => ({ ...(await importOriginal<typeof import('./api')>()), api: apiMock }));
vi.mock('./components/SceneCanvas', () => ({ SceneCanvas: ({ onSelectSpin, spins, hideCaption }: any) => <div><button onClick={() => onSelectSpin('q2')}>select spin</button><span>{spins?.length} nodes</span><span data-testid="caption-state">{hideCaption ? 'hidden' : 'visible'}</span></div> }));

import { App } from './App';
import { ApiConnectionError } from './api';

const state = { density_matrix: [[{ real: 0.5, imag: 0 }, { real: 0, imag: 0 }], [{ real: 0, imag: 0 }, { real: 0.5, imag: 0 }]], n_spins: 3, pair: [0, 2], spin_observables: [0, 1, 2].map(site => ({ site, bloch: { x: site === 2 ? 1 : 0, y: 0, z: 0 } })) };
const envelope = (route: string, result: any, kind = 'exact_state') => ({ route, kind, result, configuration: {}, provenance: { engine: 'quantum_lab Python scientific core', application_version: '0.1.0' } });

beforeEach(() => {
  apiMock.mockReset();
  apiMock.mockImplementation(async (route: string, body?: any) => {
    if (route === '/api/health') return { status: 'ok' };
    if (route === '/api/state') return { ...envelope(route, state), configuration: { n_spins: 5, pair: [0, 2], bell: 'singlet' } };
    if (route === '/api/state/operation') return envelope(route, { density_matrix: state.density_matrix });
    if (route === '/api/state/inspect') return envelope(route, { spin_observables: state.spin_observables });
    if (route === '/api/state/reduce') return envelope(route, { keep: body?.keep, reduced_density_matrix: state.density_matrix }, 'reduced_state');
    if (route === '/api/run/phase-damping') return envelope(route, { concurrence: [[1], [0.5], [0]], lambdas_a: [0, 0.5, 1], lambdas_b: [0] }, 'exact_phase_damping_sweep');
    if (route === '/api/analyze/sequential') return envelope(route, { exact: { joint_probabilities: {} }, sample: { paired: true }, back_action: 'Lüders projection', observations_are_paired: true }, 'sequential_measurements_with_back_action');
    if (route === '/api/stage5b/locked-result') return envelope(route, { record_name: 'original_stage5b.json', sampling_analysis: { test: 'Fisher exact with Holm' }, statistical_criteria: { shots_per_group: 14000 } }, 'saved_stage5b_confirmatory_analysis');
    if (route.startsWith('/api/run/')) return envelope(route, { concurrence: 0.8, chsh_maximal: 2.4, sampled_chsh: 2.35 }, 'sampled_measurement_and_exact_prediction');
    if (route === '/api/experiments/save') return { saved: true, files: { json: 'record.json' } };
    if (route === '/api/experiments') return { records: ['record.json', 'other.json'] };
    if (route === '/api/experiments/compare') return envelope(route, { comparison: { configurations_match: false, numeric_differences: [{ path: 'results.value', left: 1, right: 2, difference: 1 }] } }, 'descriptive_record_comparison');
    return {};
  });
});

describe('Orbital Lab scientific interface', () => {
  it('lets the user expand and collapse independently scrollable scientific panels', async () => {
    render(<App />);
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/api/state', expect.any(Object)));
    fireEvent.click(screen.getByRole('button', { name: /Наукові інструменти/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Розгорнути панель інструментів' }));
    expect(screen.getByLabelText('Наукові інструменти Модель')).toHaveClass('expanded');
    fireEvent.click(screen.getByRole('button', { name: 'Зменшити панель інструментів' }));
    expect(screen.getByLabelText('Наукові інструменти Модель')).not.toHaveClass('expanded');
    fireEvent.click(screen.getByRole('button', { name: 'select spin' }));
    fireEvent.click(screen.getByRole('button', { name: 'Розгорнути інспектор' }));
    expect(screen.getByLabelText('Інспектор вибраного спіну')).toHaveClass('expanded');
    fireEvent.click(screen.getByRole('button', { name: 'Зменшити інспектор' }));
    expect(screen.getByLabelText('Інспектор вибраного спіну')).not.toHaveClass('expanded');
    fireEvent.click(screen.getByRole('button', { name: 'Відкрити часову панель' }));
    fireEvent.click(screen.getByRole('button', { name: 'Розгорнути графік' }));
    expect(screen.getByLabelText('Часова шкала та науковий графік')).toHaveClass('expanded');
    fireEvent.click(screen.getByRole('button', { name: 'Зменшити графік' }));
    expect(screen.getByLabelText('Часова шкала та науковий графік')).not.toHaveClass('expanded');
  });

  it('keeps the scene usable when another panel opens on a compact desktop viewport', async () => {
    const originalWidth = window.innerWidth;
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1280 });
    try {
      render(<App />);
      await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/api/state', expect.any(Object)));
      fireEvent.click(screen.getByRole('button', { name: /Наукові інструменти/ }));
      fireEvent.click(screen.getByRole('button', { name: 'Розгорнути панель інструментів' }));
      fireEvent.click(screen.getByRole('button', { name: 'select spin' }));
      expect(screen.queryByLabelText('Наукові інструменти Модель')).not.toBeInTheDocument();
      expect(screen.getByLabelText('Інспектор вибраного спіну')).toHaveClass('open');
    } finally {
      Object.defineProperty(window, 'innerWidth', { configurable: true, value: originalWidth });
    }
  });
  it('opens the local scientific handbook from the main navigation and returns to the scene', async () => {
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'Довідка' }));
    expect(await screen.findByRole('heading', { name: 'Вступ до Quantum Laboratory' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Повернутися до лабораторії' }));
    expect(await screen.findByTestId('scene-workspace')).toBeInTheDocument();
  });

  it('loads the register and renders Python-derived Bloch values', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText('5 nodes')).toBeInTheDocument());
    expect(apiMock).toHaveBeenCalledWith('/api/state', { n_spins: 5, pair: [0, 2], bell: 'singlet' });
    fireEvent.click(screen.getByRole('button', { name: 'select spin' }));
    expect((await screen.findAllByText('1.000000')).length).toBeGreaterThan(0);
  });

  it('can recover the Python connection after an API disconnection', async () => {
    let available = false;
    apiMock.mockImplementation(async (route: string) => {
      if (route === '/api/health') return { status: 'ok' };
      if (route === '/api/state') return { ...envelope(route, state), configuration: { n_spins: 5, pair: [0, 2], bell: 'singlet' } };
      if (route === '/api/experiments') return { records: [] };
      if (route === '/api/run/state' && !available) throw new ApiConnectionError('API offline');
      return {};
    });
    render(<App />);
    await screen.findByText('Python ядро підключено');
    fireEvent.click(screen.getByRole('button', { name: /Вимірювання/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'ВИМІРЯТИ' }));
    await screen.findByRole('alert');
    const reconnect = await screen.findByRole('button', { name: 'Повторити підключення' });
    available = true;
    fireEvent.click(reconnect);
    await waitFor(() => expect(screen.getByText('Python ядро підключено')).toBeInTheDocument());
    expect(apiMock.mock.calls.filter(([route]) => route === '/api/health')).toHaveLength(2);
    expect(await screen.findByText('Python ядро підключено')).toBeInTheDocument();
  });

  it('keeps the connection online when Python rejects invalid input', async () => {
    apiMock.mockImplementation(async (route: string, body?: any) => {
      if (route === '/api/health') return { status: 'ok' };
      if (route === '/api/state') return { ...envelope(route, state), configuration: { n_spins: 5, pair: [0, 2], bell: 'singlet' } };
      if (route === '/api/experiments') return { records: [] };
      if (route === '/api/run/state') throw new Error('shots must be positive');
      if (route.startsWith('/api/run/')) return envelope(route, {});
      return {};
    });
    render(<App />);
    await screen.findByText('Python ядро підключено');
    fireEvent.click(screen.getByRole('button', { name: /Вимірювання/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'ВИМІРЯТИ' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('shots must be positive');
    expect(screen.getByText('Python ядро підключено')).toBeInTheDocument();
  });

  it('wires Bell measurements and CHSH to Python APIs with shot and seed parameters', async () => {
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: /Вимірювання/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'ВИМІРЯТИ' }));
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/api/run/state', expect.objectContaining({ state_name: 'singlet', shots: 2000, seed: 42 })));
    fireEvent.click(screen.getByRole('button', { name: 'ЗАПУСТИТИ РОЗРАХУНОК CHSH' }));
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/api/run/chsh', expect.objectContaining({ shots_per_setting: 2000, seed: 42 })));
    expect(await screen.findByText(/РЕЗУЛЬТАТ · sampled_measurement_and_exact_prediction/)).toBeInTheDocument();
  });

  it('adapts panel layout at 1280×720 and exposes panel controls', async () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1280 });
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 720 });
    render(<App />);
    const scene = await screen.findByTestId('scene-workspace');
    expect(scene.closest('.workspace')).toHaveAttribute('data-layout', 'compact');
    fireEvent.click(screen.getByRole('button', { name: /Приймач/ }));
    expect(screen.getByLabelText('Наукові інструменти Приймач')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Відкрити часову панель' })).toBeInTheDocument();
    expect(screen.getByTestId('caption-state')).toHaveTextContent('hidden');
  });

  it('saves a reproducible JSON/CSV record through the local Python API', async () => {
    render(<App />);
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/api/state', expect.any(Object)));
    fireEvent.click(screen.getByRole('button', { name: 'Зберегти запис' }));
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/api/experiments/save', expect.objectContaining({
      configuration: expect.objectContaining({ protocol: 'state_measurement', n_spins: 5 }),
      results: state
    })));
    expect(apiMock.mock.calls.some(([route]) => route === '/api/experiments')).toBe(true);
  });

  it('plots the API phase-damping grid against lambda rather than mislabeling it as time', async () => {
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: /Вимірювання/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'СІТКА ФАЗОВОГО ЗАТУХАННЯ' }));
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/api/run/phase-damping', expect.any(Object)));
    expect(await screen.findByText(/Concurrence · λB = 0\.00/)).toBeInTheDocument();
    expect(screen.getByText(/λA = 0\.000/)).toBeInTheDocument();
  });

  it('clears an incompatible scientific state when the register size changes', async () => {
    render(<App />);
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/api/state', expect.any(Object)));
    const toolsToggle = screen.getByRole('button', { name: /Наукові інструменти/ });
    fireEvent.click(toolsToggle);
    const sizeSelect = await screen.findByLabelText('Кількість спінів');
    fireEvent.change(sizeSelect, { target: { value: '4' } });
    expect(screen.getByText('4 nodes')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'ПІДГОТУВАТИ СТАН · PYTHON' })).toBeInTheDocument();
  });

  it('preserves the user-defined order of factors in a partial trace', async () => {
    render(<App />);
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/api/state', expect.any(Object)));
    fireEvent.click(screen.getByRole('button', { name: /Наукові інструменти/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Вилучити спін 0' }));
    fireEvent.click(screen.getByRole('button', { name: 'Вилучити спін 2' }));
    const choice = screen.getByLabelText('Додати фактор у ρ_keep');
    fireEvent.change(choice, { target: { value: '3' } });
    fireEvent.click(screen.getByRole('button', { name: 'ДОДАТИ СПІН' }));
    fireEvent.change(choice, { target: { value: '1' } });
    fireEvent.click(screen.getByRole('button', { name: 'ДОДАТИ СПІН' }));
    fireEvent.click(screen.getByRole('button', { name: 'ОБЧИСЛИТИ РЕДУКОВАНИЙ СТАН' }));
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/api/state/reduce', expect.objectContaining({ keep: [3, 1] })));
  });

  it('runs sequential measurements with a Python TFIM propagator and paired sampling', async () => {
    render(<App />);
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/api/state', expect.any(Object)));
    fireEvent.click(screen.getByRole('button', { name: 'Аналіз' }));
    fireEvent.click(await screen.findByRole('button', { name: 'ПОСЛІДОВНИЙ ТЕСТ · ТОЧНО + ВИБІРКА' }));
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/api/analyze/sequential', expect.objectContaining({
      state_at_t1: state.density_matrix, site_1: 0, site_2: 0, J: 100000, h: 200000,
      delta_time_s: 1e-7, shots: 2000, seed: 42,
    })));
    expect(await screen.findByText(/observations_are_paired/)).toBeInTheDocument();
  });

  it('loads the saved Stage 5B statistical report without rerunning sampling', async () => {
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'Аналіз' }));
    fireEvent.click(await screen.findByRole('button', { name: 'ЗАВАНТАЖИТИ ЗБЕРЕЖЕНИЙ STAGE 5B АНАЛІЗ' }));
    await waitFor(() => expect(apiMock.mock.calls.some(([route]) => route === '/api/stage5b/locked-result')).toBe(true));
    expect(await screen.findByText(/original_stage5b\.json/)).toBeInTheDocument();
  });

  it('compares two selected saved records through the Python API', async () => {
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'Аналіз' }));
    const left = await screen.findByLabelText('Перший запис для порівняння');
    const right = screen.getByLabelText('Другий запис для порівняння');
    fireEvent.change(left, { target: { value: 'record.json' } });
    fireEvent.change(right, { target: { value: 'other.json' } });
    fireEvent.click(screen.getByRole('button', { name: 'ПОРІВНЯТИ ЗАПИСИ' }));
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith('/api/experiments/compare', {
      left: 'record.json', right: 'other.json'
    }));
    expect(await screen.findByText(/descriptive_record_comparison/)).toBeInTheDocument();
  });
});
