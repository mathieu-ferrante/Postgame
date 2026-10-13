import { useNavigate } from "react-router-dom";
import type { PointSerie } from "../api";
import { nombre } from "../lib/format";

/** Courbe d'une mesure partie par partie (COM-03). Un clic sur un point ouvre la partie. */
export default function Graphique({ points, unite }: { points: PointSerie[]; unite: string }) {
  const naviguer = useNavigate();
  const valides = points.filter((p) => p.valeur !== null) as (PointSerie & { valeur: number })[];
  if (valides.length === 0) return <p className="discret">Aucune valeur sur la période.</p>;
  const L = 640, H = 240, marge = { g: 48, d: 12, h: 12, b: 28 };
  const vals = valides.map((p) => p.valeur);
  let min = Math.min(...vals), max = Math.max(...vals);
  if (min === max) { min -= 1; max += 1; }
  const x = (i: number) =>
    marge.g + (valides.length === 1 ? 0.5 : i / (valides.length - 1)) * (L - marge.g - marge.d);
  const y = (v: number) => marge.h + (1 - (v - min) / (max - min)) * (H - marge.h - marge.b);
  // Moyenne glissante sur 5 parties : la tendance compte plus qu'un match isolé.
  const moyenne = valides.map((_, i) => {
    const lot = vals.slice(Math.max(0, i - 4), i + 1);
    return lot.reduce((a, b) => a + b, 0) / lot.length;
  });
  const chemin = (serie: number[]) => serie.map((v, i) => `${i ? "L" : "M"}${x(i)},${y(v)}`).join(" ");
  const graduations = [min, (min + max) / 2, max];
  return (
    <svg className="graphique" viewBox={`0 0 ${L} ${H}`} role="img" aria-label="Évolution de la mesure">
      {graduations.map((g) => (
        <g key={g}>
          <line className="axe" x1={marge.g} x2={L - marge.d} y1={y(g)} y2={y(g)} />
          <text x={marge.g - 6} y={y(g) + 4} textAnchor="end">{nombre(g)}</text>
        </g>
      ))}
      <path d={chemin(vals)} className="courbe" opacity={0.35} />
      <path d={chemin(moyenne)} className="courbe" />
      {valides.map((p, i) => (
        <circle key={p.partie_id + "-" + i} className="point" cx={x(i)} cy={y(p.valeur)} r={4}
          style={{ cursor: "pointer" }} onClick={() => naviguer(`/partie/${p.partie_id}`)}>
          <title>{`${new Date(p.date_partie).toLocaleDateString("fr-FR")} · ${p.carte} : ${nombre(p.valeur, unite)}`}</title>
        </circle>
      ))}
      <text x={marge.g} y={H - 8}>{new Date(valides[0].date_partie).toLocaleDateString("fr-FR")}</text>
      <text x={L - marge.d} y={H - 8} textAnchor="end">
        {new Date(valides[valides.length - 1].date_partie).toLocaleDateString("fr-FR")}
      </text>
    </svg>
  );
}
