import { useEffect, useState } from 'react'

/** Phones and small tablets in portrait. Keep in sync with the CSS breakpoints (800px). */
export const COMPACT_QUERY = '(max-width: 800px)'

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)

  useEffect(() => {
    const mq = window.matchMedia(query)
    const onChange = () => setMatches(mq.matches)
    mq.addEventListener('change', onChange)
    onChange()
    return () => mq.removeEventListener('change', onChange)
  }, [query])

  return matches
}
