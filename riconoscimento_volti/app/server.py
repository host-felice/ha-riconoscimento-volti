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
import signal
import threading
import time

from flask import Flask, Response, jsonify, request, send_from_directory
from waitress import serve

import cv2

import invio
import minifasnet
import mrz
import ottico
import registro
import volti

VERSIONE = "0.39.0"
QUI = os.path.dirname(os.path.abspath(__file__))
OPZIONI_FILE = os.environ.get("OPZIONI_FILE", "/data/options.json")
# **"modello" non e' piu' un'opzione del pannello**, e non lo sara' nemmeno dopo.
# Adesso non e' una scelta perche' i due modelli viaggiano insieme: ogni confronto
# li misura tutti e due sulle stesse facce, ed e' l'unico modo per decidere fra
# loro (#34). Dopo non sara' una scelta perche' il modello sara' uno. Resta qui
# come valore di partenza, cioe' quale dei due firma la risposta finche' la
# decisione non c'e'.
PREDEFINITE = {"modello": "buffalo_l", "invio_prove": "", "lettura_ottica": True,
               "soglia": 0.4, "soglia_sface": 0.363,
               "soglia_minifasnet": 0.5,
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
        if not isinstance(atteso, dict) or "nome" not in atteso:
            raise Errore("ogni atteso vuole 'nome' e il suo vettore")
        if "vettore" not in atteso and not isinstance(atteso.get("vettori"), dict):
            raise Errore("l'atteso %r non ha ne' 'vettore' ne' 'vettori'"
                         % atteso.get("nome"))
    return attesi


def _attesi_per(attesi, modello, anche_senza_firma=False):
    """Gli attesi che hanno un vettore fatto da questo modello, e solo quelli.

    **Un vettore vale per il modello che lo ha fatto e per nessun altro.** Chi
    registra l'ospite puo' tenerne uno per modello, in 'vettori', e allora si
    prende quello giusto.

    Un 'vettore' da solo non dice chi lo ha fatto, e va trattato per quello che
    e': **si presta al modello in uso e a nessun altro.** Prestarlo anche
    all'altro e' l'errore che una prova ha trovato il 19 agosto 2026: i due
    vettori hanno lunghezze diverse, il confronto si rifiuta, e la persona
    restava fuori dalla porta per una misura che nessuno le aveva chiesto.

    Se per un modello non c'e' nessun vettore la risposta e' una lista vuota, e
    tocca a chi chiama dire che quella misura non si e' potuta fare.
    """
    fuori = []
    for atteso in attesi:
        vettori = atteso.get("vettori")
        if isinstance(vettori, dict) and modello in vettori:
            fuori.append({"nome": atteso["nome"], "vettore": vettori[modello]})
        elif anche_senza_firma and "vettore" in atteso:
            fuori.append({"nome": atteso["nome"], "vettore": atteso["vettore"]})
    return fuori


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


def _soglia_di(modello):
    """La soglia delle opzioni per quel modello, senza guardare la richiesta.

    Serve dove il modello non e' quello chiesto: quando si misura anche l'altro,
    la soglia scritta nella richiesta e' la sua, non quella dell'altro.
    """
    return float(OPZIONI["soglia_sface"] if modello == "sface" else OPZIONI["soglia"])


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
        return _soglia_di(modello)
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
    return _si_o_no(valore)


def _si_o_no(valore):
    """Un si'/no dalla richiesta, con il None che resta None e non diventa un no."""
    return None if valore is None else str(valore).lower() in ("si", "1", "true", "yes", "on")


def _campo(nome):
    """Un campo della richiesta, dal corpo JSON o dal modulo. None se non c'e'."""
    corpo = _corpo_json()
    valore = corpo.get(nome) if corpo is not None else request.form.get(nome)
    return None if valore in (None, "") else valore


def _stessa_persona():
    """Se chi prova dice che le due facce sono della stessa persona.

    **Tre stati, non due**, come per il consenso: si', no, e non detto. Non detto
    non e' un forse da indovinare: e' una riga che le somme scartano, perche' un
    punteggio senza questa etichetta non dice se il sistema ha indovinato o ha
    sbagliato, e messo nel mucchio rovina anche gli altri.
    """
    return _si_o_no(_campo("stessa_persona"))


def _presenti():
    """Chi c'era davvero davanti alla telecamera, per posto nella lista degli attesi.

    Numeri e mai nomi: nel quaderno i nomi non entrano, e il posto lo sa
    rileggere solo chi ha mandato la lista.

    La lista vuota **non e' la stessa cosa** del campo mancante, ed e' il caso
    piu' prezioso: vuol dire che davanti c'era uno sconosciuto, quindi tutti i
    punteggi di quella prova sono estranei. Il campo mancante vuol dire che
    nessuno lo ha detto, e la prova si scarta.
    """
    valore = _campo("presenti")
    if valore is None:
        return None
    if isinstance(valore, str):
        try:
            valore = json.loads(valore)
        except ValueError:
            return None
    if not isinstance(valore, list):
        return None
    return [int(v) for v in valore if isinstance(v, int) or str(v).isdigit()]


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

    **Sul documento i numeri si scrivono ma non si giudica niente**, e c'e' un
    motivo che e' costato un falso allarme il 19 agosto 2026. Si era provato a
    usare la terza probabilita', quella dello schermo, per rispondere a una
    domanda vera: l'ospite ha fotografato il documento oppure la fotografia di
    un documento su un telefono? Su un passaporto vero, tenuto in mano, ha
    risposto 0,91 e ha gridato al lupo.

    **Il modello ha ragione, e' la domanda a essere sbagliata.** Lui sa dire se
    una faccia e' una persona o la fotografia di una persona. Sul documento la
    faccia **e'** la fotografia di una persona, stampata, plastificata e lucida:
    qualunque numero dia parla della stampa, non di dove quella stampa stava.
    Distinguere la carta da uno schermo vuole altro (le righe del video, la
    trama della carta, i riflessi dell'ologramma) ed e' un lavoro suo.

    I tre numeri si scrivono lo stesso nel quaderno: se un giorno qualcuno
    fotografa davvero un documento da uno schermo, si guarda se erano diversi.

    Se il modello non c'e' (add-on aggiornato ma immagine vecchia) non e' un
    errore: si risponde che non e' stata misurata, e chi chiama lo vede.
    """
    if not minifasnet.disponibile():
        return {"misurata": False, "motivo": "modello non installato"}
    esito = minifasnet.misura(img, riquadro)
    esito["misurata"] = True
    if not documento:
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
        soglia = _soglia_di(altro)
        punteggio = volti.somiglianza(d["vettore"], s["vettore"])
        fuori[altro] = {"somiglianza": punteggio, "soglia": soglia,
                        "verificato": punteggio >= soglia,
                        # Il vettore del selfie fatto da lui. Va restituito
                        # perche' e' l'unico momento in cui esiste: la foto
                        # sparisce, e senza questo alla porta l'altro modello
                        # non avrebbe niente contro cui confrontare.
                        "vettore_selfie": s["vettore"]}
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
    """Il banco di prova da telefono: due foto, un punteggio.

    **La pagina non si mette in cache, e non e' un dettaglio.** Il 19 agosto 2026
    due prove alla porta sono girate con la pagina vecchia tenuta dal telefono:
    l'add-on era aggiornato, il telefono no, e quelle prove hanno saltato in
    silenzio il secondo modello, il limite dei due tentativi e il controllo sulla
    scadenza. Si e' visto solo perche' nel registro mancava la coda con il
    punteggio dell'altro modello.

    Vale doppio in produzione: la pagina **e' il flusso**, e le regole che il
    flusso deve rispettare vivono dentro di lei. Una pagina di ieri e' un flusso
    di ieri, e nessuno se ne accorge.
    """
    risposta = send_from_directory(QUI, "pagina.html")
    risposta.headers["Cache-Control"] = "no-store, must-revalidate"
    risposta.headers["Pragma"] = "no-cache"
    risposta.headers["Expires"] = "0"
    return risposta


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


@app.route("/azzera", methods=["POST"])
def azzera():
    """Svuota il quaderno delle prove. Solo in POST, che non si fa per sbaglio."""
    quante = registro.azzera()
    log.info("quaderno azzerato, erano %d righe", quante)
    return jsonify({"buttate": quante})


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
    log.info("confronta (%s): %.4f contro soglia %.3f%s%s",
             modello, punteggio, soglia, _detto(selfie.get("minifasnet")),
             "".join(", %s %.4f" % (n, d["somiglianza"]) for n, d in altri.items()))
    risposta = {
        "modello": modello,
        "somiglianza": punteggio,
        "soglia": soglia,
        "verificato": punteggio >= soglia,
        "documento": _senza_vettore(documento),
        "selfie": _senza_vettore(selfie),
        "minifasnet": selfie.get("minifasnet"),
        "altri_modelli": altri,
        "millisecondi": _millisecondi(partenza),
    }
    # L'etichetta va nel quaderno e non nella risposta: serve a leggere i
    # numeri fra un mese, non a chi sta guardando il suo punteggio adesso.
    risposta["prova_mandata"] = _registra(
        "confronta", dict(risposta, stessa_persona=_stessa_persona()))
    risposta["vettore_selfie"] = selfie["vettore"]
    return jsonify(risposta)


def _riconosci_con(immagini, attesi, modello, soglia, con_minifasnet=True):
    """Chi degli attesi si e' presentato, misurato con un modello solo.

    Sta fuori dalla chiamata perche' si esegue **due volte**: una con il modello
    in uso e una con l'altro, sugli stessi scatti e contro gli stessi attesi. Fra
    i due modelli non si decide discutendone, si decide mettendoli uno accanto
    all'altro sulle stesse facce, ed e' quello che il confronto documento-selfie
    faceva gia' e la porta no.

    Le immagini arrivano **gia' aperte**: gli stessi scatti passano due volte, e
    un JPEG da dodici megapixel aperto due volte costa il doppio per niente.

    MiniFASNet si misura solo al primo giro. Chi c'era davanti all'obiettivo non
    dipende dal modello dei volti: rifarlo darebbe lo stesso numero al doppio
    del prezzo.
    """
    facce = []
    for numero, img in enumerate(immagini):
        try:
            trovate = volti.tutti_i_volti(img, int(OPZIONI["volto_minimo_px"]), modello)
        except volti.NessunVolto:
            continue
        for faccia in trovate:
            faccia["minifasnet"] = (_minifasnet(img, faccia["riquadro"])
                                    if con_minifasnet else None)
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
    # Il posto nella lista come l'ha mandata chi chiama. Serve al registro
    # dell'add-on, che deve poter dire chi ha fatto quale punteggio senza
    # scrivere il nome di nessuno: il posto lo sa rileggere solo chi ha la
    # lista, cioe' chi ha chiamato.
    posizioni = {a["nome"]: numero + 1 for numero, a in enumerate(attesi)}
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

    punteggi = sorted(({"nome": n, "posizione": posizioni[n],
                        "somiglianza": round(p, 4), "minifasnet": v}
                       for n, (p, v) in per_atteso.items()),
                      key=lambda x: -x["somiglianza"])
    riconosciuti = [p for p in punteggi if p["somiglianza"] >= soglia]
    return {
        "modello": modello,
        "riconosciuti": riconosciuti,
        "sconosciuti": sconosciuti,
        "persone_in_piu": persone_in_piu,
        "tutti": punteggi,
        "volti_trovati": len(facce),
        "soglia": soglia,
        # Con il nome, perche' chi chiama deve sapere chi respingere. Il
        # quaderno lo scarta e il log ne scrive il numero.
        "respinti_da_minifasnet": [
            r for r in riconosciuti
            if r["minifasnet"] and r["minifasnet"].get("misurata")
            and not r["minifasnet"]["persona_vera"]],
    }


def _alla_porta_con_l_altro(immagini, attesi, modello):
    """Lo stesso riconoscimento rifatto con l'altro modello, sugli stessi scatti.

    Alla porta la misura non e' quella del confronto documento-selfie, e non
    basta averla fatta la': qui le facce arrivano di lontano, di sbieco e piu'
    d'una per scatto, che e' il caso in cui i due modelli possono comportarsi
    diverso.

    **Puo' non essere misurabile, e non e' un guasto.** L'ospite registrato con
    un vettore solo non ha niente contro cui confrontare l'altro modello: si dice
    che non si e' potuto misurare e perche', invece di far cadere la risposta o
    di confrontare numeri che non si parlano.
    """
    fuori = {}
    for altro in volti.CATALOGO:
        if altro == modello or not volti.disponibile(altro):
            continue
        suoi = _attesi_per(attesi, altro)
        if not suoi:
            fuori[altro] = {"misurato": False,
                            "motivo": "nessun atteso ha un vettore fatto da questo modello"}
            continue
        try:
            esito = _riconosci_con(immagini, suoi, altro, _soglia_di(altro),
                                   con_minifasnet=False)
        except (volti.NessunVolto, volti.ModelliDiversi) as e:
            fuori[altro] = {"misurato": False, "motivo": str(e)}
            continue
        esito["misurato"] = True
        esito["quanti_attesi"] = len(suoi)
        fuori[altro] = esito
    return fuori


def _numeri(riconosciuti):
    """I riconosciuti come si scrivono nel registro: il numero, non il nome."""
    return ["#%d" % r["posizione"] for r in riconosciuti]


def _detto_alla_porta(nome, esito):
    """Come l'altro modello finisce nel registro dell'add-on, in una riga.

    Se non si e' potuto misurare si scrive perche': un posto vuoto nel log
    sembrerebbe un modello che non trova nessuno, che e' un'altra cosa.
    """
    if not esito.get("misurato"):
        return ", %s non misurato (%s)" % (nome, esito.get("motivo", ""))
    return ", %s riconosciuti %s su soglia %.3f, sconosciuti %d" % (
        nome,
        ["#%d %.3f" % (r["posizione"], r["somiglianza"]) for r in esito["riconosciuti"]],
        esito["soglia"], len(esito["sconosciuti"]))


@app.route("/riconosci", methods=["POST"])
def riconosci():
    """Chi degli ospiti attesi si e' presentato davanti alla telecamera.

    Uno scatto puo' contenere piu' facce, perche' gli ospiti di una prenotazione
    arrivano insieme, e si possono mandare piu' scatti di fila: per ogni ospite
    resta il punteggio migliore fra tutte le facce di tutti gli scatti.

    Gli attesi arrivano nel campo 'attesi'. Ognuno vuole un 'nome' e il suo
    vettore: 'vettore' se ne ha uno solo, oppure 'vettori' con uno per modello,
    che e' cio' che serve per misurare tutti e due alla porta. Chi chiama decide
    chi metterci dentro: gli ospiti delle prenotazioni attive oggi, non tutti
    quelli che sono passati.
    """
    partenza = time.time()
    attesi = _attesi()
    modello = _modello()
    soglia = _soglia(modello)
    suoi = _attesi_per(attesi, modello, anche_senza_firma=True)
    if not suoi:
        raise Errore("nessuno degli attesi ha un vettore fatto da %r" % modello)

    scatti = _immagini("immagine")
    immagini = [volti.leggi(dati) for dati in scatti]
    risposta = _riconosci_con(immagini, suoi, modello, soglia)
    altri = _alla_porta_con_l_altro(immagini, attesi, modello) if _anche_l_altro() else {}

    respinti = risposta["respinti_da_minifasnet"]
    # Lo sconosciuto si porta dietro il suo punteggio: uno 0,05 e' un falso
    # rilevamento, uno 0,35 e' un ospite ripreso male e dice che la soglia
    # e' un filo alta. Senza il numero i due casi si confondono.
    fuori = ["%.2f su %d px" % (s["somiglianza_migliore"], s["larghezza_px"])
             for s in risposta["sconosciuti"]]
    # **Nel log non entra nessun nome.** Al suo posto il numero dell'atteso, cioe'
    # il suo posto nella lista arrivata con la richiesta. Il registro dell'add-on
    # e' la terza superficie dopo il quaderno delle prove e l'invio a Home
    # Assistant, ed era rimasta aperta: si legge dall'interfaccia, finisce nei
    # log che si mandano quando si chiede aiuto, e la macchina dell'add-on non
    # deve tenere i nomi (#20). Chi ha mandato la lista sa rileggere i numeri.
    log.info("riconosci (%s): %d facce in %d scatti, riconosciuti %s, sconosciuti %d %s, persone in piu' %d%s%s",
             modello, risposta["volti_trovati"], len(scatti),
             ["#%d %.3f" % (r["posizione"], r["somiglianza"]) for r in risposta["riconosciuti"]],
             len(fuori), fuori, risposta["persone_in_piu"],
             (", ma MiniFASNet respinge %s" % _numeri(respinti)) if respinti else "",
             "".join(_detto_alla_porta(n, d) for n, d in altri.items()))
    risposta.update({
        "scatti": len(scatti),
        "altri_modelli": altri,
        "millisecondi": _millisecondi(partenza),
    })
    # Nel registro i nomi non entrano (li toglie lui), restano i punteggi: sono
    # quelli a dire se la soglia alla porta e' quella giusta. E vale la stessa
    # risposta data prima del confronto: la porta non e' una seconda domanda.
    risposta["prova_mandata"] = _registra(
        "riconosci", dict(risposta,
                          presenti=_presenti(),
                          quanti_riconosciuti=len(risposta["riconosciuti"])))
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


def _detta_validita(validita):
    """La scadenza come si legge nel registro. Niente date se non si sa niente."""
    if validita.get("scaduto") is None:
        return "scadenza non giudicabile"
    if validita["scaduto"]:
        return "SCADUTO da %d giorni" % abs(validita["giorni"])
    return "valido per altri %d giorni" % validita["giorni"]


# Cosa deve dire la banda ottica quando l'ospite ha gia' dichiarato che
# documento ha. Il formato e' la conferma indipendente: la lettera da sola si
# puo' leggere male, il formato no, perche' viene dal numero e dalla lunghezza
# delle righe.
ATTESO_PER_TIPO = {"passaporto": ("TD3", "P"), "carta": ("TD1", "I")}


def _raddrizza_il_tipo(esito, dichiarato):
    """La lettera del tipo documento non ha nessuna cifra di controllo.

    Quindi una `P` letta come `F` passa senza che niente si accorga, e il
    documento diventa "non riconosciuto" con l'ospite che si vede scritta una
    lettera sbagliata addosso. Successo davvero, su un passaporto vero, il 20
    agosto 2026.

    La correzione non e' un'ipotesi: l'ospite **ha gia' dichiarato** che
    documento ha, prima ancora di fotografarlo, e il formato della banda lo
    conferma per una strada indipendente dalla lettera. Quando quelle due cose
    concordano fra loro e la lettera no, e' la lettera a essere sbagliata.
    """
    atteso = ATTESO_PER_TIPO.get(dichiarato or "")
    if not atteso:
        return esito
    formato, lettera = atteso
    if esito.get("formato") != formato:
        # Dichiarato e fotografato non coincidono: qui non si raddrizza niente,
        # si dice che non coincidono e decide chi guarda.
        esito["il_formato_non_torna"] = "dichiarato %s, letto %s" % (dichiarato, esito.get("formato"))
        return esito
    campo = (esito.get("campi") or {}).get("tipo_documento") or {}
    if str(campo.get("valore", ""))[:1] == lettera:
        return esito
    esito["tipo_letto_male"] = campo.get("valore")
    campo["valore"] = lettera
    esito["sigla_documento"] = lettera
    esito["tipo_documento"] = mrz.TIPI.get(lettera, esito.get("tipo_documento"))
    return esito


def _dal_testo(testo, dichiarato):
    """Quello che il testo stampato sa dire, secondo il documento che si guarda.

    Sulla patente i campi sono **numerati**, e il numero sopravvive alla lettura
    meglio di un'etichetta scritta. Sugli altri due i luoghi hanno un'etichetta
    scritta accanto, e si va a cercare quella.

    Le date restano sempre quelle riconosciute dal giorno e mese che hanno in
    comune: e' un controllo piu' forte di qualunque ancoraggio, e per questo non
    si lascia sovrascrivere.
    """
    dalla_forma = ottico.proponi(testo)
    if dichiarato == "patente":
        return dict(ottico.dalla_patente(testo), **dalla_forma)
    return dict(ottico.dalle_etichette(testo), **dalla_forma)


@app.route("/mrz", methods=["POST"])
def leggi_mrz():
    """Le righe di caratteri in fondo al documento, e cosa dicono.

    Torna anche quali campi hanno passato la loro cifra di controllo: sono i
    soli che si possono scrivere nel modulo senza farli ricontrollare a mano.
    """
    partenza = time.time()
    dichiarato = _campo("tipo_dichiarato")
    try:
        esito = mrz.analizza_altrove(_immagine("immagine"),
                                     anche_ottico=bool(OPZIONI["lettura_ottica"]),
                                     # La patente la banda ottica non ce l'ha:
                                     # non si cerca, e si risparmiano le due
                                     # passate della lettura.
                                     anche_banda=dichiarato != "patente")
    except mrz.NessunaMRZ as guaio:
        # **Una lettura che non riesce lascia una riga come tutte le altre.**
        # Prima non ne lasciava nessuna, perche' l'errore saltava il punto in cui
        # si scrive: su un documento senza banda ottica, cioe' la patente, quello
        # e' il caso normale e restava invisibile. Senza questa riga non si sa
        # nemmeno se la lettura del testo stampato ha girato.
        testo = getattr(guaio, "testo_stampato", [])
        proposti = _dal_testo(testo, dichiarato)
        millisecondi = _millisecondi(partenza)
        # Quante date sono state trovate nel testo: e' il numero che dice perche'
        # non si e' proposto niente, e senza di lui resta da indovinare.
        log.info("mrz: non letta (%s), righe stampate %d, date %d, campi proposti %d, %d ms, memoria %s MB",
                 guaio, len(testo), len(ottico.DATA.findall(" ".join(testo))),
                 len(proposti), millisecondi, _memoria_mb())
        _registra("mrz", {"formato": None, "affidabile": False,
                          "righe_stampate": len(testo), "quanti_proposti": len(proposti),
                          "millisecondi": millisecondi})
        return jsonify({"errore": str(guaio), "testo_stampato": testo,
                        "campi_proposti": proposti,
                        "millisecondi": millisecondi}), 422
    esito = _raddrizza_il_tipo(esito, dichiarato)
    # Nel campo che l'ospite legge ci va il nome per esteso, non la lettera
    # dello standard: "Passaporto", non "P". La lettera resta in
    # 'sigla_documento', dove serve.
    campo_tipo = (esito.get("campi") or {}).get("tipo_documento")
    if campo_tipo and esito.get("tipo_documento"):
        campo_tipo["valore"] = esito["tipo_documento"]
    # **Anche la lettura riuscita porta quello che ha letto in chiaro.** La
    # banda ottica il comune di nascita e la residenza non ce li ha, e sono
    # stampati sulla stessa carta: buttarli perche' la banda ha funzionato
    # vorrebbe dire perdere proprio i campi che alla banda mancano. Quello che
    # la banda gia' dice non si tocca, perche' ha le cifre di controllo dietro.
    letti = _dal_testo(esito.get("testo_stampato") or [], dichiarato)
    esito["campi_proposti"] = {c: v for c, v in letti.items()
                               if c not in (esito.get("campi") or {})}
    esito["millisecondi"] = _millisecondi(partenza)
    validita = esito.get("validita") or {}
    log.info("mrz: %s, seconda passata %s, campi da correggere %s, %s, memoria %s MB",
             esito["formato"], esito["seconda_passata"], esito["da_correggere"],
             _detta_validita(validita), _memoria_mb())
    # Nel quaderno va **una riga costruita a mano**, non l'esito intero: dentro
    # ci sono i campi del documento e le righe di caratteri, cioe' il nome e il
    # cognome di una persona. Allungare la lista dei vietati sarebbe il modo per
    # dimenticarsene il giorno che l'esito cresce di un campo.
    esito["prova_mandata"] = _registra("mrz", {
        "formato": esito.get("formato"),
        "seconda_passata": esito.get("seconda_passata"),
        "affidabile": esito.get("affidabile"),
        "quanti_da_correggere": len(esito.get("da_correggere") or []),
        "tipo_letto_male": bool(esito.get("tipo_letto_male")),
        "righe_stampate": len(esito.get("testo_stampato") or []),
        "da_correggere": esito.get("da_correggere"),
        "scaduto": validita.get("scaduto"),
        "millisecondi": esito["millisecondi"],
    })
    return jsonify(esito)


@app.route("/corretti", methods=["POST"])
def corretti():
    """Quanti campi la persona ha dovuto correggere a mano dopo la lettura.

    E' la misura che serve a #7 e non si puo' ricavare da nessun'altra parte:
    le cifre di controllo dicono quali campi **la macchina** sospetta, questo
    dice quali erano **davvero** sbagliati, compresi quelli che una cifra di
    controllo non ce l'hanno e passano inosservati.

    Numeri e basta: quanti, non quali valori.
    """
    quanti = _campo("campi_corretti")
    return jsonify({"prova_mandata": _registra("corretti", {
        "quanti_corretti": int(quanti) if str(quanti).isdigit() else 0,
        "sigla_documento": _campo("tipo_documento"),
    })})


def _fermati(*_):
    """Quando ci dicono di chiudere, si chiude subito.

    Dentro il contenitore questo processo e' il numero uno, e il numero uno
    ignora di suo la richiesta di fermarsi: senza questa riga il Supervisor
    aspetta dieci secondi, poi ammazza il processo e scrive un errore nel log.
    Succedeva a **ogni** aggiornamento, ed erano dieci secondi e un errore rosso
    ogni volta.

    Si esce di netto invece che per la via ordinata perche' non c'e' niente da
    chiudere: il quaderno delle prove si apre e si chiude a ogni riga, i modelli
    sono in memoria e la memoria la riprende il sistema.
    """
    log.info("mi hanno chiesto di fermarmi, chiudo")
    os._exit(0)


if __name__ == "__main__":
    porta = int(os.environ.get("PORTA", 8099))
    signal.signal(signal.SIGTERM, _fermati)
    threading.Thread(target=_guardiano, daemon=True).start()
    log.info("in ascolto sulla porta %d, soglia %.2f, memoria %s MB",
             porta, float(OPZIONI["soglia"]), _memoria_mb())
    serve(app, host="0.0.0.0", port=porta, threads=2)
