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
DATA = re.compile(r"\b(\d{2})\D{1,3}(\d{2})\D{1,3}(\d{4}|\d{2})")
# Fra un pezzo e l'altro della data ci sta **qualunque cosa che non sia una
# cifra**, non un elenco di separatori scelti da noi. L'elenco era punto, virgola,
# barra, trattino e spazio, e bastava un carattere mai visto per perdere la data:
# regole nostre che decidono cosa un documento ha il diritto di stampare.
#
# **Dopo l'anno non si pretende niente.** C'era un confine di parola, e chiedeva
# che dopo l'ultima cifra venisse uno spazio o la fine della riga. La lettura gli
# spazi se li mangia, quindi la data esce attaccata a quello che segue e quel
# confine non c'e': `21/07/71ROMA(RM)` e `21.07.20164c.MIT-UCO`, letti tutti e
# due su una patente vera. Con il confine quelle due date sparivano, e sulla
# prima sparivano in coppia, perche' le date si propongono solo a due a due:
# perdendone una non si proponeva piu' niente. Sulla **stessa** patente,
# fotografata dritta, la riga restava staccata e uscivano tutte e due.


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


MARCATORE = re.compile(r"([1-9][abc])[.,]|(?<!\d)([1-9])[.,]", re.IGNORECASE)
# Due modi di scrivere la stessa cosa. Un numero da solo (`3.`) si prende solo se
# non ha una cifra davanti, altrimenti dentro `21.07.2016` ci sarebbero tre
# marcatori finti. Un numero con la lettera (`4c.`) si prende sempre, perche' la
# lettera lo rende gia' inconfondibile e perche' la cifra davanti ce l'ha per
# davvero: letto il 20 agosto 2026, `21.07.201664c.MIT-UCO`.
NOME_DI_PERSONA = re.compile(r"^[A-Za-z\u00c0-\u024f'\u2019 .-]{2,40}$")
NUMERO_DI_PATENTE = re.compile(r"^[A-Z0-9]{8,12}$", re.IGNORECASE)

# I campi della patente italiana sono numerati, e il numero e' stampato accanto
# al valore. Vale la pena fidarsene: **i numeri sopravvivono alla lettura molto
# meglio delle parole**, e in una patente vera letta il 20 agosto 2026 c'erano
# tutti, mentre le etichette scritte uscivano sfilacciate.
DALLA_PATENTE = (("1", "cognome", NOME_DI_PERSONA),
                 ("2", "nome", NOME_DI_PERSONA),
                 ("5", "numero_documento", NUMERO_DI_PATENTE))


def _fine_dell_ultimo(testo, fine):
    """Dove finisce il valore dell'**ultimo** numero letto, che non ha un dopo.

    Prima si prendeva tutto fino in fondo, e li' dietro c'e' quello che la
    lettura ha restituito per ultimo: le intestazioni. Da una patente vera,
    fotografata storta, sono usciti cognome `MUSETTI PATENTE DI GUIDA REPUBBLICA
    ITALIANA` e nome `STEFANIA PATENTEDIGUIDA`. Il primo il controllo di forma lo
    butta perche' supera i quaranta caratteri; **il secondo passa**, perche' sono
    lettere e spazi e sta sotto il tetto. Quello e' il caso che costa: non un
    campo perso, un campo sporco che sembra pulito e va in Questura cosi'.

    Quindi all'ultimo si da' **una riga sola**: quella dove sta il suo numero, e
    se li' dopo il numero non c'e' scritto niente, quella subito sotto. La
    seconda meta' non e' un di piu': su una patente vera il campo 5 va a capo
    prima del numero (`5.` da solo, `U1A000000B` sotto), e senza di lei il numero
    del documento andrebbe perso ogni volta che 5 e' l'ultimo letto.

    Gli altri numeri restano come prima, cioe' fino al numero successivo, anche
    se per arrivarci scavalcano delle righe: e' cosi' che il campo 3 prende il
    comune di nascita, che sta sotto la data.
    """
    a_capo = testo.find("\n", fine)
    if a_capo == -1:
        return len(testo)
    if testo[fine:a_capo].strip():
        return a_capo
    dopo = testo.find("\n", a_capo + 1)
    return len(testo) if dopo == -1 else dopo


def _pezzi_numerati(testo):
    """Quello che sta scritto dopo ogni numero di campo, fino al numero dopo.

    Il testo arriva con le righe ancora separate da un a capo, e non appiattite
    in una riga sola: serve a sapere dove finisce l'ultimo numero letto.
    """
    tagli = [(quello.start(), quello.end(),
               (quello.group(1) or quello.group(2)).lower())
             for quello in MARCATORE.finditer(testo)]
    pezzi = {}
    for quante, (_, fine, numero) in enumerate(tagli):
        # La prima volta che un numero compare e' quella buona: piu' avanti le
        # date lo rifanno comparire (dentro `21.07.2016` c'e' un `2.`).
        if numero in pezzi:
            continue
        dopo = (tagli[quante + 1][0] if quante + 1 < len(tagli)
                else _fine_dell_ultimo(testo, fine))
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
    pezzi = _pezzi_numerati("\n".join(righe))
    fuori = {}
    for numero, chiave, forma in DALLA_PATENTE:
        valore = pezzi.get(numero, "").strip(" .,-")
        if valore and forma.match(valore):
            # Maiuscolo comunque: la lettura ogni tanto restituisce minuscole
            # che sul documento non ci sono, e maiuscolo lo vuole la Questura.
            fuori[chiave] = {"valore": valore.upper()}
    # Nel campo 3 c'e' la data di nascita e accanto il luogo: tolta la data,
    # quello che resta e' il comune, con la sigla della provincia fra parentesi.
    _aggiungi(fuori, "comune_nascita", DATA.sub(" ", pezzi.get("3", "")))
    _aggiungi(fuori, "comune_emissione", _ufficio(pezzi.get("4c", "")))
    return fuori


def _aggiungi(fuori, chiave, letto):
    """Il comune si scrive come lo scrive l'elenco della Polizia, non come lo ha
    letto la macchina: e' l'elenco che decide, e sotto c'e' gia' il suo codice.

    Si pesca in coda come per gli altri documenti: nel campo 3 della patente,
    accanto al comune, ci sta anche la data di nascita.
    """
    trovato = _comune_nel_pezzo(letto)
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


# Le etichette stampate accanto ai luoghi, in italiano e in inglese. Bastano
# una parola: quella intera dentro l'etichetta sopravvive alla lettura anche
# quando il resto si sfalda (letto davvero: `COMUNEOI/MUNICVPALITY`).
ETICHETTE = (("comune_emissione", ("COMUNE", "MUNICIPALITY")),
             ("comune_nascita", ("NASCITA", "BIRTH")),
             ("residenza", ("RESIDENZA", "RESIDENCE")))

# Quante parole in coda si provano, quando la riga intera non e' un comune.
CODE = (3, 2, 1)


def _c_e_l_etichetta(riga, etichette):
    """Se una delle etichette compare dentro la riga.

    **Si cerca dentro la riga, non fra le parole.** La lettura gli spazi se li
    mangia, e proprio nelle etichette, che sono stampate piccole e strette: sulla
    carta d'identita' esce `LUOGOEDATADINASCITA` tutto attaccato, sul passaporto
    `Datadinascita.Dateofbirth.` Cercare la parola intera li' dentro non la trova
    mai. Cercarla come pezzo di stringa si.
    """
    return any(e in riga for e in etichette)


def _comune_nel_pezzo(pezzo):
    """Il comune dentro un pezzo di riga, che quasi mai e' tutta la riga.

    Sotto l'etichetta ci finisce anche altro: la data di nascita (`MESSINA (ME)
    01.03.1980`) o tutto l'indirizzo (`VIALE DEI TIGLI, N. 12 TERAMO
    (TE)`). Via le date, poi si prova la riga intera e via via solo la coda,
    perche' in italiano il comune sta in fondo.

    **Il pezzo arriva grezzo, non normalizzato.** La sigla della provincia sta
    fra parentesi e la normalizzazione le parentesi le butta: normalizzando
    prima si perdeva la provincia, e senza di lei `1628 p1 sA-1978` e' diventato
    Pisa, misurato il 20 agosto 2026.

    **Senza provincia si pretende il nome esatto.** La tolleranza di due
    caratteri e' fatta per un nome storto in mezzo a una riga di cui si sa che
    e' un luogo, non per pescare comuni dentro numeri di protocollo: qui sotto
    l'etichetta ci finisce di tutto, e la provincia e' l'unica cosa che dice
    "questo pezzo un luogo lo contiene davvero".
    """
    pezzo = DATA.sub(" ", pezzo or "")
    fra_parentesi = comuni.PROVINCIA.search(pezzo)
    sigla = fra_parentesi.group(0) if fra_parentesi else ""
    # **Si divide in parole dopo aver normalizzato, non prima.** La lettura
    # restituisce `VIALEDEITIGLI,N.12TERAMO` in un pezzo solo: diviso cosi'
    # com'e' fa una parola sola e la coda non esiste. Normalizzare mette uno
    # spazio dove c'erano cifre e punteggiatura, e le parole tornano.
    parole = comuni.normalizza(comuni.PROVINCIA.sub(" ", pezzo)).split()
    if not parole:
        return None
    for quante in (len(parole),) + CODE:
        if quante > len(parole):
            continue
        trovato = comuni.cerca(" ".join(parole[-quante:]) + " " + sigla,
                               comuni.TETTO if sigla else 0)
        if trovato:
            return trovato
    return None


def dalle_etichette(righe):
    """I luoghi scritti sul documento, presi dall'etichetta che li annuncia.

    Qui i campi non sono numerati come sulla patente: c'e' un'etichetta scritta,
    e il valore sta nel resto della riga o poco sotto. Le tre che contano,
    guardate su una carta d'identita' e su un passaporto veri il 20 agosto 2026:

        COMUNE DI / MUNICIPALITY          il comune che ha emesso la carta
        LUOGO E DATA DI NASCITA           il comune di nascita, con la data
        INDIRIZZO DI RESIDENZA            l'indirizzo intero, comune in fondo

    Le prime due stanno sul fronte della carta, la terza sul retro, e il
    passaporto ha la sua `Luogo di nascita. Place of birth`. **Il comune che ha
    emesso il documento e quello di residenza non sono la stessa cosa** anche
    quando coincidono, ed e' per questo che si tengono due etichette separate.

    Si guarda **due righe sotto** e non una: l'etichetta italiana e quella
    inglese vanno spesso a capo fra loro, e il valore finisce nella terza riga.
    """
    # Le etichette si cercano senza spazi da tutte e due le parti, perche' la
    # lettura li perde: `LUOGO E DATA DI NASCITA` esce `LUOGOEDATADINASCITA`.
    pulite = [comuni.normalizza(r).replace(" ", "") for r in righe]
    fuori = {}
    for quante, riga in enumerate(pulite):
        for chiave, etichette in ETICHETTE:
            if chiave in fuori:
                continue
            if not _c_e_l_etichetta(riga, etichette):
                continue
            # Il valore sta nella riga stessa, e se li' non c'e' in una delle due
            # sotto: fra l'etichetta italiana e il valore ci va di mezzo quella
            # inglese. La riga intera si passa cosi' com'e' e il comune si pesca
            # in coda, che e' dove sta: tagliarla all'etichetta non si puo',
            # perche' l'etichetta l'abbiamo trovata nella riga **senza spazi** e
            # quel numero li' non vuol dire niente sulla riga vera.
            candidati = list(righe[quante:quante + 3])
            for candidato in candidati:
                trovato = _comune_nel_pezzo(candidato)
                if trovato:
                    fuori[chiave] = {"valore": "%s (%s)" % (trovato["nome"],
                                                            trovato["provincia"])}
                    break
    return fuori


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
