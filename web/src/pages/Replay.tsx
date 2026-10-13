// Replay 2D vue du dessus (CS-RPL-01), avec renvoi vers la vraie démo dans CS2 : joueurs, regard, tirs, grenades, bombe, timeline,
// vitesse réglable, saut au tick d'un constat (?tick=…).

import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import type { MetaReplay, MomentPro, RoundReplay } from "../api";
import { api } from "../api";
import { Etat, useDonnee } from "../composants/Chargement";
import { BoutonRevoir, MomentsPros } from "../composants/RevoirCS2";
import type { Projection } from "../lib/projection";
import {
  dernierePositionVivante,
  direction,
  etatAu,
  projectionFond,
  projectionRadar,
} from "../lib/projection";

const COULEURS: Record<number, string> = { 2: "#e0a030", 3: "#4a90e2" };
const VITESSES = [0.25, 0.5, 1, 2, 4];
const DUREE_TIR = 8; // ticks pendant lesquels un tir reste visible
const RAYON_SMOKE = 144;
const RAYON_FEU = 120;

function projection(meta: MetaReplay, cote: number): Projection | null {
  if (meta.radar.parametres) return projectionRadar(meta.radar.parametres, meta.radar.taille_image, cote);
  if (meta.fond) return projectionFond(meta.fond, cote);
  return null;
}

function dessiner(
  ctx: CanvasRenderingContext2D, cote: number, meta: MetaReplay, round: RoundReplay,
  tick: number, proj: Projection, image: HTMLImageElement | null,
) {
  ctx.clearRect(0, 0, cote, cote);
  // Fond : radar officiel, sinon silhouette des zones parcourues.
  if (image?.complete && image.naturalWidth) {
    ctx.globalAlpha = 0.85;
    ctx.drawImage(image, 0, 0, cote, cote);
    ctx.globalAlpha = 1;
  } else if (meta.fond) {
    ctx.fillStyle = "#2a2f38";
    const f = meta.fond;
    const taille = proj.echelle(f.cellule) + 0.5;
    for (const [i, j] of f.cellules) {
      const [x, y] = proj.versEcran(f.xmin + i * f.cellule, f.ymin + (j + 1) * f.cellule);
      ctx.fillRect(x, y, taille, taille);
    }
  }
  // Grenades actives.
  for (const [type, gx, gy, debut, fin] of round.grenades) {
    const [x, y] = proj.versEcran(gx, gy);
    if (type === "smoke" && tick >= debut && tick <= fin) {
      ctx.fillStyle = "rgba(200, 200, 210, 0.55)";
      ctx.beginPath(); ctx.arc(x, y, proj.echelle(RAYON_SMOKE), 0, 2 * Math.PI); ctx.fill();
    } else if (type === "molotov" && tick >= debut && tick <= fin) {
      ctx.fillStyle = "rgba(240, 110, 30, 0.45)";
      ctx.beginPath(); ctx.arc(x, y, proj.echelle(RAYON_FEU), 0, 2 * Math.PI); ctx.fill();
    } else if ((type === "flash" || type === "he") && tick >= debut && tick <= debut + 24) {
      ctx.strokeStyle = type === "flash" ? "#ffffff" : "#ff5040";
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(x, y, proj.echelle(type === "flash" ? 60 : 100) * (1 + (tick - debut) / 24), 0, 2 * Math.PI); ctx.stroke();
    }
  }
  // Bombe posée.
  const pose = round.bombe.find(([t, ev]) => ev === "pose" && t <= tick);
  if (pose) {
    const [x, y] = proj.versEcran(pose[2], pose[3]);
    ctx.fillStyle = "#ff3030";
    ctx.fillRect(x - 5, y - 5, 10, 10);
  }
  // Joueurs.
  const moi = new Set(meta.joueurs.filter((j) => j.moi).map((j) => String(j.id)));
  const noms = new Map(meta.joueurs.map((j) => [String(j.id), j.nom]));
  ctx.font = "11px system-ui";
  for (const [id, piste] of Object.entries(round.joueurs)) {
    const e = etatAu(round, piste, tick);
    const couleur = COULEURS[e.equipe] ?? "#999";
    if (!e.vivant) {
      const p = dernierePositionVivante(round, piste, tick);
      if (!p) continue;
      const [x, y] = proj.versEcran(p.x, p.y);
      ctx.strokeStyle = couleur; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(x - 5, y - 5); ctx.lineTo(x + 5, y + 5); ctx.moveTo(x + 5, y - 5); ctx.lineTo(x - 5, y + 5); ctx.stroke();
      continue;
    }
    const [x, y] = proj.versEcran(e.x, e.y);
    const [dx, dy] = direction(e.yaw);
    const tire = round.tirs.some(([t, qui]) => String(qui) === id && t <= tick && tick - t < DUREE_TIR);
    ctx.strokeStyle = tire ? "#fff7a0" : couleur;
    ctx.lineWidth = tire ? 2.5 : 1.5;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + dx * (tire ? 60 : 22), y + dy * (tire ? 60 : 22)); ctx.stroke();
    ctx.fillStyle = couleur;
    ctx.beginPath(); ctx.arc(x, y, 6, 0, 2 * Math.PI); ctx.fill();
    if (moi.has(id)) {
      ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(x, y, 9, 0, 2 * Math.PI); ctx.stroke();
    }
    ctx.fillStyle = "#e8eaed";
    ctx.fillText(noms.get(id) ?? id, x + 9, y - 8);
  }
}

export default function Replay() {
  const id = Number(useParams().id);
  const [params] = useSearchParams();
  const tickCible = params.get("tick") ? Number(params.get("tick")) : null;
  const meta = useDonnee(() => api.replay(id), [id]);
  const [numero, setNumero] = useState<number | null>(null);
  const round = useDonnee(
    () => (numero !== null ? api.round(id, numero) : Promise.resolve(null)),
    [id, numero],
  );
  const [tick, setTick] = useState(0);
  const [lecture, setLecture] = useState(false);
  const [vitesse, setVitesse] = useState(1);
  const canevas = useRef<HTMLCanvasElement>(null);
  const image = useRef<HTMLImageElement | null>(null);

  // Round de départ : celui qui contient le tick demandé, sinon le premier.
  useEffect(() => {
    const m = meta.donnee;
    if (!m || numero !== null) return;
    const r = tickCible !== null
      ? m.rounds.find((r) => tickCible >= r.debut - 320 && tickCible <= r.fin) ?? m.rounds[0]
      : m.rounds[0];
    if (r) setNumero(r.numero);
    if (m.radar.image) {
      const img = new Image();
      img.src = m.radar.image;
      image.current = img;
    }
  }, [meta.donnee, numero, tickCible]);

  // Position de départ dans le round.
  useEffect(() => {
    const r = round.donnee;
    if (!r) return;
    setTick(tickCible !== null && tickCible >= r.depart && tickCible <= r.fin ? tickCible : r.depart);
  }, [round.donnee, tickCible]);

  // Lecture.
  useEffect(() => {
    if (!lecture || !round.donnee || !meta.donnee) return;
    let precedent = performance.now();
    let id_anim = 0;
    const fin = round.donnee.fin;
    const tickrate = meta.donnee.tickrate;
    const avancer = (maintenant: number) => {
      const dt = (maintenant - precedent) / 1000;
      precedent = maintenant;
      setTick((t) => {
        const suivant = t + dt * tickrate * vitesse;
        if (suivant >= fin) { setLecture(false); return fin; }
        return suivant;
      });
      id_anim = requestAnimationFrame(avancer);
    };
    id_anim = requestAnimationFrame(avancer);
    return () => cancelAnimationFrame(id_anim);
  }, [lecture, vitesse, round.donnee, meta.donnee]);

  // Dessin.
  useEffect(() => {
    const c = canevas.current, m = meta.donnee, r = round.donnee;
    if (!c || !m || !r) return;
    const cote = c.clientWidth * window.devicePixelRatio;
    if (c.width !== cote) { c.width = cote; c.height = cote; }
    const proj = projection(m, cote);
    const ctx = c.getContext("2d");
    if (proj && ctx) dessiner(ctx, cote, m, r, tick, proj, image.current);
  }, [tick, meta.donnee, round.donnee]);

  // Vrais rounds pros où un joueur de mon camp se tenait là où je suis à cet instant.
  const [pros, setPros] = useState<MomentPro[] | null>(null);
  const [erreurPros, setErreurPros] = useState<string | null>(null);
  const chercherPros = async () => {
    const m = meta.donnee, rd = round.donnee;
    const moi = m?.joueurs.find((j) => j.moi);
    const piste = moi && rd ? rd.joueurs[String(moi.id)] : undefined;
    if (!m || !rd || !piste) return;
    const e = etatAu(rd, piste, tick);
    const p = e.vivant ? e : dernierePositionVivante(rd, piste, tick);
    if (!p) return;
    setErreurPros(null);
    try {
      setPros(await api.prosProches(m.carte, p.x, p.y, e.equipe === 2 ? "T" : e.equipe === 3 ? "CT" : null));
    } catch (err) {
      setErreurPros(String((err as Error).message));
    }
  };

  const noms = useMemo(() => new Map(meta.donnee?.joueurs.map((j) => [j.id, j]) ?? []), [meta.donnee]);
  const r = round.donnee;
  const tickrate = meta.donnee?.tickrate ?? 64;
  const morts = r ? r.morts.filter(([t]) => t <= tick).slice(-8).reverse() : [];

  return (
    <>
      <div className="ligne">
        <Link to={`/partie/${id}`}>← Débrief</Link>
        <h1 style={{ margin: 0 }}>Replay {meta.donnee?.carte}</h1>
        <BoutonRevoir demande={{ partie_id: id, tick: Math.round(tick) }} libelle="Revoir ce moment dans CS2" />
      </div>
      <Etat erreur={meta.erreur} chargement={meta.chargement} />
      {meta.donnee && !meta.donnee.radar.image && (
        <p className="discret">Radar officiel absent : la carte est dessinée d'après les zones parcourues.</p>
      )}
      {meta.donnee && (
        <div className="replay">
          <div>
            <canvas ref={canevas} />
            {r && (
              <>
                <div className="commandes">
                  <button onClick={() => setLecture((l) => !l)}>{lecture ? "Pause" : "Lecture"}</button>
                  <input type="range" min={r.depart} max={r.fin} step={1} value={tick}
                    onChange={(e) => { setLecture(false); setTick(Number(e.target.value)); }} />
                  <span className="discret">
                    {Math.max(0, (tick - r.debut) / tickrate).toFixed(1)} s · tick {Math.round(tick)}
                  </span>
                </div>
                <div className="commandes">
                  {VITESSES.map((v) => (
                    <button key={v} className={vitesse === v ? "actif" : ""} onClick={() => setVitesse(v)}>×{v}</button>
                  ))}
                  <button onClick={() => setTick((t) => Math.max(r.depart, t - 5 * tickrate))}>−5 s</button>
                  <button onClick={() => setTick((t) => Math.min(r.fin, t + 5 * tickrate))}>+5 s</button>
                </div>
              </>
            )}
          </div>
          <div>
            <select value={numero ?? ""} onChange={(e) => { setLecture(false); setNumero(Number(e.target.value)); }}>
              {meta.donnee.rounds.map((rd) => (
                <option key={rd.numero} value={rd.numero}>
                  Round {rd.numero}{rd.gagnant ? ` (${rd.gagnant === 2 ? "T" : "CT"})` : ""}
                </option>
              ))}
            </select>
            <Etat erreur={round.erreur} chargement={round.chargement} />
            <h3 style={{ marginTop: "1rem" }}>Les pros au même endroit</h3>
            <p className="discret">Vrais rounds pros (démos lues) où un joueur de ton camp était là où tu es à cet instant.</p>
            <button onClick={chercherPros}>Chercher à cet instant</button>
            {erreurPros && <p className="erreur">{erreurPros}</p>}
            {pros && <MomentsPros moments={pros} vide="Aucun pro à cet endroit dans les démos lues (ajoute des démos pros de cette carte)." />}
            <h3 style={{ marginTop: "1rem" }}>Éliminations</h3>
            <ul className="fil">
              {morts.map(([t, tueur, victime, arme, hs], i) => {
                const a = noms.get(tueur), v = noms.get(victime);
                const ea = r?.joueurs[String(tueur)]?.equipe, ev = r?.joueurs[String(victime)]?.equipe;
                return (
                  <li key={i} style={{ cursor: "pointer" }} onClick={() => setTick(t)}>
                    <span className={ea === 2 ? "t" : "ct"}>{a?.nom ?? "?"}</span> {arme}{hs ? " (tête)" : ""} →{" "}
                    <span className={ev === 2 ? "t" : "ct"}>{v?.nom ?? "?"}</span>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      )}
    </>
  );
}
