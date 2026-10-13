// Postgame — journal (mod Geode pour Geometry Dash 2.2081, Geode 5.11).
//
// Rôle : journaliser, sans rien modifier au jeu, ce qu'il faut pour analyser la régularité
// des clics (exigences GD-01 à GD-07 du cahier des charges) :
//   - une séance = un passage dans un niveau (PlayLayer), un fichier par séance ;
//   - chaque essai (mode normal ou entraînement, position de départ) ;
//   - chaque appui / relâchement : horodatage haute précision, temps du niveau, frame, X, Y ;
//   - une position toutes les 4 frames (pour convertir une position en instant) ;
//   - chaque mort (position, %, identifiant de l'objet touché) et chaque niveau terminé.
//
// Règle absolue : chaque hook appelle d'abord la fonction d'origine, sans changer ses
// arguments ni son résultat. Le mod ne fait qu'écrire dans un fichier.
//
// Format : JSON Lines, écrit dans <sauvegarde du mod>/sessions/<date>_<niveau>.gdsession.part
// puis renommé en .gdsession quand on quitte le niveau (le service n'importe que les
// fichiers terminés).

#include <Geode/Geode.hpp>
#include <Geode/modify/GJBaseGameLayer.hpp>
#include <Geode/modify/PlayLayer.hpp>

#include <cctype>
#include <chrono>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <string>

using namespace geode::prelude;

namespace {

constexpr int FORMAT = 1;
constexpr int PAS_POSITION = 4;  // une position toutes les 4 frames

std::string echapper(std::string const& texte) {
    std::string sortie;
    sortie.reserve(texte.size());
    for (unsigned char c : texte) {
        switch (c) {
            case '"': sortie += "\\\""; break;
            case '\\': sortie += "\\\\"; break;
            case '\n': sortie += "\\n"; break;
            case '\r': sortie += "\\r"; break;
            case '\t': sortie += "\\t"; break;
            default:
                if (c < 0x20) sortie += fmt::format("\\u{:04x}", c);
                else sortie += static_cast<char>(c);
        }
    }
    return sortie;
}

std::string nomDeFichier(std::string const& texte) {
    std::string sortie;
    for (char c : texte) {
        sortie += (std::isalnum(static_cast<unsigned char>(c)) ? c : '_');
    }
    return sortie.substr(0, 40);
}

class Journal {
public:
    bool ouvert() const { return m_flux.is_open(); }

    void ouvrir(GJGameLevel* niveau, bool plateforme) {
        fermer();
        auto dossier = Mod::get()->getSaveDir() / "sessions";
        std::error_code erreur;
        std::filesystem::create_directories(dossier, erreur);

        auto maintenant = std::time(nullptr);
        std::tm local{};
#ifdef _WIN32
        localtime_s(&local, &maintenant);
#else
        localtime_r(&maintenant, &local);
#endif
        char horodatage[32];
        std::strftime(horodatage, sizeof(horodatage), "%Y%m%d-%H%M%S", &local);
        std::string nom = niveau ? std::string(niveau->m_levelName) : "inconnu";
        m_final = dossier / fmt::format("{}_{}.gdsession", horodatage, nomDeFichier(nom));
        m_partiel = m_final;
        m_partiel += ".part";
        m_flux.open(m_partiel, std::ios::out | std::ios::trunc);
        if (!m_flux.is_open()) {
            log::error("Postgame : impossible d'écrire {}", m_partiel.string());
            return;
        }
        m_debut = std::chrono::steady_clock::now();
        m_frame = 0;
        char iso[32];
        std::strftime(iso, sizeof(iso), "%Y-%m-%dT%H:%M:%S", &local);
        int id = niveau ? niveau->m_levelID.value() : 0;
        std::string createur = niveau ? std::string(niveau->m_creatorName) : "";
        ecrire(fmt::format(
            R"({{"type":"session","format":{},"debut":"{}","niveau":{{"id":{},"nom":"{}","createur":"{}"}},"plateforme":{},"mod":"{}"}})",
            FORMAT, iso, id, echapper(nom), echapper(createur), plateforme ? "true" : "false",
            Mod::get()->getVersion().toVString()));
    }

    void fermer() {
        if (!m_flux.is_open()) return;
        ecrire(fmt::format(R"({{"type":"fin_session","t":{:.3f}}})", ms()));
        m_flux.close();
        std::error_code erreur;
        std::filesystem::rename(m_partiel, m_final, erreur);
        if (erreur) log::error("Postgame : renommage impossible ({})", erreur.message());
    }

    double ms() const {
        return std::chrono::duration<double, std::milli>(
            std::chrono::steady_clock::now() - m_debut).count();
    }

    int frame() const { return m_frame; }
    void frameSuivante() { ++m_frame; }

    void ecrire(std::string const& ligne) {
        if (!m_flux.is_open()) return;
        m_flux << ligne << '\n';
        m_flux.flush();  // un plantage du jeu ne doit pas perdre la séance
    }

private:
    std::ofstream m_flux;
    std::filesystem::path m_final;
    std::filesystem::path m_partiel;
    std::chrono::steady_clock::time_point m_debut;
    int m_frame = 0;
};

Journal g_journal;

}  // namespace

class $modify(PostgamePlayLayer, PlayLayer) {
    bool init(GJGameLevel* level, bool useReplay, bool dontCreateObjects) {
        if (!PlayLayer::init(level, useReplay, dontCreateObjects)) return false;
        g_journal.ouvrir(level, m_isPlatformer);
        return true;
    }

    void resetLevel() {
        PlayLayer::resetLevel();
        if (!g_journal.ouvert() || !m_player1) return;
        g_journal.ecrire(fmt::format(
            R"({{"type":"essai","n":{},"mode":"{}","t":{:.3f},"tn":{:.5f},"f":{},"x":{:.2f}}})",
            m_attempts, m_isPracticeMode ? "practice" : "normal", g_journal.ms(),
            m_gameState.m_levelTime, g_journal.frame(), m_player1->m_position.x));
    }

    void destroyPlayer(PlayerObject* player, GameObject* object) {
        bool dejaMort = player && player->m_isDead;
        PlayLayer::destroyPlayer(player, object);
        // Le jeu appelle aussi destroyPlayer avec son « pic anti-triche » au chargement :
        // ce n'est pas une mort. On ne note que les vraies morts.
        if (!g_journal.ouvert() || !player || object == m_anticheatSpike) return;
        if (dejaMort || !player->m_isDead) return;
        g_journal.ecrire(fmt::format(
            R"({{"type":"mort","t":{:.3f},"tn":{:.5f},"f":{},"x":{:.2f},"y":{:.2f},"pct":{:.3f},"objet":{}}})",
            g_journal.ms(), m_gameState.m_levelTime, g_journal.frame(), player->m_position.x,
            player->m_position.y, getCurrentPercent(), object ? object->m_objectID : -1));
    }

    void levelComplete() {
        if (g_journal.ouvert()) {
            g_journal.ecrire(fmt::format(
                R"({{"type":"fin","t":{:.3f},"tn":{:.5f},"f":{},"pct":100,"complete":true,"practice":{}}})",
                g_journal.ms(), m_gameState.m_levelTime, g_journal.frame(),
                m_isPracticeMode ? "true" : "false"));
        }
        PlayLayer::levelComplete();
    }

    void onQuit() {
        g_journal.fermer();
        PlayLayer::onQuit();
    }
};

class $modify(PostgameBaseLayer, GJBaseGameLayer) {
    void handleButton(bool down, int button, bool isPlayer1) {
        GJBaseGameLayer::handleButton(down, button, isPlayer1);
        // Seulement en jeu (pas dans l'éditeur).
        auto jeu = PlayLayer::get();
        if (!g_journal.ouvert() || !jeu || static_cast<GJBaseGameLayer*>(jeu) != this) return;
        auto joueur = isPlayer1 ? m_player1 : m_player2;
        if (!joueur) return;
        g_journal.ecrire(fmt::format(
            R"({{"type":"input","t":{:.3f},"tn":{:.5f},"f":{},"x":{:.2f},"y":{:.2f},"appui":{},"bouton":{},"j":{}}})",
            g_journal.ms(), m_gameState.m_levelTime, g_journal.frame(), joueur->m_position.x,
            joueur->m_position.y, down ? "true" : "false", button, isPlayer1 ? 1 : 2));
    }

    void update(float dt) {
        GJBaseGameLayer::update(dt);
        auto jeu = PlayLayer::get();
        if (!g_journal.ouvert() || !jeu || static_cast<GJBaseGameLayer*>(jeu) != this) return;
        g_journal.frameSuivante();
        if (g_journal.frame() % PAS_POSITION != 0 || !m_player1 || m_player1->m_isDead) return;
        g_journal.ecrire(fmt::format(
            R"({{"type":"pos","t":{:.3f},"tn":{:.5f},"f":{},"x":{:.2f},"y":{:.2f}}})",
            g_journal.ms(), m_gameState.m_levelTime, g_journal.frame(), m_player1->m_position.x,
            m_player1->m_position.y));
    }
};
