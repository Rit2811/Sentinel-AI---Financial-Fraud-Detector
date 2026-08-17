function IconFrame({ children, label }) {
  return (
    <svg
      aria-label={label}
      className="icon"
      fill="none"
      role="img"
      viewBox="0 0 24 24"
    >
      {children}
    </svg>
  )
}

export function TransactionsIcon({ label }) {
  return (
    <IconFrame label={label}>
      <path d="M4 7h15m0 0-4-4m4 4-4 4M20 17H5m0 0 4 4m-4-4 4-4" />
    </IconFrame>
  )
}

export function ShieldIcon({ label }) {
  return (
    <IconFrame label={label}>
      <path d="M12 3 5 6v5c0 4.6 2.9 8.2 7 10 4.1-1.8 7-5.4 7-10V6l-7-3Z" />
      <path d="M12 7v6m0 3v.01" />
    </IconFrame>
  )
}

export function CheckIcon({ label }) {
  return (
    <IconFrame label={label}>
      <path d="m5 12 4 4L19 6" />
    </IconFrame>
  )
}
