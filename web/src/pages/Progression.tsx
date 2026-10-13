import { useMemo, useState } from "react";
import { api } from "../api";
import { Etat, useDonnee } from "../composants/Chargement";
import Graphique from "../composants/Graphique";
import { nomCourt } from "../lib/format";

// Mesures phares du cahier des charges, proposées en premier.
const PHARES = [
  "cs2.contre_strafe.part_premieres_balles_precises",
  "cs2.viseur.ecart_median",
  "cs2.trades.part_tradables_non_tradees",
  "cs2.smoke.part_reconnues",
  "gd.regularite.ecart_type_median",
];

const PERIODES = [
  ["7j", "7 jours"],
  ["30j", "30 jours"],
  ["tout", "Tout"],
] as const;

export default function Progression() {
  const definitions = useDonnee(() => api.definitions(), []);
  const presentes = useDonnee(() => api.mesuresPresentes(), []);
  const [nom, setNom] = useState("");
  const [periode, setPeriode] = useState("30j");
  const [contexte, setContexte] = useState("global");

  const choix = useMemo(() => {
    const ici = new Set(presentes.donnee ?? []);
    return (definitions.donnee ?? []).filter((d) => ici.has(d.nom));
  }, [definitions.donnee, presentes.donnee]);
  const actuel = nom || PHARES.find((n) => choix.some((d) => d.nom === n)) || choix[0]?.nom || "";
  const definition = choix.find((d) => d.nom === actuel);
  const serie = useDonnee(
    () => (actuel ? api.progression(actuel, periode) : Promise.resolve({ points: [] })),
    [actuel, periode],
  );

  // Une même mesure existe en global et par arme / tranche : on choisit la déclinaison.
  const declinaisons = useMemo(() => {
    const cles = new Set<string>();
    for (const p of serie.donnee?.points ?? []) {
      const c = Object.entries(p.contexte).filter(([k]) => k !== "n" && k !== "total");
      cles.add(c.length ? c.map(([k, v]) => `${k}=${v}`).join(",") : "global");
    }
    return [...cles].sort();
  }, [serie.donnee]);
  const contexteActif = declinaisons.includes(contexte) ? contexte : (declinaisons[0] ?? "global");
  const points = (serie.donnee?.points ?? []).filter((p) => {
    const c = Object.entries(p.contexte).filter(([k]) => k !== "n" && k !== "total");
    return (c.length ? c.map(([k, v]) => `${k}=${v}`).join(",") : "global") === contexteActif;
  });

  return (
    <>
      <h1>Progression</h1>
      <Etat erreur={definitions.erreur ?? presentes.erreur} chargement={definitions.chargement} />
      {choix.length === 0 && !definitions.chargement && (
        <p className="discret">Aucune mesure en base pour l'instant.</p>
      )}
      {choix.length > 0 && (
        <div className="carte">
          <div className="ligne">
            <select value={actuel} onChange={(e) => { setNom(e.target.value); setContexte("global"); }}>
              {choix.map((d) => (
                <option key={d.nom} value={d.nom}>{nomCourt(d.nom)}{d.fiable ? "" : " (en validation)"}</option>
              ))}
            </select>
            {declinaisons.length > 1 && (
              <select value={contexteActif} onChange={(e) => setContexte(e.target.value)}>
                {declinaisons.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            )}
            {PERIODES.map(([v, l]) => (
              <button key={v} className={periode === v ? "actif" : ""} onClick={() => setPeriode(v)}>{l}</button>
            ))}
          </div>
          {definition && (
            <p className="discret">
              {definition.description} ({definition.sens === "haut" ? "plus haut = mieux" : definition.sens === "bas" ? "plus bas = mieux" : "ni bien ni mal"})
            </p>
          )}
          <Etat erreur={serie.erreur} chargement={serie.chargement} />
          {!serie.chargement && <Graphique points={points} unite={definition?.unite ?? ""} />}
          <p className="discret">Courbe pleine : moyenne glissante sur 5 parties. Cliquer un point ouvre la partie.</p>
        </div>
      )}
    </>
  );
}
