import { NavLink, Route, Routes } from "react-router-dom";
import Accueil from "./pages/Accueil";
import Chaleur from "./pages/Chaleur";
import PagePartie from "./pages/Partie";
import Progression from "./pages/Progression";
import Replay from "./pages/Replay";

export default function App() {
  return (
    <>
      <header className="entete">
        <span className="logo">Postgame</span>
        <nav>
          <NavLink to="/" end>Parties</NavLink>
          <NavLink to="/progression">Progression</NavLink>
          <NavLink to="/chaleur">Chaleur</NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Accueil />} />
          <Route path="/partie/:id" element={<PagePartie />} />
          <Route path="/replay/:id" element={<Replay />} />
          <Route path="/progression" element={<Progression />} />
          <Route path="/chaleur" element={<Chaleur />} />
          <Route path="*" element={<p>Page introuvable.</p>} />
        </Routes>
      </main>
    </>
  );
}
