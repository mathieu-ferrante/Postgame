import { describe, expect, it } from "vitest";
import type { RoundReplay } from "../api";
import { nombre, nomCourt } from "./format";
import { analyser, enLigne } from "./markdown";
import { dernierePositionVivante, direction, etatAu, projectionFond, projectionRadar } from "./projection";

describe("markdown du débrief", () => {
  it("découpe titres, listes et citations", () => {
    const blocs = analyser("## Priorités\n1. Viseur **trop bas** [C1]\n2. Flashs _inutiles_ [C2]\n\nFin.");
    expect(blocs.map((b) => b.type)).toEqual(["titre", "liste", "paragraphe"]);
    const liste = blocs[1];
    expect(liste.type === "liste" && liste.ordonnee).toBe(true);
    expect(enLigne("a **b** [C3]")).toEqual([
      { type: "texte", texte: "a " },
      { type: "gras", texte: "b" },
      { type: "texte", texte: " " },
      { type: "source", id: "C3" },
    ]);
  });

  it("n'interprète jamais de HTML", () => {
    const blocs = analyser("<img src=x onerror=alert(1)>");
    expect(blocs).toEqual([{ type: "paragraphe", morceaux: [{ type: "texte", texte: "<img src=x onerror=alert(1)>" }] }]);
  });
});

describe("projection du radar", () => {
  it("applique la formule des radars officiels", () => {
    const p = projectionRadar({ pos_x: -3230, pos_y: 1713, scale: 5 }, 1024, 512);
    // (0 + 3230) / 5 = 646 px sur 1024 → 323 px sur 512
    expect(p.versEcran(0, 0)).toEqual([323, 171.3]);
    expect(p.echelle(100)).toBe(10);
  });

  it("cadre la silhouette en gardant y vers le haut", () => {
    const p = projectionFond({ xmin: 0, ymin: 0, cellule: 100, largeur: 10, hauteur: 5, cellules: [] }, 1000, 0);
    expect(p.versEcran(0, 500)[1]).toBeCloseTo(250);
    expect(p.versEcran(0, 0)[1]).toBeCloseTo(750);
  });

  it("oriente le regard (yaw 90 = vers le haut de l'écran)", () => {
    const [dx, dy] = direction(90);
    expect(dx).toBeCloseTo(0);
    expect(dy).toBeCloseTo(-1);
  });
});

describe("interpolation des positions", () => {
  const round: RoundReplay = {
    debut: 0, fin: 8, depart: 0, ticks: [0, 4, 8],
    joueurs: {}, tirs: [], morts: [], grenades: [], bombe: [],
  };
  const piste = { equipe: 2, x: [0, 40, 40], y: [0, 0, 0], yaw: [170, -170, -170], vivant: [1, 1, 0], arme: ["ak47", "ak47", ""] };

  it("interpole position et angle (en passant par 180°)", () => {
    const e = etatAu(round, piste, 2);
    expect(e.x).toBe(20);
    expect(e.yaw).toBe(180);
    expect(e.vivant).toBe(true);
  });

  it("retrouve la dernière position vivante", () => {
    expect(dernierePositionVivante(round, piste, 8)).toEqual({ x: 40, y: 0 });
  });
});

describe("format", () => {
  it("formate en français", () => {
    expect(nombre(61.25, "%")).toBe("61,3 %");
    expect(nombre(null)).toBe("—");
    expect(nomCourt("cs2.viseur.ecart_median")).toBe("viseur · ecart median");
  });
});
