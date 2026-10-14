// Apprendre les stuffs de chaque carte (STUFF-01) : catalogue appris sur démos pros,
// commandes d'entraînement hors ligne, maîtrise en match, notes et révisions espacées.

import { useEffect, useMemo, useState } from "react";
import { Etat, useDonnee } from "../composants/Chargement";
import { carteParDefaut } from "../lib/format";
import { MomentsPros } from "../composants/RevoirCS2";
import { api } from "../api";
import { nombre } from "../lib/format";
import { projectionRadar } from "../lib/projection";

interface Stuff {
  cle: string; type: string; nom: string; technique: string; commandes: string | null;
  lieu_lancer: string | null; lieu_arrivee: string | null;
  phase: string | null; part_phase: number | null; temps_median: number | null;
  temps_q1: number | null; temps_q3: number | null; raison: string | null;
  part_victoire: number | null; nb_joueurs: number | null; exemple_joueur: string | null;
  trajectoire: [number, number, number, number][] | null;
  x: number; y: number; lx: number | null; ly: number | null; lz: number | null; nb: number; nb_demos: number;
  lpitch: number | null; lyaw: number | null; image: string | null;
  maitrise: { tentatives: number; reussites: number; dernier_ecart: number | null; derniere_reussite: string | null };
  revision: { boite: number; prochaine: string } | null;
  notes: { id: number; texte: string }[];
}
interface VueStuffs {
  carte: string; stuffs: Stuff[]; notes_carte: { id: number; texte: string }[];
  config_entrainement: string;
  radar: {
    parametres: { pos_x: number; pos_y: number; scale: number } | null; image: string | null; taille_image: number;
    image_bas: string | null; altitude_bas: number | null;
  };
}
type Vers = (x: number, y: number) => [number, number];

// Fond : uniquement le radar officiel du jeu (étage inférieur si le lancer est en bas).
function FondCarte({ vue, C, z }: { vue: VueStuffs; C: number; z?: number | null }) {
  const r = vue.radar;
  const bas = r.image_bas && r.altitude_bas !== null && z !== undefined && z !== null && z < r.altitude_bas;
  const image = bas ? r.image_bas : r.image;
  return image ? <image href={image} width={C} height={C} /> : null;
}

function RadarManquant() {
  return (
    <p className="discret">
      Radar officiel de cette carte absent de cette machine : Postgame l'exporte des fichiers du
      jeu sur ton PC de jeu (voir A_VALIDER.md, point 15). En attendant, la position exacte est
      dans la commande setpos ci-dessous.
    </p>
  );
}

// « Où te placer » : zoom sur le point de lancer (toi), le regard, et l'arrivée.
function OuTePlacer({ s, vue, vers, C }: { s: Stuff; vue: VueStuffs; vers: Vers; C: number }) {
  if (s.lx === null || s.ly === null) return <p className="discret">Point de lancer inconnu.</p>;
  if (!vue.radar.image || !vue.radar.parametres) return <RadarManquant />;
  const [px, py] = vers(s.lx, s.ly), [ax, ay] = vers(s.x, s.y);
  const vol = (s.trajectoire ?? []).map(([, x, y]) => vers(x, y));
  const xs = [px, ax, ...vol.map((p) => p[0])], ys = [py, ay, ...vol.map((p) => p[1])];
  const marge = 70;
  const x0 = Math.min(...xs) - marge, y0 = Math.min(...ys) - marge;
  const cote = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)) + 2 * marge;
  const echelle = cote / 300; // tailles constantes à l'écran
  const yaw = ((s.lyaw ?? 0) * Math.PI) / 180;
  const [dx, dy] = [Math.cos(yaw), -Math.sin(yaw)];
  return (
    <svg viewBox={`${x0} ${y0} ${cote} ${cote}`} style={{ width: "100%", maxWidth: 360, background: "#0e1013", borderRadius: 10 }}>
      <FondCarte vue={vue} C={C} z={s.lz} />
      {vol.length > 1
        ? <polyline points={vol.map((p) => p.join(",")).join(" ")} fill="none" stroke={COULEURS[s.type]} strokeWidth={2 * echelle} />
        : <line x1={px} y1={py} x2={ax} y2={ay} stroke={COULEURS[s.type]} strokeWidth={2 * echelle} strokeDasharray={`${6 * echelle} ${4 * echelle}`} />}
      <circle cx={ax} cy={ay} r={9 * echelle} fill={COULEURS[s.type]} fillOpacity={0.5} />
      <line x1={px} y1={py} x2={px + dx * 30 * echelle} y2={py + dy * 30 * echelle} stroke="#f0b429" strokeWidth={3 * echelle} />
      <circle cx={px} cy={py} r={7 * echelle} fill="#f0b429" stroke="#000" strokeWidth={echelle} />
      <text x={px + 10 * echelle} y={py - 10 * echelle} fill="#f0b429" fontSize={14 * echelle} fontWeight="bold">TOI</text>
      <text x={ax + 12 * echelle} y={ay + 4 * echelle} fill="#e8eaed" fontSize={12 * echelle}>arrivée</text>
    </svg>
  );
}

// « Où viser » : vraie capture de la vue du pro au lâcher (F12 dans la démo, jointe seule).
function OuViser({ s, recharger }: { s: Stuff; recharger: () => void }) {
  const pros = useDonnee(() => api.prosStuff(s.cle), [s.cle]);
  const [etat, setEtat] = useState<{ attente: boolean; message?: string; vues?: string; commandes?: string[] } | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    if (!etat?.attente) return;
    const minuteur = setInterval(async () => {
      const r = await json<{ attente: boolean; image: string | null }>(`/api/cs2/stuffs/${s.cle}/capture`);
      if (r.image) { setEtat(null); recharger(); }
      else if (!r.attente) setEtat(null);
    }, 2000);
    return () => clearInterval(minuteur);
  }, [etat, s.cle, recharger]);

  const capturer = async () => {
    const m = pros.donnee?.find((x) => x.disponible);
    if (!m) return;
    setErreur(null);
    try {
      const r = await json<{ commandes: string[]; joueur: string; installe: boolean }>(`/api/cs2/stuffs/${s.cle}/capture`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ empreinte: m.empreinte, tick: m.tick, joueur: m.joueur }),
      });
      setEtat({ attente: true, commandes: r.commandes, message: r.installe ? undefined : "Dossier de CS2 introuvable sur cette machine : à faire sur le PC de jeu." });
    } catch (e) {
      setErreur(String((e as Error).message));
    }
  };

  return (
    <>
      {s.image
        ? <img src={`${s.image}?v=${Date.now() % 100000}`} alt="Vue du lanceur au moment du lancer : le viseur est sur le repère" style={{ width: "100%", borderRadius: 8 }} />
        : <p className="discret">Pas encore de vue : capture-la dans la vraie démo d'un pro (le viseur montre le repère exact).</p>}
      {pros.donnee && !pros.donnee.some((x) => x.disponible) && !s.image && (
        <p className="discret">Pour capturer la vue, il faut la démo .dem du pro sur cette machine (à côté de l'extrait ou dans le dossier pros).</p>
      )}
      {pros.donnee && pros.donnee.some((x) => x.disponible) && !etat && (
        <button onClick={capturer}>{s.image ? "Refaire la capture depuis la démo du pro" : "Capturer la vue du pro"}</button>
      )}
      {erreur && <p className="erreur">{erreur}</p>}
      {etat?.attente && (
        <div className="carte revoir-etapes">
          {etat.message && <p className="discret">{etat.message}</p>}
          Dans CS2 : console <code>{etat.commandes?.[0]}</code>, puis <code>{etat.commandes?.[1]}</code> une fois la démo chargée.
          L'image est figée au lâcher de la grenade, vue du pro. Appuie sur <strong>F12</strong> :
          la capture Steam arrive ici toute seule. <span className="discret">En attente…</span>
        </div>
      )}
    </>
  );
}

interface Cartes { cartes: { code: string; nom: string; pool: boolean; categorie?: string; parties?: number }[] }

function regard(s: Stuff): string | null {
  if (s.lpitch === null) return null;
  const haut = s.lpitch < 0 ? "vers le haut" : "vers le bas";
  return `regard ${Math.abs(s.lpitch).toFixed(1)}° ${haut}`;
}

const COULEURS: Record<string, string> = { smoke: "#c8c8d2", flash: "#ffffff", molotov: "#f06e1e" };

async function json<T>(url: string, options?: RequestInit): Promise<T> {
  const r = await fetch(url, options);
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

function copier(texte: string) {
  navigator.clipboard?.writeText(texte).catch(() => undefined);
}

// Vrais lancers pros de ce stuff : on les revoit dans CS2, caméra sur le lanceur.
function ProsDuStuff({ cle }: { cle: string }) {
  const pros = useDonnee(() => api.prosStuff(cle), [cle]);
  return (
    <>
      <h4 style={{ marginBottom: "0.2rem" }}>Le voir lancé par un pro, dans CS2</h4>
      <Etat erreur={pros.erreur} chargement={pros.chargement} />
      {pros.donnee && <MomentsPros moments={pros.donnee} vide="Démos pros de ce stuff absentes de cette machine (ou lues avant cette version : relance « postgame references ajouter »)." />}
    </>
  );
}

export default function Stuffs() {
  const cartes = useDonnee(() => json<Cartes>("/api/cs2/cartes"), []);
  const [choix, setChoix] = useState<string | null>(null);
  const carte = choix ?? carteParDefaut(cartes.donnee?.cartes) ?? "de_mirage";
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

  const recharger = vue.recharger;
  const [messageAnnot, setMessageAnnot] = useState("");
  const envoyerImage = async (cle: string, fichiers: FileList | null) => {
    if (!fichiers?.length) return;
    const corps = new FormData();
    corps.append("fichier", fichiers[0]);
    await fetch(`/api/cs2/stuffs/${cle}/image`, { method: "POST", body: corps });
    recharger();
  };
  const installerAnnotations = async () => {
    const r = await json<{ fichier: string; commande: string }>(`/api/cs2/stuffs/annotations?carte=${carte}`, { method: "POST" });
    setMessageAnnot(`Écrit dans ${r.fichier}. En jeu (entraînement) : ${r.commande}`);
  };
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
          {cartes.donnee?.cartes.map((c) => <option key={c.code} value={c.code}>{c.nom}{c.pool ? "" : ` (${c.categorie ?? "hors pool"})`}</option>)}
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
          {vue.donnee.radar.image && vue.donnee.radar.parametres ? (
          <svg viewBox={`0 0 ${C} ${C}`} style={{ width: "100%", background: "#0e1013", borderRadius: 10 }}>
            <FondCarte vue={vue.donnee} C={C} />
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
          ) : (
            <div>
              <RadarManquant />
              <ul className="fil">
                {liste.map((s) => (
                  <li key={s.cle} style={{ cursor: "pointer" }} onClick={() => setSelection(s.cle)}>
                    <strong>{s.nom}</strong>{" "}
                    <span className="discret">
                      {s.phase ? `· ${s.phase}${s.temps_median !== null ? ` à ${nombre(s.temps_median, "s")}` : ""} ` : ""}· {s.technique}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div>
            {choisi ? (
              <div className="carte">
                <h3>{choisi.nom}</h3>
                <h4>1. Où te placer{choisi.lieu_lancer ? ` — ${choisi.lieu_lancer}` : ""}</h4>
                <OuTePlacer s={choisi} vue={vue.donnee} vers={vers} C={C} />
                {vue.donnee.radar.image && <p className="discret">Le trait jaune donne la direction du regard ; {choisi.trajectoire ? `la ligne est la vraie trajectoire de la grenade de ${choisi.exemple_joueur ?? "l'exemple pro"} (relevée dans la démo)` : "les pointillés vont du lancer à l'arrivée"}{choisi.lieu_arrivee ? `, arrivée sur ${choisi.lieu_arrivee}` : ""}.</p>}
                <h4>Quand et pourquoi</h4>
                {choisi.phase ? (
                  <>
                    <p><strong>{choisi.phase}</strong>
                      {choisi.temps_median !== null && <> · à {nombre(choisi.temps_median, "s")} du début du round</>}
                      {choisi.part_phase !== null && <span className="discret"> ({Math.round(100 * choisi.part_phase)} % des lancers)</span>}
                    </p>
                    {choisi.raison && <p>{choisi.raison}</p>}
                    <p className="discret">Lineup reproduit {choisi.nb} fois par {choisi.nb_joueurs ?? "?"} joueur(s) pro, même point de lancer et même visée (à 3° près). Les grenades lancées au jugé ne sont pas retenues.</p>
                  </>
                ) : <p className="discret">Timing inconnu : ce stuff vient d'une démo lue par une ancienne version (relance « postgame references ajouter »).</p>}
                <h4>2. Où viser (vraie vue du pro dans la démo)</h4>
                <OuViser s={choisi} recharger={recharger} />
                <h4>3. Comment lancer</h4>
                <p style={{ fontSize: "1.15rem" }}><strong>{choisi.technique}</strong>{regard(choisi) ? <span className="discret"> · {regard(choisi)}</span> : null}</p>
                <ProsDuStuff cle={choisi.cle} />
                <p className="discret">Joué {choisi.nb} fois par les pros ({choisi.nb_demos} démos).</p>
                <label className="discret" style={{ display: "block", margin: "0.4rem 0" }}>
                  Ou joindre ta propre capture :{" "}
                  <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => envoyerImage(choisi.cle, e.target.files)} />
                </label>
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
          <h3 style={{ marginTop: "1rem" }}>Voir les stuffs dans le jeu</h3>
          <p className="discret">Les annotations officielles de CS2 affichent en entraînement où te placer, le point exact à viser avec la technique, et où la grenade doit tomber.</p>
          <div className="ligne">
            <button onClick={installerAnnotations}>Installer les annotations de {carte}</button>
            <a href={`/api/cs2/stuffs/annotations?carte=${carte}`}>Télécharger le fichier</a>
          </div>
          {messageAnnot && <p className="discret">{messageAnnot}</p>}
          <h3 style={{ marginTop: "1rem" }}>S'entraîner hors ligne</h3>
          <p className="discret">Dans une partie privée (Jouer → Entraînement), colle cette ligne dans la console, puis les commandes « setpos » des stuffs :</p>
          <code style={{ wordBreak: "break-all" }}>{vue.donnee.config_entrainement}</code>{" "}
          <button onClick={() => copier(vue.donnee!.config_entrainement)}>Copier</button>
        </div>
      )}
    </>
  );
}
