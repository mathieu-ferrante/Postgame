import type { Morceau } from "../lib/markdown";
import { analyser } from "../lib/markdown";

function Morceaux({ morceaux }: { morceaux: Morceau[] }) {
  return (
    <>
      {morceaux.map((m, i) => {
        switch (m.type) {
          case "gras":
            return <strong key={i}>{m.texte}</strong>;
          case "italique":
            return <em key={i}>{m.texte}</em>;
          case "source":
            return (
              <a key={i} className="source" href={`#${m.id}`} title="Voir la mesure et ses preuves">
                [{m.id}]
              </a>
            );
          default:
            return <span key={i}>{m.texte}</span>;
        }
      })}
    </>
  );
}

/** Affiche le texte du débrief ; les citations [C1] renvoient au constat correspondant. */
export default function Markdown({ texte }: { texte: string }) {
  return (
    <div className="redige">
      {analyser(texte).map((b, i) => {
        if (b.type === "titre") return <h2 key={i}><Morceaux morceaux={b.morceaux} /></h2>;
        if (b.type === "paragraphe") return <p key={i}><Morceaux morceaux={b.morceaux} /></p>;
        const Liste = b.ordonnee ? "ol" : "ul";
        return (
          <Liste key={i}>
            {b.elements.map((e, j) => (
              <li key={j}><Morceaux morceaux={e} /></li>
            ))}
          </Liste>
        );
      })}
    </div>
  );
}
