export default function Home() {
  return (
    <main className="page">
      <section className="card" aria-labelledby="title">
        <p className="eyebrow">EIGSI Casablanca</p>
        <h1 id="title">Pointage du personnel</h1>
        <p>Pointage du personnel par QR code, avec horodatage côté serveur.</p>
        <nav
          aria-label="Accès aux fonctions de pointage"
          className="home-links"
        >
          <a className="button-link" href="/my-qr">
            Mon QR personnel
          </a>
          <a className="button-link" href="/attendance">
            Scanner un QR (RH/Scolarité)
          </a>
          <a className="button-link" href="/my-attendance">
            Mes heures de présence
          </a>
          <a className="button-link" href="/admin/schedules">
            Gérer les horaires (RH/Scolarité)
          </a>
          <a className="button-link" href="/admin/alerts">
            Alertes de présence (RH/Scolarité)
          </a>
          <a className="button-link" href="/admin/dashboard">
            Tableau de bord (RH/Scolarité)
          </a>
          <a className="button-link" href="/admin/corrections">
            Corriger des pointages (RH/Scolarité)
          </a>
          <a className="button-link" href="/admin/exports">
            Export hebdomadaire (RH/Finance)
          </a>
          <a className="text-link" href="/login">
            Se connecter
          </a>
        </nav>
      </section>
    </main>
  );
}
