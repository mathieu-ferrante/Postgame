import { useEffect, useState } from "react";

/** Charge une donnée asynchrone et suit son état. `cle` relance le chargement. */
export function useDonnee<T>(charger: () => Promise<T>, cle: unknown[]): {
  donnee: T | null;
  erreur: string | null;
  chargement: boolean;
  recharger: () => void;
} {
  const [donnee, setDonnee] = useState<T | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [chargement, setChargement] = useState(true);
  const [tour, setTour] = useState(0);
  useEffect(() => {
    let actif = true;
    setChargement(true);
    setErreur(null);
    charger()
      .then((d) => actif && setDonnee(d))
      .catch((e: Error) => actif && setErreur(e.message))
      .finally(() => actif && setChargement(false));
    return () => {
      actif = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...cle, tour]);
  return { donnee, erreur, chargement, recharger: () => setTour((t) => t + 1) };
}

export function Etat({ erreur, chargement }: { erreur: string | null; chargement: boolean }) {
  if (erreur) return <p className="erreur">Erreur : {erreur}</p>;
  if (chargement) return <p className="discret">Chargement…</p>;
  return null;
}
