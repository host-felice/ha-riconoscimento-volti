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
import datetime
import re

import comuni

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
DATA = re.compile(r"\b(\d{2})[.,/\- ]{1,3}(\d{2})[.,/\- ]{1,3}(\d{4}|\d{2})\b")


def _anno(cifre):
    """Le due cifre dell'anno diventano quattro, e il secolo si sceglie.

    Sulla patente la data di nascita e' stampata con l'anno a due cifre: letta
    davvero il 20 agosto 2026, `01/03/80`. Il taglio e' quello di sempre: fino
    all'anno in corso siamo nel Duemila, oltre nel Novecento.

    ponytail: vale per una data di nascita. Una scadenza a due cifre finirebbe
    nel Novecento, ma sui documenti visti finora la scadenza l'anno ce l'ha
    intero, e inventare adesso il secondo taglio vuol dire indovinare.
    """
    if len(cifre) == 4:
        return cifre
    return ("20" if int(cifre) <= datetime.date.today().year % 100 else "19") + cifre


MARCATORE = re.compile(r"([1-9][abc])[.,]|(?<!\d)([1-9])[.,]")
# Due modi di scrivere la stessa cosa. Un numero da solo (`3.`) si prende solo se
# non ha una cifra davanti, altrimenti dentro `21.07.2016` ci sarebbero tre
# marcatori finti. Un numero con la lettera (`4c.`) si prende sempre, perche' la
# lettera lo rende gia' inconfondibile e perche' la cifra davanti ce l'ha per
# davvero: letto il 20 agosto 2026, `21.07.201664c.MIT-UCO`.
NOME_DI_PERSONA = re.compile(r"^[A-Za-z\u00c0-\u024f'\u2019 .-]{2,40}$")
NUMERO_DI_PATENTE = re.compile(r"^[A-Z0-9]{8,12}$")

# I campi della patente italiana sono numerati, e il numero e' stampato accanto
# al valore. Vale la pena fidarsene: **i numeri sopravvivono alla lettura molto
# meglio delle parole**, e in una patente vera letta il 20 agosto 2026 c'erano
# tutti, mentre le etichette scritte uscivano sfilacciate.
DALLA_PATENTE = (("1", "cognome", NOME_DI_PERSONA),
                 ("2", "nome", NOME_DI_PERSONA),
                 ("5", "numero_documento", NUMERO_DI_PATENTE))


def _pezzi_numerati(testo):
    """Quello che sta scritto dopo ogni numero di campo, fino al numero dopo."""
    tagli = [(quello.start(), quello.end(), quello.group(1) or quello.group(2))
             for quello in MARCATORE.finditer(testo)]
    pezzi = {}
    for quante, (_, fine, numero) in enumerate(tagli):
        # La prima volta che un numero compare e' quella buona: piu' avanti le
        # date lo rifanno comparire (dentro `21.07.2016` c'e' un `2.`).
        if numero in pezzi:
            continue
        dopo = tagli[quante + 1][0] if quante + 1 < len(tagli) else len(testo)
        pezzi[numero] = testo[fine:dopo].strip()
    return pezzi


def dalla_patente(righe):
    """Cognome, nome e numero del documento, presi dal numero del loro campo.

    Detta da Felice il 20 agosto 2026, guardando cosa era uscito davvero: "se
    tagli 1. 2. 3. 4a. 4b. 5. e ignori 7. e 9., riconosce tutto bene".

    **Il valore si prende solo se ha la forma giusta.** Un cognome fatto di
    lettere, un numero di patente fatto di lettere e cifre e lungo il giusto: e'
    la rete che tiene, perche' la lettura ogni tanto salta gli spazi e attacca un
    pezzo al successivo (visto davvero: `64c.MIT-UCO`, con un 6 di troppo
    davanti). Se il pezzo non ha la forma, il campo resta vuoto e lo scrive
    l'ospite: dieci secondi suoi contro una schedina sbagliata alla Questura.
    """
    pezzi = _pezzi_numerati(" ".join(righe))
    fuori = {}
    for numero, chiave, forma in DALLA_PATENTE:
        valore = pezzi.get(numero, "").strip(" .,-")
        if valore and forma.match(valore):
            fuori[chiave] = {"valore": valore}
    # Nel campo 3 c'e' la data di nascita e accanto il luogo: tolta la data,
    # quello che resta e' il comune, con la sigla della provincia fra parentesi.
    _aggiungi(fuori, "comune_nascita", DATA.sub(" ", pezzi.get("3", "")))
    _aggiungi(fuori, "comune_emissione", _ufficio(pezzi.get("4c", "")))
    return fuori


def _aggiungi(fuori, chiave, letto):
    """Il comune si scrive come lo scrive l'elenco della Polizia, non come lo ha
    letto la macchina: e' l'elenco che decide, e sotto c'e' gia' il suo codice."""
    trovato = comuni.cerca(letto)
    if trovato:
        fuori[chiave] = {"valore": "%s (%s)" % (trovato["nome"], trovato["provincia"])}


def _ufficio(letto):
    """Il comune dell'ufficio che ha rilasciato la patente.

    Regola detta da Felice il 20 agosto 2026: quando c'e' scritto **MIT-UCO** il
    documento e' un duplicato emesso dall'Ufficio Centrale Operativo, che sta a
    **Roma**. Si cerca somigliante e non identico perche' la lettura quella
    sigla la storpia: vista uscire `MIT-UCTO`.

    Negli altri casi l'ufficio e' scritto come sigla piu' citta' (`MC-TERAMO`), e
    la citta' e' quello che sta dopo il trattino.
    """
    if comuni.distanza(comuni.normalizza(letto), comuni.normalizza("MIT-UCO")) <= comuni.TETTO:
        return "ROMA (RM)"
    return letto.rsplit("-", 1)[-1]


ETICHETTE_DEL_COMUNE = ("COMUNE", "MUNICIPALITY")


def dalla_carta(righe):
    """Il comune che ha emesso la carta d'identita'.

    Qui i campi non sono numerati come sulla patente: c'e' un'etichetta scritta e
    il valore va a capo. Letto davvero il 20 agosto 2026:

        CARTA DIIDENTITA/IDENTITY CARD
        COMUNEOI/MUNICVPALITY
        TERAMO

    L'etichetta esce sfilacciata (`COMUNEOI`, `MUNICVPALITY`) ma **la parola
    intera dentro sopravvive**, ed e' quella che si cerca, con la stessa
    tolleranza di due caratteri che si usa per i comuni. Il valore si prende dal
    resto della riga se c'e' rimasto qualcosa, altrimenti dalla riga dopo.
    """
    pulite = [comuni.normalizza(r) for r in righe]
    for quante, riga in enumerate(pulite):
        parole = riga.split()
        dove = next((i for i, p in enumerate(parole)
                     if any(comuni.distanza(p, e) <= comuni.TETTO
                            for e in ETICHETTE_DEL_COMUNE)), None)
        if dove is None:
            continue
        resto = " ".join(parole[dove + 1:])
        for candidato in (resto, pulite[quante + 1] if quante + 1 < len(pulite) else ""):
            trovato = comuni.cerca(candidato)
            if trovato:
                return {"comune_emissione": {
                    "valore": "%s (%s)" % (trovato["nome"], trovato["provincia"])}}
    return {}


def proponi(righe):
    """La data di nascita e la scadenza, riconosciute l'una dall'altra.

    **Sono due le date che servono**, non tre: nascita e scadenza. Quella di
    rilascio non la chiede nessuno.

    ## Come si riconoscono in mezzo alle altre

    Regola detta da Felice il 20 agosto 2026: sui documenti italiani, carta
    d'identita' e patente, **la scadenza cade nello stesso giorno e mese della
    data di nascita**, cambia solo l'anno. Sono lo stesso dato scritto due volte
    in due punti, ed e' la stessa cosa che fanno le cifre di controllo della
    banda ottica.

    Quindi non si conta e non si va a posizione: **si cerca l'unica coppia di
    date che condivide giorno e mese**. La piu' vecchia e' la nascita, l'altra e'
    la scadenza, e le due si sono verificate a vicenda. Se le coppie sono zero o
    piu' d'una non si propone niente: un campo vuoto costa dieci secondi
    all'ospite, un campo pieno e sbagliato costa una schedina sbagliata alla
    Questura.

    **Andare a posizione non si poteva.** Il primo tentativo prendeva la prima
    data e la terza, e una lettura vera l'ha smentito: la data di rilascio esce
    attaccata al campo che segue (`21/07/20164c.MIT-UCO`), quindi le date
    riconoscibili non sono tre e non sono in fila.
    """
    date = ["%s/%s/%s" % (g, m, _anno(a)) for g, m, a in DATA.findall(" ".join(righe))]
    coppie = [(prima, poi) for quante, prima in enumerate(date) for poi in date[quante + 1:]
              if prima[:5] == poi[:5] and prima[6:] != poi[6:]]
    if len(coppie) != 1:
        return {}
    nascita, scadenza = sorted(coppie[0], key=lambda quando: quando[6:])
    return {"data_nascita": {"valore": nascita}, "scadenza": {"valore": scadenza}}
