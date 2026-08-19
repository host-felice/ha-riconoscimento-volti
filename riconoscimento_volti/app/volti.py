# -*- coding: utf-8 -*-
"""Il pezzo che sa di facce: le trova, le trasforma in numeri, le confronta.

Nessun database, nessuno stato. Chi chiama decide cosa farne.

I modelli che trasformano una faccia in numeri sono **due**, e si sceglie quale
usare. Non e' indecisione: buffalo_l separa meglio ma e' dichiarato per sola
ricerca non commerciale, SFace e' Apache 2.0 e costa un terzo della memoria.
Tenerli tutti e due permette di misurarli sulle stesse facce mentre il progetto
va avanti, invece di scegliere adesso su ventuno confronti.

**I numeri di un modello non valgono per l'altro.** Un vettore fatto da SFace
confrontato con uno fatto da buffalo_l da' un risultato che non vuol dire
niente, e non se ne accorgerebbe nessuno. Per questo ogni vettore si porta
dietro il nome di chi lo ha fatto.
"""
import os
import threading
import time

import numpy as np
import cv2

MODELLI = os.environ.get("MODELLI", "/modelli")
YUNET = os.path.join(MODELLI, "yunet.onnx")

# Per ognuno: il file, la soglia sua, e quanto e' costato misurarlo il 19
# agosto 2026 sulle foto del banco di prova.
CATALOGO = {
    "buffalo_l": {
        "file": "w600k_r50.onnx",
        "soglia": 0.40,      # scelta sulle prove del 18 agosto 2026
        "memoria_mb": 331,
        "millisecondi": 259,
    },
    "sface": {
        "file": "sface.onnx",
        "soglia": 0.363,     # quella consigliata da OpenCV per questo modello
        "memoria_mb": 135,
        "millisecondi": 69,
    },
}
PREDEFINITO = "buffalo_l"

# Dove stanno occhi, naso e bocca in un ritaglio 112x112, secondo ArcFace.
# Serve a raddrizzare la faccia prima di misurarla: senza, una foto storta
# vale meno di quanto vale davvero.
RIFERIMENTO = np.array([
    [38.2946, 51.6963],   # occhio sinistro nell'immagine
    [73.5318, 51.5014],   # occhio destro
    [56.0252, 71.7366],   # naso
    [41.5493, 92.3655],   # angolo sinistro della bocca
    [70.7299, 92.2041],   # angolo destro
], dtype=np.float32)

LATO_LUNGO_MAX = 1600     # oltre non serve, e le foto dei telefoni sono enormi
LATO_SECONDA_PASSATA = 640
FIDUCIA_MINIMA = 0.6

_reti = {}
_ultimo_uso = {}
# Quanto e' costata l'ultima apertura, per saperlo invece che stimarlo.
secondi_ultima_apertura = None
# Una richiesta alla volta dentro la rete: il server ne serve piu' di una insieme
# e questa non e' fatta per essere usata da due parti nello stesso momento.
_una_alla_volta = threading.Lock()

# Dopo quanto silenzio il modello si chiude. Fra un check-in e l'altro passano
# giorni, dentro un check-in le richieste sono a raffica: venti minuti stanno
# larghi nel primo caso e non si fanno mai sentire nel secondo.
MINUTI_DI_PAZIENZA = 20


def percorso(modello):
    return os.path.join(MODELLI, CATALOGO[modello]["file"])


def disponibile(modello):
    return modello in CATALOGO and os.path.exists(percorso(modello))


def _rete_pronta(modello):
    """Il modello si apre alla prima faccia, non all'avvio.

    All'avvio il file verrebbe solo letto, e per buffalo_l sarebbero
    centosessanta megabyte. Le aree di lavoro dei suoi strati nascono alla
    prima misurazione e sono il conto vero: si pagano solo quando servono.
    Da chiamare con la serratura gia' presa.

    Chi si apre resta aperto: se si misurano tutti e due i modelli sulla stessa
    faccia, la memoria e' la somma. Se ne apre uno solo quando se ne chiede uno.
    """
    global secondi_ultima_apertura
    if modello not in _reti:
        partenza = time.time()
        if modello == "sface":
            _reti[modello] = cv2.FaceRecognizerSF.create(percorso(modello), "")
        else:
            _reti[modello] = cv2.dnn.readNetFromONNX(percorso(modello))
        secondi_ultima_apertura = round(time.time() - partenza, 2)
    _ultimo_uso[modello] = time.time()
    return _reti[modello]


def chiudi_se_inattiva():
    """Chiude i modelli che non cerca piu' nessuno da un po'.

    Si riaprono da soli alla richiesta dopo. Quella richiesta paga qualche
    secondo in piu', ed e' il motivo per cui la pazienza e' lunga: alla porta
    l'ospite sta aspettando.
    """
    chiusi = []
    with _una_alla_volta:
        for nome in list(_reti):
            if time.time() - _ultimo_uso.get(nome, 0) >= MINUTI_DI_PAZIENZA * 60:
                del _reti[nome]
                chiusi.append(nome)
    return chiusi


class NessunVolto(Exception):
    pass


class ModelliDiversi(Exception):
    """Due vettori fatti da modelli diversi: il confronto non vorrebbe dire niente."""
    pass


def _rimpicciolisci(img, lato_lungo):
    """L'immagine rimpicciolita e di quanto: uno se era gia' abbastanza piccola."""
    h, w = img.shape[:2]
    scala = float(lato_lungo) / max(h, w)
    if scala >= 1:
        return img, 1.0
    piccola = cv2.resize(img, (int(w * scala), int(h * scala)), interpolation=cv2.INTER_AREA)
    return piccola, scala


def leggi(dati_binari):
    """I byte di una foto diventano un'immagine. Un'immagine gia' aperta passa.

    Il passaggio serve a chi deve guardare due volte la stessa foto (le facce
    e poi MiniFASNet): aprire un JPEG da dodici megapixel costa, e farlo due
    volte costa il doppio per niente.
    """
    if isinstance(dati_binari, np.ndarray):
        return dati_binari
    img = cv2.imdecode(np.frombuffer(dati_binari, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise NessunVolto("immagine illeggibile")
    return _rimpicciolisci(img, LATO_LUNGO_MAX)[0]


def trova_volti(img, volto_minimo_px=80):
    """Tutti i volti, dal piu' grande al piu' piccolo, gia' scartati i troppo piccoli.

    Il filtro sulla dimensione non e' un dettaglio: sulle pagine dei documenti
    il rilevatore trova anche macchie da quindici pixel che facce non sono.
    """
    h, w = img.shape[:2]
    det = cv2.FaceDetectorYN.create(YUNET, "", (w, h), FIDUCIA_MINIMA, 0.3, 5000)
    _, grezzi = det.detect(img)
    volti = []
    if grezzi is not None:
        for r in grezzi:
            x, y, bw, bh = [float(v) for v in r[0:4]]
            if bw < volto_minimo_px:
                continue
            volti.append({
                "riquadro": [int(x), int(y), int(bw), int(bh)],
                "punti": r[4:14].reshape(5, 2).astype(np.float32),
                # La riga com'e' uscita dal rilevatore: SFace si allinea da solo
                # e la vuole tutta, non solo i cinque punti.
                "riga": r.copy(),
                "fiducia": round(float(r[14]), 3),
                "larghezza_px": int(bw),
            })
    volti.sort(key=lambda v: -v["larghezza_px"])
    return volti


def vettore(img, volto, modello=PREDEFINITO):
    """La faccia raddrizzata diventa numeri di lunghezza uno.

    I due modelli raddrizzano in modo diverso e non si puo' fare a meta': SFace
    porta il suo allineamento dentro la libreria, buffalo_l vuole i cinque punti
    portati sopra le posizioni di riferimento. Il risultato e' un vettore per
    ognuno, e i due non si parlano.
    """
    with _una_alla_volta:
        rete = _rete_pronta(modello)
        if modello == "sface":
            ritaglio = rete.alignCrop(img, np.array([volto["riga"]], dtype=np.float32))
            v = rete.feature(ritaglio).flatten()
        else:
            M, _ = cv2.estimateAffinePartial2D(volto["punti"], RIFERIMENTO,
                                               method=cv2.LMEDS)
            ritaglio = cv2.warpAffine(img, M, (112, 112), borderValue=0)
            blob = cv2.dnn.blobFromImage(ritaglio, 1.0 / 127.5, (112, 112),
                                         (127.5, 127.5, 127.5), swapRB=True)
            rete.setInput(blob)
            v = rete.forward().flatten()
    return v / np.linalg.norm(v)


def inclinazione(volto):
    """Di quanti gradi e' storta la faccia, misurata sulla linea degli occhi.

    Serve a distinguere due fallimenti che il punteggio confonde: una persona
    diversa e una foto fatta male. Un documento fotografato di sbieco si vede da
    qui, e all'ospite si puo' chiedere di rifarla dritta invece di respingerlo.
    """
    (sx, sy), (dx, dy) = volto["punti"][0], volto["punti"][1]
    # float() e' obbligatorio: numpy restituisce un suo numero, che poi non sa
    # diventare JSON e fa cadere la risposta invece del calcolo.
    return round(float(abs(np.degrees(np.arctan2(dy - sy, dx - sx)))), 1)


def _ingrandisci(volto, fattore):
    """Riporta un volto trovato sulla copia piccola alle misure dell'immagine vera."""
    x, y, bw, bh = volto["riquadro"]
    volto["riquadro"] = [int(x * fattore), int(y * fattore),
                         int(bw * fattore), int(bh * fattore)]
    volto["punti"] = volto["punti"] * fattore
    # Anche la riga grezza, altrimenti SFace allineerebbe sulle misure sbagliate.
    volto["riga"][0:14] = volto["riga"][0:14] * fattore
    volto["larghezza_px"] = int(bw * fattore)
    return volto


def tutti_i_volti(dati_binari, volto_minimo_px=80, modello=PREDEFINITO):
    """Ogni faccia dell'immagine con il suo vettore, dalla piu' grande in giu'.

    Serve alla porta: gli ospiti di una prenotazione arrivano insieme, e uno
    scatto solo puo' contenerne quattro. La faccia piu' grande e' quella davanti,
    non necessariamente quella che ci interessa.
    """
    img = leggi(dati_binari)
    trovati = _cerca(img, volto_minimo_px)
    if not trovati:
        raise NessunVolto("nessun volto trovato")
    img_giusta, volti_trovati, seconda = trovati
    return [{
        "vettore": vettore(img_giusta, v, modello).tolist(),
        "modello": modello,
        "riquadro": v["riquadro"],
        "fiducia": v["fiducia"],
        "larghezza_px": v["larghezza_px"],
        "inclinazione_gradi": inclinazione(v),
        "seconda_passata": seconda,
    } for v in volti_trovati]


def _cerca(img, volto_minimo_px):
    """I volti dell'immagine, riprovando in piccolo se al primo giro non c'e' niente."""
    volti = trova_volti(img, volto_minimo_px)
    if volti:
        return img, volti, False
    piccola, scala = _rimpicciolisci(img, LATO_SECONDA_PASSATA)
    if scala >= 1:
        return None
    volti = [_ingrandisci(v, 1.0 / scala) for v in trova_volti(piccola, volto_minimo_px * scala)]
    return (img, volti, True) if volti else None


def volto_principale(dati_binari, volto_minimo_px=80, modello=PREDEFINITO):
    """Il volto piu' grande dell'immagine, con il suo vettore e i suoi vicini.

    Restituisce anche gli altri volti trovati: su un documento il secondo e'
    quasi sempre l'immagine fantasma, e chi chiama deve poterlo sapere.
    """
    img = leggi(dati_binari)
    trovati = trova_volti(img, volto_minimo_px)
    seconda_passata = False
    if not trovati:
        # Una faccia che riempie l'inquadratura il rilevatore non la vede: e'
        # tarato su facce da un centinaio di pixel, non da cinquecento. Si
        # riprova su una copia rimpicciolita, e le misure si riportano indietro.
        piccola, scala = _rimpicciolisci(img, LATO_SECONDA_PASSATA)
        if scala < 1:
            trovati = [_ingrandisci(v, 1.0 / scala)
                       for v in trova_volti(piccola, volto_minimo_px * scala)]
            seconda_passata = bool(trovati)
    if not trovati:
        raise NessunVolto("nessun volto trovato")
    principale = trovati[0]
    return {
        "vettore": vettore(img, principale, modello).tolist(),
        "modello": modello,
        "riquadro": principale["riquadro"],
        "fiducia": principale["fiducia"],
        "larghezza_px": principale["larghezza_px"],
        "inclinazione_gradi": inclinazione(principale),
        "volti_trovati": len(trovati),
        "altri_volti_px": [v["larghezza_px"] for v in trovati[1:]],
        "seconda_passata": seconda_passata,
    }


def somiglianza(a, b):
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    if a.shape != b.shape:
        raise ModelliDiversi(
            "vettori di lunghezza diversa (%d e %d): sono di due modelli diversi"
            % (a.size, b.size))
    return round(float(np.dot(a, b)), 4)
