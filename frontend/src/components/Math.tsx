import katex from 'katex';
import { useMemo } from 'react';

type MathProps = Readonly<{ latex: string; label?: string }>;

/** Рендерить локальну перевірену формулу KaTeX; довільний користувацький ввід не приймається. */
function RenderedMath({ latex, label, displayMode }: MathProps & { displayMode: boolean }) {
  const result = useMemo(() => {
    try {
      return { html: katex.renderToString(latex, { displayMode, throwOnError: true, output: 'htmlAndMathml', strict: 'warn', trust: false }), error: false };
    } catch {
      return { html: '', error: true };
    }
  }, [latex, displayMode]);
  if (result.error) return <span className="math-error" role="alert" aria-label={label}>Формулу не вдалося відобразити: <code>{latex}</code></span>;
  return <span className={displayMode ? 'math-render math-block' : 'math-render math-inline'} aria-label={label} dangerouslySetInnerHTML={{ __html: result.html }} />;
}

/** Inline-відображення перевірених формул у тексті інтерфейсу. */
export function MathInline(props: MathProps) { return <RenderedMath {...props} displayMode={false} />; }
/** Блокове відображення перевірених формул у довідці та поясненнях. */
export function MathBlock(props: MathProps) { return <RenderedMath {...props} displayMode />; }
