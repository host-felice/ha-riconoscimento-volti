# -*- coding: utf-8 -*-
"""Quattro chiamate sopra volti.py, e nient'altro.

Nessun database, nessuna foto salvata: le immagini arrivano, diventano numeri
e finiscono li'. I vettori li conserva chi chiama, che sa a quale prenotazione
appartengono e quando vanno cancellati.
"""
import base64
import hmac
import json
import logging
import os
import threading
import time

from flask import Flask, Response, jsonify, request, send_from_directory
from waitress import serve

import cv2

import mrz
import volti

VERSIONE = "0.7.2"
QUI = os.path.dirname(os.path.abspath(__file__))
OPZIONI_FILE = os.environ.get("OPZIONI_FILE", "/data/options.json")
PREDEFINITE = {"soglia": 0.4, "volto_minimo_px": 80, "parola": "", "log_level": "info"}
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

# Un thread solo dentro opencv: ognuno si porta dietro la sua area di lavoro,
# e qui le richieste sono poche e non hanno fretta.
cv2.setNumThreads(2)


def _memoria_mb():
    """Quanta memoria sta occupando questo processo, secondo il sistema."""
    try:
        with open("/proc/self/status", encoding="utf-8") as f:
            for riga in f:
                if riga.startswith("VmRSS:"):
                    return round(int(riga.split()[1]) / 1024)
    except (IOError, OSError, ValueError):
        pass
    return None


def _guardiano():
    """Ogni minuto guarda se il modello dei volti si puo' chiudere."""
    while True:
        time.sleep(60)
        try:
            if volti.chiudi_se_inattiva():
                mrz.restituisci_memoria()
                log.info("modello dei volti chiuso per inattivita', memoria %s MB",
                         _memoria_mb())
        except Exception as guaio:
            log.warning("il guardiano della memoria e' inciampato: %s", guaio)


CHIUSA = """<!DOCTYPE html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Serve la parola</title>
<style>body{font:17px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
max-width:22rem;margin:4rem auto;padding:0 1rem;background:#faf9f7;color:#1c1b19}
input,button{width:100%;padding:.8rem;font-size:1rem;border-radius:10px;margin-top:.6rem}
input{border:1px solid #c9c3b8}button{border:0;background:#1c1b19;color:#fff;font-weight:600}
</style></head><body>
<h1>Serve la parola</h1>
<p>Questa pagina si apre solo con la parola che ti hanno mandato.</p>
<form method="get"><input name="parola" autofocus placeholder="la parola">
<button>Entra</button></form></body></html>"""


def _parola_data():
    """La parola arrivata con la richiesta, da qualunque delle tre strade."""
    dalla_query = request.args.get("parola")
    if dalla_query:
        return dalla_query
    dal_capo = request.headers.get("X-Parola")
    if dal_capo:
        return dal_capo
    if request.is_json:
        corpo = request.get_json(silent=True)
        if isinstance(corpo, dict) and corpo.get("parola"):
            return corpo["parola"]
    return request.form.get("parola", "")


@app.before_request
def _controlla_la_parola():
    """Senza parola non si entra, se una parola e' stata scelta.

    Sta dentro il link che si manda alla persona, cosi' non deve scriverla.
    Vale anche per le chiamate, altrimenti proteggerebbe solo la vetrina.
    """
    attesa = str(OPZIONI.get("parola") or "")
    if not attesa:
        return None
    if hmac.compare_digest(str(_parola_data()), attesa):
        return None
    if request.path == "/":
        return Response(CHIUSA, status=401, mimetype="text/html")
    return jsonify({"errore": "parola d'ordine mancante o sbagliata"}), 401


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


@app.errorhandler(mrz.NessunaMRZ)
def _errore_senza_mrz(e):
    return jsonify({"errore": str(e)}), 422


@app.errorhandler(mrz.LettoreAssente)
def _errore_lettore(e):
    log.error("%s", e)
    return jsonify({"errore": str(e)}), 503


def _corpo_json():
    """Il corpo JSON, se la richiesta arriva cosi'. Altrimenti niente.

    Due porte d'ingresso per la stessa cosa: le immagini come allegato, per chi
    chiama da un programma, oppure scritte in base64 dentro un JSON, per chi ha
    solo un comando HTTP e basta, come Home Assistant.
    """
    if not request.is_json:
        return None
    corpo = request.get_json(silent=True)
    if not isinstance(corpo, dict):
        raise Errore("il corpo JSON deve essere un oggetto")
    return corpo


def _immagine(nome):
    corpo = _corpo_json()
    if corpo is not None:
        scritta = corpo.get(nome)
        if not scritta:
            raise Errore("manca l'immagine '%s'" % nome)
        try:
            return base64.b64decode(scritta, validate=True)
        except Exception:
            raise Errore("l'immagine '%s' non e' base64 valido" % nome)
    inviato = request.files.get(nome)
    if inviato is None:
        raise Errore("manca l'immagine '%s'" % nome)
    dati = inviato.read()
    if not dati:
        raise Errore("l'immagine '%s' e' vuota" % nome)
    return dati


def _immagini(nome):
    """Tutte le immagini arrivate con quel nome: una, o una raffica."""
    corpo = _corpo_json()
    if corpo is not None:
        grezze = corpo.get(nome)
        if isinstance(grezze, str):
            grezze = [grezze]
        if not grezze:
            raise Errore("manca l'immagine '%s'" % nome)
        try:
            return [base64.b64decode(g, validate=True) for g in grezze]
        except Exception:
            raise Errore("una delle immagini '%s' non e' base64 valido" % nome)
    inviate = [f.read() for f in request.files.getlist(nome)]
    inviate = [d for d in inviate if d]
    if not inviate:
        raise Errore("manca l'immagine '%s'" % nome)
    return inviate


def _attesi():
    """La lista degli ospiti attesi, controllata."""
    corpo = _corpo_json()
    if corpo is not None:
        attesi = corpo.get("attesi")
    else:
        grezzi = request.form.get("attesi")
        if not grezzi:
            raise Errore("manca il campo 'attesi'")
        try:
            attesi = json.loads(grezzi)
        except ValueError:
            raise Errore("'attesi' non e' un JSON valido")
    if not isinstance(attesi, list) or not attesi:
        raise Errore("'attesi' deve essere una lista non vuota")
    for atteso in attesi:
        if not isinstance(atteso, dict) or "nome" not in atteso or "vettore" not in atteso:
            raise Errore("ogni atteso vuole 'nome' e 'vettore'")
    return attesi


def _soglia():
    """Quella scritta nelle opzioni, salvo che la richiesta ne chieda un'altra.

    La porta puo' volerla piu' alta del confronto documento-selfie: li' si
    confrontano due immagini molto diverse, qui due fotografie dal vero.
    """
    corpo = _corpo_json()
    chiesta = corpo.get("soglia") if corpo is not None else request.form.get("soglia")
    if chiesta is None:
        return float(OPZIONI["soglia"])
    try:
        return float(chiesta)
    except (TypeError, ValueError):
        raise Errore("soglia non e' un numero: %r" % chiesta)


def _analizza(dati):
    return volti.volto_principale(dati, int(OPZIONI["volto_minimo_px"]))


def _millisecondi(partenza):
    """Quanto e' costata la richiesta. Serve a sapere se la macchina regge."""
    return int(round((time.time() - partenza) * 1000))


def _senza_vettore(esito):
    return {c: v for c, v in esito.items() if c != "vettore"}


@app.route("/", methods=["GET"])
def pagina():
    """Il banco di prova da telefono: due foto, un punteggio."""
    return send_from_directory(QUI, "pagina.html")


@app.route("/salute", methods=["GET"])
def salute():
    return jsonify({
        "stato": "vivo",
        "versione": VERSIONE,
        "memoria_mb": _memoria_mb(),
        "soglia": float(OPZIONI["soglia"]),
        "volto_minimo_px": int(OPZIONI["volto_minimo_px"]),
    })


@app.route("/volto", methods=["POST"])
def volto():
    """Un'immagine, il vettore della faccia piu' grande che ci sta dentro."""
    partenza = time.time()
    esito = _analizza(_immagine("immagine"))
    esito["millisecondi"] = _millisecondi(partenza)
    log.info("volto: %d px, fiducia %.3f, altri %s",
             esito["larghezza_px"], esito["fiducia"], esito["altri_volti_px"])
    return jsonify(esito)


@app.route("/confronta", methods=["POST"])
def confronta():
    """Documento contro selfie: e' la stessa persona?

    Restituisce anche il vettore del selfie, che e' quello da conservare per
    riconoscere l'ospite alla porta. Della foto del documento non resta niente.
    """
    partenza = time.time()
    documento = _analizza(_immagine("documento"))
    selfie = _analizza(_immagine("selfie"))
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
        "millisecondi": _millisecondi(partenza),
    })


@app.route("/riconosci", methods=["POST"])
def riconosci():
    """Chi degli ospiti attesi si e' presentato davanti alla telecamera.

    Uno scatto puo' contenere piu' facce, perche' gli ospiti di una prenotazione
    arrivano insieme, e si possono mandare piu' scatti di fila: per ogni ospite
    resta il punteggio migliore fra tutte le facce di tutti gli scatti.

    Gli attesi arrivano nel campo 'attesi', una lista di {nome, vettore}. Chi
    chiama decide chi metterci dentro: gli ospiti delle prenotazioni attive
    oggi, non tutti quelli che sono passati.
    """
    partenza = time.time()
    attesi = _attesi()
    soglia = _soglia()

    scatti = _immagini("immagine")
    facce = []
    for dati in scatti:
        try:
            facce.extend(volti.tutti_i_volti(dati, int(OPZIONI["volto_minimo_px"])))
        except volti.NessunVolto:
            continue
    if not facce:
        raise volti.NessunVolto("nessun volto trovato in nessuno degli scatti")

    # Per ogni faccia il suo miglior candidato, e per ogni atteso la sua
    # miglior faccia: sono due domande diverse e servono tutte e due.
    per_atteso = {a["nome"]: 0.0 for a in attesi}
    sconosciuti = []
    for faccia in facce:
        migliore = ("", -1.0)
        for atteso in attesi:
            punteggio = volti.somiglianza(faccia["vettore"], atteso["vettore"])
            if punteggio > per_atteso[atteso["nome"]]:
                per_atteso[atteso["nome"]] = punteggio
            if punteggio > migliore[1]:
                migliore = (atteso["nome"], punteggio)
        if migliore[1] < soglia:
            sconosciuti.append({
                "larghezza_px": faccia["larghezza_px"],
                "somiglianza_migliore": migliore[1],
                "assomiglia_a": migliore[0],
            })

    punteggi = sorted(({"nome": n, "somiglianza": round(p, 4)} for n, p in per_atteso.items()),
                      key=lambda x: -x["somiglianza"])
    riconosciuti = [p for p in punteggi if p["somiglianza"] >= soglia]
    # Lo sconosciuto si porta dietro il suo punteggio: uno 0,05 e' un falso
    # rilevamento, uno 0,35 e' un ospite ripreso male e dice che la soglia
    # e' un filo alta. Senza il numero i due casi si confondono.
    fuori = ["%.2f su %d px" % (s["somiglianza_migliore"], s["larghezza_px"])
             for s in sconosciuti]
    log.info("riconosci: %d facce in %d scatti, riconosciuti %s, sconosciuti %d %s",
             len(facce), len(scatti), [r["nome"] for r in riconosciuti],
             len(fuori), fuori)
    return jsonify({
        "riconosciuti": riconosciuti,
        "sconosciuti": sconosciuti,
        "tutti": punteggi,
        "volti_trovati": len(facce),
        "scatti": len(scatti),
        "soglia": soglia,
        "millisecondi": _millisecondi(partenza),
    })


@app.after_request
def _restituisci_memoria(risposta):
    """Ogni foto si lascia dietro centinaia di megabyte di aree di lavoro.

    Le libera opencv, ma il magazzino se le tiene in tasca invece di ridarle
    al sistema: finora lo chiedevamo solo dopo la MRZ, che era il posto
    sbagliato, perche' le foto grosse passano dal confronto dei volti.
    """
    if request.method == "POST":
        mrz.restituisci_memoria()
        log.info("memoria dopo la richiesta: %s MB", _memoria_mb())
    return risposta


@app.route("/mrz", methods=["POST"])
def leggi_mrz():
    """Le righe di caratteri in fondo al documento, e cosa dicono.

    Torna anche quali campi hanno passato la loro cifra di controllo: sono i
    soli che si possono scrivere nel modulo senza farli ricontrollare a mano.
    """
    partenza = time.time()
    esito = mrz.analizza_altrove(_immagine("immagine"))
    esito["millisecondi"] = _millisecondi(partenza)
    log.info("mrz: %s, seconda passata %s, campi da correggere %s, memoria %s MB",
             esito["formato"], esito["seconda_passata"], esito["da_correggere"],
             _memoria_mb())
    return jsonify(esito)


if __name__ == "__main__":
    porta = int(os.environ.get("PORTA", 8099))
    threading.Thread(target=_guardiano, daemon=True).start()
    log.info("in ascolto sulla porta %d, soglia %.2f, memoria %s MB",
             porta, float(OPZIONI["soglia"]), _memoria_mb())
    serve(app, host="0.0.0.0", port=porta, threads=2)
