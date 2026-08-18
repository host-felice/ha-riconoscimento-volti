# -*- coding: utf-8 -*-
"""Le due o tre righe di caratteri in fondo al documento, lette e verificate.

Leggerle e' un lavoro da modello, e lo fa MRZScanner. Capire cosa dicono e'
aritmetica scritta nello standard ICAO 9303, e la facciamo qui: ogni campo
importante porta con se' una cifra di controllo, e quella cifra dice se il
campo si puo' usare o va fatto correggere all'ospite.
"""
import gc
import threading
import time

import cv2
import numpy as np

PESI = (7, 3, 1)

# Due misure: si prova alla prima, e solo se qualcosa non torna si rifa' con
# piu' pixel. La seconda costa il doppio del tempo, quindi non e' di serie.
LATO_PRIMO = 2000
LATO_SECONDO = 3500

# I tre formati previsti dallo standard, riconosciuti da quante righe sono
# e da quanto sono lunghe.
FORMATI = {
    (3, 30): "TD1",   # carta d'identita' elettronica
    (2, 36): "TD2",   # documenti di viaggio piccoli
    (2, 44): "TD3",   # passaporto
}

# La prima lettera dice che documento e', secondo lo standard. Il resto della
# sigla cambia da paese a paese e non serve a noi.
TIPI = {
    "P": "passaporto",
    "I": "carta d'identita'",
    "A": "carta d'identita'",
    "C": "carta d'identita'",
    "V": "visto",
    "D": "patente",
}

_lettore = None
_ultimo_uso = 0.0
_serratura = threading.Lock()
MINUTI_DI_PAZIENZA = 10


class NessunaMRZ(Exception):
    pass


class LettoreAssente(Exception):
    pass


def _lettore_pronto():
    """Il modello si carica alla prima richiesta, non all'avvio.

    Sono trecento megabyte di roba: chi usa solo il riconoscimento dei volti
    non deve pagarli.
    """
    global _lettore, _ultimo_uso
    with _serratura:
        if _lettore is None:
            try:
                from mrzscanner import MRZScanner
                _lettore = MRZScanner()
            except Exception as guaio:
                raise LettoreAssente("il lettore della MRZ non si carica: %s" % guaio)
        _ultimo_uso = time.time()
        return _lettore


def restituisci_memoria():
    """Chiede alla libreria di sistema di ridare al sistema quello che avanza.

    Python libera la memoria ma la tiene per se': su un servizio che sta acceso
    per settimane la differenza si vede nel conto dell'add-on, non nel codice.
    """
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass


def libera_se_inattivo():
    """Scarica il lettore della MRZ se non lo cerca nessuno da un po'.

    Sono centinaia di megabyte per un lavoro che capita due volte a
    prenotazione: tenerli occupati tutto l'anno non ha senso. Si ricarica da
    solo alla richiesta dopo, in pochi secondi.
    """
    global _lettore
    with _serratura:
        if _lettore is None or time.time() - _ultimo_uso < MINUTI_DI_PAZIENZA * 60:
            return False
        _lettore = None
    restituisci_memoria()
    return True


def cifra_di_controllo(testo):
    """La cifra che chiude un campo, secondo ICAO 9303.

    Ogni carattere vale qualcosa (le cifre se stesse, le lettere da 10 in su,
    il riempitivo zero), si moltiplica per 7, 3, 1 a giro e si prende il resto
    della divisione per dieci.
    """
    somma = 0
    for posto, carattere in enumerate(testo):
        if carattere.isdigit():
            valore = int(carattere)
        elif "A" <= carattere <= "Z":
            valore = ord(carattere) - 55
        elif carattere == "<":
            valore = 0
        else:
            return None
        somma += valore * PESI[posto % 3]
    return str(somma % 10)


def _campo(valore, atteso=None, sorgente=None):
    """Un campo letto, con il verdetto della sua cifra di controllo.

    verificato vale True se torna, False se non torna, None se quel campo una
    cifra di controllo non ce l'ha e quindi nessuno puo' garantirlo.
    """
    verificato = None
    if atteso is not None:
        verificato = cifra_di_controllo(sorgente) == atteso
    return {"valore": valore, "verificato": verificato}


def _nomi(pezzo):
    """Cognome e nome dalla parte dei nomi: separati da due riempitivi."""
    pezzo = pezzo.rstrip("<")
    if "<<" in pezzo:
        cognome, resto = pezzo.split("<<", 1)
    else:
        cognome, resto = pezzo, ""
    return cognome.replace("<", " ").strip(), resto.replace("<", " ").strip()


def _pulisci(valore):
    return valore.replace("<", "").strip()


def _data(sei_cifre):
    """AAMMGG cosi' com'e', piu' la stessa data scritta per una persona."""
    if len(sei_cifre) != 6 or not sei_cifre.isdigit():
        return sei_cifre
    return "%s/%s/%s" % (sei_cifre[4:6], sei_cifre[2:4], sei_cifre[0:2])


def _td3(righe):
    prima, seconda = righe
    cognome, nome = _nomi(prima[5:44])
    numero = seconda[0:9]
    nascita = seconda[13:19]
    scadenza = seconda[21:27]
    facoltativo = seconda[28:42]
    finale = seconda[0:10] + seconda[13:20] + seconda[21:43]
    return {
        "tipo_documento": _campo(_pulisci(prima[0:2])),
        "stato_emissione": _campo(_pulisci(prima[2:5])),
        "cognome": _campo(cognome),
        "nome": _campo(nome),
        "numero_documento": _campo(_pulisci(numero), seconda[9], numero),
        "cittadinanza": _campo(_pulisci(seconda[10:13])),
        "data_nascita": _campo(_data(nascita), seconda[19], nascita),
        "sesso": _campo(_pulisci(seconda[20])),
        "scadenza": _campo(_data(scadenza), seconda[27], scadenza),
        "numero_personale": _campo(_pulisci(facoltativo), seconda[42], facoltativo),
        "tutto_insieme": _campo("", seconda[43], finale),
    }


def _td2(righe):
    prima, seconda = righe
    cognome, nome = _nomi(prima[5:36])
    numero = seconda[0:9]
    nascita = seconda[13:19]
    scadenza = seconda[21:27]
    finale = seconda[0:10] + seconda[13:20] + seconda[21:35]
    return {
        "tipo_documento": _campo(_pulisci(prima[0:2])),
        "stato_emissione": _campo(_pulisci(prima[2:5])),
        "cognome": _campo(cognome),
        "nome": _campo(nome),
        "numero_documento": _campo(_pulisci(numero), seconda[9], numero),
        "cittadinanza": _campo(_pulisci(seconda[10:13])),
        "data_nascita": _campo(_data(nascita), seconda[19], nascita),
        "sesso": _campo(_pulisci(seconda[20])),
        "scadenza": _campo(_data(scadenza), seconda[27], scadenza),
        "tutto_insieme": _campo("", seconda[35], finale),
    }


def _td1(righe):
    prima, seconda, terza = righe
    cognome, nome = _nomi(terza)
    numero = prima[5:14]
    nascita = seconda[0:6]
    scadenza = seconda[8:14]
    finale = prima[5:30] + seconda[0:7] + seconda[8:15] + seconda[18:29]
    return {
        "tipo_documento": _campo(_pulisci(prima[0:2])),
        "stato_emissione": _campo(_pulisci(prima[2:5])),
        "cognome": _campo(cognome),
        "nome": _campo(nome),
        "numero_documento": _campo(_pulisci(numero), prima[14], numero),
        "numero_supporto": _campo(_pulisci(prima[15:30])),
        "data_nascita": _campo(_data(nascita), seconda[6], nascita),
        "sesso": _campo(_pulisci(seconda[7])),
        "scadenza": _campo(_data(scadenza), seconda[14], scadenza),
        "cittadinanza": _campo(_pulisci(seconda[15:18])),
        "tutto_insieme": _campo("", seconda[29], finale),
    }


def interpreta(righe):
    """Dalle righe grezze ai campi, o l'ammissione che non si capisce cosa sono."""
    righe = [r.strip().upper() for r in righe if r and r.strip()]
    formato = FORMATI.get((len(righe), len(righe[0]) if righe else 0))
    if formato is None:
        raise NessunaMRZ("le righe lette non hanno una forma prevista dallo standard: %s"
                         % [len(r) for r in righe])
    campi = {"TD1": _td1, "TD2": _td2, "TD3": _td3}[formato](righe)
    return formato, campi


def _apri(dati_binari):
    img = cv2.imdecode(np.frombuffer(dati_binari, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise NessunaMRZ("immagine illeggibile")
    return img


def _rimpicciolisci(img, lato_lungo):
    h, w = img.shape[:2]
    scala = float(lato_lungo) / max(h, w)
    if scala >= 1:
        return img
    return cv2.resize(img, (int(w * scala), int(h * scala)), interpolation=cv2.INTER_AREA)


def _righe(img):
    esito = _lettore_pronto()(img, do_center_crop=False, do_postprocess=True)
    righe = [r for r in (esito.get("mrz_texts") or []) if r.strip()]
    if not righe:
        raise NessunaMRZ("nessuna zona leggibile a macchina trovata nella foto")
    return righe


def analizza(dati_binari):
    """La lettura completa, con una seconda occasione se la prima non torna.

    Sulla carta d'identita' i caratteri sono piccoli: fotografata da lontano
    finiscono a una decina di pixel e il lettore tira a indovinare. Quando le
    cifre di controllo lo smentiscono si rifa' il giro con piu' pixel, che e'
    l'unica cosa che cambia davvero il risultato.
    """
    img = _apri(dati_binari)
    migliore = None
    guaio = None
    for lato in (LATO_PRIMO, LATO_SECONDO):
        try:
            righe = _righe(_rimpicciolisci(img, lato))
            formato, campi = interpreta(righe)
        except NessunaMRZ as questo:
            guaio = questo
            if max(img.shape[:2]) <= lato:
                break
            continue
        sbagliati = [c for c, v in campi.items() if v["verificato"] is False]
        sigla = campi["tipo_documento"]["valore"]
        esito = {
            "formato": formato,
            "tipo_documento": TIPI.get(sigla[:1], "documento non riconosciuto"),
            "sigla_documento": sigla,
            "righe": righe,
            "campi": campi,
            "da_correggere": sbagliati,
            "affidabile": not sbagliati,
            "seconda_passata": lato != LATO_PRIMO,
        }
        if not sbagliati:
            return esito
        if migliore is None:
            migliore = esito
        if max(img.shape[:2]) <= lato:
            break
    if migliore is not None:
        return migliore
    raise guaio or NessunaMRZ("nessuna zona leggibile a macchina trovata nella foto")
