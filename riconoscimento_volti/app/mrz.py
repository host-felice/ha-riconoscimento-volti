# -*- coding: utf-8 -*-
"""Le due o tre righe di caratteri in fondo al documento, lette e verificate.

Leggerle e' un lavoro da modello, e lo fa MRZScanner. Capire cosa dicono e'
aritmetica scritta nello standard ICAO 9303, e la facciamo qui: ogni campo
importante porta con se' una cifra di controllo, e quella cifra dice se il
campo si puo' usare o va fatto correggere all'ospite.
"""
import datetime
import gc
import multiprocessing

import cv2
import numpy as np

import ottico

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
# I nomi come li legge l'ospite, per esteso. La lettera resta in
# 'sigla_documento': serve a scegliere il codice a cinque lettere che vuole
# Alloggiati Web, e quella e' un'altra cosa da un nome scritto in un modulo.
TIPI = {
    "P": "Passaporto",
    "I": "Carta d'Identità",
    "A": "Carta d'Identità",
    "C": "Carta d'Identità",
    "V": "Visto",
    "D": "Patente",
}

_lettore = None

# Oltre questo il processo che legge si considera piantato e si abbatte.
SECONDI_DI_ATTESA = 180

# Il figlio nasce da zero, non dalla copia di questo processo: dentro un
# servizio con piu' thread la copia porta con se' serrature prese da altri.
_CONTESTO = multiprocessing.get_context("spawn")


class NessunaMRZ(Exception):
    pass


class LettoreAssente(Exception):
    pass


def _lettore_pronto():
    """Il modello si carica alla prima richiesta, non all'avvio.

    Vive dentro il processo usa e getta di analizza_altrove, quindi si carica
    una volta sola e se ne va con lui: chi usa solo il riconoscimento dei
    volti non lo paga mai.
    """
    global _lettore
    if _lettore is None:
        try:
            from mrzscanner import MRZScanner
            _lettore = MRZScanner()
        except Exception as guaio:
            raise LettoreAssente("il lettore della MRZ non si carica: %s" % guaio)
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


def _validita(campo_scadenza):
    """Se il documento e' scaduto, e di quanti giorni.

    **Mancava, e si e' visto il 19 agosto 2026** (#37): un documento scaduto e'
    passato per tutto il giro fino al confronto dei volti, e nessuno ha detto
    niente. Un ospite si deve presentare munito di un documento di
    identificazione valido: scaduto non e' valido, e la cosa va detta prima
    dell'arrivo, non davanti alla porta.

    L'anno nella MRZ ha due cifre e per la scadenza non c'e' ambiguita': un
    documento che scadeva nel millenovecento non si presenta a nessun check-in,
    quindi le due cifre sono sempre duemila e qualcosa. Per la data di nascita
    la regola sarebbe un'altra, e qui non serve.

    **Se la cifra di controllo della scadenza non torna, non si giudica niente.**
    Un documento buono respinto perche' il lettore ha letto male una cifra e'
    peggio di uno scaduto che passa: quello lo vede comunque l'host, mentre
    l'ospite respinto per sbaglio non ha nessuno a cui spiegarsi.
    """
    if campo_scadenza.get("verificato") is False:
        return {"scaduto": None, "giorni": None,
                "motivo": "la cifra di controllo della scadenza non torna, la data e' da correggere"}
    pezzi = str(campo_scadenza.get("valore") or "").split("/")
    if len(pezzi) != 3 or not all(p.isdigit() for p in pezzi):
        return {"scaduto": None, "giorni": None, "motivo": "la data di scadenza non si legge"}
    try:
        quando = datetime.date(2000 + int(pezzi[2]), int(pezzi[1]), int(pezzi[0]))
    except ValueError:
        return {"scaduto": None, "giorni": None,
                "motivo": "la data di scadenza non esiste sul calendario"}
    giorni = (quando - datetime.date.today()).days
    return {"scaduto": giorni < 0, "giorni": giorni,
            "scade_il": quando.strftime("%d/%m/%Y"), "motivo": ""}


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
            righe = _righe(ottico.rimpicciolisci(img, lato))
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
            "validita": _validita(campi["scadenza"]),
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


def _in_disparte(scrivi_qui, dati_binari, anche_ottico, anche_banda):
    """Il lavoro visto da dentro il processo usa e getta: legge, risponde, muore.

    Le due letture stanno **qui dentro tutte e due**, e non e' per comodita': la
    banda ottica si prende quasi un giga e il testo stampato altri 370 MB, e
    l'unico punto in cui il sistema se li riprende con certezza e' la fine di un
    processo. Stesso innesco, cioe' l'arrivo di una fotografia, quindi stesso
    viaggio.

    **Il testo stampato si legge anche quando la banda ottica non c'e'.** Un
    documento senza banda, come la patente, non e' un documento su cui non c'e'
    niente da leggere: e' quello su cui il testo stampato e' l'unica strada.
    """
    esito = guaio = None
    if anche_banda:
        try:
            esito = analizza(dati_binari)
        except NessunaMRZ as questo:
            guaio = ("nessuna", str(questo))
        except Exception as questo:
            guaio = ("assente", "la lettura del documento e' fallita: %s" % questo)
    else:
        # **Sulla patente la banda ottica non si cerca affatto.** Non ce l'ha, e
        # cercarla comunque costava le due passate della lettura, la seconda a
        # piu' pixel apposta per riprovare quando la prima fallisce: due
        # tentativi buttati per definizione. Misurato su un N4000 il 20 agosto
        # 2026, patente e testo stampato insieme facevano 24,9 secondi.
        guaio = ("nessuna", "la patente non ha la banda ottica")
    testo = []
    if anche_ottico:
        try:
            testo = ottico.righe(dati_binari)
        except Exception as questo:
            # Non fa cadere niente: la banda ottica e' la lettura che conta, e
            # il testo stampato e' quello che si aggiunge quando si puo'.
            testo = ["(il testo stampato non si e' letto: %s)" % questo]
    try:
        if esito is not None:
            esito["testo_stampato"] = testo
            scrivi_qui.send(("bene", esito, testo))
        else:
            scrivi_qui.send((guaio[0], guaio[1], testo))
    finally:
        scrivi_qui.close()


def analizza_altrove(dati_binari, secondi=SECONDI_DI_ATTESA, anche_ottico=False,
                     anche_banda=True):
    """La stessa lettura, fatta da un processo che subito dopo muore.

    Il motore della MRZ si prende quasi un giga e non lo restituisce: non e' un
    errore da correggere, e' il modo in cui si procura la memoria. L'unico
    punto in cui il sistema se la riprende con certezza e' la fine di un
    processo, quindi la lettura si fa la' dentro e il servizio resta leggero.
    Costa il tempo di avviare un interprete, che su un lavoro da qualche
    secondo, e che capita due volte a prenotazione, non si nota.
    """
    leggi_qui, scrivi_qui = _CONTESTO.Pipe(duplex=False)
    figlio = _CONTESTO.Process(target=_in_disparte,
                               args=(scrivi_qui, dati_binari, anche_ottico, anche_banda),
                               daemon=True)
    figlio.start()
    scrivi_qui.close()
    try:
        if not leggi_qui.poll(secondi):
            raise NessunaMRZ("la lettura del documento ci ha messo troppo")
        try:
            come, cosa, testo = leggi_qui.recv()
        except EOFError:
            raise LettoreAssente("la lettura del documento si e' interrotta")
    finally:
        leggi_qui.close()
        if figlio.is_alive():
            figlio.terminate()
        figlio.join(10)
        if figlio.is_alive():
            figlio.kill()
        figlio.close()
    if come == "bene":
        return cosa
    # Il testo stampato viaggia **anche sul fallimento**, appeso all'errore: e'
    # esattamente il caso in cui serve di piu', perche' se la banda ottica non
    # c'e' o non si legge quel testo e' tutto quello che resta.
    guaio = NessunaMRZ(cosa) if come == "nessuna" else LettoreAssente(cosa)
    guaio.testo_stampato = testo
    raise guaio
