export default function AuthCard({ title, subtitle, children }) {
  return (
    <main className="chatly-auth">
      <section className="chatly-auth__brand">
        <div className="chatly-auth__wordmark-wrap">
          <span className="chatly-auth__wordmark">Chatly</span>
        </div>
      </section>
      <section className="chatly-auth__panel">
        <div className="chatly-auth__content">
          <h1 className="chatly-auth__title">{title}</h1>
          {subtitle && <p className="chatly-auth__subtitle">{subtitle}</p>}
          {children}
        </div>
      </section>
    </main>
  );
}
