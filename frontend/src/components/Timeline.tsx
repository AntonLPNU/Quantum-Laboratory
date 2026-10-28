import { useState } from 'react';
import { Activity, ChevronDown, ChevronUp, Pause, Play, SkipBack, SkipForward } from 'lucide-react';
import { MathInline } from './Math';

/** Plot-ready values are computed by the Python core; formula is trusted static TeX for its visible axis label. */
export type TimelineData = Readonly<{ label: string; values: readonly number[]; times: readonly number[]; unit: string; kind: string; axisLabel?: string; formula?: string }>;
type Props = Readonly<{ open: boolean; onToggle: () => void; onExpand: () => void; playing: boolean; onPlay: () => void; index: number; onIndex: (index: number) => void; data?: TimelineData }>;

/** Presents API-computed time-series data and playback controls; it does not calculate physics. */
export function Timeline({ open, onToggle, onExpand, playing, onPlay, index, onIndex, data }: Props) {
  const [expanded, setExpanded] = useState(false);
  const values = data?.values ?? [];
  const finite = values.filter(Number.isFinite);
  const low = finite.length ? Math.min(...finite) : 0;
  const high = finite.length ? Math.max(...finite) : 1;
  const span = high - low || 1;
  const points = values.map((value, i) => `${values.length < 2 ? 50 : (i / (values.length - 1)) * 100},${100 - ((value - low) / span) * 76 - 12}`).join(' ');
  const currentTime = data?.times[Math.min(index, Math.max(0, (data?.times.length ?? 1) - 1))];
  return <section className={`timeline${open ? ' open' : ''}${expanded ? ' expanded' : ''}`} aria-label="Часова шкала та науковий графік" aria-hidden={!open} inert={!open}>
    <div className="timeline-heading"><button className="timeline-toggle" onClick={onToggle} aria-label={open ? 'Згорнути графік' : 'Відкрити графік'}>{open ? <ChevronDown size={15} /> : <ChevronUp size={15} />}<Activity size={14} /><span>{open ? 'ЧАСОВА ШКАЛА · РЕЗУЛЬТАТ PYTHON' : 'Графік і час'}</span></button>{open && <button className="timeline-size" aria-label={expanded ? 'Зменшити графік' : 'Розгорнути графік'} onClick={() => { if (!expanded) onExpand(); setExpanded(value => !value); }}>{expanded ? 'Зменшити' : 'Розгорнути'}</button>}</div>
    {open && <div className="timeline-body"><div className="chart-label"><span>{data ? data.kind.toUpperCase() : 'НЕМАЄ РОЗРАХОВАНИХ ДАНИХ'}</span><strong>{data?.formula && <MathInline latex={data.formula} label={data.label} />} {data?.label ?? 'Запустіть науковий розрахунок'} <b>{data ? `(${data.unit})` : ''}</b></strong></div>
      {data && finite.length > 0 ? <svg className="demo-chart" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label={`${data.label}, дані з Python`}><defs><linearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="var(--active)" stopOpacity=".2" /><stop offset="100%" stopColor="var(--active)" stopOpacity="0" /></linearGradient></defs><path d={`M0,100 L${points} L100,100 Z`} fill="url(#chartFill)" /><polyline points={points} fill="none" stroke="var(--active)" strokeWidth="1.2" vectorEffect="non-scaling-stroke" /></svg> : <div className="chart-empty">Графік з’явиться тут після розрахунку. UI не створює наукових даних.</div>}
      <div className="transport"><button aria-label="На початок" onClick={() => onIndex(0)} disabled={!data}><SkipBack size={15} /></button><button className="play-button" aria-label={playing ? 'Пауза' : 'Відтворити'} onClick={onPlay} disabled={!data}>{playing ? <Pause size={15} /> : <Play size={15} />}</button><button aria-label="Крок вперед" onClick={() => onIndex(Math.min(index + 1, (data?.values.length ?? 1) - 1))} disabled={!data}><SkipForward size={15} /></button><input aria-label="Індекс збереженої точки" type="range" min="0" max={Math.max(0, (data?.values.length ?? 1) - 1)} step="1" value={Math.min(index, Math.max(0, (data?.values.length ?? 1) - 1))} disabled={!data} onChange={event => onIndex(Number(event.target.value))} /><code>{data && currentTime !== undefined ? `${data.axisLabel ?? (data.unit === 'с' ? 't' : 'λA')} = ${currentTime.toPrecision(4)}${data.unit.startsWith('λ') ? '' : ` ${data.unit}`}` : '—'}</code><span className="demo-badge">ЗАПИСАНІ ТОЧКИ</span></div>
      <div className="timeline-disclaimer">Відтворення переглядає розраховані Python точки; хід часу не залежить від FPS.</div></div>}
  </section>;
}
