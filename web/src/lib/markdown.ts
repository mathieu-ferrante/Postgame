// Mini-analyseur du Markdown produit par le débrief : titres « ## », listes numérotées ou à
// puces, paragraphes, **gras**, _italique_ et citations de sources [C1]. Rien d'autre : le
// texte vient du modèle et n'est jamais injecté comme HTML.

export type Morceau =
  | { type: "texte"; texte: string }
  | { type: "gras"; texte: string }
  | { type: "italique"; texte: string }
  | { type: "source"; id: string };

export type Bloc =
  | { type: "titre"; morceaux: Morceau[] }
  | { type: "liste"; ordonnee: boolean; elements: Morceau[][] }
  | { type: "paragraphe"; morceaux: Morceau[] };

const EN_LIGNE = /\*\*(.+?)\*\*|_(.+?)_|\[(C\d+)\]/g;

export function enLigne(texte: string): Morceau[] {
  const morceaux: Morceau[] = [];
  let dernier = 0;
  for (const m of texte.matchAll(EN_LIGNE)) {
    if (m.index > dernier) morceaux.push({ type: "texte", texte: texte.slice(dernier, m.index) });
    if (m[1] !== undefined) morceaux.push({ type: "gras", texte: m[1] });
    else if (m[2] !== undefined) morceaux.push({ type: "italique", texte: m[2] });
    else morceaux.push({ type: "source", id: m[3] });
    dernier = m.index + m[0].length;
  }
  if (dernier < texte.length) morceaux.push({ type: "texte", texte: texte.slice(dernier) });
  return morceaux;
}

export function analyser(texte: string): Bloc[] {
  const blocs: Bloc[] = [];
  let liste: { ordonnee: boolean; elements: Morceau[][] } | null = null;
  const fermer = () => {
    if (liste) blocs.push({ type: "liste", ...liste });
    liste = null;
  };
  for (const brute of texte.split(/\r?\n/)) {
    const ligne = brute.trim();
    if (!ligne) {
      fermer();
      continue;
    }
    const titre = /^#{1,4}\s+(.*)$/.exec(ligne);
    const ordonnee = /^\d+[.)]\s+(.*)$/.exec(ligne);
    const puce = /^[-*]\s+(.*)$/.exec(ligne);
    if (titre) {
      fermer();
      blocs.push({ type: "titre", morceaux: enLigne(titre[1]) });
    } else if (ordonnee || puce) {
      const estOrdonnee = Boolean(ordonnee);
      const contenu = (ordonnee ?? puce)![1];
      if (!liste || liste.ordonnee !== estOrdonnee) {
        fermer();
        liste = { ordonnee: estOrdonnee, elements: [] };
      }
      liste.elements.push(enLigne(contenu));
    } else {
      fermer();
      blocs.push({ type: "paragraphe", morceaux: enLigne(ligne) });
    }
  }
  fermer();
  return blocs;
}
