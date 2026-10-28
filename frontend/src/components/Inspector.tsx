import { useState } from 'react';
import { Activity, ChevronRight, CircleDot, PanelRightClose } from 'lucide-react';
import type { Spin } from '../data/mockData';
import { MathInline } from './Math';

/** Дані Inspector завжди надходять з Python API; координати Spin лишаються схематичними. */
type Props = Readonly<{ open: boolean; onClose: () => void; onOpen: () => void; onExpand: () => void; spin: Spin; registerSize: number; kind: string }>;

/** Показує вибраний вузол і локальні середні компонентів Паулі. */
export function Inspector({ open, onClose, onOpen, onExpand, spin, registerSize, kind }: Props) {
  const [expanded, setExpanded] = useState(false);
  return <>
    {!open && <button className="edge-handle right-handle" aria-label="Відкрити інспектор" onClick={onOpen}><ChevronRight size={17} /></button>}
    <aside className={`inspector${open ? ' open' : ''}${expanded ? ' expanded' : ''}`} aria-label="Інспектор вибраного спіну" aria-hidden={!open} inert={!open}>
      <div className="drawer-head"><span>ІНСПЕКТОР</span><div className="drawer-actions"><button className="drawer-size" aria-label={expanded ? 'Зменшити інспектор' : 'Розгорнути інспектор'} onClick={() => { if (!expanded) onExpand(); setExpanded(value => !value); }}>{expanded ? 'Зменшити' : 'Розгорнути'}</button><button aria-label="Згорнути інспектор" onClick={onClose}><PanelRightClose size={16} /></button></div></div>
      <div className="inspect-title"><div className="particle-icon"><CircleDot size={22} /></div><div><span className="eyebrow">ВИБРАНИЙ СПІН</span><h2>Спін {spin.label}</h2><small>{spin.id} · {spin.group} · {registerSize} спінів</small></div></div>
      <div className="notice-chip"><span className="status-dot" /> Значення з Python · {kind || 'стан не розраховано'}</div>
      <section className="inspect-section"><div className="section-heading"><span>ЛОКАЛЬНИЙ ВЕКТОР БЛОХА</span></div><div className="property-row"><span>Схема розташування</span><code>{spin.coordinate}</code></div><div className="property-row"><MathInline latex={'\\langle\\sigma_x\\rangle'} label="Середнє сигма x" /><code className="active-text">{spin.bloch[0].toFixed(6)}</code></div><div className="property-row"><MathInline latex={'\\langle\\sigma_y\\rangle'} label="Середнє сигма y" /><code className="active-text">{spin.bloch[1].toFixed(6)}</code></div><div className="property-row"><MathInline latex={'\\langle\\sigma_z\\rangle'} label="Середнє сигма z" /><code className="active-text">{spin.bloch[2].toFixed(6)}</code></div><div className="property-row"><span>Довжина r</span><code>{Math.hypot(...spin.bloch).toFixed(6)}</code></div></section>
      <section className="inspect-section"><div className="section-heading"><span>ПОЯСНЕННЯ</span></div><div className="inspector-note"><Activity size={14} /> Вектор Блоха показує локальні середні ⟨σ⟩. Вузли розміщені схематично й не є траєкторіями частинок.</div></section>
    </aside>
  </>;
}
