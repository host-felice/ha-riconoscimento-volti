# -*- coding: utf-8 -*-
"""Il cablaggio del secondo modello alla porta, senza scaricare i modelli veri.

Non misura le facce: misura che gli attesi con un vettore per modello arrivino
dove devono, che ognuno usi la sua soglia, che il caso "non misurabile" si
racconti invece di far cadere la risposta, e che nel quaderno delle prove non
finisca nessun vettore.
"""
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

import numpy as np

import registro
registro.CARTELLA = DATI
registro.FILE = os.path.join(DATI, "prove.jsonl")

import volti
import minifasnet
import server

# ---- i modelli finti: due lunghezze diverse, come i veri (512 e 128) ----
LUNGHEZZA = {"buffalo_l": 512, "sface": 128}
PERSONE = ("felice", "padre", "estranea")


def _vettore(persona, modello):
    seme = PERSONE.index(persona) * 100 + LUNGHEZZA[modello]
    rng = np.random.default_rng(seme)
    v = rng.normal(size=LUNGHEZZA[modello])
    return (v / np.linalg.norm(v)).tolist()


def _faccia(persona, modello, px=200):
    return {"vettore": _vettore(persona, modello), "modello": modello,
            "riquadro": [10, 10, px, px], "fiducia": 0.9, "larghezza_px": px,
            "inclinazione_gradi": 1.0, "seconda_passata": False}


# Ogni "immagine" e' il nome di chi c'e' dentro, cosi' la finta e' leggibile.
volti.leggi = lambda dati: dati if isinstance(dati, str) else dati.decode("utf-8")
volti.disponibile = lambda modello: modello in LUNGHEZZA
volti.tutti_i_volti = lambda img, px, modello: [_faccia(p, modello) for p in img.split(",")]
volti.volto_principale = lambda img, px, modello: dict(
    _faccia(img.split(",")[0], modello), volti_trovati=1, altri_volti_px=[])
minifasnet.disponibile = lambda: False

server.OPZIONI["parola"] = ""
cliente = server.app.test_client()
fallite = []


def controlla(cosa, condizione, dettaglio=""):
    print(("  ok   " if condizione else "  NO   ") + cosa + (" " + dettaglio if dettaglio else ""))
    if not condizione:
        fallite.append(cosa)


def alla_porta(attesi, anche_l_altro="si", modello=None, chi="felice,padre"):
    dati = {"attesi": json.dumps(attesi), "anche_l_altro": anche_l_altro}
    if modello:
        dati["modello"] = modello
    # Tre scatti sotto lo stesso nome, com'e' la raffica vera.
    dati["immagine"] = [(io.BytesIO(chi.encode("utf-8")), "s%d.jpg" % n) for n in range(3)]
    r = cliente.post("/riconosci", data=dati, content_type="multipart/form-data")
    return r.status_code, r.get_json()


def righe_del_quaderno():
    if not os.path.exists(registro.FILE):
        return []
    return [json.loads(r) for r in io.open(registro.FILE, encoding="utf-8") if r.strip()]


print("\n1. l'ospite di ieri, con un vettore solo: la porta risponde, l'altro dice perche' no")
attesi_vecchi = [{"nome": "FELICE", "vettore": _vettore("felice", "buffalo_l")}]
codice, r = alla_porta(attesi_vecchi)
controlla("la risposta arriva", codice == 200, str(codice))
controlla("riconosciuto con il modello in uso",
          [x["nome"] for x in r["riconosciuti"]] == ["FELICE"], str(r.get("riconosciuti")))
altro = r["altri_modelli"].get("sface", {})
controlla("l'altro modello dice che non si e' potuto misurare", altro.get("misurato") is False)
controlla("e dice perche'", "vettore" in altro.get("motivo", ""), altro.get("motivo", ""))

print("\n2. l'ospite di oggi, un vettore per modello: si misurano tutti e due")
attesi_nuovi = [
    {"nome": "FELICE", "vettori": {"buffalo_l": _vettore("felice", "buffalo_l"),
                                   "sface": _vettore("felice", "sface")}},
    {"nome": "PADRE", "vettori": {"buffalo_l": _vettore("padre", "buffalo_l"),
                                  "sface": _vettore("padre", "sface")}},
]
codice, r = alla_porta(attesi_nuovi)
controlla("la risposta arriva", codice == 200, str(codice))
controlla("il modello in uso riconosce tutti e due",
          sorted(x["nome"] for x in r["riconosciuti"]) == ["FELICE", "PADRE"],
          str([x["somiglianza"] for x in r["riconosciuti"]]))
altro = r["altri_modelli"]["sface"]
controlla("l'altro modello e' stato misurato", altro.get("misurato") is True)
controlla("l'altro riconosce tutti e due",
          sorted(x["nome"] for x in altro["riconosciuti"]) == ["FELICE", "PADRE"],
          str([x["somiglianza"] for x in altro["riconosciuti"]]))
controlla("e usa la sua soglia, non quella dell'altro",
          altro["soglia"] == 0.363 and r["soglia"] == 0.4,
          "%.3f contro %.3f" % (altro["soglia"], r["soglia"]))
controlla("dice quanti attesi ha potuto misurare", altro.get("quanti_attesi") == 2)
controlla("MiniFASNet non si rifa' al secondo giro",
          all(x["minifasnet"] is None for x in altro["tutti"]))

print("\n3. chi non e' fra gli attesi resta fuori, e con l'altro modello pure")
codice, r = alla_porta(attesi_nuovi, chi="estranea")
controlla("nessuno riconosciuto", r["riconosciuti"] == [], str(r["riconosciuti"]))
controlla("una persona in piu' contata", r["persone_in_piu"] == 1, str(r["persone_in_piu"]))
altro = r["altri_modelli"]["sface"]
controlla("l'altro modello la vede pure lui",
          altro["riconosciuti"] == [] and altro["persone_in_piu"] == 1,
          "riconosciuti %s, in piu' %s" % (altro["riconosciuti"], altro["persone_in_piu"]))

print("\n4. si puo' anche non chiederlo, e allora non si paga")
codice, r = alla_porta(attesi_nuovi, anche_l_altro="no")
controlla("nessun secondo giro", r["altri_modelli"] == {}, str(r["altri_modelli"]))

print("\n5. l'atteso senza il vettore del modello chiesto: errore chiaro, non un numero falso")
solo_sface = [{"nome": "FELICE", "vettori": {"sface": _vettore("felice", "sface")}}]
codice, r = alla_porta(solo_sface, modello="buffalo_l")
controlla("la richiesta viene respinta", codice == 400, str(codice))
controlla("e il motivo si legge", "buffalo_l" in r.get("errore", ""), r.get("errore", ""))

print("\n6. l'atteso senza nessun vettore: respinto in ingresso")
codice, r = alla_porta([{"nome": "FELICE"}])
controlla("la richiesta viene respinta", codice == 400, str(codice))
controlla("e il motivo nomina i due campi",
          "vettore" in r.get("errore", "") and "vettori" in r.get("errore", ""), r.get("errore", ""))

print("\n7. il confronto restituisce il vettore dell'altro modello, che prima buttava via")
dati = {"anche_l_altro": "si",
        "documento": (io.BytesIO(b"felice"), "d.jpg"),
        "selfie": (io.BytesIO(b"felice"), "s.jpg")}
r = cliente.post("/confronta", data=dati, content_type="multipart/form-data").get_json()
controlla("il vettore del modello in uso c'e'", isinstance(r.get("vettore_selfie"), list))
altro = r["altri_modelli"]["sface"]
controlla("e anche quello dell'altro", isinstance(altro.get("vettore_selfie"), list))
controlla("della lunghezza giusta, cioe' e' suo",
          len(altro["vettore_selfie"]) == 128 and len(r["vettore_selfie"]) == 512,
          "%d e %d" % (len(altro["vettore_selfie"]), len(r["vettore_selfie"])))

print("\n8. nel quaderno delle prove non entra nessun vettore e nessun nome")
righe = righe_del_quaderno()
controlla("il quaderno ha scritto", len(righe) > 0, "%d righe" % len(righe))

def campi(dato, visti=None):
    """Tutti i nomi di campo del quaderno, a qualunque profondita'."""
    visti = visti if visti is not None else set()
    if isinstance(dato, dict):
        for chiave, valore in dato.items():
            visti.add(chiave)
            campi(valore, visti)
    elif isinstance(dato, list):
        for valore in dato:
            campi(valore, visti)
    return visti


def liste_lunghe(dato):
    """Le liste di numeri troppo lunghe per essere altro che un vettore."""
    if isinstance(dato, dict):
        return any(liste_lunghe(v) for v in dato.values())
    if isinstance(dato, list):
        if len(dato) > 32 and all(isinstance(v, (int, float)) for v in dato):
            return True
        return any(liste_lunghe(v) for v in dato)
    return False


nomi_campi = campi(righe)
for vietato in ("vettore", "vettori", "vettore_selfie", "assomiglia_a",
                "respinti_da_minifasnet", "nome", "riconosciuti"):
    controlla("nessun campo %r" % vietato, vietato not in nomi_campi)
controlla("nessun vettore travestito da lista di numeri", not liste_lunghe(righe))
crudo = json.dumps(righe, ensure_ascii=False)
for nome in ("FELICE", "PADRE"):
    controlla("nessun nome %r" % nome, nome not in crudo)
ultima = [r for r in righe if r["chiamata"] == "riconosci"][-1]
controlla("ma i punteggi dell'altro modello si sono salvati",
          "altri_modelli" in ultima and "punteggi" in ultima,
          str(sorted(ultima.keys()))[:120])

print("\n9. nel registro dell'add-on non entra nessun nome, ma si legge chi per numero")
import logging


class Ascolta(logging.Handler):
    """Tiene da parte quello che l'add-on scrive nel suo registro."""

    def __init__(self):
        logging.Handler.__init__(self)
        self.righe = []

    def emit(self, record):
        self.righe.append(record.getMessage())


orecchio = Ascolta()
server.log.addHandler(orecchio)
alla_porta(attesi_nuovi)
alla_porta(attesi_nuovi, chi="estranea")
server.log.removeHandler(orecchio)
scritto = "\n".join(orecchio.righe)
controlla("il registro ha scritto", "riconosci" in scritto, "%d righe" % len(orecchio.righe))
for nome in ("FELICE", "PADRE"):
    controlla("nessun nome %r nel registro" % nome, nome not in scritto)
controlla("ma chi si legge, per numero", "#1" in scritto,
          [r for r in orecchio.righe if "riconosci" in r][0][:120])

print("\n" + ("TUTTO A POSTO" if not fallite else "FALLITE: " + ", ".join(fallite)))
sys.exit(1 if fallite else 0)
