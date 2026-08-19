# Cosa cambia, versione per versione

Home Assistant mostra questa pagina quando propone un aggiornamento. Serve a
sapere cosa si sta installando senza andare a leggere il codice.

## 0.14.0

Due regole che erano decise e non erano costruite. Vengono da una sessione di
prova del 19 agosto 2026 andata storta.

- **Due tentativi, mai tre.** Al primo fallimento il banco di prova consiglia le
  migliorie che spostano davvero il punteggio, con i numeri misurati accanto. Al
  secondo si ferma e propone le due strade: mandare documento e selfie all'host
  per la convalida, oppure il controllo di persona all'arrivo. Prima non contava
  niente, e un quattordicenne ha riprovato quattro volte davanti alla sua
  famiglia mentre i punteggi salivano perche' migliorava l'inquadratura: alla
  fine non si sapeva piu' quale numero fosse il suo.
- **Non esiste l'ospite senza dati.** Il ripiego che chiamava l'ospite
  "ospite 1" quando il documento non si leggeva e' stato tolto. L'identita' di un
  ospite sono i suoi dati, e il doppione si riconosce su quelli: prima la stessa
  persona finiva due volte nella lista, una col nome letto e una col ripiego, e
  alla porta le due voci agganciavano la stessa faccia con lo stesso punteggio.
  Due voci per una persona contano due arrivi dove ce n'e' uno, e chi e' arrivato
  davvero e' quello che finisce in Questura. Le voci salvate prima di questa
  versione non hanno identita' e vengono buttate.

## 0.13.1

- **Il registro dell'add-on non scrive piu' il nome dell'ospite.** Al suo posto
  il numero, cioe' il posto nella lista degli attesi arrivata con la richiesta:
  `riconosciuti ['#1 0.721', '#2 0.721']`. Chi ha mandato la lista sa rileggere
  i numeri, chi legge il registro no. La 0.13.0 aveva chiuso il quaderno delle
  prove e l'invio a Home Assistant e aveva lasciato aperta questa, che e' la
  terza superficie: il registro si legge dall'interfaccia e finisce nei log che
  si mandano quando si chiede aiuto. La macchina dell'add-on non deve tenere i
  nomi.
- Nella risposta i nomi restano, perche' chi chiama deve sapere chi e' arrivato.
  Ogni atteso si porta dietro anche il suo numero.

## 0.13.0

- **Alla porta si misurano tutti e due i modelli dei volti**, come il confronto
  documento-selfie faceva gia'. Prima il riconoscimento girava con uno solo, e
  fra i due si sarebbe deciso senza averli mai visti nel caso che conta: le
  facce alla porta arrivano di lontano, di sbieco e piu' d'una per scatto.
  L'ospite entra fra gli attesi con **un vettore per modello**, perche' il
  selfie sparisce subito e dopo non c'e' piu' modo di rifarlo.
- **Chi era registrato prima non resta fuori.** Con un vettore solo la porta
  risponde come sempre e l'altro modello dice che non si e' potuto misurare, con
  il perche'. Nessuna misura di confronto puo' costare a una persona la porta
  chiusa: se il secondo giro inciampa, il primo vale lo stesso.
- **Il quaderno delle prove non scrive piu' il nome dell'ospite.** Ci finiva da
  sempre, nascosto in "a chi assomiglia" la faccia sconosciuta: non si chiamava
  "nome", quindi il filtro lo lasciava passare. Il quaderno viaggia verso Home
  Assistant quando la persona acconsente, e li' dentro devono restare solo
  numeri che non riportano a nessuno.

## 0.12.1

- **Tolto l'allarme "il documento sembra ripreso da uno schermo".** Su un
  passaporto vero, tenuto in mano, era scattato a 0,91. Il modello ha ragione e
  la domanda era sbagliata: lui sa dire se una faccia e' una persona o la
  fotografia di una persona, e sul documento la faccia **e'** la fotografia di
  una persona. Qualunque numero dia parla della stampa, non di dove quella
  stampa stava. I tre numeri si continuano a scrivere nel quaderno, ma non
  fanno piu' scattare niente.

## 0.12.0

- **Il "No, grazie" adesso ferma tutto.** Prima fermava solo l'invio, e il
  risultato finiva comunque nel quaderno dentro l'add-on: siccome l'add-on
  gira sulla macchina di chi ha chiesto il favore, era esattamente la cosa che
  la domanda chiama "tenere il risultato". Un no che ferma solo meta' e' un no
  finto. Chi risponde no adesso non lascia traccia da nessuna parte.
- La prova alla porta segue la stessa risposta del confronto, e non chiede una
  seconda volta.
- **Una faccia sconosciuta in un solo scatto non e' piu' un allarme.** Su un
  fotogramma mosso il rilevatore inventa una faccia che non c'e', e quella
  somiglia a zero a chiunque, esattamente come un estraneo vero: il punteggio
  non li distingue. A distinguerli e' il tempo, ed e' il motivo per cui alla
  porta si scattano tre foto. Adesso si avvisa solo per chi compare in almeno
  due scatti.

## 0.11.0

- **La fotocamera si gira.** Alla porta partiva quella dietro e non c'era modo
  di cambiarla: adesso c'è un pulsante, e vale anche per il selfie. Alla porta
  ora parte quella davanti, che è come si tiene il telefono per provare.
- **Il registro della porta scrive con che punteggio** ha riconosciuto ognuno.
  Prima diceva solo il nome, e "riconosciuto" senza un numero non dice se è
  passato largo o per un pelo.
- Di ogni prova si annota se veniva da un Android o da un iPhone. Solo la
  famiglia, non la riga intera del browser, che in mezzo a poche prove
  riporterebbe a una persona sola.

## 0.10.1

- Le due risposte sul consenso sono esplicite, "Sì, tienilo" e "No, grazie",
  e nessuna delle due parte scelta. Finché non si risponde il pulsante del
  controllo resta spento.
- Il riquadro del consenso era illeggibile per chi tiene il sistema in tema
  scuro: aveva colori suoi, adesso è un riquadro come tutti gli altri.

## 0.10.0

- Chi fa una prova può dire di sì all'invio del risultato, e i numeri arrivano
  da soli a Home Assistant. Non deve scaricare né mandare niente.
- Partono solo numeri: punteggi, dimensioni e tempi. Facce, nomi e documenti
  no, e le foto vengono cancellate comunque.
- Se l'invio non arriva, la prova resta scritta in casa e il guasto si conta.

## 0.9.0

- **Due modelli invece di uno** per il confronto dei volti, e si sceglie quale
  con un'opzione. `buffalo_l` separa meglio ma è dichiarato per sola ricerca
  non commerciale; `sface` è Apache 2.0, occupa 135 MB invece di 331 ed è
  quasi quattro volte più veloce.
- Una richiesta sola può restituire il punteggio di tutti e due sulla stessa
  faccia, che è l'unico confronto che vuol dire qualcosa.
- I vettori dei due modelli non si parlano: chi prova a mischiarli si sente
  rispondere che sono di modelli diversi, invece di ricevere un numero senza
  senso.
- Ogni confronto finisce in un quaderno delle prove che si rilegge da `/prove`,
  con le somme già tirate per modello. Vettori, immagini e nomi non ci entrano.
- **MiniFASNet non guardava niente.** Rispondeva sempre lo stesso numero su
  qualunque foto. Le istruzioni di chi lo ha convertito sono sbagliate su due
  punti, e si vede solo misurando: corretto, adesso i selfie veri stanno fra
  0,84 e 0,99.
- Sul documento MiniFASNet guarda solo se la foto veniva da uno schermo. Su una
  pagina stampata chiedere se c'era una persona non ha senso.
- L'opzione della soglia di MiniFASNet nel pannello aveva il nome vecchio,
  quindi cambiarla non faceva niente.

## 0.8.0

- **MiniFASNet**: dice se davanti all'obiettivo c'era una persona o la sua
  fotografia. Non chiede niente all'ospite, guarda un solo scatto.
- L'add-on ha un'icona nell'elenco di Home Assistant.
- Una licenza sul repository (Apache 2.0) e l'avviso che i modelli hanno la
  loro, diversa.

## 0.7.x

- La memoria torna indietro dopo ogni foto e non solo dopo la lettura dei
  caratteri. A riposo l'add-on sta sotto i 70 MB.
- Il modello dei volti si apre solo quando serve e si chiude dopo venti minuti
  di silenzio. Riaprirlo costa mezzo secondo.
- La lettura dei caratteri gira in un processo che poi muore, così non lascia
  memoria occupata dietro di sé.
