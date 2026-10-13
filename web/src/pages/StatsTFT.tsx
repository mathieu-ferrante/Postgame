// TFT (TFT-02, TFT-03) : ce qui fait gagner ou perdre des places à Mathieu, par set et patch,
// face au haut classement du même patch.

import { useState } from "react";
import { Etat, useDonnee } from "../composants/Chargement";
import { nombre } from "../lib/format";

interface Element {
  type: string; nom: string; parties: number; place_moyenne: number; ecart: number; top4: number;
  ref_place_moyenne?: number | null; ref_parties?: number;
}
interface Bloc {
  set: number; patch: string; parties: number; place_moyenne: number; elements: Element[];
  reference: { parties: number } | null; a_essayer: Element[];
}

async function charger(): Promise<Record<string, Bloc>> {
  const r = await fetch("/api/tft/stats");
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

const TYPES: Record<string, string> = { trait: "Trait", unite: "Unité", objet: "Objet", augment: "Augment" };

export default function StatsTFT() {
  const { donnee, erreur, chargement } = useDonnee(charger, []);
  const cles = Object.keys(donnee ?? {}).sort().reverse();
  const [choix, setChoix] = useState<string | null>(null);
  const cle = choix ?? cles[0];
  const b = cle ? donnee?.[cle] : undefined;
  return (
    <>
      <h1>TFT — ce qui te fait gagner des places</h1>
      <Etat erreur={erreur} chargement={chargement} />
      {donnee && cles.length === 0 && <p className="discret">Aucune partie TFT pour l'instant.</p>}
      {cles.length > 0 && (
        <select value={cle} onChange={(e) => setChoix(e.target.value)}>
          {cles.map((c) => <option key={c} value={c}>Set {donnee![c].set} — patch {donnee![c].patch}</option>)}
        </select>
      )}
      {b && (
        <>
          <p className="discret">
            {b.parties} partie(s) sur ce patch, place moyenne {nombre(b.place_moyenne)}.{" "}
            {b.reference ? `Référence : ${b.reference.parties} parties de haut classement du même patch.`
              : "Pas encore de référence de haut classement pour ce patch (commande « riot meta »)."}
          </p>
          <div className="carte" style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr><th>Élément</th><th>Parties</th><th>Ta place moy.</th><th>Écart</th><th>Haut classement</th></tr>
              </thead>
              <tbody>
                {b.elements.map((e) => (
                  <tr key={e.type + e.nom}>
                    <td><span className="discret">{TYPES[e.type] ?? e.type}</span> {e.nom}</td>
                    <td className="nombre">{e.parties}</td>
                    <td className="nombre">{nombre(e.place_moyenne)}</td>
                    <td className="nombre" style={{ color: e.ecart < 0 ? "var(--bien)" : "var(--mal)" }}>
                      {e.ecart > 0 ? "+" : ""}{nombre(e.ecart)}
                    </td>
                    <td className="nombre discret">{e.ref_place_moyenne ? nombre(e.ref_place_moyenne) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="discret">Écart négatif (vert) : tu finis mieux classé quand tu le joues. Minimum 3 parties.</p>
          </div>
          {b.a_essayer.length > 0 && (
            <div className="carte">
              <h3>Forts en haut classement, rarement joués par toi</h3>
              {b.a_essayer.map((e) => (
                <div key={e.type + e.nom}>{TYPES[e.type]} {e.nom} — place moyenne {nombre(e.place_moyenne)} ({e.parties} parties)</div>
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}
