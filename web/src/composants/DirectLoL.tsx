// Panneau LoL de la page « En direct » (LOL-07) : visible seulement pendant une partie.

import { useEffect, useState } from "react";
import { nombre } from "../lib/format";

interface LiveLoL {
  actif: boolean; temps?: number; niveau?: number; or?: number; champion?: string;
  kills?: number; morts?: number; assistances?: number; cs?: number; cs_par_minute?: number | null;
  vision?: number; objets?: string[];
  adversaire?: { champion: string; cs: number; niveau: number };
  reperes?: { cs_par_minute_moyen?: number | null; cs_par_minute_meta?: number | null };
}

export default function DirectLoL() {
  const [l, setL] = useState<LiveLoL>({ actif: false });
  useEffect(() => {
    let ws: WebSocket | null = null;
    let fini = false;
    let attente = 0;
    const connecter = () => {
      const schema = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${schema}://${location.host}/api/lol/live/ws`);
      ws.onmessage = (e) => setL(JSON.parse(e.data));
      ws.onclose = () => { if (!fini) attente = window.setTimeout(connecter, 3000); };
    };
    connecter();
    return () => { fini = true; window.clearTimeout(attente); ws?.close(); };
  }, []);
  if (!l.actif) return null;
  const minutes = Math.floor((l.temps ?? 0) / 60);
  const r = l.reperes ?? {};
  return (
    <div className="carte">
      <div className="ligne" style={{ justifyContent: "space-between" }}>
        <h3 style={{ margin: 0 }}>LoL — {l.champion} · niveau {l.niveau}</h3>
        <span className="discret">{minutes}:{String((l.temps ?? 0) % 60).padStart(2, "0")}</span>
      </div>
      <div className="grille" style={{ marginTop: "0.5rem" }}>
        <div><div className="discret">K / M / A</div><strong style={{ fontSize: "1.6rem" }}>{l.kills}/{l.morts}/{l.assistances}</strong></div>
        <div>
          <div className="discret">Farm</div>
          <strong style={{ fontSize: "1.6rem" }}>{l.cs} ({l.cs_par_minute ?? "—"}/min)</strong>
          <div className="discret">
            {r.cs_par_minute_moyen ? `ta moyenne sur ${l.champion} : ${nombre(r.cs_par_minute_moyen)}/min` : ""}
            {r.cs_par_minute_meta ? ` · haut classement : ${nombre(r.cs_par_minute_meta)}/min` : ""}
          </div>
          {l.adversaire && <div className="discret">{l.adversaire.champion} : {l.adversaire.cs} sbires</div>}
        </div>
        <div><div className="discret">Or</div><strong style={{ fontSize: "1.6rem" }}>{l.or}</strong>
          <div className="discret">{(l.objets ?? []).join(", ")}</div></div>
      </div>
    </div>
  );
}
