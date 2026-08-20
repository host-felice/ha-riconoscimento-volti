# -*- coding: utf-8 -*-
"""Il controllo sulla scadenza del documento.

Mancava, ed e' passato inosservato fino al 19 agosto 2026, quando un documento
scaduto ha fatto tutto il giro fino al confronto dei volti senza che nessuno
dicesse niente. Questa prova esiste perche' non ricapiti.

Due cose che devono restare vere e che sono facili da rompere:

- **Quando la cifra di controllo della scadenza non torna non si giudica.** Un
  documento buono respinto per una cifra letta male e' peggio di uno scaduto che
  passa: quello lo vede comunque l'host.
- **Nel registro dell'add-on non entrano date di nascita ne' numeri di
  documento**, e la scadenza si scrive come "quanti giorni", non come data:
  una data di scadenza e' un pezzo di documento e riporta a una persona.
"""
import datetime
import io
import json
import os
import sys
import tempfile

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(QUI), "riconoscimento_volti", "app"))

DATI = tempfile.mkdtemp()
os.environ["DATI"] = DATI
os.environ["OPZIONI_FILE"] = os.path.join(DATI, "options.json")

import registro
registro.CARTELLA = DATI
registro.FILE = os.path.join(DATI, "prove.jsonl")

import mrz
import server

fallite = []


def controlla(cosa, condizione, dettaglio=""):
    print(("  ok   " if condizione else "  NO   ") + cosa + (" " + dettaglio if dettaglio else ""))
    if not condizione:
        fallite.append(cosa)


def campo(valore, verificato=True):
    return {"valore": valore, "verificato": verificato}


def fra_anni(quanti):
    """Una data di scadenza scritta come la scrive la MRZ, gg/mm/aa."""
    oggi = datetime.date.today()
    return (oggi.replace(year=oggi.year + quanti)).strftime("%d/%m/%y")


print("\n1. il documento valido e quello scaduto si distinguono")
v = mrz._validita(campo(fra_anni(3)))
controlla("il valido non e' scaduto", v["scaduto"] is False, str(v))
controlla("e dice quanti giorni gli restano", v["giorni"] > 1000, str(v["giorni"]))
v = mrz._validita(campo(fra_anni(-2)))
controlla("lo scaduto e' scaduto", v["scaduto"] is True, str(v))
controlla("e dice da quanto", v["giorni"] < -700, str(v["giorni"]))
controlla("con la data per esteso, che l'ospite deve poter leggere",
          v["scade_il"].count("/") == 2 and len(v["scade_il"]) == 10, v.get("scade_il", ""))

print("\n2. il documento che scade domani non e' scaduto, quello di ieri si'")
domani = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%d/%m/%y")
ieri = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%d/%m/%y")
controlla("domani: valido", mrz._validita(campo(domani))["scaduto"] is False)
controlla("ieri: scaduto", mrz._validita(campo(ieri))["scaduto"] is True)
oggi = datetime.date.today().strftime("%d/%m/%y")
controlla("oggi: valido, l'ultimo giorno vale", mrz._validita(campo(oggi))["scaduto"] is False)

print("\n3. quando non si sa, non si giudica: e' la regola che protegge l'ospite")
for valore, verificato, cosa in (
        (fra_anni(-2), False, "la cifra di controllo non torna"),
        ("ABC", True, "la data non si legge"),
        ("31/02/28", True, "la data non esiste sul calendario"),
        ("", True, "il campo e' vuoto"),
):
    v = mrz._validita(campo(valore, verificato))
    controlla("%-38s non si giudica" % cosa, v["scaduto"] is None, str(v.get("motivo", "")))
    controlla("%-38s e dice perche'" % cosa, bool(v.get("motivo")))

print("\n4. un documento scaduto per una cifra letta male non viene respinto")
# E' il caso che conta: la data dice che e' scaduto, ma la cifra di controllo
# la smentisce. Deve vincere il dubbio, non la data.
v = mrz._validita(campo(fra_anni(-5), verificato=False))
controlla("il dubbio vince sulla data", v["scaduto"] is None, str(v))

print("\n5. nel registro dell'add-on la scadenza si scrive senza date")
for v, atteso in (
        ({"scaduto": True, "giorni": -30}, "SCADUTO"),
        ({"scaduto": False, "giorni": 900}, "valido"),
        ({"scaduto": None, "giorni": None, "motivo": "x"}, "non giudicabile"),
):
    detto = server._detta_validita(v)
    controlla("%-16s si legge come %r" % (str(v["scaduto"]), detto), atteso in detto)
    controlla("%-16s e non contiene una data" % str(v["scaduto"]), "/" not in detto, detto)

print("\n6. la lettura del documento restituisce il giudizio sulla scadenza")
scaduto = {"formato": "TD1", "seconda_passata": False, "da_correggere": [],
           "validita": mrz._validita(campo(fra_anni(-2))), "campi": {}}
server.OPZIONI["parola"] = ""
mrz.analizza_altrove = lambda dati, **comunque: dict(scaduto)
cliente = server.app.test_client()
r = cliente.post("/mrz", data={"immagine": (io.BytesIO(b"finta"), "d.jpg")},
                 content_type="multipart/form-data").get_json()
controlla("la risposta porta la validita'", isinstance(r.get("validita"), dict))
controlla("e dice che e' scaduto", r["validita"]["scaduto"] is True, str(r.get("validita")))

print("\n" + ("TUTTO A POSTO" if not fallite else "FALLITE: " + ", ".join(fallite)))
sys.exit(1 if fallite else 0)
