/** Outlined status icons (24-unit grid, currentColor stroke) used beside labels. */
const PATHS = {
  // Sun: disc + rays (solar power, Sun rows)
  sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4',
  // Radio: emitter + two wave pairs (Earth radio link)
  radio:
    'M12 10.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zM8.5 15.5a5 5 0 0 1 0-7M15.5 8.5a5 5 0 0 1 0 7M5.6 18.4a9 9 0 0 1 0-12.8M18.4 5.6a9 9 0 0 1 0 12.8',
  // Earth: globe with meridian and equator
  earth: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z',
  // Bundled data: database cylinder
  database: 'M4 6c0 1.7 3.6 3 8 3s8-1.3 8-3-3.6-3-8-3-8 1.3-8 3zM4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3',
  // Terrain horizon: ridge line
  mountain: 'M2.5 19.5l6.5-11 4 6.5 2.5-3.5 6 8z',
  // Payload categories
  droplet: 'M12 3c3.6 4.3 6 7.7 6 10.6a6 6 0 0 1-12 0C6 10.7 8.4 7.3 12 3z',
  spectrum: 'M3 12h3.5l2.5-7 4 14 3-9 1.5 2H21',
  rover: 'M4 13.5h15.5M6.5 13.5V10h8l2.5 3.5M6.5 18.5a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM16.5 18.5a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM10 10V7h3',
  gauge: 'M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18zM12 12l3.5-3.5M12 7v1.5M7 12h1.5M16 12h1.5',
  // Comparison outcomes
  up: 'M3 17l6-6 4 4 8-8M15 7h6v6',
  down: 'M3 7l6 6 4-4 8 8M15 17h6v-6',
  level: 'M5 9.5h14M5 14.5h14',
  none: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM5.6 5.6l12.8 12.8',
  check: 'M4.5 12.5l4.5 4.5L19.5 6.5',
  // Live engine: server with a status light
  server: 'M4 4h16v6H4zM4 14h16v6H4zM8 7h.01M8 17h.01M12 7h4M12 17h4',
  // Waking: circular arrow
  waking: 'M20 12a8 8 0 1 1-2.3-5.7M20 4v4.5h-4.5',
  // Custom point: map pin
  pin: 'M12 21s-6.5-6.2-6.5-11.2a6.5 6.5 0 0 1 13 0C18.5 14.8 12 21 12 21zM12 7.5a2.3 2.3 0 1 0 0 4.6 2.3 2.3 0 0 0 0-4.6z',
  // Dates
  calendar: 'M4 6h16v14H4zM4 10h16M8 3.5V7M16 3.5V7',
  // Events: rise / set arrows on a horizon
  rise: 'M3 18h18M12 15V5M8 9l4-4 4 4',
  set: 'M3 18h18M12 5v10M8 11l4 4 4-4',
  close: 'M6 6l12 12M18 6L6 18',
} as const

export type IconName = keyof typeof PATHS

export function Icon({ name, size = 15, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg
      className={`icon${className ? ` ${className}` : ''}`}
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  )
}
