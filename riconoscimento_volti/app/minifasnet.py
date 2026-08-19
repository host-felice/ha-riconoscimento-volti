# -*- coding: utf-8 -*-
"""MiniFASNet: se davanti all'obiettivo c'era una persona o la sua fotografia.

Un modello solo, da 1,7 MB, che guarda un ritaglio da 80x80 pixel e risponde
con tre probabilita': persona vera, foto stampata, schermo. Non chiede niente
all'ospite: niente girare la testa, niente sorridere, nessun passaggio in piu'.

**Non va usato sulla foto di un documento.** La faccia stampata su una carta
d'identita' e' una fotografia per definizione, e questo modello la dichiarera'
falsa, giustamente. Serve sul selfie e sullo scatto della telecamera, cioe'
dove ci si aspetta una persona in carne e ossa.
"""
import os
import threading
import time

import numpy as np
import cv2

MODELLI = os.environ.get("MODELLI", "/modelli")
MINIFASNET = os.path.join(MODELLI, "minifasnet_v2.onnx")

# Il modello non guarda solo la faccia: guarda la faccia e quello che le sta
# intorno, perche' il bordo di un telefono o la grana della carta si vedono li'.
# 2,7 volte il riquadro e' il margine con cui e' stato addestrato: cambiarlo
# vuol dire dargli in pasto qualcosa che non ha mai visto.
MARGINE = 2.7
LATO = 80

_rete = None
_ultimo_uso = 0.0
secondi_ultima_apertura = None
_una_alla_volta = threading.Lock()

# La stessa pazienza del modello dei volti: fra un check-in e l'altro passano
# giorni, dentro un check-in le richieste sono a raffica.
MINUTI_DI_PAZIENZA = 20


def _rete_pronta():
    """Il modello si apre alla prima richiesta. Da chiamare con la serratura presa."""
    global _rete, _ultimo_uso, secondi_ultima_apertura
    if _rete is None:
        partenza = time.time()
        _rete = cv2.dnn.readNetFromONNX(MINIFASNET)
        secondi_ultima_apertura = round(time.time() - partenza, 2)
    _ultimo_uso = time.time()
    return _rete


def chiudi_se_inattiva():
    """Chiude il modello se non lo cerca nessuno da un po'. Si riapre da solo."""
    global _rete
    with _una_alla_volta:
        if _rete is None or time.time() - _ultimo_uso < MINUTI_DI_PAZIENZA * 60:
            return False
        _rete = None
    return True


def disponibile():
    """Se il file del modello c'e'. Senza, l'add-on lavora come prima."""
    return os.path.exists(MINIFASNET)


def _ritaglio(img, riquadro):
    """La faccia con il suo contorno, riportata dentro i bordi dell'immagine.

    Quando la faccia sta vicino a un bordo il margine non ci sta tutto: invece
    di riempire di nero, si sposta la finestra verso l'interno. Un bordo nero
    finto e' una cosa che il modello non ha mai visto in addestramento.
    """
    alt, larg = img.shape[:2]
    x, y, bw, bh = [float(v) for v in riquadro]
    scala = min(MARGINE, (alt - 1) / bh, (larg - 1) / bw)
    nuova_l, nuova_a = bw * scala, bh * scala
    cx, cy = x + bw / 2.0, y + bh / 2.0
    sx, sy = cx - nuova_l / 2.0, cy - nuova_a / 2.0
    dx, dy = sx + nuova_l, sy + nuova_a
    if sx < 0:
        dx -= sx
        sx = 0
    if sy < 0:
        dy -= sy
        sy = 0
    if dx > larg - 1:
        sx -= dx - (larg - 1)
        dx = larg - 1
    if dy > alt - 1:
        sy -= dy - (alt - 1)
        dy = alt - 1
    return img[int(max(sy, 0)):int(dy), int(max(sx, 0)):int(dx)]


def _probabilita(uscita):
    """Le tre uscite del modello come probabilita' che sommano a uno.

    Alcune conversioni in ONNX portano dentro l'ultimo passaggio, altre no, e
    applicarlo due volte schiaccerebbe i numeri senza che nessuno se ne accorga.
    Quindi si guarda com'e' fatta l'uscita invece di darlo per scontato.
    """
    v = np.asarray(uscita, dtype=np.float64).flatten()
    if v.min() >= 0 and abs(v.sum() - 1.0) < 1e-3:
        return v
    e = np.exp(v - v.max())
    return e / e.sum()


def misura(img, riquadro):
    """Quanto e' probabile che davanti all'obiettivo ci fosse una persona vera.

    Restituisce anche le due probabilita' di attacco separate, perche' dicono
    cose diverse: 'stampa' e' la fotografia sulla carta, 'schermo' e' il selfie
    mostrato dal telefono di un altro. Il secondo e' il caso che capita davvero.
    """
    ritaglio = _ritaglio(img, riquadro)
    if ritaglio.size == 0:
        raise ValueError("il ritaglio per MiniFASNet e' vuoto")
    blob = cv2.dnn.blobFromImage(ritaglio, 1.0 / 255.0, (LATO, LATO), swapRB=False)
    with _una_alla_volta:
        rete = _rete_pronta()
        rete.setInput(blob)
        p = _probabilita(rete.forward())
    return {
        "punteggio": round(float(p[0]), 4),
        "stampa": round(float(p[1]), 4),
        "schermo": round(float(p[2]), 4),
    }
