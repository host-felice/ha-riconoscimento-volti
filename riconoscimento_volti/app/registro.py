# -*- coding: utf-8 -*-
"""Il quaderno delle prove: cosa e' successo a ogni confronto, senza le facce.

Serve a decidere con i numeri invece che a memoria. Le prove le faranno persone
diverse, su telefoni diversi, in giorni diversi, e senza un posto dove finiscono
resterebbero nei ricordi di chi c'era.

**Cosa non entra qui dentro, mai:** i vettori, le immagini, i nomi degli ospiti.
Un vettore e' un dato biometrico e ha il suo posto (#20), un nome legherebbe un
punteggio a una persona. Qui restano numeri che non riportano a nessuno: quanto
era grande la faccia, quanto era storta, che punteggio ha fatto, se e' passata.

Il file sta in /data, che e' l'unica cartella dell'add-on che sopravvive a un
riavvio, e si legge da /prove senza doverci entrare dentro.
"""
import json
import os
import threading
import time

CARTELLA = os.environ.get("DATI", "/data")
FILE = os.path.join(CARTELLA, "prove.jsonl")

# Oltre questo il file si accorcia, tenendo le piu' recenti. Diecimila prove
# sono anni di lavoro vero e stanno in pochi megabyte: il tetto non e' per lo
# spazio, e' perche' nessun file cresca per sempre senza che nessuno guardi.
QUANTE_NE_TENGO = 10000

_una_alla_volta = threading.Lock()

# I campi che non escono di qui nemmeno per sbaglio. Il controllo si fa sui
# nomi e non sulla buona volonta' di chi aggiunge una riga fra un anno.
# "assomiglia_a" e "respinti_da_minifasnet" sono nomi di ospiti travestiti da
# altro, ed e' cosi' che un campo vietato entra: non chiamandosi "nome". Il
# primo stava nel quaderno da sempre, trovato da una prova il 19 agosto 2026.
VIETATI = ("vettore", "vettore_selfie", "vettori", "punti", "riga", "immagine",
           "nome", "nomi", "attesi", "riconosciuti", "assomiglia_a",
           "respinti_da_minifasnet", "_img")


def _ripulisci(dato):
    """Toglie tutto quello che non deve essere scritto, a qualunque profondita'."""
    if isinstance(dato, dict):
        return {c: _ripulisci(v) for c, v in dato.items() if c not in VIETATI}
    if isinstance(dato, list):
        return [_ripulisci(v) for v in dato]
    return dato


def ripulita(chiamata, dati):
    """La riga come sara' scritta: con l'ora, senza niente che riporti a qualcuno.

    Sta qui e non dentro scrivi() perche' la stessa riga serve due volte: una
    per il quaderno di casa e una per l'invio a Home Assistant. Ripulirla in un
    posto solo vuol dire che non ci sono due liste di campi vietati da tenere
    d'accordo, e quindi non c'e' il giorno in cui una delle due si dimentica un
    campo nuovo.
    """
    riga = {"quando": time.strftime("%Y-%m-%dT%H:%M:%S"), "chiamata": chiamata}
    riga.update(_ripulisci(dati))
    return riga


def azzera():
    """Butta il quaderno e ricomincia da zero. Torna quante righe c'erano.

    Serve prima di mandare il banco di prova in giro: le righe di casa sono
    quasi tutte della stessa faccia, e mescolate a quelle degli altri sballano
    le somme senza aggiungere niente. Il file non si svuota, si toglie: cosi'
    se la cartella non e' scrivibile ce ne accorgiamo adesso e non alla prima
    prova di uno sconosciuto.
    """
    quante = len(leggi())
    if os.path.exists(FILE):
        os.remove(FILE)
    return quante


def scrivi(chiamata, dati):
    return scrivi_riga(ripulita(chiamata, dati))


def scrivi_riga(riga):
    """Una riga per prova. Se non si puo' scrivere, la richiesta non ne soffre.

    Il registro e' una comodita', non il lavoro: un disco pieno o una cartella
    che non c'e' non devono lasciare un ospite fuori dalla porta.
    """
    try:
        with _una_alla_volta:
            if not os.path.isdir(CARTELLA):
                return False
            with open(FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(riga, ensure_ascii=False) + "\n")
        return True
    except (IOError, OSError, ValueError, TypeError):
        return False


def leggi(quante=None):
    """Le prove scritte finora, dalla piu' vecchia."""
    try:
        with open(FILE, encoding="utf-8") as f:
            righe = [json.loads(r) for r in f if r.strip()]
    except (IOError, OSError, ValueError):
        return []
    return righe[-quante:] if quante else righe


def accorcia():
    """Tiene le ultime e butta il resto. La chiama il guardiano, una volta ogni tanto."""
    righe = leggi()
    if len(righe) <= QUANTE_NE_TENGO:
        return 0
    tagliate = len(righe) - QUANTE_NE_TENGO
    try:
        with _una_alla_volta:
            with open(FILE, "w", encoding="utf-8") as f:
                for r in righe[tagliate:]:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
    except (IOError, OSError):
        return 0
    return tagliate


def _statistica(punti):
    """Come si distribuisce un mucchio di punteggi. Vuoto vuol dire niente."""
    if not punti:
        return None
    punti = sorted(punti)
    return {"quante": len(punti), "peggiore": round(punti[0], 4),
            "mediana": round(punti[len(punti) // 2], 4),
            "migliore": round(punti[-1], 4)}


def coppie(riga):
    """(modello, punteggio, doveva_combaciare, soglia) per ogni confronto della riga.

    **Una riga senza l'etichetta non ne produce nessuna**, ed e' il punto di
    tutta questa funzione. Un punteggio di cui non si sa se doveva combaciare
    non e' una misura: buttato nel mucchio insieme agli altri fa sparire proprio
    la distanza fra i due mondi, che e' il numero per cui il quaderno esiste.

    Le due etichette arrivano da due posti diversi perche' le due prove sono
    diverse. Nel confronto documento-selfie chi prova dice se le due facce sono
    sue. Alla porta dice chi c'e' davanti alla telecamera, per posto nella lista
    e mai per nome: da li' escono un confronto giusto e tutti gli estranei degli
    altri attesi, che e' l'unico posto da cui gli estranei arrivano davvero.
    """
    chiamata = riga.get("chiamata")
    if chiamata == "confronta":
        stessa = riga.get("stessa_persona")
        if stessa is None or "somiglianza" not in riga:
            return
        yield riga.get("modello", "?"), riga["somiglianza"], bool(stessa), riga.get("soglia")
        for altro, d in (riga.get("altri_modelli") or {}).items():
            if isinstance(d, dict) and "somiglianza" in d:
                yield altro, d["somiglianza"], bool(stessa), d.get("soglia")
    elif chiamata == "riconosci":
        presenti = riga.get("presenti")
        if presenti is None:
            return
        presenti = set(presenti)
        # Il modello in uso piu' ognuno degli altri che si e' potuto misurare.
        esiti = [(riga.get("modello", "?"), riga)] + [
            (altro, d) for altro, d in (riga.get("altri_modelli") or {}).items()
            if isinstance(d, dict) and d.get("misurato")]
        for modello, esito in esiti:
            for p in esito.get("tutti") or []:
                if isinstance(p, dict) and "posizione" in p and "somiglianza" in p:
                    yield (modello, p["somiglianza"],
                           p["posizione"] in presenti, esito.get("soglia"))


def somme():
    """Le somme tirate, e il numero che decide sta in fondo.

    La domanda non e' "con quale modello i punteggi sono piu' alti": e' **quanto
    spazio resta fra il peggiore dei confronti che dovevano combaciare e il
    migliore di quelli che non dovevano**. Un modello che alza tutti e due i
    mondi insieme non ha guadagnato niente, e finche' le due meta' stavano nello
    stesso mucchio quella distanza non si poteva nemmeno calcolare.

    Le righe che non portano l'etichetta si contano a parte invece di sparire:
    un mucchio di prove scartate e' un guasto da vedere, non un dettaglio.
    """
    righe = leggi()
    per_modello = {}
    senza_etichetta = 0
    for riga in righe:
        if riga.get("chiamata") not in ("confronta", "riconosci"):
            continue
        trovate = list(coppie(riga))
        if not trovate:
            senza_etichetta += 1
            continue
        for modello, punteggio, giusta, soglia in trovate:
            d = per_modello.setdefault(modello, {"giusti": [], "estranei": [],
                                                 "respinti": 0, "passati": 0})
            d["giusti" if giusta else "estranei"].append(punteggio)
            if soglia is None:
                continue
            if giusta and punteggio < soglia:
                d["respinti"] += 1
            elif not giusta and punteggio >= soglia:
                d["passati"] += 1

    fuori = {}
    for modello, d in per_modello.items():
        giusti, estranei = _statistica(d["giusti"]), _statistica(d["estranei"])
        fuori[modello] = {
            "giusti": giusti,
            "estranei": estranei,
            # Quanto manca al primo errore. **Negativo vuol dire che i due mondi
            # si sono gia' sovrapposti**: da qualche parte, con qualunque soglia
            # si scelga, o si respinge un ospite vero o si fa passare uno
            # sconosciuto. Non e' una soglia da spostare, e' il modello.
            "margine": (round(giusti["peggiore"] - estranei["migliore"], 4)
                        if giusti and estranei else None),
            # Gli errori veri, contro la soglia che c'era quel giorno.
            "ospiti_respinti_per_sbaglio": d["respinti"],
            "estranei_fatti_passare": d["passati"],
        }
    return {"prove_in_tutto": len(righe), "confronti": fuori,
            "righe_senza_etichetta": senza_etichetta}
