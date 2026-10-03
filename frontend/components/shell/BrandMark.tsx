/** Original Fantasy Football AI mark: a centre circle with an ascending signal path. */
export function BrandMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false" className="brand-mark">
      <defs>
        <linearGradient id="brand-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#a78bfa" />
          <stop offset="1" stopColor="#6d28d9" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#brand-grad)" />
      <circle cx="16" cy="16" r="8.5" fill="none" stroke="rgba(255,255,255,.35)" strokeWidth="1.4" />
      <path d="M7.5 21 L13 15.5 L17 18.5 L24.5 10.5" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="24.5" cy="10.5" r="2" fill="#5eead4" />
    </svg>
  );
}
