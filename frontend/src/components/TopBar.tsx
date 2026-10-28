import { Activity, ChevronDown, Save } from 'lucide-react';
import { modes } from '../data/mockData';

type Props = Readonly<{ mode: string; onModeChange: (mode: string) => void; onSave: () => void; onReconnect: () => void; connected: boolean; busy: boolean }>;

/** Shared application header and navigation between laboratory modes. */
export function TopBar({ mode, onModeChange, onSave, onReconnect, connected, busy }: Props) {
  return <header className="topbar">
    <div className="brand"><div className="brand-mark">◉</div><div><strong>QUANTUM LAB</strong><span>ORBITAL LAB <i>·</i> НАУКОВА ЛАБОРАТОРІЯ</span></div></div>
    {connected
      ? <div className="project-select"><span className="status-dot" />Python ядро підключено <ChevronDown size={14} /></div>
      : <button className="project-select reconnect-button" type="button" disabled={busy} onClick={onReconnect} aria-label="Повторити підключення"><span className="status-dot disconnected" />Ядро недоступне · повторити</button>}
    <nav className="mode-nav" aria-label="Режими лабораторії">
      {modes.map(item => <button key={item.id} className={mode === item.id ? 'mode-link active' : 'mode-link'} onClick={() => onModeChange(item.id)}>{item.label}</button>)}
    </nav>
    <div className="top-actions"><span className="save-state"><Activity size={13} /> Розрахунки: Python</span><button className="save-button" onClick={onSave}><Save size={14} /><span>Зберегти запис</span></button></div>
  </header>;
}
