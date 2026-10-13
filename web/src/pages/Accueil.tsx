import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Etat, useDonnee } from "../composants/Chargement";
import { JEUX, RESULTATS, dateCourte, duree } from "../lib/format";

function Depot({ apresImport }: { apresImport: () => void }) {
  const [survol, setSurvol] = useState(false);
  const [message, setMessage] = useState("");
  const envoyer = async (fichiers: FileList | null) => {
    if (!fichiers) return;
    for (const f of Array.from(fichiers)) {
      setMessage(`Import de ${f.name}…`);
      try {
        const r = await api.importer(f);
        setMessage(`${f.name} : ${r.statut === "deja_connu" ? "déjà importé" : r.message}`);
      } catch (e) {
        setMessage(`${f.name} : ${(e as Error).message}`);
      }
    }
    apresImport();
  };
  return (
    <label
      className={`depot ${survol ? "survol" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setSurvol(true); }}
      onDragLeave={() => setSurvol(false)}
      onDrop={(e) => { e.preventDefault(); setSurvol(false); envoyer(e.dataTransfer.files); }}
    >
      <input type="file" multiple hidden onChange={(e) => envoyer(e.target.files)} />
      Glisser une démo ici (ou cliquer) pour l'importer à la main.
      {message && <div className="discret">{message}</div>}
    </label>
  );
}

export default function Accueil() {
  const parties = useDonnee(() => api.parties(undefined, 60), []);
  const etat = useDonnee(() => api.etatImport(), []);
  const erreurs = etat.donnee?.derniers_fichiers.filter((f) => f.statut === "erreur") ?? [];
  return (
    <>
      <h1>Parties</h1>
      <Depot apresImport={() => { parties.recharger(); etat.recharger(); }} />
      {etat.donnee && etat.donnee.en_attente.length > 0 && (
        <p className="discret">{etat.donnee.en_attente.length} fichier(s) en cours d'écriture, importés dès qu'ils sont complets.</p>
      )}
      {erreurs.length > 0 && (
        <p className="erreur">{erreurs.length} fichier(s) n'ont pas pu être importés : {erreurs[0].message}</p>
      )}
      <Etat erreur={parties.erreur} chargement={parties.chargement} />
      {parties.donnee?.parties.length === 0 && (
        <p className="discret">Aucune partie pour l'instant : jouez, ou déposez une démo ci-dessus.</p>
      )}
      <div className="grille">
        {parties.donnee?.parties.map((p) => (
          <Link key={p.id} to={`/partie/${p.id}`} className="carte partie">
            <div className="ligne">
              <span className="badge">{JEUX[p.jeu] ?? p.jeu}</span>
              <span className="discret">{dateCourte(p.date_partie)}</span>
            </div>
            <h3 style={{ marginTop: "0.4rem" }}>{p.carte}</h3>
            <div className="ligne">
              <span className={`score ${p.resultat}`}>
                {p.score_joueur !== null ? `${p.score_joueur} – ${p.score_adverse}` : RESULTATS[p.resultat]}
              </span>
              <span className="discret">{p.mode} · {duree(p.duree_s)}</span>
            </div>
          </Link>
        ))}
      </div>
    </>
  );
}
