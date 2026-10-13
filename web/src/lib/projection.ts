// Passage des coordonnées du jeu à l'écran pour le radar 2D.
//
// Avec le radar officiel : pixel = ((x − pos_x) / scale, (pos_y − y) / scale) sur une image
// de 1024 px, puis mise à l'échelle du canevas. Sans radar : on cadre la zone parcourue
// (silhouette) en gardant les proportions, y vers le haut.

import type { Fond, ParametresRadar, PisteJoueur, RoundReplay } from "../api";

export interface Projection {
  versEcran(x: number, y: number): [number, number];
  /** Taille à l'écran d'une distance en unités du jeu. */
  echelle(unites: number): number;
}

export function projectionRadar(p: ParametresRadar, taille: number, cote: number): Projection {
  const k = cote / taille;
  return {
    versEcran: (x, y) => [((x - p.pos_x) / p.scale) * k, ((p.pos_y - y) / p.scale) * k],
    echelle: (u) => (u / p.scale) * k,
  };
}

export function projectionFond(f: Fond, cote: number, marge = 0.04): Projection {
  const largeur = f.largeur * f.cellule;
  const hauteur = f.hauteur * f.cellule;
  const etendue = Math.max(largeur, hauteur) * (1 + 2 * marge);
  const k = cote / etendue;
  const x0 = f.xmin - (etendue - largeur) / 2;
  const yHaut = f.ymin + hauteur + (etendue - hauteur) / 2;
  return {
    versEcran: (x, y) => [(x - x0) * k, (yHaut - y) * k],
    echelle: (u) => u * k,
  };
}

/** Direction de regard à l'écran : le yaw tourne vers la gauche, l'axe y de l'écran descend. */
export function direction(yawDegres: number): [number, number] {
  const r = (yawDegres * Math.PI) / 180;
  return [Math.cos(r), -Math.sin(r)];
}

export interface EtatJoueur {
  x: number;
  y: number;
  yaw: number;
  vivant: boolean;
  arme: string;
  equipe: number;
}

/** Position interpolée d'un joueur au tick (non entier) donné. */
export function etatAu(round: RoundReplay, piste: PisteJoueur, tick: number): EtatJoueur {
  const pas = round.ticks.length > 1 ? round.ticks[1] - round.ticks[0] : 1;
  const f = (tick - round.depart) / pas;
  const i = Math.max(0, Math.min(round.ticks.length - 1, Math.floor(f)));
  const j = Math.min(round.ticks.length - 1, i + 1);
  const t = Math.max(0, Math.min(1, f - i));
  let dyaw = piste.yaw[j] - piste.yaw[i];
  if (dyaw > 180) dyaw -= 360;
  if (dyaw < -180) dyaw += 360;
  const continu = piste.vivant[i] === piste.vivant[j];
  return {
    x: continu ? piste.x[i] + (piste.x[j] - piste.x[i]) * t : piste.x[i],
    y: continu ? piste.y[i] + (piste.y[j] - piste.y[i]) * t : piste.y[i],
    yaw: piste.yaw[i] + dyaw * t,
    vivant: piste.vivant[i] === 1,
    arme: piste.arme[i],
    equipe: piste.equipe,
  };
}

/** Dernière position vivante d'un joueur mort (pour dessiner sa croix). */
export function dernierePositionVivante(round: RoundReplay, piste: PisteJoueur, tick: number) {
  const pas = round.ticks.length > 1 ? round.ticks[1] - round.ticks[0] : 1;
  let i = Math.min(round.ticks.length - 1, Math.floor((tick - round.depart) / pas));
  while (i > 0 && piste.vivant[i] === 0) i--;
  return piste.vivant[i] === 1 ? { x: piste.x[i], y: piste.y[i] } : null;
}
