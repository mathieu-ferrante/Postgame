// Accès à l'API locale de Postgame (docs/API.md). Mêmes noms de champs que le service.

export interface ResumePartie {
  id: number;
  jeu: string;
  date_partie: string;
  mode: string;
  carte: string;
  resultat: string;
  score_joueur: number | null;
  score_adverse: number | null;
  duree_s: number | null;
}

export interface MesureEnBase {
  nom: string;
  version: number;
  valeur: number | null;
  unite: string;
  contexte: Record<string, unknown>;
}

export interface PreuveEnBase {
  mesure: string;
  tick: number | null;
  round: number | null;
  texte: string;
  donnees: Record<string, unknown>;
  lien?: string;
}

export interface Partie extends ResumePartie {
  source: string;
  details: Record<string, unknown>;
  mesures: MesureEnBase[];
  preuves: PreuveEnBase[];
}

export interface Constat {
  id: string;
  mesure: string;
  libelle: string;
  valeur: number;
  unite: string;
  sens: string;
  contexte: Record<string, unknown>;
  n: number | null;
  reference: number | null;
  nb_reference: number;
  cible: number | null;
  impact: number;
  statut: "a_corriger" | "point_fort" | "neutre";
  experimental: boolean;
  preuves: PreuveEnBase[];
}

export interface Debrief {
  id: number;
  partie_id: number;
  cree_le: string;
  fournisseur: string;
  modele: string;
  statut: "redige" | "structure" | "rejete" | "erreur";
  message: string;
  texte: string;
  jetons_entree: number;
  jetons_sortie: number;
  cout: number;
  contenu: {
    priorites: Constat[];
    points_forts: Constat[];
    details: Constat[];
    mesures_masquees: number;
  };
}

export interface Definition {
  nom: string;
  version: number;
  unite: string;
  description: string;
  sens: string;
  fiable: boolean;
}

export interface PointSerie {
  partie_id: number;
  date_partie: string;
  carte: string;
  mode: string;
  valeur: number | null;
  contexte: Record<string, unknown>;
}

export interface ParametresRadar {
  pos_x: number;
  pos_y: number;
  scale: number;
}

export interface Fond {
  xmin: number;
  ymin: number;
  cellule: number;
  largeur: number;
  hauteur: number;
  cellules: [number, number][];
}

export interface MetaReplay {
  carte: string;
  tickrate: number;
  joueurs: { id: number; steamid: string; nom: string; moi: boolean }[];
  rounds: { numero: number; debut: number; fin: number; gagnant: number | null }[];
  fond: Fond | null;
  radar: {
    parametres: ParametresRadar | null;
    image: string | null;
    taille_image: number;
  };
}

export interface PisteJoueur {
  equipe: number;
  x: number[];
  y: number[];
  yaw: number[];
  vivant: number[];
  arme: string[];
}

export interface RoundReplay {
  debut: number;
  fin: number;
  depart: number;
  ticks: number[];
  joueurs: Record<string, PisteJoueur>;
  tirs: [number, number][];
  morts: [number, number, number, string, boolean][];
  grenades: [string, number, number, number, number, number][];
  bombe: [number, string, number, number][];
}

export interface PointChaleur {
  x: number;
  y: number;
  camp: string | null;
  arme: string | null;
  partie_id: number;
  tick: number;
  round: number | null;
}

async function lire<T>(chemin: string, options?: RequestInit): Promise<T> {
  const r = await fetch(chemin, options);
  if (!r.ok) {
    let detail = `${r.status}`;
    try {
      detail = (await r.json()).detail ?? detail;
    } catch {
      // réponse sans JSON
    }
    throw new Error(String(detail));
  }
  return r.json() as Promise<T>;
}

export const api = {
  parties: (jeu?: string, limite = 50) =>
    lire<{ total: number; parties: ResumePartie[] }>(
      `/api/parties?limite=${limite}${jeu ? `&jeu=${jeu}` : ""}`,
    ),
  partie: (id: number) => lire<Partie>(`/api/parties/${id}`),
  debrief: (id: number, regenerer = false) =>
    lire<Debrief>(`/api/parties/${id}/debrief${regenerer ? "?regenerer=true" : ""}`),
  definitions: () => lire<Definition[]>("/api/mesures/definitions"),
  mesuresPresentes: () => lire<string[]>("/api/mesures"),
  progression: (nom: string, periode: string) =>
    lire<{ points: PointSerie[] }>(`/api/progression/${encodeURIComponent(nom)}?periode=${periode}`),
  etatImport: () =>
    lire<{ derniere_passe: string | null; en_attente: string[]; derniers_fichiers: { chemin: string; statut: string; message: string; partie_id: number | null }[] }>(
      "/api/import/etat",
    ),
  importer: (fichier: File) => {
    const corps = new FormData();
    corps.append("fichier", fichier);
    return lire<{ statut: string; message: string; partie_id: number | null }>("/api/import", {
      method: "POST",
      body: corps,
    });
  },
  replay: (id: number) => lire<MetaReplay>(`/api/cs2/replay/${id}`),
  round: (id: number, numero: number) =>
    lire<RoundReplay>(`/api/cs2/replay/${id}/round/${numero}`),
  chaleur: (carte: string, type: string, camp: string, periode: string) =>
    lire<{ points: PointChaleur[] }>(
      `/api/cs2/chaleur?carte=${carte}&type=${type}&periode=${periode}${camp ? `&camp=${camp}` : ""}`,
    ),
  sante: () => lire<{ statut: string; version: string; parties: number }>("/api/sante"),
};
