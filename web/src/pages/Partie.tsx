import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Constat, Debrief } from "../api";
import { api } from "../api";
import { Etat, useDonnee } from "../composants/Chargement";
import Markdown from "../composants/Markdown";
import { JEUX, dateCourte, duree, nombre, nomCourt, score } from "../lib/format";

function CarteConstat({ c, partieId, jeu }: { c: Constat; partieId: number; jeu: string }) {
  const contexte = Object.entries(c.contexte).map(([k, v]) => `${k} ${v}`).join(", ");
  return (
    <div id={c.id} className={`carte constat ${c.statut}`}>
      <div className="ligne">
        <span className="badge">{c.id}</span>
        <strong>{nomCourt(c.mesure)}</strong>
        {contexte && <span className="discret">({contexte})</span>}
        {c.experimental && <span className="badge" title="Pas encore vérifiée à la main">en validation</span>}
      </div>
      <div className="discret">{c.libelle}</div>
      <div className="chiffres">
        <span>Cette partie <strong>{nombre(c.valeur, c.unite)}</strong></span>
        {c.reference !== null && (
          <span>Ta moyenne <strong>{nombre(c.reference, c.unite)}</strong>
            <span className="discret"> ({c.nb_reference} parties)</span></span>
        )}
        {c.cible !== null && <span>Cible <strong>{nombre(c.cible, c.unite)}</strong></span>}
        {c.n !== null && <span className="discret">échantillon {c.n}</span>}
      </div>
      {c.preuves.length > 0 && (
        <ul className="preuves">
          {c.preuves.map((p, i) => (
            <li key={i}>
              {jeu === "cs2" && p.tick !== null ? (
                <Link to={`/replay/${partieId}?tick=${p.tick}`}>
                  {p.round !== null ? `Round ${p.round}` : `Tick ${p.tick}`}
                </Link>
              ) : (
                <span>{p.round !== null ? `Round ${p.round}` : ""}</span>
              )}{" "}
              — {p.texte}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function BlocDebrief({ d, partieId, jeu, regenerer }: { d: Debrief; partieId: number; jeu: string; regenerer: () => void }) {
  const { priorites, points_forts, details, mesures_masquees } = d.contenu;
  return (
    <>
      {d.statut === "redige" && (
        <div className="carte"><Markdown texte={d.texte} /></div>
      )}
      {d.statut === "rejete" && (
        <p className="discret">Le texte du modèle a été écarté ({d.message}) : voici le débrief chiffré.</p>
      )}
      <h2>Priorités</h2>
      {priorites.length === 0 && <p className="discret">Aucun point prioritaire.</p>}
      {priorites.map((c) => <CarteConstat key={c.id} c={c} partieId={partieId} jeu={jeu} />)}
      {points_forts.length > 0 && <h2>Points forts</h2>}
      {points_forts.map((c) => <CarteConstat key={c.id} c={c} partieId={partieId} jeu={jeu} />)}
      {details.length > 0 && <h2>Détail</h2>}
      {details.map((c) => <CarteConstat key={c.id} c={c} partieId={partieId} jeu={jeu} />)}
      {mesures_masquees > 0 && (
        <p className="discret">{mesures_masquees} mesure(s) pas encore vérifiée(s) à la main ne sont pas affichées.</p>
      )}
      <p className="discret ligne">
        <span>
          Débrief {d.fournisseur === "aucun" ? "chiffré (sans modèle de langage)" : `rédigé par ${d.modele}`}
          {d.cout > 0 && ` — ${d.jetons_entree + d.jetons_sortie} jetons, ${d.cout.toFixed(4)} $`}
        </span>
        <button onClick={regenerer}>Régénérer</button>
      </p>
    </>
  );
}

export default function PagePartie() {
  const id = Number(useParams().id);
  const [regen, setRegen] = useState(0);
  const partie = useDonnee(() => api.partie(id), [id]);
  const debrief = useDonnee(() => api.debrief(id, regen > 0), [id, regen]);
  const p = partie.donnee;
  return (
    <>
      <Etat erreur={partie.erreur} chargement={partie.chargement} />
      {p && (
        <>
          <div className="ligne">
            <span className="badge">{JEUX[p.jeu] ?? p.jeu}</span>
            <span className="discret">{dateCourte(p.date_partie)} · {p.mode} · {duree(p.duree_s)}</span>
          </div>
          <h1 style={{ marginTop: "0.4rem" }}>
            {p.carte}{" "}
            <span className={p.resultat}>
              {score(p)}
            </span>
          </h1>
          {p.jeu === "cs2" && <Link to={`/replay/${p.id}`}>Ouvrir le replay 2D →</Link>}
          {p.jeu === "gd" && <Link to={`/gd/${p.id}`}>Voir tous les essais superposés →</Link>}
        </>
      )}
      <Etat erreur={debrief.erreur} chargement={debrief.chargement} />
      {debrief.donnee && p && (
        <BlocDebrief d={debrief.donnee} partieId={id} jeu={p.jeu} regenerer={() => setRegen((r) => r + 1)} />
      )}
      {p && p.mesures.length > 0 && (
        <>
          <h2>Toutes les mesures</h2>
          <div className="carte" style={{ overflowX: "auto" }}>
            <table>
              <tbody>
                {p.mesures.map((m, i) => (
                  <tr key={i}>
                    <td>{nomCourt(m.nom)}</td>
                    <td className="discret">
                      {Object.entries(m.contexte).filter(([k]) => k !== "n" && k !== "total").map(([k, v]) => `${k} ${v}`).join(", ")}
                    </td>
                    <td className="nombre">{nombre(m.valeur, m.unite)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
