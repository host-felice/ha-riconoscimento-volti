# -*- coding: utf-8 -*-
"""Le somme del quaderno separano i due mondi, o non servono a niente.

Non misura facce: misura che una riga senza etichetta venga scartata invece di
inquinare il mucchio, che alla porta il presente faccia un confronto giusto e
tutti gli altri attesi degli estranei, e che il margine sia davvero la distanza
fra i due mondi. E' il numero su cui si decide fra i due modelli (#34): se
questa funzione sbaglia, si sceglie il modello con il numero sbagliato.

Si lancia da questa cartella:  python prova_somme.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "riconoscimento_volti", "app"))
os.environ["DATI"] = tempfile.mkdtemp()
import registro


def scrivi(riga):
    registro.scrivi_riga(riga)


def confronta(modello, punteggio, stessa, soglia=0.4, altro=None):
    riga = {"chiamata": "confronta", "modello": modello, "somiglianza": punteggio,
            "soglia": soglia}
    if stessa is not None:
        riga["stessa_persona"] = stessa
    if altro:
        nome, p, s = altro
        riga["altri_modelli"] = {nome: {"somiglianza": p, "soglia": s}}
    return riga


def porta(modello, punteggi, presenti, soglia=0.4):
    """punteggi: {posizione: somiglianza}. presenti: le posizioni davvero davanti."""
    riga = {"chiamata": "riconosci", "modello": modello, "soglia": soglia,
            "tutti": [{"posizione": n, "somiglianza": p} for n, p in punteggi.items()]}
    if presenti is not None:
        riga["presenti"] = presenti
    return riga


# --- la riga senza etichetta non entra nei conti, ma si conta ----------------
scrivi(confronta("sface", 0.9, None))
s = registro.somme()
assert s["confronti"] == {}, s["confronti"]
assert s["righe_senza_etichetta"] == 1, s

# --- confronto documento-selfie, con l'altro modello sulla stessa faccia -----
scrivi(confronta("sface", 0.62, True, altro=("buffalo_l", 0.71, 0.4)))
scrivi(confronta("sface", 0.38, True, altro=("buffalo_l", 0.44, 0.4)))
scrivi(confronta("sface", 0.11, False, altro=("buffalo_l", 0.09, 0.4)))
s = registro.somme()["confronti"]
assert s["sface"]["giusti"]["quante"] == 2, s["sface"]
assert s["sface"]["estranei"]["quante"] == 1, s["sface"]
# Il margine: peggiore dei giusti meno migliore degli estranei.
assert s["sface"]["margine"] == 0.27, s["sface"]["margine"]
assert s["buffalo_l"]["margine"] == 0.35, s["buffalo_l"]["margine"]
# Gli errori, contro la soglia che c'era quel giorno.
assert s["sface"]["ospiti_respinti_per_sbaglio"] == 1, s["sface"]
assert s["sface"]["estranei_fatti_passare"] == 0, s["sface"]
assert s["buffalo_l"]["ospiti_respinti_per_sbaglio"] == 0, s["buffalo_l"]

# --- alla porta: uno giusto, tutti gli altri attesi sono estranei ------------
scrivi(porta("sface", {1: 0.55, 2: 0.20, 3: 0.17}, [1]))
s = registro.somme()["confronti"]["sface"]
assert s["giusti"]["quante"] == 3, s          # due dai confronti, uno dalla porta
assert s["estranei"]["quante"] == 3, s        # uno dal confronto, due dalla porta
assert s["estranei"]["migliore"] == 0.2, s    # il vecchio 0.11 battuto dallo 0.20
assert s["margine"] == 0.18, s["margine"]  # 0.38 il peggiore dei giusti, 0.20 il piu' alto estraneo

# --- lo sconosciuto davanti alla porta: lista vuota, non campo mancante ------
prima = registro.somme()["confronti"]["sface"]["giusti"]["quante"]
scrivi(porta("sface", {1: 0.51, 2: 0.29}, []))
s = registro.somme()["confronti"]["sface"]
assert s["giusti"]["quante"] == prima, "una lista vuota non aggiunge confronti giusti"
assert s["estranei"]["quante"] == 5, s
assert s["margine"] < 0, "i due mondi si sono sovrapposti e il margine deve dirlo"

# --- la porta senza etichetta si scarta, come il confronto ------------------
prima = registro.somme()
scrivi(porta("sface", {1: 0.99, 2: 0.98}, None))
dopo = registro.somme()
assert dopo["confronti"] == prima["confronti"], "una porta senza etichetta ha sporcato i conti"
assert dopo["righe_senza_etichetta"] == prima["righe_senza_etichetta"] + 1, dopo

print("le somme separano i due mondi: %d righe, %d scartate" %
      (dopo["prove_in_tutto"], dopo["righe_senza_etichetta"]))
