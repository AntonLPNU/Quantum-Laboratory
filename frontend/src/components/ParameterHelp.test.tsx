import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ParameterHelp } from './ParameterHelp';
import { topicById } from '../docs/topics';

const parameters = ['J', 'h', 'λ', 'CHSH S', 'Concurrence', 'Trace Distance'] as const;

describe('contextual parameter help', () => {
  it.each(parameters)('explains %s and links to the matching handbook entry', parameter => {
    const onOpenTopic = vi.fn();
    render(<ParameterHelp parameter={parameter} onOpenTopic={onOpenTopic} />);
    fireEvent.click(screen.getByRole('button', { name: `Пояснення: ${parameter}` }));
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
    expect(screen.getByRole('tooltip').textContent).toMatch(/Одиниці|безрозмірн|межа/i);
    fireEvent.click(screen.getByRole('button', { name: 'Відкрити розділ довідки' }));
    expect(onOpenTopic).toHaveBeenCalledOnce();
    expect(topicById(onOpenTopic.mock.calls[0][0])).toBeDefined();
  });
});
