// Apprendre les stuffs de chaque carte (STUFF-01) : catalogue appris sur démos pros,
// commandes d'entraînement hors ligne, maîtrise en match, notes et révisions espacées.

import { useMemo, useState } from "react";
import { Etat, useDonnee } from "../composants/Chargement";
import { nombre } from "../lib/format";
import { projectionRadar } from "../lib/projection";

interface Stuff {
  cle: string; type: string; nom: string; technique: string; commandes: string | null;
  x: number; y: number; lx: number | null; ly: number | null; nb: number; nb_demos: number;
  maitrise: { tentatives: number; reussites: number; dernier_ecart: number | null; derniere_reussite: string | null };
  revision: { boite: number; prochaine: string } | null;
  notes: { id: number; texte: string }[];
}
interface VueStuffs {
  carte: string; stuffs: Stuff[]; notes_carte: { id: number; texte: string }[];
  config_entrainement: string;
  radar: { parametres: { pos_x: number; pos_y: number; scale: number } | null; image: string | null; taille_image: number };
}
interface Cartes { cartes: { code: string; nom: string; pool: boolean }[] }

const COULEURS: Record<string, string> = { smoke: "#c8c8d2", flash: "#ffffff", molotov: "#f06e1e" };

async function json<T>(url: string, options?: RequestInit): Promise<T> {
  const r = await fetch(url, options);
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

function copier(texte: string) {
  navigator.clipboard?.writeText(texte).catch(() => undefined);
}

export default function Stuffs() {
  const cartes = useDonnee(() => json<Cartes>("/api/cs2/cartes"), []);
  const [choix, setChoix] = useState<string | null>(null);
  const carte = choix ?? cartes.donnee?.cartes[0]?.code ?? "de_mirage";
  const vue = useDonnee(() => json<VueStuffs>(`/api/cs2/stuffs?carte=${carte}`), [carte]);
  const [type, setType] = useState("smoke");
  const [selection, setSelection] = useState<string | null>(null);
  const [revision, setRevision] = useState<{ liste: Stuff[]; i: number; montre: boolean } | null>(null);
  const [note, setNote] = useState("");

  const liste = (vue.donnee?.stuffs ?? []).filter((s) => s.type === type);
  const choisi = liste.find((s) => s.cle === selection) ?? null;

  // Projection : radar officiel s'il est là, sinon cadrage sur tous les points.
  const C = 600;
  const vers = useMemo(() => {
    const r = vue.donnee?.radar;
    if (r?.parametres && r.image) return projectionRadar(r.parametres, r.taille_image, C).versEcran;
    const pts = (vue.donnee?.stuffs ?? []).flatMap((s) => [[s.x, s.y], ...(s.lx !== null ? [[s.lx, s.ly!]] : [])]);
    if (!pts.length) return (x: number, y: number): [number, number] => [x, y];
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const etendue = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), 500) * 1.15;
    const cx = (Math.max(...xs) + Math.min(...xs)) / 2, cy = (Math.max(...ys) + Math.min(...ys)) / 2;
    return (x: number, y: number): [number, number] => [(x - cx) / etendue * C + C / 2, (cy - y) / etendue * C + C / 2];
  }, [vue.donnee]);

  const recharger = () => vue.recharger();
  const ajouterNote = async (stuff: string | null) => {
    if (!note.trim()) return;
    await json("/api/notes", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ carte, texte: note, stuff }) });
    setNote("");
    recharger();
  };
  const supprimerNote = async (id: number) => {
    await json(`/api/notes/${id}`, { method: "DELETE" });
    recharger();
  };
  const commencerRevision = async () => {
    const l = await json<Stuff[]>(`/api/cs2/stuffs/a_reviser?carte=${carte}&nombre=10`);
    setRevision({ liste: l, i: 0, montre: false });
  };
  const repondre = async (reussi: boolean) => {
    if (!revision) return;
    const s = revision.liste[revision.i];
    await json(`/api/cs2/stuffs/${s.cle}/revision`, { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reussi }) });
    if (revision.i + 1 >= revision.liste.length) { setRevision(null); recharger(); }
    else setRevision({ ...revision, i: revision.i + 1, montre: false });
  };

  const enRevision = revision ? revision.liste[revision.i] : null;

  return (
    <>
      <h1>Stuffs</h1>
      <div className="ligne">
        <select value={carte} onChange={(e) => { setChoix(e.target.value); setSelection(null); }}>
          {cartes.donnee?.cartes.map((c) => <option key={c.code} value={c.code}>{c.nom}{c.pool ? "" : " (hors pool)"}</option>)}
        </select>
        {["smoke", "flash", "molotov"].map((t) => (
          <button key={t} className={type === t ? "actif" : ""} onClick={() => setType(t)}>{t}</button>
        ))}
        <button onClick={commencerRevision}>Réviser</button>
      </div>
      <Etat erreur={vue.erreur} chargement={vue.chargement} />
      {vue.donnee && vue.donnee.stuffs.length === 0 && (
        <p className="discret">Pas encore de stuffs pour cette carte : ajoute des démos pros (commande « references ajouter »).</p>
      )}

      {enRevision && (
        <div className="carte" style={{ borderLeft: "6px solid var(--accent)" }}>
          <div className="discret">Révision {revision!.i + 1} / {revision!.liste.length}</div>
          <h3>{enRevision.nom}</h3>
          {!revision!.montre ? (
            <button onClick={() => setRevision({ ...revision!, montre: true })}>Montrer la solution</button>
          ) : (
            <>
              <p>Lancer {enRevision.technique}. {enRevision.commandes && <code>{enRevision.commandes}</code>}</p>
              <div className="ligne">
                <button onClick={() => repondre(true)}>Je la connais</button>
                <button onClick={() => repondre(false)}>À revoir</button>
              </div>
            </>
          )}
        </div>
      )}
      {revision && revision.liste.length === 0 && <p className="discret">Rien à réviser aujourd'hui sur cette carte.</p>}

      {vue.donnee && vue.donnee.stuffs.length > 0 && (
        <div className="replay">
          <svg viewBox={`0 0 ${C} ${C}`} style={{ width: "100%", background: "#0e1013", borderRadius: 10 }}>
            {vue.donnee.radar.image && <image href={vue.donnee.radar.image} width={C} height={C} opacity={0.8} />}
            {liste.map((s) => {
              const [ax, ay] = vers(s.x, s.y);
              const actif = s.cle === selection;
              return (
                <g key={s.cle} onClick={() => setSelection(s.cle)} style={{ cursor: "pointer" }}>
                  {s.lx !== null && (() => {
                    const [lx, ly] = vers(s.lx, s.ly!);
                    return <line x1={lx} y1={ly} x2={ax} y2={ay} stroke={COULEURS[s.type]}
                      strokeOpacity={actif ? 0.9 : 0.25} strokeWidth={actif ? 2 : 1} />;
                  })()}
                  <circle cx={ax} cy={ay} r={actif ? 10 : 7} fill={COULEURS[s.type]}
                    fillOpacity={s.maitrise.reussites > 0 ? 0.9 : 0.35} stroke={actif ? "#f0b429" : "none"} strokeWidth={2} />
                </g>
              );
            })}
          </svg>
          <div>
            {choisi ? (
              <div className="carte">
                <h3>{choisi.nom}</h3>
                <p className="discret">Joué {choisi.nb} fois par les pros ({choisi.nb_demos} démos). Lancer {choisi.technique}.</p>
                {choisi.commandes && (
                  <p><code style={{ wordBreak: "break-all" }}>{choisi.commandes}</code>{" "}
                    <button onClick={() => copier(choisi.commandes!)}>Copier</button></p>
                )}
                <p>
                  En match : {choisi.maitrise.reussites} réussie(s) sur {choisi.maitrise.tentatives}
                  {choisi.maitrise.dernier_ecart !== null && ` · dernier écart ${nombre(choisi.maitrise.dernier_ecart, "u")}`}
                </p>
                {choisi.revision && <p className="discret">Prochaine révision : {choisi.revision.prochaine} (boîte {choisi.revision.boite}/5)</p>}
                {choisi.notes.map((n) => (
                  <div key={n.id} className="ligne"><span>📝 {n.texte}</span><button onClick={() => supprimerNote(n.id)}>×</button></div>
                ))}
                <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} style={{ width: "100%" }}
                  placeholder="Note sur ce stuff (repère de visée, quand l'utiliser…)" />
                <button onClick={() => ajouterNote(choisi.cle)}>Ajouter la note</button>
              </div>
            ) : <p className="discret">Clique un point d'arrivée pour voir le stuff.</p>}
          </div>
        </div>
      )}

      {vue.donnee && (
        <div className="carte">
          <h3>Notes sur {carte}</h3>
          {vue.donnee.notes_carte.map((n) => (
            <div key={n.id} className="ligne"><span>{n.texte}</span><button onClick={() => supprimerNote(n.id)}>×</button></div>
          ))}
          {!choisi && (
            <>
              <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} style={{ width: "100%" }}
                placeholder="Note générale sur la carte (rappelée au chargement de la partie)" />
              <button onClick={() => ajouterNote(null)}>Ajouter la note</button>
            </>
          )}
          <h3 style={{ marginTop: "1rem" }}>S'entraîner hors ligne</h3>
          <p className="discret">Dans une partie privée (Jouer → Entraînement), colle cette ligne dans la console, puis les commandes « setpos » des stuffs :</p>
          <code style={{ wordBreak: "break-all" }}>{vue.donnee.config_entrainement}</code>{" "}
          <button onClick={() => copier(vue.donnee!.config_entrainement)}>Copier</button>
        </div>
      )}
    </>
  );
}
