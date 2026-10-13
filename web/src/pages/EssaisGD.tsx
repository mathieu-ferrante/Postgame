// Geometry Dash (GD-07) : tous les essais d'une séance superposés sur le profil du niveau,
// avec les appuis, les morts et la régularité de chaque input attendu.

import { Link, useParams } from "react-router-dom";
import { Etat, useDonnee } from "../composants/Chargement";
import { nombre } from "../lib/format";

interface ReplayGD {
  niveau: string;
  longueur: number | null;
  essais: {
    numero: number; mode: string; x_debut: number; x_fin: number | null; pct_fin: number | null;
    mort: boolean; complete: boolean; appuis: number[];
  }[];
  inputs: { x: number; pct: number | null; ecart_type: number; decalage: number; n: number }[];
}

async function charger(id: number): Promise<ReplayGD> {
  const r = await fetch(`/api/gd/replay/${id}`);
  if (!r.ok) throw new Error((await r.json()).detail ?? r.status);
  return r.json();
}

function couleur(ecartType: number): string {
  if (ecartType <= 15) return "var(--bien)";
  if (ecartType <= 30) return "var(--accent)";
  return "var(--mal)";
}

export default function EssaisGD() {
  const id = Number(useParams().id);
  const { donnee: d, erreur, chargement } = useDonnee(() => charger(id), [id]);
  if (!d) return <Etat erreur={erreur} chargement={chargement} />;

  const fin = d.longueur ?? Math.max(1, ...d.essais.map((e) => e.x_fin ?? 0));
  const L = 900, hauteurLigne = 9, haut = 46, marge = 40;
  const H = haut + d.essais.length * hauteurLigne + 30;
  const x = (u: number) => marge + (Math.min(u, fin) / fin) * (L - marge - 10);
  // Histogramme des morts par tranche de 2 %.
  const tranches = new Array(50).fill(0);
  for (const e of d.essais) if (e.mort && e.pct_fin !== null) tranches[Math.min(49, Math.floor(e.pct_fin / 2))]++;
  const maxMorts = Math.max(1, ...tranches);
  const pires = [...d.inputs].sort((a, b) => b.ecart_type - a.ecart_type).slice(0, 5);

  return (
    <>
      <div className="ligne">
        <Link to={`/partie/${id}`}>← Débrief</Link>
        <h1 style={{ margin: 0 }}>{d.niveau} — {d.essais.length} essais</h1>
      </div>
      <div className="carte" style={{ overflowX: "auto" }}>
        <svg viewBox={`0 0 ${L} ${H}`} style={{ width: "100%", minWidth: 600 }} role="img"
          aria-label="Essais superposés sur le niveau">
          {[0, 25, 50, 75, 100].map((p) => (
            <g key={p}>
              <line x1={x((p / 100) * fin)} x2={x((p / 100) * fin)} y1={10} y2={H - 20} stroke="var(--bord)" />
              <text x={x((p / 100) * fin)} y={H - 6} textAnchor="middle" fill="var(--texte-2)" fontSize="11">{p} %</text>
            </g>
          ))}
          {/* Morts : histogramme en haut. */}
          {tranches.map((n, i) => n > 0 && (
            <rect key={i} x={x((i * 2 / 100) * fin)} width={Math.max(2, ((2 / 100) * (L - marge - 10)) - 1)}
              y={30 - (n / maxMorts) * 24} height={(n / maxMorts) * 24} fill="var(--mal)" opacity={0.7}>
              <title>{`${i * 2}-${i * 2 + 2} % : ${n} mort(s)`}</title>
            </rect>
          ))}
          {/* Inputs attendus : couleur selon la régularité. */}
          {d.inputs.map((inp) => (
            <line key={inp.x} x1={x(inp.x)} x2={x(inp.x)} y1={haut - 8} y2={H - 20}
              stroke={couleur(inp.ecart_type)} strokeOpacity={0.25} strokeWidth={2}>
              <title>{`${nombre(inp.pct)} % : écart-type ${nombre(inp.ecart_type)} ms, décalage ${nombre(inp.decalage)} ms`}</title>
            </line>
          ))}
          {/* Essais. */}
          {d.essais.map((e, i) => {
            const y = haut + i * hauteurLigne;
            const xf = e.x_fin ?? e.x_debut;
            return (
              <g key={i}>
                <line x1={x(e.x_debut)} x2={x(xf)} y1={y} y2={y}
                  stroke={e.mode === "practice" ? "var(--ct)" : "var(--texte-2)"} strokeWidth={2} />
                {e.appuis.map((a, j) => <circle key={j} cx={x(a)} cy={y} r={1.6} fill="var(--texte)" />)}
                {e.mort && <text x={x(xf)} y={y + 3} fill="var(--mal)" fontSize="9" textAnchor="middle">✕</text>}
                {e.complete && <circle cx={x(xf)} cy={y} r={3} fill="var(--bien)" />}
              </g>
            );
          })}
        </svg>
        <p className="discret">
          Gris : essai normal, bleu : entraînement ; points : appuis ; ✕ : mort. Lignes verticales : inputs
          attendus (vert ≤ 15 ms d'écart-type, orange ≤ 30 ms, rouge au-delà). En haut : morts par tranche de 2 %.
        </p>
      </div>
      {pires.length > 0 && (
        <div className="carte">
          <h3>Inputs les plus irréguliers</h3>
          <table>
            <tbody>
              {pires.map((p) => (
                <tr key={p.x}>
                  <td>{nombre(p.pct)} %</td>
                  <td className="nombre">écart-type {nombre(p.ecart_type, "ms")}</td>
                  <td className="nombre">{p.decalage < 0 ? "trop tôt" : "trop tard"} de {nombre(Math.abs(p.decalage), "ms")}</td>
                  <td className="nombre discret">{p.n} passages</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
