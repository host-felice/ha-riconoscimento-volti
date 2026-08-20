# Cosa cambia, versione per versione

Home Assistant mostra questa pagina quando propone un aggiornamento. Serve a
sapere cosa si sta installando senza andare a leggere il codice.

## 0.27.0

- **La patente si legge dai numeri dei suoi campi.** Detta da Felice il 20 agosto
  2026 guardando cosa era uscito davvero: "se tagli 1. 2. 3. 4a. 4b. 5. e ignori
  7. e 9., riconosce tutto bene". Adesso arrivano gia' scritti anche **cognome**
  (campo 1), **nome** (campo 2) e **numero del documento** (campo 5). Con le due
  date fanno cinque campi su sette.

  Smentisce una scelta fatta prima: si era deciso di non fidarsi delle etichette
  perche' la lettura le sfilaccia. Vero per le etichette **scritte**, falso per
  quelle **numerate**: i numeri sopravvivono, e in una patente vera c'erano tutti.

  La rete e' la forma del valore. Un cognome fatto di lettere, un numero di
  patente fatto di lettere e cifre e lungo il giusto. Serve, perche' la lettura
  ogni tanto salta gli spazi e attacca un pezzo al successivo, e perche' dentro
  una data come `21.07.2016` c'e' un `2.` che senza rete diventerebbe il nome.
  Quello che non ha la forma resta vuoto e lo scrive l'ospite.

- **L'anno di una data ha due cifre o quattro, mai tre.** Con tre usciva un anno
  inventato.

- **L'avviso "mi serve il numero del documento" adesso se ne va.** Restava
  appiccicato sotto anche dopo che il numero era stato scritto e la
  registrazione era andata a buon fine: si leggeva "non ha funzionato" davanti a
  una cosa che aveva funzionato.

## 0.26.0

Riscritta la regola che ricava le date dal testo stampato, sulle righe vere di
una patente letta il 20 agosto 2026. Il registro diceva "date trovate: 1" mentre
in pagina se ne vedevano tre: non sbagliava la lettura, sbagliava la regola.

- **L'anno puo' avere due cifre.** Sulla patente la data di nascita e' stampata
  cosi': `01/03/80`. La regola ne pretendeva quattro, quindi la data di nascita
  non la vedeva proprio, e l'unica che contava era la scadenza. Il taglio e'
  quello di sempre: fino all'anno in corso siamo nel Duemila, oltre nel
  Novecento.
- **Le date che servono sono due**, nascita e scadenza. Quella di rilascio non la
  chiede nessuno.
- **Non si conta piu' e non si va piu' a posizione.** Si cerca **l'unica coppia
  di date che condivide giorno e mese**: la piu' vecchia e' la nascita, l'altra
  la scadenza, e le due si sono verificate a vicenda. Andare a posizione non si
  poteva piu', e a dirlo e' la stessa lettura: la data di rilascio esce attaccata
  al campo che segue (`21/07/20164c.MIT-UCO`), quindi le date riconoscibili non
  sono tre e non sono in fila. Zero coppie o piu' d'una, non si propone niente.
- **Il tipo di documento non fa piu' cadere la lettura** quando manca. Bastava un
  esito senza quel campo e la richiesta finiva in errore invece di rispondere.
  Trovato dal controllo sulla scadenza, che era rotto dalla 0.24.0 e non se ne
  era accorto nessuno: adesso i controlli si lanciano tutti e cinque.

## 0.25.0

- **Meno campi da guardare.** Restano tipo di documento, cognome, nome, sesso,
  data di nascita, numero del documento e scadenza. Spariscono **numero di
  supporto** e **numero personale**, che non vogliono dire niente per chi ha il
  documento in mano, e **stato di rilascio**, che finche' si prova con documenti
  italiani e' sempre lo stesso. Via anche **cittadinanza**, che tornera' quando
  sara' un menu' che si completa mentre si scrive. La banda ottica continua a
  leggerli tutti e quattro: non si mostrano, non si perdono.
- **Il formato della data adesso si vede**: nei campi vuoti c'e' scritto
  `gg/mm/aaaa`, e sul telefono si apre la tastiera numerica. Senza un esempio
  davanti non c'era modo di sapere se l'anno lo volesse a due cifre o a quattro.
- **Il testo stampato si legge a 1600 pixel invece di 1000** quando il documento
  non ha la banda ottica. Il 1000 era stato scelto quando ogni lettura pagava
  anche le due passate della banda, e il tetto era il tempo. Sulla patente quelle
  passate non ci sono piu' (24,9 secondi diventati 5,2) e i venti secondi
  liberati si spendono meglio in pixel. Serviva: nell'ultima prova, delle **tre**
  date stampate sulla patente ne era stata letta **una**, e sono la riga piu'
  piccola del documento.

## 0.24.0

Da una riga di registro sulla prova con la patente: **24,9 secondi**, righe
stampate 11, campi proposti 0.

- **Sulla patente la banda ottica non si cerca piu'.** Non ce l'ha, e lo si sa
  prima di scattare perche' l'ospite lo ha dichiarato. Cercarla lo stesso
  costava le **due passate** della lettura, la seconda a piu' pixel apposta per
  riprovare quando la prima fallisce: su un documento senza banda sono due
  tentativi buttati per definizione, ed erano la fetta grossa di quei 25
  secondi.
- Nel registro compare anche **quante date sono state trovate** nel testo
  stampato. E' il numero che spiega perche' non si e' proposto niente: la regola
  vuole tre date esatte, e senza questo numero restava da indovinare quante ne
  avesse viste davvero.

Le 11 righe lette dicono la cosa importante: **la lettura del testo stampato
funziona**. Quello che non ha funzionato e' la regola che da quel testo ricava i
campi.

## 0.23.0

Tutto da una prova con la patente: due tentativi, il primo con il giorno di
nascita letto male e il secondo giusto.

- **La scadenza verifica la data di nascita, e dove non torna la corregge.**
  Regola detta da Felice: sui documenti italiani, carta d'identita' e patente,
  **la scadenza cade nello stesso giorno e mese della data di nascita**, cambia
  solo l'anno. E' lo stesso dato scritto due volte in due punti del documento,
  cioe' la stessa cosa che fanno le cifre di controllo della banda ottica. Le due
  letture non sono ugualmente difficili: la scadenza e' stampata piu' grande e si
  legge meglio, quindi quando non concordano si tiene il giorno e il mese della
  scadenza. Nella prova che ha fatto nascere la regola sarebbe bastato questo a
  raddrizzare il primo tentativo.
- Quando le due concordano **si sono verificate a vicenda** e non compaiono col
  bordo rosso: non c'e' niente da ricontrollare a mano.
- **Le letture non si buttavano via al momento giusto.** Sparivano appena si
  premeva Controlla, quindi al secondo tentativo la scheda usciva coi campi vuoti
  e senza il testo letto, come se la lettura non fosse mai partita. E' il motivo
  per cui la patente sembrava non passare mai per la lettura. Adesso restano
  finche' non si rifa' la fotografia.
- **Confermare non chiude piu' la porta.** Chi premeva "s&igrave;, i dati sono
  giusti" e si accorgeva dopo di dover scrivere qualcosa restava con le mani
  legate: i campi erano bloccati e non si tornava indietro. Adesso basta scrivere
  in un campo e il tasto si riapre.
- **Meno spiegazioni ovunque.** Il messaggio piu' lungo era di cinque righe e
  raccontava perche' un ospite senza documento finirebbe due volte nella lista:
  adesso dice "mi serve il numero del documento, scrivilo qui sopra". Stessa cura
  sugli altri.

## 0.22.0

Da una prova con la patente andata a vuoto: nel modulo compariva solo "Patente"
e nient'altro, come se la lettura non avesse girato. **Nel registro dell'add-on
non c'era una riga per dirlo**, e non si poteva sapere.

- **Una lettura che non riesce lascia una riga come tutte le altre**, con quante
  righe di testo stampato ha trovato, quanti campi ha proposto e quanto ci ha
  messo. Prima l'errore saltava il punto in cui si scrive, quindi su un
  documento senza banda ottica, cioe' la patente, il caso normale era
  invisibile. Era il buco che impediva di capire cosa fosse successo.
- **Il testo letto si apre da solo quando non si e' proposto niente.** E' il solo
  momento in cui serve vederlo, perche' distingue due guasti diversi: la lettura
  che non ha girato affatto, e la lettura che ha girato e dentro non ha trovato
  niente di riconoscibile.
- **Gli avvisi che sono ragionamenti nostri non si mostrano piu' a chi prova.**
  Una faccia sconosciuta in un solo scatto e' quello che il rilevatore inventa su
  un fotogramma mosso: a chi sta facendo il favore di provare diceva che
  qualcosa non andava, e non era vero. Resta nel registro, che e' dove lo
  leggiamo noi.
- **I numeri della porta stanno piegati.** Chi prova vede il verdetto; i
  punteggi, le soglie, i millisecondi e il secondo modello si aprono a chi li
  vuole. Sono la stessa cosa di prima, non piu' in faccia a chi non li ha
  chiesti.

## 0.21.1

- **Il tipo di documento si legge per esteso**: "Passaporto", "Carta d'Identità",
  "Patente". Nel campo compariva la lettera dello standard, `P` o `I`, che non
  vuol dire niente per chi la legge. La lettera resta dov'e' utile, cioe' dove
  servira' a scegliere il codice a cinque lettere che vuole Alloggiati Web.
- Quando i dati si scrivono a mano quel campo arriva **gia' compilato e senza
  bordo rosso**: non e' una lettura da controllare, e' il documento che l'ospite
  ha dichiarato lui stesso due passi prima.

## 0.21.0

- **Anche la patente propone i campi, invece di lasciare il modulo vuoto.**
  Il testo stampato lo si leggeva gia', ma restava una lista di righe da
  guardare: adesso quello che si riconosce arriva scritto dentro i campi e
  l'ospite conferma o corregge, com'e' per gli altri documenti.
- **Si propone solo quello che si riconosce dalla forma**, non quello che sta
  accanto a un'etichetta: le etichette stampate l'OCR se le sfilaccia mentre i
  valori li legge bene. E si propone **solo quando il conto torna esatto**: la
  patente porta tre date stampate e sempre in quell'ordine, quindi se se ne
  trovano tre quelle sono, e se se ne trovano due o quattro non si propone
  niente invece di indovinare.
- I campi proposti si vedono **col bordo rosso**, come quelli che non passano la
  loro cifra di controllo, e con scritto perche': dietro a questi non c'e'
  nessuna verifica, quindi vanno guardati uno per uno.
- **Se non si legge niente lo si dice subito, non alla fine**, ed e' il vero
  guadagno della lettura che parte allo scatto: si consiglia di rifare la foto
  li' per li'. Il motivo che conta non sono i dati, che l'ospite puo' scrivere:
  e' che **una fotografia troppo scarsa per essere letta di solito lo e' anche
  per riconoscere il viso**, e quello si scopre in fondo, quando rifare la foto
  vuol dire ricominciare da capo.
- Vale il solito **limite di due tentativi, mai tre**: al secondo non si insiste
  piu' e si va avanti, i dati si scriveranno a mano.

## 0.20.2

**All'ospite non serve sapere come funziona.** Fa due foto e un selfie: dove
stiano le righe a lettura automatica, cosa ci sia scritto dentro e perche' su un
documento ci siano e su un altro no non gli cambia niente di quello che deve
fare. La 0.20.1 aveva sostituito una parola sbagliata con una parola giusta,
quando la frase intera era di troppo.

- Sparite tutte le spiegazioni del meccanismo dalle istruzioni. Restano il lato
  da fotografare e come inquadrarlo: vicino, di lato, senza riflessi.
- Della patente si dice **la sola cosa che cambia per lui**, e si dice prima
  dello scatto invece che dopo: il modulo lo compila lui.
- Quando la lettura non riesce, il messaggio dice cosa fare (rifare la foto piu'
  da vicino, oppure scrivere a mano) e non piu' quale parte del documento non si
  e' letta.

## 0.20.1

Solo parole, e sono quelle che legge l'ospite.

- **Il terzo tasto dice "Patente", e basta.** Diceva "Patente o altro senza
  caratteri", che vuol dire un'altra cosa: "senza caratteri" si capisce come
  "senza testo scritto", e la patente di testo ne ha parecchio. Nessuno sa che
  quelle sono le righe a lettura automatica, e non deve saperlo. E per un
  italiano oltre a patente, carta d'identita' e passaporto non c'e' altro,
  quindi i documenti sono tre e l'elenco e' finito.
- **La stessa cosa si chiama sempre "le righe fitte"**, in tutta la pagina.
  Prima era "i caratteri" in un punto, "le righe di caratteri" in un altro e
  "le righe fitte di lettere e simboli" in un terzo.
- Quando la patente arriva al risultato, si spiega **perche'** i dati vanno
  scritti a mano invece di lasciarlo capire: quelle righe si controllano da
  sole, cioe' portano con se' una cifra che dice quando la macchina ha letto
  male, e sulla patente quella prova non c'e'.
- "Confronto il viso e leggo i caratteri" non era piu' vero: quando si preme
  quel tasto il documento e' gia' letto da un pezzo, e l'unica cosa che resta
  e' il confronto dei volti.

## 0.20.0

Il pannello di configurazione diceva cose che non si capivano e chiedeva una
scelta che non e' una scelta.

- **Via la scelta fra i due modelli.** Non e' una scelta adesso, perche' i due
  viaggiano insieme: ogni confronto li misura tutti e due sulle stesse facce, ed
  e' l'unico modo per decidere fra loro. E non lo sara' nemmeno dopo, perche'
  quando la decisione c'e' il modello e' uno solo.
- **Ogni opzione rimasta ha un nome e una spiegazione nel pannello**, in italiano
  e in inglese. Prima comparivano i nomi interni: `invio_prove` e `parola` non
  dicevano niente a nessuno, e sono le due che contano di piu' (dove finiscono i
  numeri delle prove, e chi puo' aprire la pagina).

Al primo avvio dopo l'aggiornamento il Supervisor puo' scrivere che l'opzione
`modello` non esiste nello schema: e' il valore vecchio rimasto scritto nella
configurazione, non fa danno, e sparisce salvando la configurazione una volta.

## 0.19.2

Due cose sull'aggiornamento stesso, viste guardando perche' la 0.19.1 ci aveva
messo tre minuti e diciassette su Teramo.

- **I modelli si scaricano prima delle librerie, non dopo.** Docker rifa' tutto
  quello che viene dopo la prima riga cambiata: con i modelli sotto, aggiungere
  una libreria buttava via anche i 166 MB di buffalo_l e li riscaricava. Erano
  quasi tutti li' i tre minuti, non nel motore nuovo. **Questo aggiornamento e'
  ancora lento**, perche' l'ordine cambia adesso; dal prossimo in poi un cambio
  di libreria non tocca piu' i modelli.
- **L'add-on si ferma quando glielo si chiede.** Dentro il contenitore questo
  processo e' il numero uno, e il numero uno ignora di suo la richiesta di
  fermarsi: il Supervisor aspettava dieci secondi, poi lo ammazzava e scriveva
  `exit code 137` nel log. Succedeva a ogni aggiornamento.

## 0.19.1

Giro di potatura sulla versione precedente, piu' una cosa che era decisa e non
era stata costruita.

- **L'interruttore della lettura ottica c'e' davvero**, come opzione dell'add-on
  (`lettura_ottica`), accesa di serie. Nella 0.19.0 era finito un campo nella
  richiesta, che nessuno mandava mai: la decisione era per macchina, non per
  fotografia.
- Il motore della lettura ottica non si tiene piu' in caldo fra una chiamata e
  l'altra. Non serviva a nessuno: quel modulo vive dentro un processo che legge
  una fotografia sola e poi muore.
- Il rimpicciolimento della fotografia era scritto due volte, una per lettore.
  Adesso e' uno solo, con la misura come argomento.
- Via un'eccezione che nessuno prendeva per quello che era.

## 0.19.0

Il flusso deciso su #7 il 20 agosto 2026, costruito. Prima la pagina aspettava
il tasto **Controlla** per cominciare a leggere il documento: su un N4000 sono
una ventina di secondi di clessidra buttati in faccia all'ospite alla fine.

- **La lettura parte appena arriva la fotografia**, non quando si preme
  Controlla. Cosi' finisce mentre l'ospite si fa il selfie, che di suo costa fra
  i venti e i trenta secondi. Al momento di inviare resta solo il confronto fra
  il volto del documento e il selfie.
- Le fotografie si leggono **una per volta**: un N4000 ha due core, e due
  letture insieme non vanno a meta' tempo, si ostacolano.
- La pagina dice **"sto leggendo"** mentre lavora, e se l'ospite e' piu' veloce
  del previsto lo dice invece di restare ferma. Una cosa che lavora e non parla
  sembra rotta.
- **La lettura del testo stampato (RapidOCR, Apache 2.0), che non c'era.** La
  banda ottica riempie sei campi su quattordici di Alloggiati Web; comune e
  provincia di nascita e luogo di rilascio non ce li ha, e sono **stampati in
  chiaro sulla stessa fotografia**. Adesso si leggono e si vedono. Trasformarli
  nei codici della Polizia, cercandoli negli elenchi chiusi, e' il passo dopo.
- Gira **nello stesso processo usa e getta della banda ottica**: stesso innesco,
  stesso viaggio, e i suoi 370 MB se ne vanno quando quel processo muore.
- **Si legge anche il fronte della carta, che la banda ottica non ce l'ha.** Non
  e' uno spreco: e' il lato dove stanno il comune di nascita e il luogo di
  rilascio.
- **La patente si prova a leggere davvero.** Non ha la banda ottica, quindi
  quella fallisce e i campi con la cifra di controllo non ci sono, ma il testo
  stampato si legge lo stesso ed e' l'unica strada per quel documento. Nella
  versione prima la patente saltava la lettura del tutto, che era sbagliato.
- **Il tipo di documento letto male si raddrizza.** Su un passaporto vero la
  banda ha letto `F` dove c'e' scritto `P`, e il documento e' diventato "non
  riconosciuto": quella lettera non ha nessuna cifra di controllo, quindi
  l'errore passa inosservato. Adesso si incrocia con quello che l'ospite ha
  dichiarato prima di fotografare, e si corregge **solo** quando anche il
  formato della banda conferma. Se dichiarato e fotografato non coincidono non
  si raddrizza niente: si dice che non coincidono.

## 0.18.0

- **La conferma dei dati era un gesto per finta.** I campi si potevano gia'
  correggere, ma quello che ci si scriveva dentro non finiva da nessuna parte:
  l'ospite veniva iscritto **prima** che la scheda comparisse, con i dati come
  li aveva letti la macchina. Adesso e' il tasto "s&igrave;, i dati sono giusti"
  a iscrivere, e iscrive quello che c'e' scritto nei campi in quel momento.
- Sotto i campi c'e' scritto che si possono correggere, perche' nessuno prova a
  scrivere dentro una casella che sembra un risultato. E il tasto lo dice
  quando le correzioni le ha prese davvero.
- **Quanti campi sono stati corretti a mano finisce nel quaderno**, e non si
  poteva ricavare da nient'altro. Le cifre di controllo dicono quali campi la
  macchina **sospetta**; questo dice quali erano **davvero** sbagliati, compresi
  quelli che una cifra di controllo non ce l'hanno e passano inosservati.
- **Anche la lettura del documento finisce nel quaderno**: formato, se e'
  servita la seconda passata, quanti campi non tornavano, quanto ci ha messo.
  Prima non ci finiva affatto, e la domanda "quali campi si riempiono da soli e
  quali restano a mano" non aveva da nessuna parte i numeri per rispondere.
- **Un terzo documento fra cui scegliere: "patente o altro senza caratteri".**
  Non ha le due righe da leggere, quindi la lettura non parte affatto e i campi
  partono vuoti da riempire a mano. Il confronto fra la fotografia del documento
  e il selfie si fa lo stesso. Serve a provare la strada di scampo che era
  decisa da sempre e che non si poteva percorrere: finche' si sceglieva solo fra
  carta e passaporto, un documento che non si legge non si poteva nemmeno
  dichiarare.

## 0.17.0

- **Il quaderno delle prove non sapeva cosa stava misurando.** Segnava ogni
  punteggio ma non se le due facce **dovevano** essere della stessa persona, e
  le somme buttavano tutto in un mucchio solo. Da un mucchio solo si legge una
  cosa sola, quanto sono alti i punteggi, e non e' quella che decide: il numero
  che decide fra i due modelli e' **la distanza fra il peggiore dei confronti
  giusti e il piu' alto fra gli estranei**. Adesso i due mondi si contano
  separati e quella distanza si legge da `/prove`.
- **Chi prova alla porta dice chi c'e' davanti alla telecamera**, spuntandolo
  fra gli attesi, e c'e' anche la casella "nessuno di loro". E' l'unica domanda
  in piu' che il banco di prova fa, e senza di lei una raffica alla porta era
  una manciata di numeri di cui non si sapeva quale doveva combaciare.
- **E' anche l'unico posto da cui arrivano gli estranei.** Chi prova sul proprio
  documento e sul proprio selfie produce solo confronti che devono combaciare:
  di persone diverse non ne arriva nemmeno uno, e meta' della misura non si fa.
  Alla porta ogni faccia si confronta con **tutti** gli attesi, quindi ogni
  raffica regala un confronto giusto e tutti gli estranei degli altri.
- **Le prove senza etichetta si scartano e si contano.** Un punteggio di cui non
  si sa se doveva combaciare non e' una misura, e messo nel mucchio rovina anche
  gli altri. Quante ne sono state scartate si legge accanto alle somme: un
  numero che cresce e' un guasto da vedere, non un dettaglio.
- Nelle somme compaiono anche **gli errori veri**, contro la soglia di quel
  giorno: ospiti respinti per sbaglio ed estranei fatti passare. Un margine
  negativo vuol dire che i due mondi si sono gia' sovrapposti, e allora non c'e'
  soglia che tenga: e' il modello.

## 0.16.1

- **La pagina non si mette piu' in cache**, e serviva. Il 19 agosto 2026 due
  prove alla porta sono girate con la pagina vecchia tenuta in memoria dal
  telefono: l'add-on era aggiornato, il telefono no. Quelle due prove hanno
  saltato **in silenzio** il secondo modello, il limite dei due tentativi e il
  controllo sulla scadenza del documento, e ce ne siamo accorti solo perche' nel
  registro mancava la coda con il punteggio dell'altro modello.
- Conta oltre il banco di prova, e conta di piu': **la pagina e' il flusso**, e
  le regole che il flusso deve rispettare vivono dentro di lei. Una pagina di
  ieri e' un flusso di ieri, e nessuno se ne accorge.

## 0.16.0

- **Il documento scaduto viene fermato, e nessuno lo controllava.** La lettura
  della MRZ ora dice se il documento e' scaduto e di quanti giorni, e nel
  portale un documento scaduto **ferma tutto prima del confronto dei volti**:
  non e' un documento di identificazione, quindi il volto non si elabora
  affatto. Prima faceva tutto il giro fino al punteggio senza che nessuno
  dicesse niente. All'ospite si dice quando e' scaduto e che serve un documento
  valido, non e' una cosa che si sistema all'arrivo, e l'host non puo' rimediare
  guardando: puo' garantire che la faccia corrisponde, non puo' rendere valido un
  documento scaduto.
- **Quando la scadenza non si legge non si giudica.** Se la cifra di controllo
  della scadenza non torna, o la data non esiste sul calendario, il documento
  non viene respinto e si dice perche'. Un documento buono respinto per una
  cifra letta male e' peggio di uno scaduto che passa: quello lo vede comunque
  l'host, l'ospite respinto per sbaglio non ha nessuno a cui spiegarsi.
- Il documento e i volti non si guardano piu' insieme ma **in fila**, prima il
  documento. Costa i secondi della lettura prima del confronto, e li vale.
- Nel registro dell'add-on la scadenza si scrive come "quanti giorni", mai come
  data: una data di scadenza e' un pezzo di documento e riporta a una persona.

## 0.15.0

- **L'occhio dell'host e' la seconda porta d'ingresso.** Quando il confronto fra
  documento e selfie non riesce, l'host puo' guardare le due foto e dire che e'
  la stessa persona: l'ospite si iscrive comunque, e si iscrive **con il vettore
  del selfie**, non con quello del documento. Alla porta il confronto e' allora
  selfie contro telecamera, cioe' due fotografie recenti, che e' la misura che
  funziona (fra 0,47 e 0,83 nelle prove) invece di quella che era fallita.
  Serve ai minori, dove il ritratto stampato ha anni e il confronto cade: il
  fallimento resta confinato al cancello e non tocca la porta.
- Di ogni atteso si tiene **da quale delle due porte e' entrato**, confronto
  automatico oppure occhio dell'host. Non e' burocrazia: e' quello che si
  racconta se qualcuno chiede come e' stata fatta l'identificazione.

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
