"""PERF-01 : aucun import lourd pendant une partie."""

from postgame.performance import Garde
from postgame.surveillance import Surveillant


def test_garde_processus_et_gsi():
    processus = ["explorer.exe"]
    gsi = {"t": None}
    temps = {"t": 1000.0}
    g = Garde(
        lister=lambda: processus,
        dernier_gsi=lambda: gsi["t"],
        horloge=lambda: temps["t"],
        cache_s=0,
    )
    assert not g.doit_attendre("lourd")
    processus.append("GeometryDash.exe")
    assert g.doit_attendre("lourd") and not g.doit_attendre("leger")
    processus[:] = ["cs2.exe"]
    assert g.doit_attendre("leger")
    processus[:] = []
    gsi["t"] = 990.0  # message GSI il y a 10 s : partie CS2 en cours
    assert g.jeux_en_cours() == {"cs2"}
    temps["t"] = 1100.0  # plus de message depuis 110 s
    assert not g.doit_attendre("lourd")


def test_surveillance_reporte_pendant_la_partie(tmp_path, base, cfg, factice):
    dossier = tmp_path / "demos"
    dossier.mkdir()
    factice.dossiers = [dossier]
    factice.cout = "lourd"
    en_jeu = {"oui": True}

    class G:
        def doit_attendre(self, cout):
            return en_jeu["oui"] and cout == "lourd"

    s = Surveillant(base, cfg, garde=G())
    (dossier / "m.factice").write_text("carte=de_cache")
    s.passe()
    s.passe()
    assert base.compter_parties() == 0 and len(s.reportes) == 1
    en_jeu["oui"] = False  # le jeu est fermé
    s.passe()
    assert base.compter_parties() == 1 and not s.reportes
