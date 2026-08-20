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

# --- i campi numerati della patente ------------------------------------------
# "se tagli 1. 2. 3. 4a. 4b. 5. e ignori 7. e 9., riconosce tutto bene", detto
# da Felice il 20 agosto 2026 guardando cosa era uscito davvero.
patente = ["PATENTE DI GUIDA", "1. MARRA", "2. FELICE", "3. 01.03.80 MESSINA (ME)",
           "4a. 21.07.201664c.MIT-UCTO", "4b. 01.03.2030", "5. U1A000000B", "7.", "9. B"]
r = ottico.dalla_patente(patente)
assert r["cognome"] == {"valore": "MARRA", "verificato": False}, r
assert r["nome"]["valore"] == "FELICE", r
assert r["numero_documento"]["valore"] == "U1A000000B", r

# --- la data non si spaccia per un campo -------------------------------------
# Dentro `21.07.2016` c'e' un `2.`, e senza rete diventerebbe il nome.
r = ottico.dalla_patente(["1. MARRA", "4a. 21.07.2016", "5. U1A000000B"])
assert "nome" not in r, r
assert r["cognome"]["valore"] == "MARRA", r

# --- quello che non ha la forma giusta resta vuoto ---------------------------
assert ottico.dalla_patente(["1. 12345", "2. ---", "5. AB"]) == {}
assert ottico.dalla_patente([]) == {}

print("la nascita e la scadenza si riconoscono dal giorno e mese che hanno in comune,")
print("e cognome, nome e numero del documento dal numero del loro campo")

# --- il comune si prende dall'elenco, non da come lo ha letto la macchina ----
import comuni

assert comuni.cerca("MESSINA (ME)")["nome"] == "MESSINA"
# una lettera sbagliata si perdona
assert comuni.cerca("MESSIMA (ME)")["nome"] == "MESSINA"
# i cinque omonimi senza provincia non si scelgono a caso: meglio niente
assert comuni.cerca("CASTRO") is None
assert comuni.cerca("CASTRO (BG)")["provincia"] == "BG"
# apostrofi e accenti non contano da nessuno dei due lati
assert comuni.cerca("ALI (ME)")["nome"] == "ALI'"
# i comuni soppressi si usano, e la Questura li accetta: chiesto al suo web
# service il 20 agosto 2026. Ma solo quando il documento dice la provincia,
# perche' e' lei a distinguere il soppresso da chi ha preso il suo posto
assert comuni.cerca("ABBADIA CERRETO (MI)")["codice"] == "403015699"
assert comuni.cerca("ABBADIA CERRETO (LO)")["codice"] == "403098001"
# senza provincia si resta fra i vivi
assert comuni.cerca("ABBADIA CERRETO")["provincia"] == "LO"
# quello che non somiglia a niente non diventa un comune
assert comuni.cerca("XQZWKJ") is None
assert comuni.cerca("") is None

# --- il campo 3 porta il comune di nascita, il 4c quello di emissione --------
r = ottico.dalla_patente(patente)
assert r["comune_nascita"]["valore"] == "MESSINA (ME)", r
# MIT-UCO vuol dire duplicato dell'Ufficio Centrale Operativo, che sta a Roma,
# e si riconosce anche storpiato: letto davvero `MIT-UCTO`
assert r["comune_emissione"]["valore"] == "ROMA (RM)", r
r = ottico.dalla_patente(["3. 12.03.90 TERAMO (TE)", "4c. MC-TERAMO"])
assert r["comune_emissione"]["valore"] == "TERAMO (TE)", r

print("i comuni si leggono dall'elenco della Polizia, con due caratteri di tolleranza")
