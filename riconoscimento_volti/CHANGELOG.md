# Cosa cambia, versione per versione

Home Assistant mostra questa pagina quando propone un aggiornamento. Serve a
sapere cosa si sta installando senza andare a leggere il codice.

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
