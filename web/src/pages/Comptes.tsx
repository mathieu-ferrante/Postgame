// Comptes liés (CPT-01) : Steam / CS2, Riot, FACEIT, et évolution des classements.

import type { PointSerie } from "../api";
import { Etat, useDonnee } from "../composants/Chargement";
import Graphique from "../composants/Graphique";

interface Comptes {
  steam: { steamid: string | null; pseudos: string[]; appris: boolean; profil: string | null; codes_partage: boolean };
  riot: { riot_id: string | null; plateforme: string; cle_presente: boolean };
  faceit: { pseudo: string | null; cle_presente: boolean; telechargement: boolean };
  classements: Record<"premier" | "competitif" | "lol", (PointSerie & { contexte: Record<string, string> })[]>;
}

async function charger(): Promise<Comptes> {
  const r = await fetch("/api/comptes");
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

function Etat2({ ok, texte }: { ok: boolean; texte: string }) {
  return <div><span style={{ color: ok ? "var(--bien)" : "var(--mal)" }}>{ok ? "✓" : "✗"}</span> {texte}</div>;
}

export default function PageComptes() {
  const { donnee: c, erreur, chargement } = useDonnee(charger, []);
  if (!c) return <Etat erreur={erreur} chargement={chargement} />;
  return (
    <>
      <h1>Mes comptes</h1>
      <div className="grille">
        <div className="carte">
          <h3>Steam · Counter-Strike 2</h3>
          <Etat2 ok={Boolean(c.steam.steamid)} texte={c.steam.steamid
            ? `SteamID64 ${c.steam.steamid}${c.steam.appris ? " (retrouvé dans une démo)" : ""}`
            : "SteamID64 inconnu : reconnu par le pseudo en attendant"} />
          <div className="discret">Pseudos : {c.steam.pseudos.join(", ") || "—"}</div>
          <Etat2 ok={c.steam.codes_partage} texte="Codes de partage (parties Premier / compétitives)" />
          {c.steam.profil && <a href={c.steam.profil} target="_blank" rel="noreferrer">Profil Steam</a>}
        </div>
        <div className="carte">
          <h3>Riot · League of Legends, TFT</h3>
          <Etat2 ok={Boolean(c.riot.riot_id)} texte={c.riot.riot_id ?? "Riot ID absent"} />
          <Etat2 ok={c.riot.cle_presente} texte={`Clé API Riot (${c.riot.plateforme})`} />
        </div>
        <div className="carte">
          <h3>FACEIT</h3>
          <Etat2 ok={Boolean(c.faceit.pseudo)} texte={c.faceit.pseudo ?? "Pseudo FACEIT absent"} />
          <Etat2 ok={c.faceit.cle_presente} texte="Clé Data API" />
          <Etat2 ok={c.faceit.telechargement} texte="Accès aux démos (Downloads API)" />
        </div>
      </div>
      <h2>CS Rating (Premier)</h2>
      <div className="carte"><Graphique points={c.classements.premier} unite="" /></div>
      <h2>Rang LoL (classée solo, points de ligue)</h2>
      <div className="carte"><Graphique points={c.classements.lol} unite="LP" /></div>
      <p className="discret">Les classements viennent des parties elles-mêmes : chaque démo Premier contient ton CS Rating, chaque partie LoL ton rang au moment de la synchronisation.</p>
    </>
  );
}
