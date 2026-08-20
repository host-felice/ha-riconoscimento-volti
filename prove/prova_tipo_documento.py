# -*- coding: utf-8 -*-
"""La lettera del tipo documento si raddrizza con quello che l'ospite ha dichiarato.

Successo su un passaporto vero il 20 agosto 2026: la banda ottica ha letto `F`
dove c'e' scritto `P`, e il documento e' diventato "non riconosciuto". Quella
lettera **non ha nessuna cifra di controllo**, quindi niente se ne accorge.

Si lancia da questa cartella:  python prova_tipo_documento.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "riconoscimento_volti", "app"))
import server


def esito(formato, lettera):
    return {"formato": formato, "sigla_documento": lettera,
            "tipo_documento": "documento non riconosciuto",
            "campi": {"tipo_documento": {"valore": lettera, "verificato": None}}}


# --- il caso vero: passaporto dichiarato, TD3 letto, ma la lettera dice F -----
r = server._raddrizza_il_tipo(esito("TD3", "F"), "passaporto")
assert r["sigla_documento"] == "P", r
assert r["campi"]["tipo_documento"]["valore"] == "P", r
assert r["tipo_documento"] == "passaporto", r
assert r["tipo_letto_male"] == "F", r

# --- quando la lettera e' gia' giusta non si tocca niente ---------------------
r = server._raddrizza_il_tipo(esito("TD3", "P"), "passaporto")
assert "tipo_letto_male" not in r, r

# --- carta d'identita': TD1 e la I ------------------------------------------
r = server._raddrizza_il_tipo(esito("TD1", "1"), "carta")
assert r["sigla_documento"] == "I" and r["tipo_letto_male"] == "1", r

# --- dichiarato e fotografato non coincidono: non si raddrizza, si dice ------
r = server._raddrizza_il_tipo(esito("TD1", "I"), "passaporto")
assert "tipo_letto_male" not in r, "non si corregge sul formato sbagliato"
assert "il_formato_non_torna" in r, r

# --- senza dichiarazione non si inventa niente -------------------------------
for dichiarato in (None, "", "patente"):
    r = server._raddrizza_il_tipo(esito("TD3", "F"), dichiarato)
    assert "tipo_letto_male" not in r, dichiarato

print("il tipo documento si raddrizza solo quando dichiarato e formato concordano")
