# -*- coding: utf-8 -*-
"""Quattro chiamate sopra volti.py, e nient'altro.

Nessun database, nessuna foto salvata: le immagini arrivano, diventano numeri
e finiscono li'. I vettori li conserva chi chiama, che sa a quale prenotazione
appartengono e quando vanno cancellati.
"""
import json
import logging
import os

from flask import Flask, jsonify, request
from waitress import serve

import volti

VERSIONE = "0.1.0"
OPZIONI_FILE = "/data/options.json"
PREDEFINITE = {"soglia": 0.4, "volto_minimo_px": 80, "log_level": "info"}
LIMITE_CORPO = 32 * 1024 * 1024   # una foto di telefono sta larga in 32 MB


def _opzioni():
    """Quelle scritte nell'add-on, o i valori di serie se giriamo fuori da HA."""
    valori = dict(PREDEFINITE)
    try:
        with open(OPZIONI_FILE, encoding="utf-8") as f:
            valori.update({c: v for c, v in json.load(f).items() if v is not None})
    except (IOError, OSError, ValueError):
        pass
    return valori


OPZIONI = _opzioni()

logging.basicConfig(
    level=getattr(logging, str(OPZIONI["log_level"]).upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("volti")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = LIMITE_CORPO


class Errore(Exception):
    def __init__(self, messaggio, codice=400):
        Exception.__init__(self, messaggio)
        self.codice = codice


@app.errorhandler(Errore)
def _errore_nostro(e):
    return jsonify({"errore": str(e)}), e.codice


@app.errorhandler(volti.NessunVolto)
def _errore_senza_volto(e):
    return jsonify({"errore": str(e)}), 422


def _file(nome):
    inviato = request.files.get(nome)
    if inviato is None:
        raise Errore("manca l'immagine '%s'" % nome)
    dati = inviato.read()
    if not dati:
        raise Errore("l'immagine '%s' e' vuota" % nome)
    return dati


def _soglia():
    """Quella scritta nelle opzioni, salvo che la richiesta ne chieda un'altra.

    La porta puo' volerla piu' alta del confronto documento-selfie: li' si
    confrontano due immagini molto diverse, qui due fotografie dal vero.
    """
    chiesta = request.form.get("soglia")
    if chiesta is None:
        return float(OPZIONI["soglia"])
    try:
        return float(chiesta)
    except ValueError:
        raise Errore("soglia non e' un numero: %r" % chiesta)


def _analizza(dati):
    return volti.volto_principale(dati, int(OPZIONI["volto_minimo_px"]))


def _senza_vettore(esito):
    return {c: v for c, v in esito.items() if c != "vettore"}


@app.route("/salute", methods=["GET"])
def salute():
    return jsonify({
        "stato": "vivo",
        "versione": VERSIONE,
        "soglia": float(OPZIONI["soglia"]),
        "volto_minimo_px": int(OPZIONI["volto_minimo_px"]),
    })


@app.route("/volto", methods=["POST"])
def volto():
    """Un'immagine, il vettore della faccia piu' grande che ci sta dentro."""
    esito = _analizza(_file("immagine"))
    log.info("volto: %d px, fiducia %.3f, altri %s",
             esito["larghezza_px"], esito["fiducia"], esito["altri_volti_px"])
    return jsonify(esito)


@app.route("/confronta", methods=["POST"])
def confronta():
    """Documento contro selfie: e' la stessa persona?

    Restituisce anche il vettore del selfie, che e' quello da conservare per
    riconoscere l'ospite alla porta. Della foto del documento non resta niente.
    """
    documento = _analizza(_file("documento"))
    selfie = _analizza(_file("selfie"))
    soglia = _soglia()
    punteggio = volti.somiglianza(documento["vettore"], selfie["vettore"])
    log.info("confronta: %.4f contro soglia %.2f", punteggio, soglia)
    return jsonify({
        "somiglianza": punteggio,
        "soglia": soglia,
        "verificato": punteggio >= soglia,
        "documento": _senza_vettore(documento),
        "selfie": _senza_vettore(selfie),
        "vettore_selfie": selfie["vettore"],
    })


@app.route("/riconosci", methods=["POST"])
def riconosci():
    """Lo scatto della telecamera contro gli ospiti attesi: chi si e' presentato?

    Gli attesi arrivano nel campo 'attesi', una lista di {nome, vettore}. Chi
    chiama decide chi metterci dentro: di solito gli ospiti delle prenotazioni
    attive oggi, non tutti quelli che sono passati.
    """
    grezzi = request.form.get("attesi")
    if not grezzi:
        raise Errore("manca il campo 'attesi'")
    try:
        attesi = json.loads(grezzi)
    except ValueError:
        raise Errore("'attesi' non e' un JSON valido")
    if not isinstance(attesi, list) or not attesi:
        raise Errore("'attesi' deve essere una lista non vuota")

    esito = _analizza(_file("immagine"))
    soglia = _soglia()
    punteggi = []
    for atteso in attesi:
        try:
            punteggi.append({
                "nome": atteso["nome"],
                "somiglianza": volti.somiglianza(esito["vettore"], atteso["vettore"]),
            })
        except (TypeError, KeyError):
            raise Errore("ogni atteso vuole 'nome' e 'vettore'")
    punteggi.sort(key=lambda p: -p["somiglianza"])

    migliore = punteggi[0]
    riconosciuto = migliore["somiglianza"] >= soglia
    log.info("riconosci: %s a %.4f contro soglia %.2f (%d attesi)",
             migliore["nome"], migliore["somiglianza"], soglia, len(attesi))
    return jsonify({
        "riconosciuto": migliore["nome"] if riconosciuto else None,
        "somiglianza": migliore["somiglianza"],
        "soglia": soglia,
        "tutti": punteggi,
        "volto": _senza_vettore(esito),
    })


if __name__ == "__main__":
    porta = int(os.environ.get("PORTA", 8099))
    log.info("in ascolto sulla porta %d, soglia %.2f", porta, float(OPZIONI["soglia"]))
    serve(app, host="0.0.0.0", port=porta, threads=4)
