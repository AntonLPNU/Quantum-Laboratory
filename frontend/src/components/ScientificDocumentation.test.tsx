import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ScientificDocumentation } from './ScientificDocumentation';

describe('in-app scientific handbook', () => {
  it('searches topics, renders equations and references, and returns to the lab', () => {
    const onClose = vi.fn();
    render(<ScientificDocumentation initialTopic="tfim" onClose={onClose} />);
    expect(screen.getByRole('heading', { name: /Гамільтоніан TFIM/i })).toBeInTheDocument();
    expect(screen.getByLabelText('Реалізована конвенція TFIM')).toBeInTheDocument();
    fireEvent.change(screen.getByRole('searchbox', { name: 'Пошук у науковій довідці' }), { target: { value: 'Hensen 2015' } });
    fireEvent.click(screen.getByText('Експерименти Hensen 2015/2016').closest('button')!);
    expect(screen.getByRole('heading', { name: /Hensen 2015/ })).toBeInTheDocument();
    expect(screen.getAllByText(/10\.1038\/nature15759/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'Повернутися до лабораторії' }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('keeps all contents links inside a local handbook topic', () => {
    render(<ScientificDocumentation initialTopic="overview" onClose={() => undefined} />);
    fireEvent.click(screen.getByText('Матриці густини та частковий слід').closest('button')!);
    expect(screen.getByRole('heading', { name: /Матриці густини та частковий слід/ })).toBeInTheDocument();
  });
});
