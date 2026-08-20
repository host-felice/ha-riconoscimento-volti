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
import re

import cv2
import numpy as np

# Mille pixel di lato lungo. Sotto non si guadagna piu' tempo e si comincia a
# perdere caratteri: misurato su due N4000, 7,93 s a 1000 px contro 7,74 a 800.
LATO = 1000

# **Quando non c'e' una banda ottica da leggere, si puo' guardare piu' da
# vicino.** Il 1000 li' sopra era stato scelto quando ogni lettura pagava anche
# le due passate della banda: il tetto era il tempo, non la resa. Su una patente
# quelle passate non ci sono piu' (misurato il 20 agosto 2026: da 24,9 secondi a
# 5,2) e i venti secondi liberati si spendono meglio in pixel. Serve: nella
# stessa prova, delle tre date stampate sulla patente ne era stata letta **una**,
# e sono la riga piu' piccola del documento.
LATO_LARGO = 1600

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


def righe(dati_binari, lato=LATO):
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
    esito, _ = RapidOCR()(rimpicciolisci(img, lato))
    # Del riquadro non ce ne facciamo niente finche' i campi non si estraggono,
    # e portarlo in giro sarebbe peso.
    return [testo.strip() for _, testo, fiducia in (esito or [])
            if float(fiducia) >= FIDUCIA_MINIMA and testo.strip()]


# Una data stampata: due cifre, due cifre, quattro cifre, separate come capita.
DATA = re.compile(r"\b(\d{2})[.,/\- ](\d{2})[.,/\- ](\d{4})\b")

# Quante date porta stampate una patente italiana: nascita, rilascio, scadenza,
# in quest'ordine dall'alto verso il basso.
DATE_DELLA_PATENTE = 3


def proponi(righe):
    """I campi che si possono proporre dal testo stampato, e come si sanno.

    **Si propone solo quello che si riconosce dalla forma**, non quello che sta
    accanto a un'etichetta. Le etichette stampate l'OCR se le sfilaccia
    (`LUOGOFDATADENASOTA`, misurato il 20 agosto 2026) mentre i valori li legge
    bene: cercare "quello dopo la scritta Nato il" vuol dire appoggiarsi proprio
    al pezzo che si rompe.

    **E solo quando il conto torna esatto.** Una patente porta tre date stampate
    e sempre nello stesso ordine: nascita, rilascio, scadenza. Se se ne trovano
    tre, quelle sono. Se se ne trovano due o quattro e' successo qualcos'altro, e
    allora non si propone niente invece di indovinare.

    ## La regola che rende verificabile una lettura che non lo era

    Detta da Felice il 20 agosto 2026, e viene da una prova vera: al primo scatto
    la lettura aveva sbagliato **il giorno di nascita** e letto bene la scadenza.

    Sui documenti italiani, carta d'identita' e patente, **la scadenza cade nello
    stesso giorno e mese della data di nascita**: cambia solo l'anno. Sono lo
    stesso dato scritto due volte in due punti diversi del documento, ed e' la
    stessa cosa che fanno le cifre di controllo della banda ottica.

    E le due letture non sono ugualmente difficili: **la scadenza e' stampata piu'
    grande**, quindi si legge meglio. Quindi quando le due non concordano si tiene
    il giorno e il mese della scadenza e si corregge la data di nascita, che e' la
    lettura debole, tenendole il suo anno.

    Quando invece concordano si sono verificate a vicenda, e allora non si
    mostrano col bordo rosso: nessuno le deve ricontrollare a mano.
    """
    date = ["%s/%s/%s" % (g, m, a) for g, m, a in DATA.findall(" ".join(righe))]
    if len(date) != DATE_DELLA_PATENTE:
        return {}
    nascita, scadenza = date[0], date[2]
    concordano = nascita[:5] == scadenza[:5]
    if not concordano:
        # Il giorno e il mese buoni sono quelli della scadenza, l'anno resta
        # quello della nascita: e' l'unico pezzo che la scadenza non sa.
        nascita = scadenza[:6] + nascita[6:]
    return {
        # La scadenza si e' letta bene di suo, e se le due concordano si sono
        # anche confermate a vicenda: in tutti e due i casi non c'e' niente da
        # far ricontrollare.
        "scadenza": {"valore": scadenza, "verificato": True},
        # La data di nascita e' verificata solo quando le due concordavano gia'.
        # Se e' stata corretta resta da guardare: l'anno nessuno lo ha
        # controllato, e la correzione poggia su una regola, non su una lettura.
        "data_nascita": {"valore": nascita, "verificato": concordano},
    }
