import { useEffect, useState } from 'react';

/** Advances presentation time independently of physical integration, which is performed by Python. */
export function usePlayback() {
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => setTime(value => Number((value + 0.02).toFixed(2))), 50);
    return () => window.clearInterval(timer);
  }, [playing]);
  return { playing, setPlaying, time, setTime } as const;
}
