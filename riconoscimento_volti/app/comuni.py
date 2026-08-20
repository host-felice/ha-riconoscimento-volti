# -*- coding: utf-8 -*-
"""L'elenco chiuso dei comuni della Polizia di Stato, e come ritrovarci dentro
quello che ha letto la macchina.

Il nome stampato su un documento e il nome che vuole la Questura non coincidono
quasi mai al carattere: la lettura sbaglia una lettera, il documento scrive
`ALI'` dove l'elenco scrive `ALI`, l'accento va e viene. Quindi **non si usa
quello che si e' letto: si usa quello dell'elenco a cui somiglia di piu'**, e se
non somiglia abbastanza a niente non si propone niente.

## Le due trappole di questa tabella, contate

**Su 11.294 righe, 3.396 sono comuni soppressi**, che restano nell'elenco con la
data in cui hanno smesso di esistere. **Si possono usare**, e non e' una
deduzione: chiesto al web service della Questura il 20 agosto 2026, con il
metodo di prova che valida senza trasmettere. Per uno nato nel 1980 ad Abbadia
Cerreto passano tutti e due i codici, quello vecchio di Milano soppresso nel 1992
e quello nuovo di Lodi, e passano anche per uno nato nel 2000. Il controllo che
rende la prova una misura: un codice inventato viene **respinto**, con scritto
"Comune di Nascita Errato". Quindi il controllo c'e' e i soppressi lo superano.

Il ragionamento che c'era arrivato prima, di Felice: chi e' nato in un comune che
non esiste piu' continua a scrivere quello, altrimenti ogni host dovrebbe mettersi
a cercare come si chiama adesso.

**Ma i soppressi si cercano solo quando il documento dice la provincia.** Senza,
`ABBADIA CERRETO` somiglia ugualmente a due righe e non si saprebbe quale
scegliere; e siccome i cinque omonimi qui sotto sono posti **diversi**, un
pareggio sciolto a caso li' sarebbe un errore vero.

**Cinque nomi validi esistono in due province**: Castro, Livo, Peglio, Samone e
San Teodoro. Il nome da solo non e' una chiave, nome piu' provincia si. Per
fortuna la provincia il documento ce l'ha stampata accanto, fra parentesi
(`MESSINA (ME)`, letto davvero), e quando c'e' si cerca solo li' dentro: sono un
centinaio di nomi invece di ottomila, quindi piu' preciso e piu' veloce insieme.
"""
import csv
import os
import re
import unicodedata

ELENCO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tabelle", "comuni.csv")

# Due caratteri di tolleranza: e' quello che sbaglia una lettura storta senza
# cominciare a confondere due comuni diversi.
TETTO = 2

PROVINCIA = re.compile(r"[(\[]\s*([A-Za-z]{2})\s*(?:[)\]]|$|(?=[^A-Za-z]))")
# **La parentesi che chiude puo' mancare**, perche' la lettura ogni tanto se la
# mangia. Non basta renderla facoltativa: `(TERAMO` diventerebbe la provincia TE
# piu' un avanzo. Si accetta solo se dopo le due lettere non c'e' un'altra
# lettera, che e' esattamente cio' che distingue una sigla da una parola.
SOLO_LETTERE = re.compile(r"[^A-Z ]")


def normalizza(testo):
    """Il nome ridotto all'osso, per poterlo confrontare.

    Via accenti e apostrofi da tutti e due i lati, cosi' `ALI'`, `ALI` e `ALI`
    con l'accento diventano la stessa cosa, che e' quello che sono.
    """
    senza = unicodedata.normalize("NFD", testo or "")
    senza = "".join(c for c in senza if not unicodedata.combining(c))
    return " ".join(SOLO_LETTERE.sub(" ", senza.upper()).split())


def distanza(prima, poi, tetto=TETTO):
    """Quanti caratteri separano due parole, e ci si ferma appena sono troppi."""
    if abs(len(prima) - len(poi)) > tetto:
        return tetto + 1
    riga = list(range(len(poi) + 1))
    for quante, una in enumerate(prima, 1):
        nuova = [quante]
        for dove, altra in enumerate(poi, 1):
            nuova.append(min(riga[dove] + 1, nuova[dove - 1] + 1,
                             riga[dove - 1] + (una != altra)))
        if min(nuova) > tetto:
            return tetto + 1
        riga = nuova
    return riga[-1]


def _carica():
    """Tutti i comuni, gia' normalizzati, con l'ultimo posto che dice se sono
    ancora in vita. Si legge una volta e basta: questo modulo vive dentro il
    processo usa e getta che legge una fotografia sola."""
    vivi = []
    with open(ELENCO, encoding="utf-8", newline="") as dentro:
        for riga in csv.DictReader(dentro):
            nome = riga["Descrizione"].strip()
            vivi.append((normalizza(nome), nome, riga["Provincia"].strip(),
                         riga["Codice"].strip(),
                         not riga.get("DataFineVal", "").strip()))
    return vivi


_VIVI = None


def cerca(testo, tetto=TETTO):
    """Il comune dell'elenco a cui somiglia quello che si e' letto.

    Torna il nome ufficiale, la sigla della provincia e il codice a nove cifre,
    oppure niente quando non c'e' un vincitore solo. **Un pareggio non si
    scioglie a caso**: fra due comuni ugualmente somiglianti si lascia il campo
    vuoto e lo scrive l'ospite.
    """
    global _VIVI
    if _VIVI is None:
        _VIVI = _carica()
    fra_parentesi = PROVINCIA.search(testo or "")
    sigla = fra_parentesi.group(1).upper() if fra_parentesi else ""
    cercato = normalizza(PROVINCIA.sub(" ", testo or ""))
    if not cercato:
        return None
    # Con la provincia stampata si cerca dentro quella e basta, soppressi
    # compresi: la provincia scioglie da sola sia i cinque omonimi sia il doppione
    # fra un comune soppresso e quello che ha preso il suo posto. Senza, si resta
    # fra i vivi, dove ogni nome e' quasi sempre uno solo.
    dove = [c for c in _VIVI if c[2] == sigla] if sigla else [c for c in _VIVI if c[4]]
    esatti = [c for c in dove if c[0] == cercato]
    vicini = esatti or _i_piu_vicini(dove, cercato, tetto)
    if len(vicini) != 1:
        return None
    _, nome, provincia, codice, _vivo = vicini[0]
    return {"nome": nome, "provincia": provincia, "codice": codice}


def _i_piu_vicini(dove, cercato, tetto):
    migliore, vinti = tetto + 1, []
    for comune in dove:
        quanto = distanza(comune[0], cercato, tetto)
        if quanto < migliore:
            migliore, vinti = quanto, [comune]
        elif quanto == migliore and quanto <= tetto:
            vinti.append(comune)
    return vinti if migliore <= tetto else []
