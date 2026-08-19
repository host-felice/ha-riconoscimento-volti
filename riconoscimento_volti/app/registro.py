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
VIETATI = ("vettore", "vettore_selfie", "vettori", "punti", "riga", "immagine",
           "nome", "nomi", "attesi", "riconosciuti", "_img")


def _ripulisci(dato):
    """Toglie tutto quello che non deve essere scritto, a qualunque profondita'."""
    if isinstance(dato, dict):
        return {c: _ripulisci(v) for c, v in dato.items() if c not in VIETATI}
    if isinstance(dato, list):
        return [_ripulisci(v) for v in dato]
    return dato


def scrivi(chiamata, dati):
    """Una riga per prova. Se non si puo' scrivere, la richiesta non ne soffre.

    Il registro e' una comodita', non il lavoro: un disco pieno o una cartella
    che non c'e' non devono lasciare un ospite fuori dalla porta.
    """
    riga = {"quando": time.strftime("%Y-%m-%dT%H:%M:%S"), "chiamata": chiamata}
    riga.update(_ripulisci(dati))
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


def somme():
    """Le somme tirate: quante prove, come sono andate, modello per modello.

    E' la risposta alla domanda vera, che non e' "cosa e' successo il 3 ottobre"
    ma "con quale dei due modelli sbagliamo di meno".
    """
    righe = leggi()
    per_modello = {}
    for r in righe:
        if r.get("chiamata") != "confronta" or "somiglianza" not in r:
            continue
        m = r.get("modello", "?")
        per_modello.setdefault(m, []).append(r)
        # Anche il punteggio dell'altro modello sulla stessa faccia, quando c'e':
        # e' il confronto che vale, perche' e' fatto sullo stesso scatto.
        for altro, d in (r.get("altri_modelli") or {}).items():
            finto = dict(r)
            finto["somiglianza"] = d["somiglianza"]
            finto["soglia"] = d["soglia"]
            finto["verificato"] = d["verificato"]
            per_modello.setdefault(altro, []).append(finto)

    fuori = {}
    for m, prove in per_modello.items():
        punti = sorted(p["somiglianza"] for p in prove)
        passati = [p for p in prove if p.get("verificato")]
        fuori[m] = {
            "prove": len(prove),
            "passate": len(passati),
            "peggiore": punti[0],
            "mediana": punti[len(punti) // 2],
            "migliore": punti[-1],
            "sul_filo": sum(1 for p in prove
                            if 0 <= p["somiglianza"] - p.get("soglia", 0) < 0.05),
        }
    return {"prove_in_tutto": len(righe), "confronti": fuori}
