# -*- coding: utf-8 -*-
"""Il testo letto si registra solo quando qualcuno lo manda, e arriva tagliato.

E' l'unica riga del quaderno che contiene dati di una persona. Ci finisce
perche' quella persona ha premuto un tasto, e con due tetti addosso: quaranta
righe e centoventi caratteri per riga. Non sono numeri di gusto: senza, una
richiesta storta o malevola scriverebbe nel quaderno quanto vuole.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "riconoscimento_volti", "app"))
import registro
import server

registro.CARTELLA = os.environ.get("TEMP", ".")
registro.FILE = os.path.join(registro.CARTELLA, "prove_finte.jsonl")
if os.path.exists(registro.FILE):
    os.remove(registro.FILE)
server.OPZIONI["parola"] = ""
cliente = server.app.test_client()

cliente.post("/testo", data={"righe": json.dumps(["COMUNFOI/MUNICIPALITY", "TERAMO"]),
                             "mancavano": "comune_nascita,residenza",
                             "tipo_dichiarato": "carta"})
riga = [json.loads(r) for r in io.open(registro.FILE, encoding="utf-8")][-1]
assert riga["chiamata"] == "testo", riga
assert riga["testo_donato"] == ["COMUNFOI/MUNICIPALITY", "TERAMO"], riga
assert riga["mancavano"] == ["comune_nascita", "residenza"], riga

# --- i due tetti tengono ------------------------------------------------------
cliente.post("/testo", data={"righe": json.dumps(["x" * 500] * 200),
                             "tipo_dichiarato": "patente"})
riga = [json.loads(r) for r in io.open(registro.FILE, encoding="utf-8")][-1]
assert len(riga["testo_donato"]) == 40, len(riga["testo_donato"])
assert all(len(r) == 120 for r in riga["testo_donato"])

# --- una richiesta senza niente non fa cadere niente --------------------------
cliente.post("/testo", data={"righe": "non e' json"})
riga = [json.loads(r) for r in io.open(registro.FILE, encoding="utf-8")][-1]
assert riga["testo_donato"] == [], riga

os.remove(registro.FILE)
print("il testo letto si registra solo se mandato, e arriva tagliato")
