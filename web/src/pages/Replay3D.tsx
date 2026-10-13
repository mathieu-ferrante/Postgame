// Replay 3D (CS-RPL-02) avec three.js. Le sol est reconstruit à partir des hauteurs que les
// joueurs ont réellement parcourues (pas de géométrie de carte : les fichiers de Valve ne
// sont pas distribués). Repère : x du jeu → x, z du jeu → hauteur, y du jeu → −z.
// Lien partageable sur le réseau local : /replay3d/<partie>?tick=<tick>.

import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { MetaReplay, PisteJoueur, RoundReplay } from "../api";
import { api } from "../api";
import { Etat, useDonnee } from "../composants/Chargement";
import { etatAu } from "../lib/projection";

const COULEURS: Record<number, number> = { 2: 0xe0a030, 3: 0x4a90e2 };
const VITESSES = [0.25, 0.5, 1, 2, 4];
const HAUTEUR_YEUX = 64;

type Piste3D = PisteJoueur & { z?: number[]; pitch?: number[] };

function vers3D(x: number, y: number, z: number): THREE.Vector3 {
  return new THREE.Vector3(x, z, -y);
}

function hauteurAu(round: RoundReplay, piste: Piste3D, tick: number): { z: number; pitch: number } {
  const pas = round.ticks.length > 1 ? round.ticks[1] - round.ticks[0] : 1;
  const f = (tick - round.depart) / pas;
  const i = Math.max(0, Math.min(round.ticks.length - 1, Math.floor(f)));
  const j = Math.min(round.ticks.length - 1, i + 1);
  const t = Math.max(0, Math.min(1, f - i));
  const z = piste.z ? piste.z[i] + (piste.z[j] - piste.z[i]) * t : 0;
  const pitch = piste.pitch ? piste.pitch[i] : 0;
  return { z, pitch };
}

function construireSol(meta: MetaReplay): THREE.Object3D | null {
  const f = meta.fond as (MetaReplay["fond"] & { hauteurs?: number[] }) | null;
  if (!f) return null;
  const geo = new THREE.BoxGeometry(f.cellule, 6, f.cellule);
  const mat = new THREE.MeshLambertMaterial();
  const sol = new THREE.InstancedMesh(geo, mat, f.cellules.length);
  const hauteurs = f.hauteurs ?? f.cellules.map(() => 0);
  const zmin = Math.min(...hauteurs), zmax = Math.max(...hauteurs, zmin + 1);
  const m = new THREE.Matrix4();
  const couleur = new THREE.Color();
  f.cellules.forEach(([i, j], k) => {
    const x = f.xmin + (i + 0.5) * f.cellule, y = f.ymin + (j + 0.5) * f.cellule;
    m.makeTranslation(vers3D(x, y, hauteurs[k] - 3));
    sol.setMatrixAt(k, m);
    // Du bas (bleu sombre) au haut (gris clair) : le relief se lit d'un coup d'œil.
    couleur.setHSL(0.6, 0.15, 0.18 + 0.35 * (hauteurs[k] - zmin) / (zmax - zmin));
    sol.setColorAt(k, couleur);
  });
  return sol;
}

interface ObjetsJoueur { corps: THREE.Mesh; regard: THREE.Line; anneau?: THREE.Mesh }

export default function Replay3D() {
  const id = Number(useParams().id);
  const [params] = useSearchParams();
  const tickCible = params.get("tick") ? Number(params.get("tick")) : null;
  const meta = useDonnee(() => api.replay(id), [id]);
  const [numero, setNumero] = useState<number | null>(null);
  const round = useDonnee(() => (numero !== null ? api.round(id, numero) : Promise.resolve(null)), [id, numero]);
  const [tick, setTick] = useState(0);
  const [lecture, setLecture] = useState(false);
  const [vitesse, setVitesse] = useState(1);
  const [vueMathieu, setVueMathieu] = useState(false);
  const conteneur = useRef<HTMLDivElement>(null);
  const scene = useRef<{ renderer: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera;
    controles: OrbitControls; joueurs: Map<string, ObjetsJoueur>; dynamiques: THREE.Group } | null>(null);

  // Round de départ.
  useEffect(() => {
    const m = meta.donnee;
    if (!m || numero !== null) return;
    const r = tickCible !== null ? m.rounds.find((r) => tickCible >= r.debut - 320 && tickCible <= r.fin) ?? m.rounds[0] : m.rounds[0];
    if (r) setNumero(r.numero);
  }, [meta.donnee, numero, tickCible]);
  useEffect(() => {
    const r = round.donnee;
    if (r) setTick(tickCible !== null && tickCible >= r.depart && tickCible <= r.fin ? tickCible : r.depart);
  }, [round.donnee, tickCible]);

  // Mise en place de la scène.
  useEffect(() => {
    const m = meta.donnee, div = conteneur.current;
    if (!m || !div) return;
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(div.clientWidth, div.clientWidth * 0.62);
    div.appendChild(renderer.domElement);
    const sc = new THREE.Scene();
    sc.background = new THREE.Color(0x0e1013);
    sc.add(new THREE.HemisphereLight(0xffffff, 0x223344, 1.1));
    const soleil = new THREE.DirectionalLight(0xffffff, 0.8);
    soleil.position.set(2000, 4000, 1000);
    sc.add(soleil);
    const sol = construireSol(m);
    if (sol) sc.add(sol);
    const camera = new THREE.PerspectiveCamera(60, 1 / 0.62, 10, 40000);
    const f = m.fond;
    const centre = f ? vers3D(f.xmin + f.largeur * f.cellule / 2, f.ymin + f.hauteur * f.cellule / 2, 0) : new THREE.Vector3();
    camera.position.copy(centre).add(new THREE.Vector3(0, 3500, 2500));
    const controles = new OrbitControls(camera, renderer.domElement);
    controles.target.copy(centre);
    controles.update();
    const dynamiques = new THREE.Group();
    sc.add(dynamiques);
    scene.current = { renderer, scene: sc, camera, controles, joueurs: new Map(), dynamiques };
    let anim = 0;
    const boucle = () => { controles.update(); renderer.render(sc, camera); anim = requestAnimationFrame(boucle); };
    boucle();
    const redimensionner = () => renderer.setSize(div.clientWidth, div.clientWidth * 0.62);
    window.addEventListener("resize", redimensionner);
    return () => {
      cancelAnimationFrame(anim);
      window.removeEventListener("resize", redimensionner);
      renderer.dispose();
      div.removeChild(renderer.domElement);
      scene.current = null;
    };
  }, [meta.donnee]);

  // Lecture.
  useEffect(() => {
    if (!lecture || !round.donnee || !meta.donnee) return;
    let precedent = performance.now(), anim = 0;
    const fin = round.donnee.fin, tickrate = meta.donnee.tickrate;
    const avancer = (t: number) => {
      const dt = (t - precedent) / 1000;
      precedent = t;
      setTick((x) => { const s = x + dt * tickrate * vitesse; if (s >= fin) { setLecture(false); return fin; } return s; });
      anim = requestAnimationFrame(avancer);
    };
    anim = requestAnimationFrame(avancer);
    return () => cancelAnimationFrame(anim);
  }, [lecture, vitesse, round.donnee, meta.donnee]);

  // Mise à jour des objets à chaque tick.
  useEffect(() => {
    const s = scene.current, r = round.donnee, m = meta.donnee;
    if (!s || !r || !m) return;
    const moi = new Set(m.joueurs.filter((j) => j.moi).map((j) => String(j.id)));
    for (const [pid, piste] of Object.entries(r.joueurs) as [string, Piste3D][]) {
      let o = s.joueurs.get(pid);
      if (!o) {
        const corps = new THREE.Mesh(new THREE.CapsuleGeometry(16, 40, 4, 8),
          new THREE.MeshLambertMaterial({ color: COULEURS[piste.equipe] ?? 0x999999 }));
        const regard = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
          new THREE.LineBasicMaterial({ color: COULEURS[piste.equipe] ?? 0x999999 }));
        o = { corps, regard };
        if (moi.has(pid)) {
          o.anneau = new THREE.Mesh(new THREE.TorusGeometry(26, 3, 6, 24), new THREE.MeshBasicMaterial({ color: 0xffffff }));
          o.anneau.rotation.x = Math.PI / 2;
          s.scene.add(o.anneau);
        }
        s.scene.add(corps, regard);
        s.joueurs.set(pid, o);
      }
      const e = etatAu(r, piste, tick);
      const { z, pitch } = hauteurAu(r, piste, tick);
      o.corps.visible = o.regard.visible = e.vivant;
      if (o.anneau) o.anneau.visible = e.vivant;
      const pied = vers3D(e.x, e.y, z);
      o.corps.position.copy(pied).add(new THREE.Vector3(0, 36, 0));
      o.anneau?.position.copy(pied).add(new THREE.Vector3(0, 2, 0));
      const yaw = (e.yaw * Math.PI) / 180, p = (pitch * Math.PI) / 180;
      const oeil = vers3D(e.x, e.y, z + HAUTEUR_YEUX);
      const tir = r.tirs.some(([t, qui]) => String(qui) === pid && t <= tick && tick - t < 8);
      const longueur = tir ? 1500 : 160;
      const dir = new THREE.Vector3(Math.cos(p) * Math.cos(yaw), -Math.sin(p), -Math.cos(p) * Math.sin(yaw));
      o.regard.geometry.setFromPoints([oeil, oeil.clone().add(dir.multiplyScalar(longueur))]);
      (o.regard.material as THREE.LineBasicMaterial).color.set(tir ? 0xfff7a0 : (COULEURS[piste.equipe] ?? 0x999999));
      if (vueMathieu && moi.has(pid) && e.vivant) {
        s.camera.position.copy(oeil);
        s.controles.target.copy(oeil.clone().add(new THREE.Vector3(Math.cos(p) * Math.cos(yaw), -Math.sin(p), -Math.cos(p) * Math.sin(yaw)).multiplyScalar(200)));
      }
    }
    // Grenades actives.
    s.dynamiques.clear();
    for (const [type, gx, gy, debut, fin] of r.grenades) {
      if (tick < debut || tick > (type === "smoke" || type === "molotov" ? fin : debut + 24)) continue;
      const geo = type === "smoke" ? new THREE.SphereGeometry(144, 16, 12)
        : type === "molotov" ? new THREE.CylinderGeometry(120, 120, 4, 24) : new THREE.SphereGeometry(40, 8, 6);
      const couleur = type === "smoke" ? 0xc8c8d2 : type === "molotov" ? 0xf06e1e : type === "flash" ? 0xffffff : 0xff5040;
      const mesh = new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ color: couleur, transparent: true, opacity: type === "smoke" ? 0.55 : 0.8 }));
      // Hauteur : sol le plus proche connu (cellule du fond), sinon 0.
      const f = m.fond as (MetaReplay["fond"] & { hauteurs?: number[] }) | null;
      let zSol = 0;
      if (f?.hauteurs) {
        const i = Math.floor((gx - f.xmin) / f.cellule), j = Math.floor((gy - f.ymin) / f.cellule);
        const k = f.cellules.findIndex(([a, b]) => a === i && b === j);
        if (k >= 0) zSol = f.hauteurs[k];
      }
      mesh.position.copy(vers3D(gx, gy, zSol + (type === "smoke" ? 72 : 2)));
      s.dynamiques.add(mesh);
    }
  }, [tick, round.donnee, meta.donnee, vueMathieu]);

  const r = round.donnee;
  const tickrate = meta.donnee?.tickrate ?? 64;
  return (
    <>
      <div className="ligne">
        <Link to={`/replay/${id}?tick=${Math.round(tick)}`}>← Replay 2D</Link>
        <h1 style={{ margin: 0 }}>Replay 3D {meta.donnee?.carte}</h1>
      </div>
      <Etat erreur={meta.erreur} chargement={meta.chargement} />
      <p className="discret">Sol reconstruit d'après les hauteurs parcourues par les joueurs. Glisser pour tourner, molette pour zoomer.</p>
      <div ref={conteneur} style={{ width: "100%", borderRadius: 10, overflow: "hidden" }} />
      {r && meta.donnee && (
        <>
          <div className="commandes">
            <button onClick={() => setLecture((l) => !l)}>{lecture ? "Pause" : "Lecture"}</button>
            <input type="range" min={r.depart} max={r.fin} value={tick} onChange={(e) => { setLecture(false); setTick(Number(e.target.value)); }} />
            <span className="discret">{Math.max(0, (tick - r.debut) / tickrate).toFixed(1)} s</span>
          </div>
          <div className="commandes">
            {VITESSES.map((v) => <button key={v} className={vitesse === v ? "actif" : ""} onClick={() => setVitesse(v)}>×{v}</button>)}
            <button className={vueMathieu ? "actif" : ""} onClick={() => setVueMathieu((v) => !v)}>Vue de Mathieu</button>
            <select value={numero ?? ""} onChange={(e) => { setLecture(false); setNumero(Number(e.target.value)); }}>
              {meta.donnee.rounds.map((rd) => <option key={rd.numero} value={rd.numero}>Round {rd.numero}</option>)}
            </select>
            <button onClick={() => navigator.clipboard?.writeText(`${location.origin}/replay3d/${id}?tick=${Math.round(tick)}`)}>Copier le lien</button>
          </div>
        </>
      )}
    </>
  );
}
