export function Card({ actions, children, className = '', title }) {
  const classes = ['card', className].filter(Boolean).join(' ')

  return (
    <section className={classes}>
      {(title || actions) && (
        <header className="card__header">
          {title && <h2 className="card__title">{title}</h2>}
          {actions}
        </header>
      )}
      {children}
    </section>
  )
}
