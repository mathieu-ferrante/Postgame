// Second écran CS2 (CS-LIVE-01) : état de la partie en cours, poussé par le service à chaque
// message Game State Integration, et rappel des priorités du dernier débrief.

import { useEffect, useRef, useState } from "react";
import { nombre } from "../lib/format";

interface Live {
  actif: boolean;
  recu_le?: string;
  carte?: string;
  phase_round?: string;
  round?: number;
  camp?: "T" | "CT" | null;
  score?: { nous: number; eux: number };
  bombe?: string | null;
  observe?: string | null;
  joueur?: {
    vie: number; armure: number; casque: boolean; argent: number; valeur_equipement: number;
    argent_si_defaite?: number;
    kills_round: number; kills: number; assistances: number; morts: number;
    armes: { nom: string; active: boolean; munitions: number | null; reserve: number | null }[];
  } | null;
  recommandation?: { type: string; titre: string; raison: string } | null;
  coequipiers?: { nom: string; argent: number; vie: number }[] | null;
  rappel?: { id: string; libelle: string; valeur: number; unite: string; cible: number | null }[];
}

const COULEUR_RECO: Record<string, string> = {
  complet: "var(--bien)", force: "var(--accent)", eco: "var(--mal)", pistolet: "var(--ct)", tout: "var(--accent)",
};

function adresseWs(): string {
  const schema = location.protocol === "https:" ? "wss" : "ws";
  return `${schema}://${location.host}/api/cs2/live/ws`;
}

export default function Direct() {
  const [live, setLive] = useState<Live>({ actif: false });
  const [connecte, setConnecte] = useState(false);
  const [maintenant, setMaintenant] = useState(Date.now());
  const verrou = useRef<{ release: () => Promise<void> } | null>(null);

  // Connexion WebSocket, reconnexion automatique toutes les 2 s si le service redémarre.
  useEffect(() => {
    let ws: WebSocket | null = null;
    let fini = false;
    let attente = 0;
    const connecter = () => {
      ws = new WebSocket(adresseWs());
      ws.onopen = () => setConnecte(true);
      ws.onmessage = (e) => setLive(JSON.parse(e.data));
      ws.onclose = () => {
        setConnecte(false);
        if (!fini) attente = window.setTimeout(connecter, 2000);
      };
    };
    connecter();
    const horloge = window.setInterval(() => setMaintenant(Date.now()), 1000);
    return () => {
      fini = true;
      window.clearTimeout(attente);
      window.clearInterval(horloge);
      ws?.close();
    };
  }, []);

  // Garder l'écran du téléphone allumé pendant la partie (si le navigateur le permet).
  useEffect(() => {
    const nav = navigator as Navigator & { wakeLock?: { request: (t: "screen") => Promise<{ release: () => Promise<void> }> } };
    nav.wakeLock?.request("screen").then((v) => { verrou.current = v; }).catch(() => undefined);
    return () => { verrou.current?.release().catch(() => undefined); };
  }, []);

  const age = live.recu_le ? Math.round((maintenant - new Date(live.recu_le).getTime()) / 1000) : null;
  const j = live.joueur;
  return (
    <>
      <div className="ligne">
        <h1 style={{ margin: 0 }}>En direct</h1>
        <span className="badge">{connecte ? "connecté" : "connexion…"}</span>
        {age !== null && <span className="discret">dernier message il y a {age} s</span>}
      </div>
      {!live.actif && (
        <p className="discret">
          En attente de CS2. Le jeu doit avoir la config Game State Integration
          (<code>python -m postgame gsi-config</code>) et une partie doit être lancée.
        </p>
      )}
      {live.actif && (
        <>
          <div className="carte ligne" style={{ justifyContent: "space-between" }}>
            <span>{live.carte} · round {live.round} · {live.phase_round}</span>
            <span className={live.camp === "T" ? "t" : "ct"} style={{ fontSize: "1.4rem", fontWeight: 700 }}>
              {live.camp} {live.score?.nous} – {live.score?.eux}
            </span>
          </div>
          {live.observe && <p className="discret">Tu observes {live.observe} (mort ou spectateur).</p>}
          {live.recommandation && (
            <div className="carte" style={{ borderLeft: `6px solid ${COULEUR_RECO[live.recommandation.type] ?? "var(--bord)"}` }}>
              <div style={{ fontSize: "1.6rem", fontWeight: 700 }}>{live.recommandation.titre}</div>
              <div>{live.recommandation.raison}</div>
            </div>
          )}
          {j && (
            <div className="grille">
              <div className="carte">
                <div className="discret">Argent</div>
                <div style={{ fontSize: "2rem", fontWeight: 700 }}>{nombre(j.argent)} $</div>
                <div className="discret">équipement {nombre(j.valeur_equipement)} $</div>
                {j.argent_si_defaite !== undefined && (
                  <div className="discret">si défaite : {nombre(j.argent_si_defaite)} $ au prochain round</div>
                )}
              </div>
              <div className="carte">
                <div className="discret">Vie / armure</div>
                <div style={{ fontSize: "2rem", fontWeight: 700 }}>{j.vie} / {j.armure}{j.casque ? " + casque" : ""}</div>
                <div className="discret">{j.armes.filter((a) => a.active).map((a) => `${a.nom} ${a.munitions ?? ""}/${a.reserve ?? ""}`)}</div>
              </div>
              <div className="carte">
                <div className="discret">Match</div>
                <div style={{ fontSize: "2rem", fontWeight: 700 }}>{j.kills} / {j.morts} / {j.assistances}</div>
                <div className="discret">kills / morts / assistances · {j.kills_round} kill(s) ce round</div>
              </div>
            </div>
          )}
          {live.coequipiers && live.coequipiers.length > 0 && (
            <div className="carte">
              <h3>Équipe</h3>
              {live.coequipiers.map((c) => <div key={c.nom}>{c.nom} : {nombre(c.argent)} $</div>)}
            </div>
          )}
        </>
      )}
      {live.rappel && live.rappel.length > 0 && (
        <div className="carte">
          <h3>À garder en tête (dernier débrief)</h3>
          <ol style={{ margin: 0, paddingLeft: "1.2rem" }}>
            {live.rappel.map((r) => (
              <li key={r.id}>
                {r.libelle} — dernière partie {nombre(r.valeur, r.unite)}
                {r.cible !== null && `, cible ${nombre(r.cible, r.unite)}`}
              </li>
            ))}
          </ol>
        </div>
      )}
    </>
  );
}
