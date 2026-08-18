# -*- coding: utf-8 -*-
"""Il pezzo che sa di facce: le trova, le trasforma in numeri, le confronta.

Due modelli, nessun database, nessuno stato. Chi chiama decide cosa farne.
"""
import os
import threading

import numpy as np
import cv2

MODELLI = os.environ.get("MODELLI", "/modelli")
YUNET = os.path.join(MODELLI, "yunet.onnx")
ARCFACE = os.path.join(MODELLI, "w600k_r50.onnx")

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

_rete = cv2.dnn.readNetFromONNX(ARCFACE)
# Una richiesta alla volta dentro la rete: il server ne serve piu' di una insieme
# e questa non e' fatta per essere usata da due parti nello stesso momento.
_una_alla_volta = threading.Lock()


class NessunVolto(Exception):
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
                "fiducia": round(float(r[14]), 3),
                "larghezza_px": int(bw),
            })
    volti.sort(key=lambda v: -v["larghezza_px"])
    return volti


def vettore(img, punti):
    """La faccia raddrizzata diventa 512 numeri di lunghezza uno."""
    M, _ = cv2.estimateAffinePartial2D(punti, RIFERIMENTO, method=cv2.LMEDS)
    ritaglio = cv2.warpAffine(img, M, (112, 112), borderValue=0)
    blob = cv2.dnn.blobFromImage(ritaglio, 1.0 / 127.5, (112, 112),
                                 (127.5, 127.5, 127.5), swapRB=True)
    with _una_alla_volta:
        _rete.setInput(blob)
        v = _rete.forward().flatten()
    return v / np.linalg.norm(v)


def _ingrandisci(volto, fattore):
    """Riporta un volto trovato sulla copia piccola alle misure dell'immagine vera."""
    x, y, bw, bh = volto["riquadro"]
    volto["riquadro"] = [int(x * fattore), int(y * fattore),
                         int(bw * fattore), int(bh * fattore)]
    volto["punti"] = volto["punti"] * fattore
    volto["larghezza_px"] = int(bw * fattore)
    return volto


def volto_principale(dati_binari, volto_minimo_px=80):
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
        "vettore": vettore(img, principale["punti"]).tolist(),
        "riquadro": principale["riquadro"],
        "fiducia": principale["fiducia"],
        "larghezza_px": principale["larghezza_px"],
        "volti_trovati": len(trovati),
        "altri_volti_px": [v["larghezza_px"] for v in trovati[1:]],
        "seconda_passata": seconda_passata,
    }


def somiglianza(a, b):
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    return round(float(np.dot(a, b)), 4)
