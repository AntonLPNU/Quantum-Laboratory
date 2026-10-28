import { useMemo, useState } from 'react';
import { ArrowLeft, BookOpen, ExternalLink, Search } from 'lucide-react';
import { MathBlock } from './Math';
import { references } from '../docs/references';
import { topics, type HandbookBlock, topicById } from '../docs/topics';

type Props = Readonly<{ initialTopic?: string; onClose: () => void }>;

function renderText(text: string, onTopic: (id: string) => void) {
  return text.split(/(\[[^\]]+\]\([a-z0-9-]+\))/g).map((part, index) => {
    const match = part.match(/^\[([^\]]+)\]\(([a-z0-9-]+)\)$/);
    const target = match ? ({ density: 'density-trace', multispin: 'density-trace', 'partial-trace': 'density-trace' }[match[2]] ?? match[2]) : '';
    return match ? <button className="handbook-inline-link" key={index} type="button" onClick={() => onTopic(target)}>{match[1]}</button> : part;
  });
}

function ContentBlock({ block, onTopic }: { block: HandbookBlock; onTopic: (id: string) => void }) {
  if (block.type === 'paragraph') return <p>{renderText(block.text, onTopic)}</p>;
  if (block.type === 'formula') return <figure className="handbook-formula"><MathBlock latex={block.latex} label={block.label} /><figcaption>{block.label} <span>{block.sources.map(id => references[id].id.toUpperCase()).join(' · ')}</span></figcaption></figure>;
  if (block.type === 'list') return <ul>{block.items.map(item => <li key={item}>{item}</li>)}</ul>;
  return <aside className={`handbook-note ${block.tone ?? 'info'}`}><strong>{block.title}</strong><p>{block.text}</p></aside>;
}

/** Локальний тематичний довідник. Його вміст і математичні формули постачаються разом із застосунком. */
export function ScientificDocumentation({ initialTopic = 'overview', onClose }: Props) {
  const [selectedId, setSelectedId] = useState(topicById(initialTopic)?.id ?? 'overview');
  const [query, setQuery] = useState('');
  const selected = topicById(selectedId) ?? topics[0];
  const filtered = useMemo(() => {
    const value = query.trim().toLocaleLowerCase('uk');
    return value ? topics.filter(topic => `${topic.title} ${topic.summary} ${topic.category}`.toLocaleLowerCase('uk').includes(value)) : topics;
  }, [query]);
  return <section className="handbook" aria-label="Наукова довідка">
    <header className="handbook-header"><div><BookOpen size={18} /><div><strong>НАУКОВА ДОВІДКА</strong><small>Quantum Laboratory · локальний довідник</small></div></div><button type="button" onClick={onClose}><ArrowLeft size={15} /> Повернутися до лабораторії</button></header>
    <div className="handbook-layout">
      <nav className="handbook-nav" aria-label="Зміст довідки">
        <label className="handbook-search"><Search size={15} /><input type="search" aria-label="Пошук у науковій довідці" placeholder="Пошук тем" value={query} onChange={event => setQuery(event.target.value)} /></label>
        <div className="handbook-topic-list">{filtered.map(topic => <button type="button" key={topic.id} className={topic.id === selected.id ? 'active' : ''} onClick={() => setSelectedId(topic.id)}><small>{topic.category}</small><span>{topic.title}</span></button>)}{!filtered.length && <p>За цим запитом тем не знайдено.</p>}</div>
      </nav>
      <article className="handbook-article" key={selected.id}>
        <div className="handbook-kicker">{selected.category} <span>·</span> {selected.id}</div>
        <h1>{selected.title}</h1><p className="handbook-summary">{selected.summary}</p>
        <div className="handbook-content" id="topic-content">{selected.blocks.map((block, index) => <ContentBlock key={`${selected.id}-${index}`} block={block} onTopic={setSelectedId} />)}</div>
        <section className="handbook-references" id="topic-sources"><h2>Джерела для цієї теми</h2>{selected.sources.map(id => {
          const ref = references[id];
          const href = ref.doi ? `https://doi.org/${ref.doi}` : ref.url!;
          return <article key={id}><strong>{ref.authors.join(', ')} ({ref.year}). {ref.title}.</strong><span>{ref.venue}</span><p>{ref.supports.join(' ')}</p><a href={href} target="_blank" rel="noreferrer">{ref.doi ? `DOI: ${ref.doi}` : ref.url} <ExternalLink size={12} /></a></article>;
        })}</section>
      </article>
      <aside className="handbook-toc"><strong>У ЦЬОМУ РОЗДІЛІ</strong><a href="#topic-content">Пояснення</a><a href="#topic-sources">Джерела</a><span>{selected.blocks.filter(block => block.type === 'formula').length} формул</span></aside>
    </div>
  </section>;
}
