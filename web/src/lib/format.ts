// Mise en forme des valeurs affichées (français).

const NOMBRE = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });

export function nombre(v: number | null | undefined, unite = ""): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const texte = NOMBRE.format(v);
  return unite ? `${texte} ${unite}` : texte;
}

export function dateCourte(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("fr-FR", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function duree(secondes: number | null): string {
  if (!secondes) return "—";
  const m = Math.floor(secondes / 60);
  return `${m} min`;
}

export const RESULTATS: Record<string, string> = {
  victoire: "Victoire",
  defaite: "Défaite",
  nul: "Nul",
  sans_objet: "—",
  inconnu: "?",
};

export const JEUX: Record<string, string> = {
  cs2: "CS2",
  gd: "Geometry Dash",
  lol: "LoL",
  tft: "TFT",
};

/** Libellé lisible d'un nom de mesure : « cs2.viseur.ecart_median » → « viseur · ecart median ». */
export function nomCourt(nom: string): string {
  return nom.split(".").slice(1).join(" · ").replaceAll("_", " ");
}

/** Score affiché : « 13 – 9 » (CS2), « 87 % » (meilleur % en Geometry Dash), sinon le résultat. */
export function score(p: { score_joueur: number | null; score_adverse: number | null; resultat: string }): string {
  if (p.score_joueur === null) return RESULTATS[p.resultat] ?? p.resultat;
  if (p.score_adverse === null) return `${p.score_joueur} %`;
  return `${p.score_joueur} – ${p.score_adverse}`;
}
