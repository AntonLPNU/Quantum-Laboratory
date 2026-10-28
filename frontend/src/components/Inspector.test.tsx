import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Inspector } from './Inspector';

describe('Inspector', () => {
  it('renders the Bloch expectation as mathematical brackets', () => {
    render(<Inspector open onClose={() => {}} onOpen={() => {}} onExpand={() => {}} registerSize={2} kind="exact_state"
      spin={{ id: 'q0', label: 'A', group: 'Передавач', coordinate: 'схема 1',
        state: 'ρ із Python', expectation: '0', position: [0, 0, 0], bloch: [0, 0, 0] }} />);
    const math = screen.getByLabelText('Середнє сигма x');
    expect(math.querySelector('.katex-html')?.textContent).toContain('⟨');
    expect(math.querySelector('.katex-html')?.textContent).toContain('⟩');
  });
});
