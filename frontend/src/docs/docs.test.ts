import { describe, expect, it } from 'vitest';
import { references } from './references';
import { topics } from './topics';

describe('scientific handbook source registry', () => {
  it('contains all 21 handbook topics with local navigation metadata', () => {
    expect(topics).toHaveLength(21);
    expect(new Set(topics.map(topic => topic.id)).size).toBe(21);
    for (const topic of topics) {
      expect(topic.title.trim()).not.toBe('');
      expect(topic.summary.trim()).not.toBe('');
      expect(topic.blocks.length).toBeGreaterThan(0);
      for (const sourceId of topic.sources) expect(references[sourceId]).toBeDefined();
    }
  });

  it('has unique, complete citations with a DOI or authoritative URL', () => {
    const ids = Object.keys(references);
    expect(new Set(ids).size).toBe(ids.length);
    for (const [id, ref] of Object.entries(references)) {
      expect(ref.title, id).toBeTruthy();
      expect(ref.authors.length, id).toBeGreaterThan(0);
      expect(ref.year, id).toBeGreaterThan(1800);
      expect(ref.venue, id).toBeTruthy();
      expect(ref.doi || ref.url, id).toBeTruthy();
      expect(ref.supports.length, id).toBeGreaterThan(0);
    }
  });

  it('resolves all math citations and topic links', () => {
    const topicIds = new Set(topics.map(topic => topic.id));
    for (const topic of topics) {
      for (const block of topic.blocks) {
        if (block.type === 'formula') for (const id of block.sources) expect(references[id]).toBeDefined();
        if ('topicId' in block && block.topicId) expect(topicIds.has(block.topicId)).toBe(true);
      }
    }
  });
});
