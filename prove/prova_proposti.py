# -*- coding: utf-8 -*-
"""I campi proposti dal testo stampato: pochi, e solo quando il conto torna.

Sono i soli valori che l'ospite si vede gia' scritti senza che nessuna cifra di
controllo li abbia verificati. Un campo vuoto gli costa dieci secondi di
scrittura; un campo pieno e sbagliato costa una schedina sbagliata in Questura.

Si lancia da questa cartella:  python prova_proposti.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "riconoscimento_volti", "app"))
import ottico

# --- una patente letta bene: tre date, in ordine ----------------------------
r = ottico.proponi(["ROSSI", "MARIO", "01.03.1980 MESSINA (ME)",
                    "4a. 12.03.2019", "4b. 12.03.2029", "5. TE1234567X"])
assert r == {"data_nascita": "01/03/1980", "scadenza": "12/03/2029"}, r

# --- i separatori cambiano da stampa a stampa, il conto no -------------------
r = ottico.proponi(["01/03/1980", "12-03-2019", "12 03 2029"])
assert r["data_nascita"] == "01/03/1980" and r["scadenza"] == "12/03/2029", r

# --- il conto non torna: non si propone niente invece di indovinare ----------
for righe in ([], ["01.03.1980"], ["01.03.1980", "12.03.2019"],
              ["01.03.1980", "12.03.2019", "12.03.2029", "01.01.2000"]):
    assert ottico.proponi(righe) == {}, righe

# --- il rumore non diventa una data ------------------------------------------
assert ottico.proponi(["LUOGOFDATADENASOTA", "1234567890", "12.3.2029"]) == {}

print("si propone solo quello che si riconosce dalla forma, e solo se il conto torna")
