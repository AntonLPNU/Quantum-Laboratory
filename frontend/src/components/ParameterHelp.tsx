import { useState } from 'react';
import { Info } from 'lucide-react';
import { MathInline } from './Math';

const help = {
  J: { topic: 'tfim', title: 'Обмінна взаємодія J', units: 's⁻¹ (кутова частота)', range: 'Будь-яке скінченне дійсне значення, включно з 0.', formula: 'H/\\hbar=-J\\sum_i\\sigma_i^z\\sigma_{i+1}^z-\\cdots', effect: 'Задає силу взаємодії сусідніх спінів у відкритому ланцюгу TFIM.' },
  h: { topic: 'tfim', title: 'Поперечне поле h', units: 's⁻¹ (кутова частота)', range: 'Будь-яке скінченне дійсне значення, включно з 0.', formula: 'H/\\hbar=\\cdots-h\\sum_i\\sigma_i^x', effect: 'Задає амплітуду поперечного поля вздовж осі x.' },
  'λ': { topic: 'decoherence', title: 'Частка фазового затухання λ', units: 'Безрозмірна', range: '0 ≤ λ ≤ 1; 0 — немає втрати когерентності, 1 — повне фазове затухання.', formula: '\\rho_{01}\\mapsto(1-\\lambda)\\rho_{01}', effect: 'Керує локальним каналом у Z-базисі; не є T₂ або каліброваною швидкістю.' },
  'CHSH S': { topic: 'chsh-concurrence', title: 'Параметр CHSH S', units: 'Безрозмірний', range: 'Квантова двокубітна межа 2√2; класична межа 2.', formula: 'S=|E_{00}+E_{01}+E_{10}-E_{11}|', effect: 'Розрізняйте обчислення для фіксованих осей та оптимізоване S_max.' },
  Concurrence: { topic: 'chsh-concurrence', title: 'Concurrence C', units: 'Безрозмірна; 0…1 для двох кубітів.', range: '0 — separable; 1 — максимально заплутані два кубіти.', formula: 'C=\\max(0,r_1-r_2-r_3-r_4)', effect: 'Обчислюється Python-ядром для вибраного двокубітного стану.' },
  'Trace Distance': { topic: 'analyzer', title: 'Trace distance', units: 'Безрозмірна; 0…1 для нормованих станів.', range: '0 — однакові стани; 1 — ортогональні стани з ідеальною розрізнюваністю.', formula: 'D(\\rho,\\sigma)=\\tfrac12\\operatorname{Tr}|\\rho-\\sigma|', effect: 'Міра відмінності двох матриць густини; не визначає самостійно статистичну значущість.' },
} as const;
type Parameter = keyof typeof help;
type Props = Readonly<{ parameter: Parameter; onOpenTopic: (topic: string) => void }>;

/** Доступне контекстне пояснення параметра з переходом до відповідної сторінки довідки. */
export function ParameterHelp({ parameter, onOpenTopic }: Props) {
  const [open, setOpen] = useState(false);
  const item = help[parameter];
  return <span className="parameter-help"><button type="button" className="parameter-help-trigger" aria-label={`Пояснення: ${parameter}`} aria-expanded={open} onClick={() => setOpen(value => !value)}><Info size={13} /></button>{open && <span className="parameter-tooltip" role="tooltip"><strong>{item.title}</strong><span>Одиниці: {item.units}</span><span>Допустимі значення: {item.range}</span><MathInline latex={item.formula} label={`Формула ${parameter}`} /><span>{item.effect}</span><button type="button" onClick={() => onOpenTopic(item.topic)}>Відкрити розділ довідки</button></span>}</span>;
}
