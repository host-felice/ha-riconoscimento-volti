# -*- coding: utf-8 -*-
"""Si manda solo quello che la macchina non ha saputo usare.

Le righe sono quelle uscite davvero da una carta d'identita' il 20 agosto 2026.
Lo scenario: la banda ottica ha letto tutto, il testo stampato ha dato il comune
di emissione, e il comune di nascita e' rimasto vuoto. Devono partire le
etichette e la riga del campo mancante, e restare a casa il cognome, il nome, il
numero del documento e le date.

Il pezzo di pagina si estrae e si fa girare con node, che e' l'unico modo di
provare davvero quello che gira sul telefono invece di una sua imitazione.
"""
import io
import os
import re
import subprocess
import sys

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "riconoscimento_volti", "app", "pagina.html")
js = "\n".join(re.findall(r"<script>(.*?)</script>",
                          io.open(APP, encoding="utf-8").read(), re.S))

pezzi = []
for nome in ("ORDINE", "SOLO_SU", "RESTA_POCO"):
    trovato = re.search(r"^const " + nome + r"\s*=.*?;\s*$", js, re.S | re.M)
    assert trovato, "non trovo " + nome
    pezzi.append(trovato.group(0))
for nome in ("daMostrare", "nudo", "righeDaMandare"):
    trovato = re.search(r"^function " + nome + r"\(.*?^}", js, re.S | re.M)
    assert trovato, "non trovo " + nome
    pezzi.append(trovato.group(0))

CASO = '''
let tipo = "carta";
const carta = {
  campi: { cognome: { valore: "ROSSI" }, nome: { valore: "MARIO" },
           sesso: { valore: "M" }, data_nascita: { valore: "01/03/1980" },
           comune_nascita: { valore: "" }, numero_documento: { valore: "CA00000AB" },
           scadenza: { valore: "01/03/2035" }, comune_emissione: { valore: "TERAMO (TE)" } },
  testo_stampato: ["REPUBBLICA ITALIANA", "CA00000AB", "MINISTERO DELL'INTERNO",
    "CARTA DIIDENTITA /IDENTITY CARD", "IT", "COMUNFOI/MUNICIPALITY", "TERAMO",
    "COGNOME/SURNAME", "4RSH", "ROSSI", "NOME/NAME", "MARIO", "LUOGOEDATADINASCITA",
    "PLACEANDDATEOFBIRTH", "MESSINA(ME)01.03.1980", "SESSO", "STATURA", "CITTADINANZA",
    "XGS", "HEIGHT", "NATIONALITY", "168", "ITA", "EMISSIONE/ISSUING", "SCADENZA/EXPIRY",
    "01.03.2024", "01.03.2035", "FIRMADELTITOLARE", "HOLDER'SSIGNATURE", "785146"]
};
console.log(JSON.stringify(righeDaMandare(carta)));
'''

dove = os.path.join(os.environ.get("TEMP", "."), "prova_filtro.js")
io.open(dove, "w", encoding="utf-8").write("\n\n".join(pezzi) + "\n" + CASO)
uscita = subprocess.run([("node.exe" if os.name == "nt" else "node"), dove],
                        capture_output=True, text=True)
assert uscita.returncode == 0, uscita.stderr
import json
mandate = json.loads(uscita.stdout.strip().splitlines()[-1])
os.remove(dove)

# quello che la banda ottica ha gia' letto bene non serve a nessuno
for restare in ("ROSSI", "MARIO", "CA00000AB", "TERAMO", "01.03.2035", "168"):
    assert restare not in mandate, "non doveva partire: " + restare

# la riga del campo mancante parte, anche se porta con se' una data buona: senza
# di lei non si capisce perche' il comune di nascita non e' uscito
assert "MESSINA(ME)01.03.1980" in mandate, mandate
# e le etichette, che sono quelle che dicono dove sbagliamo l'ancoraggio
for serve in ("LUOGOEDATADINASCITA", "COMUNFOI/MUNICIPALITY"):
    assert serve in mandate, "manca l'etichetta: " + serve

print("parte solo quello che non si e' saputo usare: %d righe su 30" % len(mandate))
