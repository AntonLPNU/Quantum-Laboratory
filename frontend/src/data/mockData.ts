// Schematic node positions only; scientific state values are always returned by Python.
export type Spin = Readonly<{
  id: string;
  label: string;
  group: string;
  coordinate: string;
  state: string;
  expectation: string;
  position: readonly [number, number, number];
  bloch: readonly [number, number, number];
}>;

const labels = ['A', 'B', 'C', 'D', 'E', 'F'];
const groups = ['Передавач', 'Приймач', 'Приймач', 'Приймач', 'Приймач', 'Приймач'];
export const schematicSpins = labels.map((label, i) => ({
  id: `q${i}`, label, group: groups[i], position: [(i - 2.5) * 1.45, 0, 0] as const
}));

export const modes = [
  { id: 'model', label: 'Модель' }, { id: 'interaction', label: 'Вимірювання' }, { id: 'receiver', label: 'Приймач' },
  { id: 'analyzer', label: 'Аналіз' }, { id: 'validation', label: 'Валідація' }, { id: 'docs', label: 'Довідка' }
] as const;
