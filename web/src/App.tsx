import { lazy, Suspense } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import Accueil from "./pages/Accueil";
import Chaleur from "./pages/Chaleur";
import PageComptes from "./pages/Comptes";
import Direct from "./pages/Direct";
import CarteLoL from "./pages/CarteLoL";
import EssaisGD from "./pages/EssaisGD";
import PagePartie from "./pages/Partie";
import Progression from "./pages/Progression";
import Replay from "./pages/Replay";
import StatsTFT from "./pages/StatsTFT";
import Stuffs from "./pages/Stuffs";

// three.js est lourd : la page 3D n'est chargée que si on l'ouvre.
const Replay3D = lazy(() => import("./pages/Replay3D"));

export default function App() {
  return (
    <>
      <header className="entete">
        <span className="logo">Postgame</span>
        <nav>
          <NavLink to="/" end>Parties</NavLink>
          <NavLink to="/progression">Progression</NavLink>
          <NavLink to="/chaleur">Chaleur</NavLink>
          <NavLink to="/stuffs">Stuffs</NavLink>
          <NavLink to="/tft">TFT</NavLink>
          <NavLink to="/direct">En direct</NavLink>
          <NavLink to="/comptes">Comptes</NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Accueil />} />
          <Route path="/partie/:id" element={<PagePartie />} />
          <Route path="/replay/:id" element={<Replay />} />
          <Route path="/replay3d/:id" element={<Suspense fallback={<p className="discret">Chargement de la 3D…</p>}><Replay3D /></Suspense>} />
          <Route path="/progression" element={<Progression />} />
          <Route path="/chaleur" element={<Chaleur />} />
          <Route path="/direct" element={<Direct />} />
          <Route path="/gd/:id" element={<EssaisGD />} />
          <Route path="/lol/:id" element={<CarteLoL />} />
          <Route path="/tft" element={<StatsTFT />} />
          <Route path="/stuffs" element={<Stuffs />} />
          <Route path="/comptes" element={<PageComptes />} />
          <Route path="*" element={<p>Page introuvable.</p>} />
        </Routes>
      </main>
    </>
  );
}
