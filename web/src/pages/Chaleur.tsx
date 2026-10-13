// Cartes de chaleur des morts et kills de Mathieu (CS-POS-01), toutes parties confondues.

import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { PointChaleur } from "../api";
import { api } from "../api";
import { Etat, useDonnee } from "../composants/Chargement";

interface Cartes {
  date: string;
  source: string;
  cartes: { code: string; nom: string; pool: boolean }[];
}

async function chargerCartes(): Promise<Cartes> {
  const r = await fetch("/api/cs2/cartes");
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

function cadrer(points: PointChaleur[], cote: number) {
  const xs = points.map((p) => p.x), ys = points.map((p) => p.y);
  const xmin = Math.min(...xs), xmax = Math.max(...xs), ymin = Math.min(...ys), ymax = Math.max(...ys);
  const etendue = Math.max(xmax - xmin, ymax - ymin, 500) * 1.15;
  const cx = (xmin + xmax) / 2, cy = (ymin + ymax) / 2;
  const k = cote / etendue;
  return (x: number, y: number): [number, number] => [(x - cx) * k + cote / 2, (cy - y) * k + cote / 2];
}

export default function Chaleur() {
  const cartes = useDonnee(chargerCartes, []);
  const [choix, setCarte] = useState<string | null>(null);
  const carte = choix ?? cartes.donnee?.cartes[0]?.code ?? "de_mirage";
  const [type, setType] = useState("mort");
  const [camp, setCamp] = useState("");
  const [periode, setPeriode] = useState("tout");
  const donnees = useDonnee(() => api.chaleur(carte, type, camp, periode), [carte, type, camp, periode]);
  const canevas = useRef<HTMLCanvasElement>(null);
  const naviguer = useNavigate();
  const points = useMemo(() => donnees.donnee?.points ?? [], [donnees.donnee]);

  useEffect(() => {
    const c = canevas.current;
    if (!c) return;
    const cote = c.clientWidth * window.devicePixelRatio;
    c.width = cote; c.height = cote;
    const ctx = c.getContext("2d")!;
    ctx.clearRect(0, 0, cote, cote);
    if (!points.length) return;
    const ecran = cadrer(points, cote);
    // Densité : chaque point est une tache translucide, les zones chaudes se renforcent.
    for (const p of points) {
      const [x, y] = ecran(p.x, p.y);
      const g = ctx.createRadialGradient(x, y, 0, x, y, cote / 25);
      const couleur = type === "mort" ? "229, 83, 75" : "63, 178, 127";
      g.addColorStop(0, `rgba(${couleur}, 0.45)`);
      g.addColorStop(1, `rgba(${couleur}, 0)`);
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(x, y, cote / 25, 0, 2 * Math.PI); ctx.fill();
    }
    for (const p of points) {
      const [x, y] = ecran(p.x, p.y);
      ctx.fillStyle = p.camp === "T" ? "#e0a030" : "#4a90e2";
      ctx.beginPath(); ctx.arc(x, y, 3, 0, 2 * Math.PI); ctx.fill();
    }
  }, [points, type]);

  const clic = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const c = canevas.current;
    if (!c || !points.length) return;
    const rect = c.getBoundingClientRect();
    const k = c.width / rect.width;
    const ecran = cadrer(points, c.width);
    const mx = (e.clientX - rect.left) * k, my = (e.clientY - rect.top) * k;
    let meilleur: PointChaleur | null = null, distance = 15 * k;
    for (const p of points) {
      const [x, y] = ecran(p.x, p.y);
      const d = Math.hypot(x - mx, y - my);
      if (d < distance) { meilleur = p; distance = d; }
    }
    if (meilleur) naviguer(`/replay/${meilleur.partie_id}?tick=${meilleur.tick}`);
  };

  return (
    <>
      <h1>Cartes de chaleur</h1>
      <div className="carte">
        <div className="ligne">
          <select value={carte} onChange={(e) => setCarte(e.target.value)}>
            <optgroup label="Pool actif (Premier, compétitif)">
              {cartes.donnee?.cartes.filter((c) => c.pool).map((c) => <option key={c.code} value={c.code}>{c.nom}</option>)}
            </optgroup>
            <optgroup label="Autres cartes jouées">
              {cartes.donnee?.cartes.filter((c) => !c.pool).map((c) => <option key={c.code} value={c.code}>{c.nom}</option>)}
            </optgroup>
          </select>
          <button className={type === "mort" ? "actif" : ""} onClick={() => setType("mort")}>Morts</button>
          <button className={type === "kill" ? "actif" : ""} onClick={() => setType("kill")}>Kills</button>
          <select value={camp} onChange={(e) => setCamp(e.target.value)}>
            <option value="">T et CT</option><option value="T">T</option><option value="CT">CT</option>
          </select>
          <select value={periode} onChange={(e) => setPeriode(e.target.value)}>
            <option value="7j">7 jours</option><option value="30j">30 jours</option><option value="tout">Tout</option>
          </select>
        </div>
        <Etat erreur={donnees.erreur} chargement={donnees.chargement} />
        <p className="discret">{points.length} point(s). Cliquer un point ouvre le replay à ce moment.</p>
        {cartes.donnee && <p className="discret">Pool actif d'après : {cartes.donnee.source}.</p>}
        <canvas ref={canevas} onClick={clic} style={{ width: "100%", maxWidth: 640, aspectRatio: "1", background: "#0e1013", borderRadius: 10 }} />
      </div>
    </>
  );
}
