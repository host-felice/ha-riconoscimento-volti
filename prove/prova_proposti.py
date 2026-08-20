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
assert r["data_nascita"] == {"valore": "01/03/1980"}, r
assert r["scadenza"] == {"valore": "01/03/2030"}, r

# --- l'anno intero funziona uguale -------------------------------------------
r = ottico.proponi(["01.03.1980", "21.07.2016", "01.03.2030"])
assert r["data_nascita"]["valore"] == "01/03/1980", r

# --- chi e' nato nel Duemila non finisce nel Novecento -----------------------
r = ottico.proponi(["01.03.05", "21.07.2016", "01.03.2030"])
assert r["data_nascita"]["valore"] == "01/03/2005", r

# --- i separatori cambiano da stampa a stampa --------------------------------
r = ottico.proponi(["01/03/1980", "21-07-2016", "01. 03. 2030"])
assert r["data_nascita"]["valore"] == "01/03/1980", r

# --- nessuna coppia: una delle due e' stata letta male, non si propone -------
assert ottico.proponi(["05.03.80", "21.07.2016", "01.03.2030"]) == {}

# --- due coppie: non si sa quale sia la buona, non si propone ----------------
assert ottico.proponi(["01.03.80", "01.03.2030", "03.09.80", "03.09.2030"]) == {}

# --- il rumore non diventa una data ------------------------------------------
assert ottico.proponi(["LUOGOFDATADENASOTA", "1234567890", "TE1234567X"]) == {}
assert ottico.proponi([]) == {}

# --- i campi numerati della patente ------------------------------------------
# "se tagli 1. 2. 3. 4a. 4b. 5. e ignori 7. e 9., riconosce tutto bene", detto
# da Felice il 20 agosto 2026 guardando cosa era uscito davvero.
patente = ["PATENTEDIGUIDA", "1.ROSSI", "2.MARIO", "3.01.03.80", "MESSINA(ME)",
           "4a.21.07.2016", "4C.MIT-UCO", "4b.01.03.2030", "5.U1A000000B", "9.B"]
r = ottico.dalla_patente(patente)
assert r["cognome"] == {"valore": "ROSSI"}, r
assert r["nome"]["valore"] == "MARIO", r
assert r["numero_documento"]["valore"] == "U1A000000B", r

# --- la data non si spaccia per un campo -------------------------------------
# Dentro `21.07.2016` c'e' un `2.`, e senza rete diventerebbe il nome.
r = ottico.dalla_patente(["1. ROSSI", "4a. 21.07.2016", "5. U1A000000B"])
assert "nome" not in r, r
assert r["cognome"]["valore"] == "ROSSI", r

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
# il caso guardato a mano nel portale della Questura il 20 agosto 2026: nel menu'
# CALATAFIMI compare sbarrato ma si puo' scegliere, con sotto CALATAFIMI SEGESTA.
# I due nomi convivono nella stessa provincia e non si devono confondere
assert comuni.cerca("CALATAFIMI (TP)")["codice"] == "419081003"
assert comuni.cerca("CALATAFIMI SEGESTA (TP)")["codice"] == "419081903"
assert comuni.cerca("CALATAFIM (TP)")["codice"] == "419081003"
# quello che non somiglia a niente non diventa un comune
assert comuni.cerca("XQZWKJ") is None
assert comuni.cerca("") is None

# --- il campo 3 porta il comune di nascita, il 4c quello di emissione --------
r = ottico.dalla_patente(patente)
# MIT-UCO vuol dire duplicato dell'Ufficio Centrale Operativo, che sta a Roma,
# e si riconosce anche storpiato: letto davvero `MIT-UCTO`
assert r["comune_emissione"]["valore"] == "ROMA (RM)", r
r = ottico.dalla_patente(["3. 12.03.90 TERAMO (TE)", "4c. MC-TERAMO"])
assert r["comune_emissione"]["valore"] == "TERAMO (TE)", r

print("i comuni si leggono dall'elenco della Polizia, con due caratteri di tolleranza")

# --- i luoghi presi dall'etichetta stampata ---------------------------------
# Righe ricalcate su una carta d'identita' e un passaporto veri, guardati il
# 20 agosto 2026. L'etichetta esce sfilacciata ma la parola intera sopravvive.
# **Le righe sono quelle uscite davvero dalla lettura**, spazi mangiati
# compresi: e' proprio quello che aveva rotto il primo tentativo, che cercava
# parole intere e nelle etichette non ne trovava nessuna.
fronte = ["CARTA DIIDENTITA /IDENTITY CARD", "COMUNFOI/MUNICIPALITY", "TERAMO",
          "COGNOME/SURNAME", "ROSSI", "LUOGOEDATADINASCITA",
          "PLACEANDDATEOFBIRTH", "MESSINA(ME)01.03.1980"]
r = ottico.dalle_etichette(fronte)
assert r["comune_emissione"]["valore"] == "TERAMO (TE)", r
# il valore sta due righe sotto, perche' fra le due etichette c'e' l'inglese
assert r["comune_nascita"]["valore"] == "MESSINA (ME)", r

retro = ["CODICEFISCALE", "ESTREMIATTODINASCITA", "FISCALCODE",
         "1234p5sB-1980012345", "RSSMRA80A01H501U",
         "INDIRIZZODIRESIDENZA/RESIDENCE",
         "VIALEDEITIGLI,N.12TERAMO(TE)"]
r = ottico.dalle_etichette(retro)
# il comune sta in fondo all'indirizzo, non e' tutta la riga
assert r["residenza"]["valore"] == "TERAMO (TE)", r
# e il numero dell'atto di nascita non deve diventare un comune: senza la sigla
# della provincia si pretende il nome esatto, altrimenti usciva Pisa
assert "comune_nascita" not in r, r

passaporto = ["Datadinascita.Dateofbirth.Datedenaissance.(4)", "01MAR/MAR1980",
              "Sesso.Sex.Sexe.(5)Luogodi nascita.Placeof birthLieu denaissance. (6)",
              "MESSINA(ME)"]
assert ottico.dalle_etichette(passaporto)["comune_nascita"]["valore"] == "MESSINA (ME)"

# senza etichetta non si prende niente
assert ottico.dalle_etichette(["CARTA DIIDENTITA", "TERAMO"]) == {}
assert ottico.dalle_etichette([]) == {}

print("i luoghi si trovano dall'etichetta che li annuncia, anche sfilacciata")

# --- la patente come esce davvero dalla lettura ------------------------------
r = ottico.dalla_patente(patente)
# il comune di nascita va a capo rispetto al numero del campo e alla data
assert r["comune_nascita"]["valore"] == "MESSINA (ME)", r
# e il numero del campo puo' avere la lettera maiuscola: 4C vale come 4c
assert r["comune_emissione"]["valore"] == "ROMA (RM)", r

# --- e queste sono le righe uscite dalla patente vera, il 20 agosto 2026 -----
# Il campo 5 va a capo prima del numero, il 4c resta attaccato alla data del 4a,
# e le date usano la barra invece del punto. Sette campi su sette.
vera = ["PATENTEDI GUIDA", "REPUBBLICAITALIANA", "1. ROSSI", "2. MARIO",
        "3.01/03/80", "MESSINA(ME)", "4a.21/07/20164c.MIT-UCO", "4b.01/03/2030",
        "5.", "U1A000000B", "7.", "9.B"]
r = dict(ottico.dalla_patente(vera), **ottico.proponi(vera))
atteso = {"cognome": "ROSSI", "nome": "MARIO", "data_nascita": "01/03/1980",
          "comune_nascita": "MESSINA (ME)", "numero_documento": "U1A000000B",
          "scadenza": "01/03/2030", "comune_emissione": "ROMA (RM)"}
for chiave, valore in atteso.items():
    assert r.get(chiave, {}).get("valore") == valore, (chiave, r.get(chiave))

print("la patente si legge anche senza spazi e con i numeri di campo maiuscoli,")
print("e sulla patente vera escono sette campi su sette")

# --- regole piu' lasche, ognuna da un caso che era fallito -------------------
# il numero del documento puo' uscire minuscolo, e si rimette maiuscolo
assert ottico.dalla_patente(["5. u1a000000b", "9.B"])["numero_documento"]["valore"] == "U1A000000B"
# fra i pezzi di una data ci sta qualunque cosa che non sia una cifra
assert ottico.proponi(["07·05·78", "07·05·2027"])
# la parentesi che chiude la provincia puo' mancare
assert ottico._comune_nel_pezzo("257TERAMO(TE")["nome"] == "TERAMO"
# ma una parola intera non diventa una sigla: (TERAMO) resta Teramo, non TE
assert comuni.cerca("(TERAMO)")["nome"] == "TERAMO"
# e il mese scritto a lettere non e' una data
assert ottico.proponi(["01MAR/MAR1980", "18GIU/JUN2029"]) == {}

print("le regole lasche reggono, e i casi di guardia non si rompono")

# --- la parentesi larga vale come quella normale, in ogni combinazione -------
# Letto davvero il 20 agosto 2026 su carta d'identita' e patente: la lettura,
# davanti a una stampa spaziata, tira fuori i caratteri a larghezza doppia delle
# scritture orientali, e non sempre tutti e due.
for aperta in ("(", "（"):
    for chiusa in (")", "）"):
        scritto = "MESSINA" + aperta + "ME" + chiusa
        assert comuni.cerca(scritto)["nome"] == "MESSINA", scritto
        assert ottico._comune_nel_pezzo("3." + scritto)["provincia"] == "ME", scritto

# e il caso vero, dove il comune di nascita spariva su tutti e due i documenti
assert ottico.dalla_patente(
    ["3.01/03/80", "MESSINA（ME)", "4a.21/07/20164c.MIT-UCO"]
)["comune_nascita"]["valore"] == "MESSINA (ME)"
assert ottico.dalle_etichette(
    ["LUOGOEDATADINASCITA", "PLACEANDDATEOFBIRTH", "MESSINA（ME)01.03.1980"]
)["comune_nascita"]["valore"] == "MESSINA (ME)"

print("la parentesi larga vale come quella normale, anche mescolata")
