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
assert r["tipo_documento"] == "Passaporto", r
assert r["tipo_letto_male"] == "F", r

# --- quando la lettera e' gia' giusta non si tocca niente ---------------------
r = server._raddrizza_il_tipo(esito("TD3", "P"), "passaporto")
assert "tipo_letto_male" not in r, r

# --- carta d'identita': TD1 e la I ------------------------------------------
r = server._raddrizza_il_tipo(esito("TD1", "1"), "carta")
assert r["sigla_documento"] == "I" and r["tipo_letto_male"] == "1", r

# --- le tre lettere della carta d'identita' vanno bene tutte e tre -----------
# La carta elettronica italiana scrive `C`, e prima veniva segnata come letta
# male su ogni singola lettura riuscita.
for gia_giusta in ("I", "A", "C"):
    r = server._raddrizza_il_tipo(esito("TD1", gia_giusta), "carta")
    assert "tipo_letto_male" not in r, gia_giusta
    assert r["sigla_documento"] == gia_giusta, r

# --- dichiarato e fotografato non coincidono: non si raddrizza, si dice ------
r = server._raddrizza_il_tipo(esito("TD1", "I"), "passaporto")
assert "tipo_letto_male" not in r, "non si corregge sul formato sbagliato"
assert "il_formato_non_torna" in r, r

# --- senza dichiarazione non si inventa niente -------------------------------
for dichiarato in (None, "", "patente"):
    r = server._raddrizza_il_tipo(esito("TD3", "F"), dichiarato)
    assert "tipo_letto_male" not in r, dichiarato

# --- e il numero di versione e' scritto in due posti: devono dire lo stesso --
# Il 21 agosto 2026 la 0.45.3 e' stata installata su Teramo e si e' presentata
# come 0.45.2: il numero che Home Assistant guarda per proporre l'aggiornamento
# sta in `config.yaml`, quello che l'add-on dichiara quando gli si chiede come
# sta e' scritto nel codice, ed era stato alzato solo il primo. Sono due copie e
# restano due copie, perche' `config.yaml` nell'immagine non ci finisce: questa
# riga e' la rete che si accorge quando divergono. Sbagliare il numero non e' un
# dettaglio, e' l'unico modo che abbiamo di sapere che cosa gira davvero su una
# macchina che non e' qui.
import io
import re

CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "..", "riconoscimento_volti", "config.yaml")
scritta = re.search(r'^version:\s*"([^"]+)"', io.open(CONFIG, encoding="utf-8").read(), re.M)
assert scritta, "in config.yaml non c'e' nessuna versione"
assert scritta.group(1) == server.VERSIONE, (scritta.group(1), server.VERSIONE)

print("il tipo documento si raddrizza solo quando dichiarato e formato"
      " concordano, e i due numeri di versione dicono lo stesso")
