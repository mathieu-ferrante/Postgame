// Revoir un vrai moment dans CS2 : Postgame prépare la démo et les commandes, le jeu la joue.

import { useState } from "react";
import type { DemandeRevoir, MomentPro, Revoir } from "../api";
import { api } from "../api";

function copier(texte: string) {
  void navigator.clipboard?.writeText(texte);
}

export function BoutonRevoir({ demande, libelle = "Revoir dans CS2" }: { demande: DemandeRevoir; libelle?: string }) {
  const [revoir, setRevoir] = useState<Revoir | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [encours, setEncours] = useState(false);

  const preparer = async () => {
    setEncours(true);
    setErreur(null);
    try {
      setRevoir(await api.revoir(demande));
    } catch (e) {
      setErreur(String((e as Error).message));
    } finally {
      setEncours(false);
    }
  };

  return (
    <span className="revoir">
      <button onClick={preparer} disabled={encours}>{encours ? "Préparation…" : libelle}</button>
      {erreur && <span className="erreur"> {erreur}</span>}
      {revoir && (
        <span className="carte revoir-etapes">
          {!revoir.installe && (
            <span className="discret">Dossier de CS2 introuvable sur cette machine : les fichiers sont dans {revoir.demo}. À faire sur le PC de jeu.<br /></span>
          )}
          Dans la console de CS2 :{" "}
          <code>{revoir.commandes[0]}</code> <button onClick={() => copier(revoir.commandes[0])}>Copier</button>
          {", puis une fois la démo chargée "}
          <code>{revoir.commandes[1]}</code>
          {revoir.joueur ? ` (caméra sur ${revoir.joueur}, 5 s avant).` : " (5 s avant)."}
          <br />
          <a href={revoir.lien_steam}>CS2 fermé ? Le lancer directement sur la démo</a>
        </span>
      )}
    </span>
  );
}

export function MomentsPros({ moments, vide }: { moments: MomentPro[]; vide: string }) {
  if (!moments.length) return <p className="discret">{vide}</p>;
  return (
    <ul className="fil">
      {moments.map((m) => (
        <li key={`${m.empreinte}-${m.round}-${m.joueur}`}>
          <strong>{m.joueur ?? "?"}</strong>{" "}
          <span className="discret">{m.demo}{m.round ? `, round ${m.round}` : ""}{m.lieu ? ` · ${m.lieu}` : ""}</span>{" "}
          <BoutonRevoir demande={{ empreinte: m.empreinte, tick: m.tick, joueur: m.joueur }} libelle="▶ CS2" />
        </li>
      ))}
    </ul>
  );
}
