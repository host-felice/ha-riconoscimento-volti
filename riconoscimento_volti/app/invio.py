# -*- coding: utf-8 -*-
"""Manda il risultato di una prova a Home Assistant, se chi l'ha fatta ha detto si'.

Le prove le fanno persone che ci fanno un favore. Non devono scaricare niente,
non devono mandare niente a mano, non devono capire come funziona: fanno le due
foto, vedono il risultato, e se dicono di si' i numeri arrivano da soli.

**Cosa parte:** gli stessi numeri che finiscono nel quaderno delle prove, cioe'
punteggi, dimensioni, tempi. Le foto no, i vettori no, i nomi no: li toglie il
quaderno prima, e qui si manda quello che lui ha gia' ripulito.

**Cosa non fa:** far aspettare la persona. L'invio parte per conto suo e se il
collegamento non c'e' la prova resta comunque scritta in casa. Ma un invio che
fallisce non sparisce in silenzio: si conta, e il conto si vede da /prove e da
/salute. E' la regola di tutto il progetto, e vale anche per due numeri.
"""
import json
import logging
import threading
import urllib.error
import urllib.request

log = logging.getLogger("volti")

SECONDI_DI_ATTESA = 8

_stato = {"mandati": 0, "falliti": 0, "ultimo_guaio": None}
_una_alla_volta = threading.Lock()


def stato():
    with _una_alla_volta:
        return dict(_stato)


def _manda_davvero(url, riga):
    dati = json.dumps(riga, ensure_ascii=False).encode("utf-8")
    richiesta = urllib.request.Request(
        url, data=dati, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(richiesta, timeout=SECONDI_DI_ATTESA) as risposta:
            if risposta.status >= 300:
                raise urllib.error.HTTPError(url, risposta.status, "", None, None)
        with _una_alla_volta:
            _stato["mandati"] += 1
    except Exception as guaio:
        with _una_alla_volta:
            _stato["falliti"] += 1
            _stato["ultimo_guaio"] = str(guaio)[:200]
        log.warning("la prova non e' arrivata a Home Assistant: %s", guaio)


def manda(url, riga):
    """Parte e non aspetta. Restituisce se ha almeno provato."""
    if not url:
        return False
    threading.Thread(target=_manda_davvero, args=(url, riga), daemon=True).start()
    return True
