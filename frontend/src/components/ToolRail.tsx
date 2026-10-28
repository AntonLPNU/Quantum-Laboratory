import { ChevronLeft, ChevronRight, Focus, Layers3, Orbit, PanelLeftClose, Play, RotateCcw, Scan, ZoomIn } from 'lucide-react';

type Props = Readonly<{ open: boolean; onToggle: () => void; tool: 'orbit' | 'pan' | 'zoom'; onTool: (tool: 'orbit' | 'pan' | 'zoom') => void; cameraMode: 'orbit' | 'fly'; onCameraMode: (mode: 'orbit' | 'fly') => void; onFocus: () => void; onReset: () => void; onOpenInspector: () => void; onOpenCharts: () => void }>;
const cameraTools = [{ id: 'orbit', label: 'Обертання', Icon: Orbit }, { id: 'pan', label: 'Панорамування', Icon: Scan }, { id: 'zoom', label: 'Масштаб', Icon: ZoomIn }] as const;

/** Overlay controls for camera interaction, tools, and contextual panels. */
export function ToolRail({ open, onToggle, tool, onTool, cameraMode, onCameraMode, onFocus, onReset, onOpenInspector, onOpenCharts }: Props) {
  return <>
    <button className={`edge-handle left-handle${open ? ' shifted' : ''}`} aria-label={open ? 'Згорнути панель інструментів' : 'Відкрити панель інструментів'} onClick={onToggle}>{open ? <ChevronLeft size={17} /> : <ChevronRight size={17} />}</button>
    <aside className={`tool-drawer${open ? ' open' : ''}`} aria-label="Панель інструментів" aria-hidden={!open} inert={!open}>
      <div className="drawer-head"><span>ІНСТРУМЕНТИ СЦЕНИ</span><button aria-label="Згорнути панель інструментів" onClick={onToggle}><PanelLeftClose size={16} /></button></div>
      <section className="tool-section"><label>КАМЕРА</label>{cameraTools.map(({ id, label, Icon }) => <button key={id} className={`tool-row${tool === id && cameraMode === 'orbit' ? ' selected' : ''}`} onClick={() => { onCameraMode('orbit'); onTool(id); }}><Icon size={16} /><span>{label}</span><kbd>{id === 'orbit' ? 'ЛКМ' : id === 'pan' ? 'ЛКМ' : 'ЛКМ'}</kbd></button>)}
        <button className={`tool-row${cameraMode === 'fly' ? ' selected' : ''}`} onClick={() => onCameraMode(cameraMode === 'fly' ? 'orbit' : 'fly')}><Focus size={16} /><span>{cameraMode === 'fly' ? 'Вийти з Fly Mode' : 'Fly Mode'}</span><kbd>WASD</kbd></button>
        <div className="tool-inline"><button onClick={onFocus}><Focus size={15} /> Фокус</button><button onClick={onReset}><RotateCcw size={15} /> Скинути</button></div>
      </section>
      <section className="tool-section"><label>СИСТЕМА</label><button className="tool-row selected" onClick={onOpenInspector}><Layers3 size={16} /><span>Вибраний спін</span><ChevronRight size={13} /></button><button className="tool-row" onClick={onOpenCharts}><Play size={16} /><span>Розраховані точки часу</span><ChevronRight size={13} /></button></section>
      <section className="drawer-callout"><span className="callout-icon"><Play size={14} /></span><div><strong>Часова еволюція</strong><p>Перегляд результатів Python</p><button onClick={onOpenCharts}>Відкрити часову шкалу <ChevronRight size={13} /></button></div></section>
      <div className="drawer-foot"><span className="mini-dot" /> QUANTUM LAB <span>LOCAL</span></div>
    </aside>
  </>;
}
