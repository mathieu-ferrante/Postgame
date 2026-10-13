// League of Legends (LOL-06) : carte minute par minute, positions des 10 joueurs et combats.
// Les positions ne sont connues qu'à chaque minute (limite de la chronologie Riot).

import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Etat, useDonnee } from "../composants/Chargement";

interface ReplayLoL {
  patch: string;
  joueurs: { id: number; champion: string; equipe: number; moi: boolean; role: string }[];
  minutes: { t: number; positions: Record<string, [number, number]> }[];
  evenements: { type: string; t: number; x: number | null; y: number | null; tueur: number | null;
    victime: number | null; monstre: string | null; equipe: number | null }[];
}

const TAILLE_CARTE = 14870;  // unités de la Faille de l'invocateur

async function charger(id: number): Promise<ReplayLoL> {
  const r = await fetch(`/api/lol/replay/${id}`);
  if (!r.ok) throw new Error((await r.json()).detail ?? r.status);
  return r.json();
}

export default function CarteLoL() {
  const id = Number(useParams().id);
  const { donnee: d, erreur, chargement } = useDonnee(() => charger(id), [id]);
  const [minute, setMinute] = useState(10);
  if (!d) return <Etat erreur={erreur} chargement={chargement} />;

  const m = Math.min(minute, d.minutes.length - 1);
  const frame = d.minutes[m];
  const C = 600;
  const vers = (x: number, y: number): [number, number] => [(x / TAILLE_CARTE) * C, C - (y / TAILLE_CARTE) * C];
  // Évènements de la minute écoulée (entre m − 1 et m).
  const recents = d.evenements.filter((e) => e.t > (m - 1) * 60000 && e.t <= m * 60000);
  const noms = new Map(d.joueurs.map((j) => [j.id, j]));

  return (
    <>
      <div className="ligne">
        <Link to={`/partie/${id}`}>← Débrief</Link>
        <h1 style={{ margin: 0 }}>Carte — minute {m}</h1>
        <span className="discret">patch {d.patch}</span>
      </div>
      <div className="replay">
        <div>
          <svg viewBox={`0 0 ${C} ${C}`} style={{ width: "100%", background: "#0e1013", borderRadius: 10 }}>
            <image href={`https://ddragon.leagueoflegends.com/cdn/${d.patch}.1/img/map/map11.png`}
              width={C} height={C} opacity={0.55} />
            {recents.filter((e) => e.x !== null).map((e, i) => {
              const [x, y] = vers(e.x!, e.y!);
              const couleur = e.type === "CHAMPION_KILL" ? "#e5534b" : "#f0b429";
              return <circle key={i} cx={x} cy={y} r={10} fill="none" stroke={couleur} strokeWidth={2} />;
            })}
            {d.joueurs.map((j) => {
              const p = frame?.positions[String(j.id)];
              if (!p) return null;
              const [x, y] = vers(p[0], p[1]);
              return (
                <g key={j.id}>
                  <circle cx={x} cy={y} r={j.moi ? 9 : 7} fill={j.equipe === 100 ? "#4a90e2" : "#e5534b"}
                    stroke={j.moi ? "#fff" : "none"} strokeWidth={2} />
                  <text x={x + 10} y={y - 8} fill="#e8eaed" fontSize="12">{j.champion}</text>
                </g>
              );
            })}
          </svg>
          <div className="commandes">
            <input type="range" min={0} max={d.minutes.length - 1} value={m} onChange={(e) => setMinute(Number(e.target.value))} />
            <span className="discret">{m}:00</span>
          </div>
        </div>
        <div>
          <h3>Pendant la minute</h3>
          <ul className="fil">
            {recents.length === 0 && <li className="discret">Rien de notable.</li>}
            {recents.map((e, i) => (
              <li key={i}>
                {e.type === "CHAMPION_KILL" && <>{noms.get(e.tueur ?? -1)?.champion ?? "?"} tue {noms.get(e.victime ?? -1)?.champion ?? "?"}</>}
                {e.type === "ELITE_MONSTER_KILL" && <>{e.monstre?.toLowerCase()} pris par l'équipe {e.equipe === 100 ? "bleue" : "rouge"}</>}
                {e.type === "BUILDING_KILL" && <>structure de l'équipe {e.equipe === 100 ? "bleue" : "rouge"} détruite</>}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </>
  );
}
