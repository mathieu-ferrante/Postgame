// Panneau Geometry Dash de la page « En direct » (GD-08) : visible pendant une séance.

import { useEffect, useState } from "react";

interface Zone { de: number; a: number; morts: number }
interface LiveGD {
  actif: boolean; niveau?: string; plateforme?: boolean; essai?: number; mode?: string;
  pct?: number | null; essais_normaux?: number; essais_practice?: number;
  meilleur?: number | null; moyenne_10?: number | null; complete?: boolean;
  zones_mort?: Zone[]; duree_s?: number;
  historique?: {
    passages_irreguliers?: { pct: number; ecart_type: number | null; sens: string; decalage: number }[];
    zones_mort?: Zone[]; morts_total?: number;
  };
}

const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v.toFixed(1).replace(".", ",")} %`);

export default function DirectGD() {
  const [g, setG] = useState<LiveGD>({ actif: false });
  useEffect(() => {
    let ws: WebSocket | null = null;
    let fini = false;
    let attente = 0;
    const connecter = () => {
      const schema = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${schema}://${location.host}/api/gd/live/ws`);
      ws.onmessage = (e) => setG(JSON.parse(e.data));
      ws.onclose = () => { if (!fini) attente = window.setTimeout(connecter, 3000); };
    };
    connecter();
    return () => { fini = true; window.clearTimeout(attente); ws?.close(); };
  }, []);
  if (!g.actif) return null;
  const h = g.historique ?? {};
  const minutes = Math.floor((g.duree_s ?? 0) / 60);
  return (
    <div className="carte">
      <div className="ligne" style={{ justifyContent: "space-between" }}>
        <h3 style={{ margin: 0 }}>Geometry Dash — {g.niveau}</h3>
        <span className="discret">{minutes} min · essai {g.essai}{g.mode === "practice" ? " (entraînement)" : ""}</span>
      </div>
      <div className="grille" style={{ marginTop: "0.5rem" }}>
        <div><div className="discret">Position</div><strong style={{ fontSize: "1.6rem" }}>{pct(g.pct)}</strong></div>
        <div><div className="discret">Meilleur</div><strong style={{ fontSize: "1.6rem" }}>{g.complete ? "terminé !" : pct(g.meilleur)}</strong></div>
        <div><div className="discret">Moyenne des 10 derniers</div><strong style={{ fontSize: "1.6rem" }}>{pct(g.moyenne_10)}</strong>
          <div className="discret">{g.essais_normaux} essais normaux · {g.essais_practice} en entraînement</div></div>
      </div>
      {g.zones_mort && g.zones_mort.length > 0 && (
        <p>Morts de la séance : {g.zones_mort.map((z) => `${z.de}-${z.a} % (${z.morts})`).join(", ")}</p>
      )}
      {h.passages_irreguliers && h.passages_irreguliers.length > 0 && (
        <p className="discret">
          Séance précédente, passages les plus irréguliers :{" "}
          {h.passages_irreguliers.map((p) => `${pct(p.pct)} (${p.sens} de ${Math.round(p.decalage)} ms)`).join(" · ")}
        </p>
      )}
      {h.zones_mort && h.zones_mort.length > 0 && (
        <p className="discret">Où tu meurs le plus sur ce niveau : {h.zones_mort.map((z) => `${z.de}-${z.a} %`).join(", ")} ({h.morts_total} morts au total)</p>
      )}
    </div>
  );
}
