"""English catalog: Italian text (as written in the code) → English text. Placeholders must match."""
T = {
    # ---------- CLI ----------
    "Stockfish non trovato. Esegui 'chess-io setup' oppure installalo nel PATH.":
        "Stockfish not found. Run 'chess-io setup' or install it on your PATH.",
    "llama-server non trovato: esegui 'chess-io setup --llm' oppure avvia senza --llm.":
        "llama-server not found: run 'chess-io setup --llm' or start without --llm.",
    "Da scaricare in {path}: {items}": "To download into {path}: {items}",
    "Lingua predefinita: {name} ({code})": "Default language: {name} ({code})",
    "Analizza una partita con Stockfish e la rivedi nel terminale: mosse classificate, commenti, varianti migliori e riassunto.":
        "Analyse a game with Stockfish and review it in the terminal: classified moves, comments, best lines and summary.",
    "link a una partita di lichess.org o chess.com": "link to a lichess.org or chess.com game",
    "file .pgn, testo PGN tra virgolette, oppure - per leggerlo da stdin":
        ".pgn file, quoted PGN text, or - to read it from stdin",
    "scegli tra le ultime partite di un utente: piattaforma lichess o chess.com":
        "pick one of a user's recent games: platform lichess or chess.com",
    "il tuo colore (default: auto, ricavato dal link o dall'utente, altrimenti chiesto)":
        "your colour (default: auto, taken from the link or the user, otherwise asked)",
    "profondità di Stockfish per posizione (default 16)": "Stockfish depth per position (default 16)",
    "se il PGN (o -u) contiene più partite, analizza la N-esima (default: scelta a schermo)":
        "if the PGN (or -u) contains several games, analyse the N-th (default: pick on screen)",
    "lingua di interfaccia e commenti solo per questa volta (default: quella impostata con chess-io lang, ora {lang})":
        "interface and comment language for this run only (default: the one set with chess-io lang, now {lang})",
    "Scarica le risorse mancanti in {path} (Stockfish, aperture; con --llm anche llama-server e modello).":
        "Download missing resources into {path} (Stockfish, openings; with --llm also llama-server and the model).",
    "anche llama-server e il modello Qwen3 1.7B (~1,1 GB)": "also llama-server and the Qwen3 1.7B model (~1.1 GB)",
    "non chiedere conferma": "do not ask for confirmation",
    "Tutto già presente.": "Everything is already installed.",
    "Eliminato {path}": "Deleted {path}",
    "Nessun modello da eliminare.": "No model to delete.",
    "Mostra o imposta la lingua predefinita di interfaccia e commenti.":
        "Show or set the default language for the interface and comments.",
    "impossibile salvare l'impostazione in {path}": "could not save the setting in {path}",
    "--depth va da 4 a 30": "--depth must be between 4 and 30",
    "Scarico le ultime partite di {user}…": "Downloading {user}'s recent games…",
    "PIATTAFORMA": "PLATFORM",
    "UTENTE": "USER",
    "Lingua": "Language",
    "database delle aperture": "openings database",
    "modello LLM (1,1 GB)": "LLM model (1.1 GB)",
    "Scarico la partita…": "Downloading the game…",
    "Procedo? [s/N] ": "Proceed? [y/N] ",

    # ---------- downloads, risorse ----------
    "  aperture: scarico i TSV e costruisco il database…": "  openings: downloading the TSV files and building the database…",
    "{label}: SHA256 diverso da quello atteso, file scartato": "{label}: SHA256 does not match, file discarded",
    "nessun Stockfish precompilato per {platform}: installalo e mettilo nel PATH":
        "no prebuilt Stockfish for {platform}: install it and put it on your PATH",
    "nessun llama-server precompilato per {platform}: installalo e mettilo nel PATH":
        "no prebuilt llama-server for {platform}: install it and put it on your PATH",
    "{label}: download non riuscito ({error})": "{label}: download failed ({error})",
    "Stockfish: eseguibile non trovato nell'archivio": "Stockfish: executable not found in the archive",
    "llama-server: eseguibile non trovato nell'archivio": "llama-server: executable not found in the archive",
    "Aperture": "Openings",
    "Modello LLM": "LLM model",
    "Prompt": "Prompts",
    "Dati utente": "User data",
    "{path} (si scarica al primo --llm)": "{path} (downloaded on first --llm)",
    "predefiniti": "default",
    "no (Python)": "no (Python)",
    "non trovato (chess-io setup)": "not found (chess-io setup)",
    "non trovate: niente riconoscimento della teoria": "not found: no opening recognition",
    "non trovato: --llm non disponibile": "not found: --llm not available",

    # ---------- mosse a parole, pezzi ----------
    "l'arrocco lungo": "queenside castling",
    "l'arrocco corto": "kingside castling",
    "{piece} che prende in {square}": "{piece} takes on {square}",
    "move|{piece} in {square}": "{piece} to {square}",
    "{piece} in {square}": "{piece} on {square}",
    " con promozione a {piece}": " promoting to a {piece}",
    " e ": " and ",
    "la qualità": "the exchange",
    "la donna": "the queen",
    "due pedoni": "two pawns",
    "un pezzo": "a piece",
    "molto materiale": "a lot of material",

    # ---------- note posizionali ----------
    "perdi il diritto di arroccare": "you lose the right to castle",
    "la donna esce troppo presto e può diventare un bersaglio": "the queen comes out too early and can become a target",
    "indebolisci la struttura di pedoni davanti al tuo re": "you weaken the pawn structure in front of your king",
    "{piece} ha pochissime case a disposizione": "{piece} has very few squares available",
    "muovi di nuovo lo stesso pezzo invece di sviluppare gli altri":
        "you move the same piece again instead of developing the others",

    # ---------- commenti alle mosse ----------
    "{move} Scacco matto!": "{move} Checkmate!",
    "il matto alla mossa successiva": "mate on the next move",
    "il matto in {n} mosse": "mate in {n}",
    "al matto alla mossa successiva": "to mate on the next move",
    "al matto in {n} mosse": "to mate in {n}",
    "Mossa di teoria{opening}.": "Book move{opening}.",
    "Buona mossa{note}. Era leggermente meglio {move}{why}.": "Good move{note}. {move} was slightly better{why}.",
    " Meglio {move}{why}.": " Better was {move}{why}.",
    ", che porta {mate}": ", which leads {mate}",
    ", con una forchetta che attacca {targets}": ", with a fork attacking {targets}",
    ", che inchioda {targets}": ", which pins {targets}",
    ", con un attacco di scoperta contro {targets}": ", with a discovered attack on {targets}",
    ", che para la minaccia {threat}": ", which parries the threat {threat}",
    ", che vince {gain}": ", which wins {gain}",
    " sulla traversa": " on the back rank",
    "sacrifica {what}": "sacrifices {what}",
    "sacrifica materiale": "sacrifices material",
    " e porta {mate}": " and leads {mate}",
    ", ma l'attacco che ne segue compensa ampiamente": ", but the attack that follows more than makes up for it",
    " Le alternative, come {move}, peggiorano nettamente la posizione.":
        " The alternatives, such as {move}, make the position clearly worse.",
    "l'unica mossa che mantiene il vantaggio": "the only move that keeps the advantage",
    "l'unica mossa che mantiene l'equilibrio": "the only move that holds the balance",
    "l'unica mossa che neutralizza la minaccia {threat}": "the only move that neutralises the threat {threat}",
    "{move} è {what}.": "{move} is {what}.",
    " Forchetta: attacca {targets}.": " Fork: attacks {targets}.",
    "Mossa migliore.": "Best move.",
    "Ottima mossa. Il motore preferiva di poco {move}.": "Excellent move. The engine slightly preferred {move}.",
    "L'avversario aveva sbagliato, ma questa mossa non ne approfitta. Con {move}{gain}.":
        "Your opponent had slipped, but this move does not punish it. With {move}{gain}.",
    " avresti mantenuto il vantaggio": " you would have kept the advantage",
    "La mossa migliore era {move}{why}.": "The best move was {move}{why}.",
    "lascia sfuggire {mate}": "misses {mate}",
    "non para la minaccia {threat}": "does not parry the threat {threat}",
    "permette la forchetta {move}, che attacca {targets}": "allows the fork {move}, attacking {targets}",
    "una forchetta decisiva che attacca {targets}": "a decisive fork attacking {targets}",
    " Inchioda {targets}.": " Pins {targets}.",
    "peggiora la posizione (da {before} a {after})": "worsens the position (from {before} to {after})",
    "peggiora la posizione": "worsens the position",
    "Variante del motore: {line}.": "Engine line: {line}.",
    ", e così {reason}": ", and so it {reason}",
    "Dopo {move} il motore risponde {line}{why}.": "After {move} the engine replies {line}{why}.",
    "Valutazione prima di {move}: {before}; dopo: {after}.": "Evaluation before {move}: {before}; after: {after}.",
    "permette {move}, che inchioda {targets}": "allows {move}, which pins {targets}",
    "dopo {move} perdi {loss} ({piece} cade)": "after {move} you lose {loss} ({piece} falls)",
    "lascia in presa {pieces}": "leaves {pieces} hanging",
    "l'unica strada verso {mate}": "the only way to {mate}",
    " Attacco di scoperta contro {targets}.": " Discovered attack on {targets}.",
    "concede {mate}": "allows {mate}",
    "perdi {loss}: {line}": "you lose {loss}: {line}",
    "perdi {loss}": "you lose {loss}",
    "lascia sfuggire l'occasione di vincere {gain}": "misses the chance to win {gain}",
    " Porta {mate}.": " Leads {mate}.",

    # ---------- riassunto ----------
    " (per esempio {items})": " (for example {items})",
    " per {how}": " by {how}",
    "il bianco": "White",
    "il nero": "Black",
    "mossa tua": "your move",
    "mossa dell'avversario": "opponent's move",
    "Una volta": "Once",
    "{n} volte": "{n} times",
    "In {n} occasioni": "On {n} occasions",
    "{outcome}{ending} in {moves} mosse": "{outcome}{ending} in {moves} moves",
    "Non terminata dopo {moves} mosse": "Unfinished after {moves} moves",
    " · accuratezza {me:.0f}% contro {opp:.0f}%": " · accuracy {me:.0f}% vs {opp:.0f}%",
    "La tua accuratezza è stata del {me:.0f}%, quella dell'avversario del {opp:.0f}%.":
        "Your accuracy was {me:.0f}%, your opponent's {opp:.0f}%.",
    "La partita è rimasta in equilibrio per quasi tutto il tempo.": "The game stayed balanced almost the whole time.",
    "Risultato: {outcome}{ending}, dopo {moves} mosse.": "Result: {outcome}{ending}, after {moves} moves.",
    "La partita non è terminata (dopo {moves} mosse).": "The game was not finished (after {moves} moves).",
    "Hai concesso una forchetta": "You allowed a fork",
    "Hai concesso {n} forchette": "You allowed {n} forks",
    "L’errore più pesante è stato": "Your costliest mistake was",
    "Gli errori più pesanti sono stati": "Your costliest mistakes were",
    "Uno dei tuoi errori è arrivato": "One of your mistakes came",
    "{n} dei tuoi errori sono arrivati": "{n} of your mistakes came",
    "Momento chiave: {move} ({cls}).": "Key moment: {move} ({cls}).",
    "Da ricordare: {lesson}.": "Remember: {lesson}.",
    "Hai giocato con {color} contro {opponent}": "You played {color} against {opponent}",
    "tu": "you",
    "l'avversario": "your opponent",
    "l’avversario": "your opponent",
    "L'equilibrio si è rotto alla mossa {n} ({move}): da lì in avanti è stato in vantaggio {who}.":
        "The balance broke on move {n} ({move}): from then on {who} had the advantage.",
    "Alla mossa {n} ({move}) è passato in vantaggio {who}, ma la partita è cambiata ancora: dalla mossa {n2} ({move2}) è stato in vantaggio {who2}.":
        "On move {n} ({move}) {who} took the lead, but the game turned again: from move {n2} ({move2}) {who2} had the advantage.",
    "{move}, dove era meglio {best}": "{move}, where the better move was {best}",
    "Hai concesso il matto{examples}: quando il tuo re è esposto, prima di ogni mossa guarda gli scacchi che può dare l'avversario.":
        "You allowed mate{examples}: when your king is exposed, look at the checks your opponent can give before every move.",
    "proteggi il re dagli scacchi": "protect your king from checks",
    "{when} hai perso materiale per un pezzo rimasto senza difesa{examples}: prima di muovere controlla quali pezzi restano indifesi.":
        "{when} you lost material to a piece left without defence{examples}: before moving, check which pieces are left unprotected.",
    "controlla i pezzi indifesi": "check for unprotected pieces",
    "{when} non hai parato la minaccia dell'avversario{examples}: dopo ogni sua mossa chiediti che cosa vuole fare.":
        "{when} you did not parry your opponent's threat{examples}: after each of their moves, ask yourself what they want to do.",
    "chiediti cosa minaccia l'avversario": "ask yourself what your opponent threatens",
    "{what}{examples}: prima di muovere guarda da quali case un pezzo avversario potrebbe attaccarne due dei tuoi insieme.":
        "{what}{examples}: before moving, look for squares from which an enemy piece could attack two of yours at once.",
    "attento alle forchette": "watch out for forks",
    "{what} {moves}: prima di muovere confronta almeno due mosse candidate e chiediti qual è la risposta più forte dell'avversario.":
        "{what} {moves}: before moving, compare at least two candidate moves and ask yourself what your opponent's strongest reply is.",
    "confronta più mosse candidate": "compare several candidate moves",
    "Ti è sfuggito un matto{examples}: quando il re avversario è esposto, prova sempre prima gli scacchi.":
        "You missed a mate{examples}: when the enemy king is exposed, always try the checks first.",
    "cerca gli scacchi al re avversario": "look for checks against the enemy king",
    "{when} non hai approfittato di un errore dell'avversario{examples}: quando l'avversario sbaglia, cerca catture e scacchi.":
        "{when} you did not punish a mistake by your opponent{examples}: when your opponent slips, look for captures and checks.",
    "punisci gli errori dell'avversario": "punish your opponent's mistakes",
    "{what} con meno di {limit} sull'orologio{examples}: dosa meglio il tempo nelle fasi tranquille.":
        "{what} with less than {limit} on the clock{examples}: manage your time better in quiet phases.",
    "gestisci meglio il tempo": "manage your time better",
    "Svolta: {move}, poi in vantaggio {who}.": "Turning point: {move}, then {who} took the lead.",
    "Partita in equilibrio, senza svolte nette.": "A balanced game with no clear turning points.",
    ", nella {opening}": ", in the {opening}",
    "La fase più difficile è stata {phase} (accuratezza {acc:.0f}%): {tip}.":
        "The hardest phase was {phase} (accuracy {acc:.0f}%): {tip}.",
    "cura {phase}": "work on {phase}",
    "Partita molto pulita, senza errori: continua a giocare così e prova ad alzare il livello degli avversari.":
        "A very clean game with no mistakes: keep playing like this and try stronger opponents.",
    "continua così": "keep it up",
    "Hai commesso solo piccole imprecisioni ({n}): rivedi i momenti critici e confronta la tua mossa con quella del motore.":
        "You made only small inaccuracies ({n}): review the critical moments and compare your move with the engine's.",
    "rivedi le piccole imprecisioni": "review the small inaccuracies",
    "mossa brillante": "brilliant move",
    "ottima mossa": "great move",
    "mossa migliore": "best move",
    "ottima": "excellent",
    "buona": "good",
    "teoria": "book",
    "imprecisione": "inaccuracy",
    "errore": "mistake",
    "grave errore": "blunder",
    "occasione persa": "missed opportunity",
    "l'apertura": "the opening",
    "il mediogioco": "the middlegame",
    "il finale": "the endgame",
    "ripassa le prime mosse delle tue aperture e punta su sviluppo, centro e arrocco":
        "review the first moves of your openings and focus on development, the centre and castling",
    "prima di ogni mossa controlla catture, scacchi e minacce di entrambi":
        "before every move check captures, checks and threats for both sides",
    "nei finali attiva il re e calcola fino in fondo le spinte di pedone":
        "in endgames activate your king and calculate pawn pushes all the way",
    "scacco matto": "checkmate",
    "stallo": "stalemate",
    "materiale insufficiente": "insufficient material",
    "regola delle 50 mosse": "the 50-move rule",
    "ripetizione di posizione": "repetition",
    "abbandono": "resignation",
    "tempo scaduto": "timeout",
    "patta concordata": "agreement",
    "partita interrotta": "abandonment",
    "non terminata": "unfinished",
    "patta": "draw",
    "vittoria": "win",
    "sconfitta": "loss",

    # ---------- LLM ----------
    "risposta vuota": "empty answer",
    "cita mosse non presenti nei fatti": "mentions moves that are not in the facts",
    "nomina pezzi non presenti nel commento": "names pieces that are not in the comment",
    "introduce concetti non presenti: {words}": "introduces concepts that are not there: {words}",
    "usa il termine di un'altra classe ({cls})": "uses the term of another class ({cls})",
    "testo troppo lungo": "text too long",
    "testo troppo corto": "text too short",
    "non cita nessuna mossa": "does not mention any move",
    "errore LLM: {error}": "LLM error: {error}",
    "llama-server non trovato": "llama-server not found",
    "llama-server non risponde": "llama-server is not responding",
    "download del modello fallito: {error}": "model download failed: {error}",
    "il file scaricato non corrisponde (SHA256 diverso)": "the downloaded file does not match (different SHA256)",
    "llama-server terminato (codice {code})": "llama-server exited (code {code})",

    # ---------- PGN, sorgenti ----------
    "variante non supportata ({variant})": "unsupported variant ({variant})",
    "variante non supportata (Chess960 o simili)": "unsupported variant (Chess960 or similar)",
    "PGN non valido: {error}": "invalid PGN: {error}",
    "la partita non contiene mosse": "the game contains no moves",
    "PGN non valido": "invalid PGN",
    "posizione iniziale (FEN) non valida": "invalid starting position (FEN)",
    "mossa illegale nel PGN": "illegal move in the PGN",
    "file troppo grande (massimo 5 MB)": "file too large (5 MB maximum)",
    "PGN incollato": "pasted PGN",
    "file non trovato: {path}": "file not found: {path}",
    "nessuna partita valida nel PGN": "no valid game in the PGN",
    "nessuna partita trovata per l'utente {user}": "no games found for user {user}",
    "il PGN contiene {n} partite: --game va da 1 a {n}": "the PGN contains {n} games: --game goes from 1 to {n}",
    "partita {n}: {error}": "game {n}: {error}",
    "impossibile leggere {path}: {error}": "cannot read {path}: {error}",
    "chess.com, utente {user}": "chess.com, user {user}",
    "Lichess, utente {user}": "Lichess, user {user}",
    "sono supportati solo link di lichess.org e chess.com": "only lichess.org and chess.com links are supported",
    "link Lichess non riconosciuto: serve il link di una partita (lichess.org/abcd1234)":
        "Lichess link not recognised: a game link is needed (lichess.org/abcd1234)",
    "link chess.com non riconosciuto: serve il link di una partita (chess.com/game/live/123…)":
        "chess.com link not recognised: a game link is needed (chess.com/game/live/123…)",
    "{what}: non trovato": "{what}: not found",
    "{what}: troppe richieste, riprova tra un minuto": "{what}: too many requests, try again in a minute",
    "{what}: errore {code}": "{what}: error {code}",
    "chess.com: partita non trovata negli archivi pubblici. Incolla il PGN da Condividi → PGN":
        "chess.com: game not found in the public archives. Paste the PGN from Share → PGN",
    "nome utente non valido: {name}": "invalid username: {name}",
    "{what}: il server non risponde, riprova più tardi": "{what}: the server is not responding, try again later",
    "{what}: impossibile connettersi. C'è accesso a Internet? In alternativa incolla il PGN.":
        "{what}: cannot connect. Are you online? Alternatively, paste the PGN.",
    "piattaforma sconosciuta: {name} (usa lichess oppure chess.com)": "unknown platform: {name} (use lichess or chess.com)",
    "chess.com: formato della risposta inatteso. Incolla il PGN da Condividi → PGN":
        "chess.com: unexpected response format. Paste the PGN from Share → PGN",
    "{what}: formato della risposta inatteso": "{what}: unexpected response format",

    # ---------- TUI ----------
    "profondità {depth}": "depth {depth}",
    "Per i commenti LLM serve il modello Qwen3 1.7B ({size:.1f} GB), da scaricare una volta sola da Hugging Face. Scaricarlo ora?":
        "LLM comments need the Qwen3 1.7B model ({size:.1f} GB), downloaded once from Hugging Face. Download it now?",
    "modello non scaricato": "model not downloaded",
    "{n} semimosse": "{n} plies",
    "Bianco": "White",
    "Nero": "Black",
    "Posizione iniziale. Usa ← → per scorrere le mosse, n per il prossimo momento critico.":
        "Starting position. Use ← → to step through the moves, n for the next critical moment.",
    " (tu)": " (you)",
    "Accuratezza": "Accuracy",
    "← → per scorrere · Esc per tornare alla partita": "← → to step · Esc to go back to the game",
    "⏸ Momento saliente: premi spazio per continuare": "⏸ Key moment: press space to continue",
    "prima": "before",
    "dopo": "after",
    "✍ testo LLM verificato": "✍ verified LLM text",
    "✍ testo LLM scartato ({reason}): template": "✍ LLM text discarded ({reason}): template",
    "Migliore": "Best",
    "[b] esplora": "[b] explore",
    "Confutazione": "Refutation",
    "[r] esplora": "[r] explore",
    "Minaccia": "Threat",
    "controllo non superato": "check failed",
    "Nessun altro momento critico più avanti": "No more critical moments ahead",
    "Nessun altro momento critico prima": "No earlier critical moments",
    "Migliore: {move}": "Best: {move}",
    "Ora sei il Bianco: riassunto ricalcolato": "You are now White: summary recalculated",
    "Ora sei il Nero: riassunto ricalcolato": "You are now Black: summary recalculated",
    "In breve": "In short",
    "⬇ Scarico il modello LLM (una volta sola)…": "⬇ Downloading the LLM model (only once)…",
    "✍ LLM al lavoro {done}/{total}": "✍ LLM working {done}/{total}",
    "✍ LLM: {mode} (l per cambiare)": "✍ LLM: {mode} (l to switch)",
    "✍ LLM non disponibile: {error}": "✍ LLM not available: {error}",
    "Hai giocato la mossa migliore": "You played the best move",
    "Nessuna confutazione per questa mossa": "No refutation for this move",
    "Mosse": "Moves",
    "attivo": "on",
    "template": "template",
    "nome utente": "username",
    "Cerca": "Search",
    "Invio per cercare le ultime 50 partite.": "Enter to search the last 50 games.",
    "Stockfish sta analizzando le posizioni… {done}/{total}": "Stockfish is analysing the positions… {done}/{total}",
    "Rating stimato": "Estimated rating",
    "chess-io · cerca le partite di un utente": "chess-io · search a user's games",
    "Lingua di interfaccia e commenti (F2 per cambiarla)": "Interface and comment language (F2 to change)",
    "Com'è andata": "How it went",
    "Consigli": "Advice",
    "In attesa di Stockfish…": "Waiting for Stockfish…",
    "Analisi non riuscita: {error}\nPremi q per uscire.": "Analysis failed: {error}\nPress q to quit.",
    "Con quale colore hai giocato? (serve per il riassunto e il verso della scacchiera)":
        "Which colour did you play? (used for the summary and the board orientation)",
    "V": "W",
    "P": "L",
    "sm": "ply",
    "Tasti": "Keys",
    "Riassunto LLM non disponibile": "LLM summary not available",
    " (in corso…)": " (in progress…)",
    "Ultime {n} partite di {user} (○ bianco, ● nero · V vinta, P persa, = patta): quale vuoi analizzare?":
        "Last {n} games of {user} (○ white, ● black · W won, L lost, = draw): which one do you want to analyse?",
    "Il PGN contiene {n} partite: quale vuoi analizzare?": "The PGN contains {n} games: which one do you want to analyse?",
    "Sì [s]": "Yes [y]",
    "No [n]": "No [n]",
    "Momenti critici (Invio per andare alla mossa)": "Critical moments (Enter to go to the move)",
    "Brillante": "Brilliant",
    "Ottima": "Great",
    "Eccellente": "Excellent",
    "Buona": "Good",
    "Teoria": "Book",
    "Imprecisione": "Inaccuracy",
    "Errore": "Mistake",
    "Occasione persa": "Missed opportunity",
    "Grave errore": "Blunder",
    "Non terminata": "Unfinished",
    "Patta": "Draw",
    "Vittoria": "Win",
    "Sconfitta": "Loss",
    "Bullet": "Bullet",
    "Blitz": "Blitz",
    "Rapid": "Rapid",
    "Classica": "Classical",
    "Daily": "Daily",
    # aiuto e footer
    "← →": "← →",
    "mossa precedente / successiva": "previous / next move",
    "Home End": "Home End",
    "inizio / fine partita": "start / end of the game",
    "spazio": "space",
    "riproduzione automatica (si ferma sui momenti salienti)": "autoplay (stops at key moments)",
    "n  N": "n  N",
    "momento critico successivo / precedente": "next / previous critical moment",
    "b": "b",
    "esplora la variante migliore": "explore the best line",
    "r": "r",
    "esplora la confutazione": "explore the refutation",
    "Esc": "Esc",
    "torna alla partita": "back to the game",
    "s": "s",
    "riassunto della partita": "game summary",
    "l": "l",
    "commenti template ↔ LLM (con --llm)": "template ↔ LLM comments (with --llm)",
    "f": "f",
    "gira la scacchiera": "flip the board",
    "c": "c",
    "cambia il tuo colore": "change your colour",
    "q": "q",
    "esci": "quit",
    "Esci": "Quit",
    "Sì": "Yes",
    "No": "No",
    "Chiudi": "Close",
    "Indietro": "Back",
    "Torna alla revisione": "Back to the review",
    "Template/LLM": "Template/LLM",
    "Mossa": "Move",
    "←/→": "←/→",
    "Autoplay": "Autoplay",
    "Critico": "Critical",
    "n/N": "n/N",
    "Riassunto": "Summary",
    "LLM": "LLM",
    "Gira": "Flip",
    "Aiuto": "Help",
    "?": "?",

    # ---------- impostazioni LLM ----------
    "--llm-model serve con --llm-url (o con un servizio impostato con chess-io llm).":
        "--llm-model needs --llm-url (or a service set with chess-io llm).",
    "Annulla":
        "Cancel",
    "Chiave API":
        "API key",
    "Chiave API (vuota = nessuna): ":
        "API key (empty = none): ",
    "Disattivato (si può sempre usare --llm)":
        "Off (you can still use --llm)",
    "Elimina modello":
        "Delete model",
    "Il mio servizio (API compatibile OpenAI)":
        "My own service (OpenAI-compatible API)",
    "Il modello {model} risponde, ma non è tra quelli elencati dal servizio.":
        "The model {model} answers, but it is not among those listed by the service.",
    "Il modello {model} risponde: {reply}":
        "The model {model} answers: {reply}",
    "Impostazioni LLM":
        "LLM settings",
    "Inserisci l'indirizzo del servizio.":
        "Enter the service address.",
    "LLM disattivato: premi o per sceglierlo, oppure avvia con --llm":
        "LLM is off: press o to choose one, or start with --llm",
    "LLM solo con --llm, in locale":
        "LLM only with --llm, local",
    "LLM: uso il servizio {url}, niente da scaricare.":
        "LLM: using the service {url}, nothing to download.",
    "Locale: Qwen3 1.7B sul tuo computer (~1,1 GB)":
        "Local: Qwen3 1.7B on your computer (~1.1 GB)",
    "MODELLO":
        "MODEL",
    "Modalità":
        "Mode",
    "Modelli disponibili: {models}":
        "Available models: {models}",
    "Modello":
        "Model",
    "Nota: {url} è remoto, le partite vengono inviate lì.":
        "Note: {url} is remote, games are sent there.",
    "Per il tuo servizio servono indirizzo e nome del modello.":
        "Your service needs an address and a model name.",
    "Prova connessione":
        "Test connection",
    "Provo {url}…":
        "Trying {url}…",
    "Salva":
        "Save",
    "Scarica":
        "Download",
    "Scarico il modello (una volta sola)…":
        "Downloading the model (only once)…",
    "Scarico llama-server…":
        "Downloading llama-server…",
    "Sceglie l'LLM per commenti e riassunto: off (solo con --llm), local (llama-server + Qwen3 1.7B) oppure il proprio servizio compatibile OpenAI (Ollama, LM Studio, OpenAI, OpenRouter…).":
        "Choose the LLM for comments and summary: off (only with --llm), local (llama-server + Qwen3 1.7B) or your own OpenAI-compatible service (Ollama, LM Studio, OpenAI, OpenRouter…).",
    "Senza -l/-pgn/-u si apre la ricerca delle partite di un utente. Altri comandi: chess-io doctor · chess-io setup [--llm] [--yes] · chess-io remove-model · chess-io lang [it|en|es] · chess-io llm":
        "Without -l/-pgn/-u the user game search opens. Other commands: chess-io doctor · chess-io setup [--llm] [--yes] · chess-io remove-model · chess-io lang [it|en|es] · chess-io llm",
    "Servizio":
        "Service",
    "Servizio LLM":
        "LLM service",
    "Un LLM può riscrivere commenti e riassunto in modo più discorsivo. Ogni testo viene verificato: se cita mosse, pezzi o idee che non c'erano, resta il commento originale.":
        "An LLM can rewrite comments and summary in a more conversational way. Every text is checked: if it mentions moves, pieces or ideas that were not there, the original comment is kept.",
    "chiave API (facoltativa, non serve per Ollama e LM Studio)":
        "API key (optional, not needed for Ollama and LM Studio)",
    "chiave API mancante o non valida (HTTP {code})":
        "missing or invalid API key (HTTP {code})",
    "chiave API: presa dalla variabile d'ambiente":
        "API key: taken from the environment variable",
    "chiede la chiave API (non resta nella cronologia)":
        "ask for the API key (it stays out of the shell history)",
    "commenti e riassunto riscritti dall'LLM (verificati): Qwen3 locale o il servizio impostato con chess-io llm":
        "comments and summary rewritten by the LLM (verified): local Qwen3 or the service set with chess-io llm",
    "da variabile d'ambiente":
        "from environment variable",
    "disattivato (solo con --llm)":
        "off (only with --llm)",
    "il mio servizio, attivo di default":
        "my own service, on by default",
    "il servizio ha risposto HTTP {code}":
        "the service answered HTTP {code}",
    "impossibile contattare {url}":
        "cannot reach {url}",
    "impostazioni LLM: Qwen3 locale o il tuo servizio":
        "LLM settings: local Qwen3 or your own service",
    "indirizzo base, es. http://localhost:11434/v1":
        "base address, e.g. http://localhost:11434/v1",
    "indirizzo, es. http://localhost:11434/v1":
        "address, e.g. http://localhost:11434/v1",
    "llama-server + Qwen3 1.7B, attivo di default":
        "llama-server + Qwen3 1.7B, on by default",
    "llama-server da scaricare (~17 MB)":
        "llama-server to download (~17 MB)",
    "llama-server non trovato: scaricalo dalle impostazioni LLM (o)":
        "llama-server not found: download it from the LLM settings (o)",
    "llama-server presente":
        "llama-server installed",
    "locale, attivo di default":
        "local, on by default",
    "manca il nome del modello":
        "model name missing",
    "manca il nome del modello: usa --llm-model oppure 'chess-io llm set --model NOME'.":
        "model name missing: use --llm-model or 'chess-io llm set --model NAME'.",
    "modello da scaricare ({size:.1f} GB, da Hugging Face)":
        "model to download ({size:.1f} GB, from Hugging Face)",
    "modello o indirizzo non trovato (HTTP 404 da {url})":
        "model or address not found (HTTP 404 from {url})",
    "modello presente ({size:.1f} GB)":
        "model installed ({size:.1f} GB)",
    "modello, es. qwen3:4b":
        "model, e.g. qwen3:4b",
    "mostra le impostazioni (default)":
        "show the settings (default)",
    "nessun servizio configurato: usa 'chess-io llm set --url … --model …'.":
        "no service configured: use 'chess-io llm set --url … --model …'.",
    "nessuna":
        "none",
    "nessuna risposta da {url} (tempo scaduto)":
        "no answer from {url} (timed out)",
    "niente LLM per questa volta":
        "no LLM for this run",
    "nome del modello per --llm-url":
        "model name for --llm-url",
    "nome del modello, es. qwen3:4b":
        "model name, e.g. qwen3:4b",
    "non indicato":
        "not set",
    "o":
        "o",
    "prova il servizio configurato":
        "test the configured service",
    "rimuove la chiave API salvata":
        "remove the saved API key",
    "risposta inattesa dal servizio LLM":
        "unexpected answer from the LLM service",
    "salvata":
        "saved",
    "usa questo servizio compatibile OpenAI solo per questa volta, es. http://localhost:11434/v1 (implica --llm)":
        "use this OpenAI-compatible service for this run only, e.g. http://localhost:11434/v1 (implies --llm)",
    "{url} (remoto: le partite vengono inviate lì)":
        "{url} (remote: games are sent there)",
    "⚠ {url} è remoto: le mosse e i commenti delle partite vengono inviati lì.":
        "⚠ {url} is remote: the moves and comments of your games are sent there.",
    "✓ Il modello {model} risponde.":
        "✓ The model {model} answers.",
    "✓ Servizio raggiungibile: indica il nome del modello.":
        "✓ Service reachable: enter the model name.",
    "✓ Servizio raggiungibile: scegli un modello dall'elenco.":
        "✓ Service reachable: pick a model from the list.",
}
