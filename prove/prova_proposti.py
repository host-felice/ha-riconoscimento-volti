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

# --- la patente vera letta il 20 agosto 2026 --------------------------------
# Le righe sono quelle uscite davvero: l'anno di nascita a due cifre, e la data
# di rilascio appiccicata al campo che segue, che infatti non deve risultare.
vera = ["PATENTE DI GUIDA", "ROSSI", "MARIO", "3. 01.03.80 MESSINA (ME)",
        "4a. 21.07.20164c.MIT-UCO", "4b. 01.03.2030", "5. TE1234567X"]
r = ottico.proponi(vera)
assert r["data_nascita"] == {"valore": "01/03/1980", "verificato": True}, r
assert r["scadenza"] == {"valore": "01/03/2030", "verificato": True}, r

# --- l'anno intero funziona uguale -------------------------------------------
r = ottico.proponi(["01.03.1980", "21.07.2016", "01.03.2030"])
assert r["data_nascita"]["valore"] == "01/03/1980", r

# --- chi e' nato nel Duemila non finisce nel Novecento -----------------------
r = ottico.proponi(["07.05.05", "21.07.2016", "01.03.2030"])
assert r["data_nascita"]["valore"] == "07/05/2005", r

# --- i separatori cambiano da stampa a stampa --------------------------------
r = ottico.proponi(["01/03/1980", "21-07-2016", "07. 05. 2027"])
assert r["data_nascita"]["valore"] == "01/03/1980", r

# --- nessuna coppia: una delle due e' stata letta male, non si propone -------
assert ottico.proponi(["01.05.78", "21.07.2016", "01.03.2030"]) == {}

# --- due coppie: non si sa quale sia la buona, non si propone ----------------
assert ottico.proponi(["01.03.80", "01.03.2030", "03.09.80", "03.09.2030"]) == {}

# --- il rumore non diventa una data ------------------------------------------
assert ottico.proponi(["LUOGOFDATADENASOTA", "1234567890", "TE1234567X"]) == {}
assert ottico.proponi([]) == {}

print("la nascita e la scadenza si riconoscono dal giorno e mese che hanno in comune")
