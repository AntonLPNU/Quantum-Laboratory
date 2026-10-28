import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MathBlock, MathInline } from './Math';

describe('KaTeX formula rendering', () => {
  it('renders Greek, Dirac notation, subscripts, and superscripts accessibly', () => {
    const { container } = render(<MathInline latex="\\langle\\psi|\\rho_A|\\psi\\rangle + \\lambda^2" label="probability expression" />);
    expect(screen.getByLabelText('probability expression')).toBeInTheDocument();
    expect(container.querySelector('.katex')).toBeInTheDocument();
    expect(container.querySelector('.math-error')).not.toBeInTheDocument();
  });

  it('renders block matrices, fractions, sums, and bra-ket symbols', () => {
    const { container } = render(<MathBlock latex={String.raw`\rho=\frac{1}{2}\begin{pmatrix}1&0\\0&1\end{pmatrix}=\sum_i p_i|\psi_i\rangle\langle\psi_i|`} label="density matrix" />);
    expect(screen.getByLabelText('density matrix')).toBeInTheDocument();
    expect(container.querySelector('.math-block .katex')).toBeInTheDocument();
  });

  it('shows a visible accessible fallback for invalid TeX', () => {
    render(<MathInline latex="\\notacommand{" label="invalid equation" />);
    expect(screen.getByRole('alert')).toHaveTextContent('Формулу не вдалося відобразити');
  });
});
