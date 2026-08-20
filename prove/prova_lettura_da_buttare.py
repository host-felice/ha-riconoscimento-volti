# -*- coding: utf-8 -*-
"""Una lettura con troppe cifre di controllo sbagliate va buttata, non corretta.

Il caso vero, 20 agosto 2026, una carta d'identita': la banda ottica era stata
trovata e interpretata come TD1, ma non tornavano numero documento, data di
nascita e scadenza. Quello che ne usciva era `PUBBLCATA` come numero e `R00LLN`
come scadenza: spazzatura che somiglia a dei dati. La stessa carta rifotografata
diciassette secondi dopo si e' letta senza un errore.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "riconoscimento_volti", "app"))
import mrz

# la cifra che copre tutte le altre non si conta: cade insieme alla prima
assert mrz.quanti_sbagli([]) == 0
assert mrz.quanti_sbagli(["tutto_insieme"]) == 0
assert mrz.quanti_sbagli(["scadenza", "tutto_insieme"]) == 1

# una sola cifra che non torna e' un carattere preso per un altro: si corregge
assert mrz.quanti_sbagli(["scadenza"]) < mrz.TROPPI_SBAGLI

# il caso vero: tre campi piu' la cifra d'insieme, la lettura si butta
disastro = ["numero_documento", "data_nascita", "scadenza", "tutto_insieme"]
assert mrz.quanti_sbagli(disastro) == 3
assert mrz.quanti_sbagli(disastro) >= mrz.TROPPI_SBAGLI

print("una lettura con troppe cifre sbagliate si rifa', non si corregge")
