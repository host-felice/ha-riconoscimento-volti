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

import invio
import minifasnet
import mrz
import registro
import volti

VERSIONE = "0.12.0"
QUI = os.path.dirname(os.path.abspath(__file__))
OPZIONI_FILE = os.environ.get("OPZIONI_FILE", "/data/options.json")
PREDEFINITE = {"modello": "buffalo_l", "invio_prove": "", "soglia": 0.4, "soglia_sface": 0.363,
               "soglia_minifasnet": 0.5, "soglia_schermo": 0.5,
               "volto_minimo_px": 80, "parola": "", "log_level": "info"}
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
    """Ogni minuto guarda se i modelli si possono chiudere."""
    while True:
        time.sleep(60)
        try:
            chiusi = []
            chiusi.extend(volti.chiudi_se_inattiva())
            registro.accorcia()
            if minifasnet.chiudi_se_inattiva():
                chiusi.append("minifasnet")
            if chiusi:
                mrz.restituisci_memoria()
                log.info("chiusi per inattivita': %s, memoria %s MB",
                         " e ".join(chiusi), _memoria_mb())
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


@app.errorhandler(volti.ModelliDiversi)
def _errore_modelli_diversi(e):
    return jsonify({"errore": str(e), "come_si_rimedia":
                    "i vettori degli attesi vanno rifatti con il modello in uso"}), 400


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


def _modello():
    """Quale dei due modelli usare per questa richiesta.

    Sta nelle opzioni e si puo' scavalcare a ogni richiesta, perche' e' cosi'
    che si misurano tutti e due sulle stesse facce mentre il progetto va avanti.
    """
    corpo = _corpo_json()
    chiesto = corpo.get("modello") if corpo is not None else request.form.get("modello")
    nome = chiesto or OPZIONI["modello"]
    if nome not in volti.CATALOGO:
        raise Errore("modello sconosciuto: %r (ci sono %s)"
                     % (nome, ", ".join(volti.CATALOGO)))
    if not volti.disponibile(nome):
        raise Errore("il modello %r non e' installato su questa macchina" % nome)
    return nome


def _anche_l_altro():
    """Se la richiesta vuole il punteggio di tutti e due i modelli.

    Serve al confronto fra i due, e costa una seconda misurazione sulla stessa
    faccia: si chiede quando si sta misurando, non tutti i giorni.
    """
    corpo = _corpo_json()
    valore = (corpo.get("anche_l_altro") if corpo is not None
              else request.form.get("anche_l_altro"))
    return str(valore).lower() not in ("none", "", "0", "no", "false")


def _soglia(modello=None):
    """Quella scritta nelle opzioni, salvo che la richiesta ne chieda un'altra.

    Ogni modello ha la sua e non sono confrontabili fra loro: 0,40 per
    buffalo_l, 0,363 per SFace, che e' quella consigliata da OpenCV.

    La porta puo' volerla piu' alta del confronto documento-selfie: li' si
    confrontano due immagini molto diverse, qui due fotografie dal vero.
    """
    corpo = _corpo_json()
    chiesta = corpo.get("soglia") if corpo is not None else request.form.get("soglia")
    if chiesta is None:
        if modello == "sface":
            return float(OPZIONI["soglia_sface"])
        return float(OPZIONI["soglia"])
    try:
        return float(chiesta)
    except (TypeError, ValueError):
        raise Errore("soglia non e' un numero: %r" % chiesta)


def _soglia_minifasnet():
    """Quella delle opzioni, salvo che la richiesta ne chieda un'altra.

    Le due strade non corrono lo stesso rischio e non vogliono lo stesso numero:
    dal portale il selfie arriva da un browser qualunque e la soglia sta alta,
    alla porta la telecamera e' nostra e un allarme sbagliato lascia una persona
    chiusa fuori, quindi sta bassa.
    """
    corpo = _corpo_json()
    chiesta = (corpo.get("soglia_minifasnet") if corpo is not None
               else request.form.get("soglia_minifasnet"))
    if chiesta is None:
        return float(OPZIONI["soglia_minifasnet"])
    try:
        return float(chiesta)
    except (TypeError, ValueError):
        raise Errore("soglia_minifasnet non e' un numero: %r" % chiesta)


def _consenso():
    """Cosa ha risposto chi ha fatto la prova: si', no, oppure non gli e' stato chiesto.

    Sono tre stati e non due, e la differenza conta.

    - **si'**: la prova si scrive nel quaderno e parte verso Home Assistant.
    - **no**: non si scrive **niente, da nessuna parte**. Il quaderno sta sulla
      macchina di chi ha chiesto il favore, quindi scriverci sopra e' esattamente
      la cosa che la domanda chiama "tenere il risultato": un no che ferma solo
      l'invio sarebbe un no finto.
    - **niente**: non e' una prova, e' il portale che lavora. Il quaderno serve
      a far funzionare il sistema e si scrive, ma fuori non esce nulla.
    """
    corpo = _corpo_json()
    valore = (corpo.get("consenso_invio") if corpo is not None
              else request.form.get("consenso_invio"))
    if valore is None:
        return None
    return str(valore).lower() in ("si", "1", "true", "yes", "on")


def _registra(chiamata, risposta):
    """Scrive la prova dove va scritta, secondo cosa ha risposto la persona."""
    consenso = _consenso()
    if consenso is False:
        return False
    pulita = registro.ripulita(chiamata, dict(risposta, telefono=_telefono()))
    registro.scrivi_riga(pulita)
    return invio.manda(OPZIONI["invio_prove"], pulita) if consenso else False


def _chiesto_minifasnet():
    """Se la richiesta vuole anche il controllo su chi c'era davanti all'obiettivo."""
    corpo = _corpo_json()
    valore = (corpo.get("minifasnet") if corpo is not None
              else request.form.get("minifasnet"))
    return str(valore).lower() not in ("none", "", "0", "no", "false")


def _minifasnet(img, riquadro, documento=False):
    """Il giudizio di MiniFASNet, gia' confrontato con la sua soglia.

    **Su un documento la domanda e' un'altra.** Chiedere se davanti c'era una
    persona non ha senso: sul documento la faccia e' stampata, e stampata deve
    essere. Ma la terza probabilita', quella dello schermo, resta buona e
    risponde a una domanda vera: l'ospite ha fotografato il documento, oppure
    la fotografia di un documento su un telefono? Quindi sul documento si
    guarda solo quella.

    Se il modello non c'e' (add-on aggiornato ma immagine vecchia) non e' un
    errore: si risponde che non e' stata misurata, e chi chiama lo vede.
    """
    if not minifasnet.disponibile():
        return {"misurata": False, "motivo": "modello non installato"}
    esito = minifasnet.misura(img, riquadro)
    esito["misurata"] = True
    if documento:
        esito["soglia_schermo"] = float(OPZIONI["soglia_schermo"])
        esito["sospetto_schermo"] = esito["schermo"] >= esito["soglia_schermo"]
    else:
        esito["soglia"] = _soglia_minifasnet()
        esito["persona_vera"] = esito["punteggio"] >= esito["soglia"]
    return esito


def _quante_persone_in_piu(sconosciuti, soglia):
    """Quante persone vere ci sono fra le facce che non sono di nessun atteso.

    **Non tutte le facce che il rilevatore trova sono persone.** Su un
    fotogramma mosso ne inventa una che non c'e', e quella somiglia a zero a
    chiunque: identica a come somiglia a zero un estraneo vero. Il punteggio
    non li distingue, e da solo farebbe gridare al lupo a ogni movimento.

    A distinguerli e' il tempo. Alla porta si scattano tre foto proprio per
    questo: **una persona c'e' in piu' scatti, un fantasma in uno solo.**
    Quindi si mettono insieme le facce sconosciute che si somigliano fra loro,
    e si contano solo i gruppi che compaiono in almeno due scatti diversi.
    """
    gruppi = []
    for faccia in sconosciuti:
        for gruppo in gruppi:
            if volti.somiglianza(faccia["vettore"], gruppo[0]["vettore"]) >= soglia:
                gruppo.append(faccia)
                break
        else:
            gruppi.append([faccia])
    return len([g for g in gruppi if len({f["scatto"] for f in g}) >= 2])


def _analizza(dati, modello, con_minifasnet=False, documento=False):
    """Il volto piu' grande, e se serve anche chi c'era davanti all'obiettivo.

    L'immagine si apre una volta sola e si passa a tutti i modelli: le foto dei
    telefoni sono grosse e aprirle due volte costa senza comprare niente.
    """
    img = volti.leggi(dati)
    esito = volti.volto_principale(img, int(OPZIONI["volto_minimo_px"]), modello)
    if con_minifasnet:
        esito["minifasnet"] = _minifasnet(img, esito["riquadro"], documento)
    esito["_img"] = img
    return esito


def _con_l_altro_modello(documento, selfie, modello):
    """Lo stesso confronto rifatto con l'altro modello, sulle stesse due facce.

    Il rilevamento si ripete, ed e' voluto: costa poche decine di millisecondi e
    tiene questa funzione fuori dai piedi del percorso normale. Serve a mettere
    i due modelli uno accanto all'altro sulle stesse foto, che e' l'unico modo
    di deciderli invece di discuterne.
    """
    fuori = {}
    for altro in volti.CATALOGO:
        if altro == modello or not volti.disponibile(altro):
            continue
        px = int(OPZIONI["volto_minimo_px"])
        try:
            d = volti.volto_principale(documento["_img"], px, altro)
            s = volti.volto_principale(selfie["_img"], px, altro)
        except volti.NessunVolto:
            continue
        soglia = float(OPZIONI["soglia_sface"]) if altro == "sface" else float(OPZIONI["soglia"])
        punteggio = volti.somiglianza(d["vettore"], s["vettore"])
        fuori[altro] = {"somiglianza": punteggio, "soglia": soglia,
                        "verificato": punteggio >= soglia}
    return fuori


def _telefono():
    """Android o iPhone, e nient'altro.

    La marca da sola non spiega niente, ma i due mondi trattano le fotografie
    in modo diverso prima ancora che escano dalla fotocamera, e se un giorno i
    punteggi si spaccassero in due gruppi questa e' la prima cosa da guardare.

    **Si tiene solo la famiglia, non la riga intera del browser.** Quella
    riga e' lunga, dice modello e versione e in mezzo a poche prove riporta a
    una persona sola. "android" e "iphone" no.
    """
    ua = (request.headers.get("User-Agent") or "").lower()
    for pezzo, nome in (("iphone", "iphone"), ("ipad", "ipad"),
                        ("android", "android"), ("macintosh", "mac"),
                        ("windows", "windows")):
        if pezzo in ua:
            return nome
    return "altro"


def _millisecondi(partenza):
    """Quanto e' costata la richiesta. Serve a sapere se la macchina regge."""
    return int(round((time.time() - partenza) * 1000))


def _detto(giudizio):
    """Il giudizio di MiniFASNet come si legge nel registro, o niente se manca.

    Le tre probabilita' si scrivono tutte e tre: sono loro a dire se un rifiuto
    e' arrivato dalla carta o dallo schermo, e sul banco di prova servono a
    verificare che l'ordine delle classi sia quello dichiarato dal modello.
    """
    if not giudizio or not giudizio.get("misurata"):
        return ""
    return ", minifasnet %.3f (stampa %.3f, schermo %.3f) %s" % (
        giudizio["punteggio"], giudizio["stampa"], giudizio["schermo"],
        "persona vera" if giudizio["persona_vera"] else "RESPINTA")


def _senza_vettore(esito):
    return {c: v for c, v in esito.items() if c not in ("vettore", "_img")}


@app.route("/", methods=["GET"])
def pagina():
    """Il banco di prova da telefono: due foto, un punteggio."""
    return send_from_directory(QUI, "pagina.html")


@app.route("/prove", methods=["GET"])
def prove():
    """Il quaderno delle prove: le somme, e le ultime righe.

    Con ?tutte=si escono tutte, con ?jsonl=si esce il file com'e', da salvare.
    I vettori non ci sono mai: qui restano solo numeri che non riportano a
    nessuno.
    """
    if request.args.get("jsonl"):
        righe = registro.leggi()
        testo = "\n".join(json.dumps(r, ensure_ascii=False) for r in righe)
        return Response(testo, mimetype="application/x-ndjson")
    quante = None if request.args.get("tutte") else 50
    return jsonify({"somme": registro.somme(), "invio": invio.stato(),
                    "ultime": registro.leggi(quante)})


@app.route("/salute", methods=["GET"])
def salute():
    return jsonify({
        "stato": "vivo",
        "versione": VERSIONE,
        "memoria_mb": _memoria_mb(),
        "modello": OPZIONI["modello"],
        "modelli": {n: {"installato": volti.disponibile(n),
                        "soglia": float(OPZIONI["soglia_sface"] if n == "sface"
                                        else OPZIONI["soglia"]),
                        "memoria_mb": d["memoria_mb"],
                        "millisecondi": d["millisecondi"]}
                    for n, d in volti.CATALOGO.items()},
        "soglia": float(OPZIONI["soglia"]),
        "soglia_minifasnet": float(OPZIONI["soglia_minifasnet"]),
        "soglia_schermo": float(OPZIONI["soglia_schermo"]),
        "minifasnet": minifasnet.disponibile(),
        "invio_prove": bool(OPZIONI["invio_prove"]),
        "invio": invio.stato(),
        "volto_minimo_px": int(OPZIONI["volto_minimo_px"]),
    })


@app.route("/volto", methods=["POST"])
def volto():
    """Un'immagine, il vettore della faccia piu' grande che ci sta dentro.

    MiniFASNet si chiede con il campo 'minifasnet', e non si calcola da solo
    apposta: questa chiamata serve anche per la foto di un documento, dove una
    faccia stampata e' quello che ci si aspetta di trovare.
    """
    partenza = time.time()
    esito = _analizza(_immagine("immagine"), _modello(), _chiesto_minifasnet())
    esito.pop("_img", None)
    esito["millisecondi"] = _millisecondi(partenza)
    log.info("volto (%s): %d px, fiducia %.3f, storta %.0f gradi, altri %s%s",
             esito["modello"], esito["larghezza_px"], esito["fiducia"],
             esito["inclinazione_gradi"], esito["altri_volti_px"],
             _detto(esito.get("minifasnet")))
    return jsonify(esito)


@app.route("/confronta", methods=["POST"])
def confronta():
    """Documento contro selfie: e' la stessa persona?

    Restituisce anche il vettore del selfie, che e' quello da conservare per
    riconoscere l'ospite alla porta. Della foto del documento non resta niente.
    """
    partenza = time.time()
    modello = _modello()
    documento = _analizza(_immagine("documento"), modello, True, documento=True)
    selfie = _analizza(_immagine("selfie"), modello, True)
    soglia = _soglia(modello)
    punteggio = volti.somiglianza(documento["vettore"], selfie["vettore"])
    altri = _con_l_altro_modello(documento, selfie, modello) if _anche_l_altro() else {}
    schermo = documento.get("minifasnet") or {}
    log.info("confronta (%s): %.4f contro soglia %.3f%s%s%s",
             modello, punteggio, soglia, _detto(selfie.get("minifasnet")),
             ", ATTENZIONE il documento sembra ripreso da uno schermo (%.2f)"
             % schermo["schermo"] if schermo.get("sospetto_schermo") else "",
             "".join(", %s %.4f" % (n, d["somiglianza"]) for n, d in altri.items()))
    risposta = {
        "modello": modello,
        "somiglianza": punteggio,
        "soglia": soglia,
        "verificato": punteggio >= soglia,
        "documento": _senza_vettore(documento),
        "selfie": _senza_vettore(selfie),
        "minifasnet": selfie.get("minifasnet"),
        "documento_da_schermo": schermo.get("sospetto_schermo"),
        "altri_modelli": altri,
        "millisecondi": _millisecondi(partenza),
    }
    risposta["prova_mandata"] = _registra("confronta", risposta)
    risposta["vettore_selfie"] = selfie["vettore"]
    return jsonify(risposta)


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
    modello = _modello()
    soglia = _soglia(modello)

    scatti = _immagini("immagine")
    facce = []
    for numero, dati in enumerate(scatti):
        img = volti.leggi(dati)
        try:
            trovate = volti.tutti_i_volti(img, int(OPZIONI["volto_minimo_px"]), modello)
        except volti.NessunVolto:
            continue
        for faccia in trovate:
            faccia["minifasnet"] = _minifasnet(img, faccia["riquadro"])
            # Da quale dei tre scatti viene: serve sotto, a distinguere una
            # persona da un fotogramma mosso.
            faccia["scatto"] = numero
        facce.extend(trovate)
    if not facce:
        raise volti.NessunVolto("nessun volto trovato in nessuno degli scatti")

    # Per ogni faccia il suo miglior candidato, e per ogni atteso la sua
    # miglior faccia: sono due domande diverse e servono tutte e due.
    # Insieme al punteggio si tiene il giudizio sulla faccia che lo ha fatto:
    # senza, si saprebbe che l'ospite e' stato riconosciuto ma non se davanti
    # all'obiettivo c'era lui o la sua fotografia.
    per_atteso = {a["nome"]: (0.0, None) for a in attesi}
    sconosciuti = []
    for faccia in facce:
        migliore = ("", -1.0)
        for atteso in attesi:
            punteggio = volti.somiglianza(faccia["vettore"], atteso["vettore"])
            if punteggio > per_atteso[atteso["nome"]][0]:
                per_atteso[atteso["nome"]] = (punteggio, faccia.get("minifasnet"))
            if punteggio > migliore[1]:
                migliore = (atteso["nome"], punteggio)
        if migliore[1] < soglia:
            sconosciuti.append({
                "larghezza_px": faccia["larghezza_px"],
                "somiglianza_migliore": migliore[1],
                "assomiglia_a": migliore[0],
                "minifasnet": faccia.get("minifasnet"),
                "scatto": faccia["scatto"],
                "vettore": faccia["vettore"],
            })

    persone_in_piu = _quante_persone_in_piu(sconosciuti, soglia)
    for sconosciuto in sconosciuti:
        del sconosciuto["vettore"]

    punteggi = sorted(({"nome": n, "somiglianza": round(p, 4), "minifasnet": v}
                       for n, (p, v) in per_atteso.items()),
                      key=lambda x: -x["somiglianza"])
    riconosciuti = [p for p in punteggi if p["somiglianza"] >= soglia]
    # Lo sconosciuto si porta dietro il suo punteggio: uno 0,05 e' un falso
    # rilevamento, uno 0,35 e' un ospite ripreso male e dice che la soglia
    # e' un filo alta. Senza il numero i due casi si confondono.
    fuori = ["%.2f su %d px" % (s["somiglianza_migliore"], s["larghezza_px"])
             for s in sconosciuti]
    respinti = [r["nome"] for r in riconosciuti
                if r["minifasnet"] and r["minifasnet"].get("misurata")
                and not r["minifasnet"]["persona_vera"]]
    log.info("riconosci (%s): %d facce in %d scatti, riconosciuti %s, sconosciuti %d %s, persone in piu' %d%s",
             modello, len(facce), len(scatti),
             ["%s %.3f" % (r["nome"], r["somiglianza"]) for r in riconosciuti],
             len(fuori), fuori, persone_in_piu,
             (", ma MiniFASNet respinge %s" % respinti) if respinti else "")
    risposta = {
        "modello": modello,
        "riconosciuti": riconosciuti,
        "sconosciuti": sconosciuti,
        "persone_in_piu": persone_in_piu,
        "tutti": punteggi,
        "volti_trovati": len(facce),
        "scatti": len(scatti),
        "soglia": soglia,
        "millisecondi": _millisecondi(partenza),
    }
    # Nel registro i nomi non entrano (li toglie lui), restano i punteggi: sono
    # quelli a dire se la soglia alla porta e' quella giusta. E vale la stessa
    # risposta data prima del confronto: la porta non e' una seconda domanda.
    risposta["prova_mandata"] = _registra(
        "riconosci", dict(risposta, punteggi=[p["somiglianza"] for p in punteggi],
                          quanti_riconosciuti=len(riconosciuti)))
    return jsonify(risposta)


@app.after_request
def _restituisci_memoria(risposta):
    """Ogni foto si lascia dietro centinaia di megabyte di aree di lavoro.

    Le libera opencv, ma il magazzino se le tiene in tasca invece di ridarle
    al sistema: finora lo chiedevamo solo dopo la MRZ, che era il posto
    sbagliato, perche' le foto grosse passano dal confronto dei volti.
    """
    if request.method == "POST":
        if volti.secondi_ultima_apertura is not None:
            log.info("modello dei volti aperto in %.2f secondi",
                     volti.secondi_ultima_apertura)
            volti.secondi_ultima_apertura = None
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
