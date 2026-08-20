# -*- coding: utf-8 -*-
"""La lettura del testo stampato sul documento, quello fuori dalla banda ottica.

La banda ottica da' sei campi su quattordici. Le tre cose che mancano ad
Alloggiati Web (comune e provincia di nascita, luogo di rilascio) piu' la
residenza che chiede Ross1000 **sono stampate in chiaro** sulla stessa
fotografia che si scatta gia': non sono da inventare, sono da leggere.

Misurato il 20 agosto 2026 su documenti veri: le legge tutte e tre, su tutte le
fotografie, compresa una passata da WhatsApp. Sbaglia in un modo solo, si mangia
gli spazi, e sono le etichette stampate a sfilacciarsi, non i valori.

**Il tempo e' il vero costo:** 1,4 secondi su un portatile, **8 su un N4000**, ed
e' un pavimento: rimpicciolire la foto sotto i mille pixel non fa piu' scendere
niente. Quegli otto secondi non stanno sulla strada dell'ospite perche' la
lettura parte appena arriva la fotografia e finisce mentre lui si fa il selfie.

**Gira dentro il processo usa e getta della banda ottica**, non accanto al
servizio: stesso innesco, stesso viaggio, e i suoi 370 MB se ne vanno quando
quel processo muore. Aprire il modello a ogni lettura costa 0,6 secondi su un
N4000, misurati, e non sposta il conto.
"""
import cv2
import numpy as np

# Mille pixel di lato lungo. Sotto non si guadagna piu' tempo e si comincia a
# perdere caratteri: misurato su due N4000, 7,93 s a 1000 px contro 7,74 a 800.
LATO = 1000

# Sotto questo il pezzo di testo si butta. Non e' per la qualita' della lettura:
# e' che le etichette stampate e le decorazioni producono stringhe plausibili con
# poca fiducia, e in mezzo ai valori veri fanno solo rumore.
FIDUCIA_MINIMA = 0.5

def rimpicciolisci(img, lato_lungo):
    """Sta qui e non nel lettore della banda ottica perche' serve a tutti e due.

    Le due letture vogliono dimensioni diverse (mille pixel questa, duemila o
    tremilacinquecento quella), ma il conto e' lo stesso e non ha senso averne
    due copie.
    """
    h, w = img.shape[:2]
    scala = float(lato_lungo) / max(h, w)
    if scala >= 1:
        return img
    return cv2.resize(img, (int(w * scala), int(h * scala)), interpolation=cv2.INTER_AREA)


def righe(dati_binari):
    """Il testo stampato che si e' riusciti a leggere, riga per riga.

    Esce grezzo apposta. Trasformarlo nei campi di Alloggiati Web vuol dire
    cercare ogni valore negli elenchi chiusi della Polizia (7.898 comuni), ed e'
    un lavoro suo: qui si vede solo **cosa la macchina ha letto davvero**, che e'
    quello che serve per sapere se su questo documento la strada e' percorribile.

    Il motore si apre qui, ogni volta, e non si tiene da parte: questo modulo
    vive dentro il processo usa e getta che legge una fotografia sola e poi
    muore, quindi tenerlo in caldo non servirebbe mai a nessuno. Aprirlo costa
    0,6 secondi su un N4000, misurati.
    """
    from rapidocr_onnxruntime import RapidOCR

    img = cv2.imdecode(np.frombuffer(dati_binari, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return []
    esito, _ = RapidOCR()(rimpicciolisci(img, LATO))
    # Del riquadro non ce ne facciamo niente finche' i campi non si estraggono,
    # e portarlo in giro sarebbe peso.
    return [testo.strip() for _, testo, fiducia in (esito or [])
            if float(fiducia) >= FIDUCIA_MINIMA and testo.strip()]
