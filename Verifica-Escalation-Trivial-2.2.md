# Escalation Trivial 2.2
## Verifica tecnica e grafica del 19 novembre 2026

La lobby è operativa. Il docente apre la partita da `/docente`, mostra il PIN o il QR da `/schermo` e avvia il quiz quando l’aula è pronta. Gli studenti entrano con un nickname. Il telefono conferma l’iscrizione, indica lo stato del collegamento e passa alla domanda al comando del docente. Nessuna registrazione con email o password è richiesta ai giocatori.

### 1. Problemi riscontrati e interventi

| Percorso | Comportamento rilevato nella 2.1 | Comportamento della 2.2 |
|---|---|---|
| Avvio locale con i telefoni | Con l’avvio predefinito sul solo computer il QR poteva puntare a `127.0.0.1`. Sul telefono quell’indirizzo indica il telefono stesso. | Gli avvii **Avvia-Aula** abilitano la rete locale. La regia e il proiettore mostrano istruzioni specifiche quando l’indirizzo di invito è limitato al computer. Il QR compare per gli indirizzi di rete. |
| Ingresso con connessione incerta | Ripetere la stessa iscrizione dopo una conferma persa restituiva «nickname già utilizzato». Il posto era già occupato dal giocatore stesso. | Il telefono conserva l’identificativo del tentativo prima dell’invio. Il server riconosce l’iscrizione e restituisce lo stesso posto anche se il docente ha già dato il via. |
| Presenze in lobby | Il conteggio degli iscritti restava invariato quando tutti i telefoni si scollegavano. La regia non poteva sapere quanti stavano ricevendo gli aggiornamenti. | Le tre interfacce mostrano gli iscritti e i collegati. Due schede dello stesso giocatore valgono una presenza. Alla chiusura dell’ultima scheda il contatore scende e il posto resta riservato. |
| Rientro e schede multiple | Una scheda vecchia poteva cancellare il riferimento locale alla partita più recente. Una terza scheda continuava a tentare il collegamento. | Ogni scheda conserva la propria identità. Alla terza viene chiesto di chiuderne una e premere **Ricollega**. Quando la pagina torna in primo piano, richiede al server lo stato corrente. |
| Risposta già inviata | Se due schede inviavano scelte diverse, la seconda poteva avviare una riconnessione e lasciare il giocatore incerto sulla scelta valida. | Entrambe ricevono la prima scelta effettivamente registrata. La domanda assegna un solo punteggio. |
| Due regie aperte | Il secondo salvataggio poteva sovrascrivere una selezione già modificata da un altro docente. | La regia controlla la versione della selezione. In caso di conflitto lascia visibile la bozza e consente di ricaricare la selezione aggiornata. |
| CSV e QR di partite successive | Da una vecchia classifica si poteva scaricare il CSV della classe successiva. Una richiesta del QR precedente poteva restituire il codice della nuova lobby. | Il collegamento CSV contiene l’identificativo della partita. Il QR richiesto con un PIN si genera soltanto per la lobby aperta con quel PIN. |

### 2. Esperienza del giocatore

Sulla schermata di attesa, il nickname conferma che il posto è quello giusto. Il riquadro sotto il nome indica che cosa succede adesso, con un messaggio distinto per attesa del via, collegamento in corso e rete assente. Lo stato è comunicato con testo e colore. Durante la domanda, una conferma identifica la lettera ricevuta dal server.

A 320 pixel CSS di larghezza la lobby è rimasta entro lo schermo, compreso un nickname di 24 caratteri. I due comandi di attesa misurano 44 pixel CSS in altezza. I contatori occupano due colonne sul telefono. Il cambio di stato aggiorna i valori sul posto, così chi sta consultando le regole può continuare a leggerle. All’avvio del round il titolo della domanda riceve il focus.

Chi conosce Kahoot! ritrova l’ingresso tramite PIN, link o QR e la scelta del nickname. Una differenza incide sulla conduzione dell’aula. Kahoot! ammette nuovi ingressi in alcune sessioni già iniziate. Escalation Trivial chiude le nuove iscrizioni alla prima domanda e permette il rientro degli iscritti. In questo modo il numero di risposte attese dal docente rimane stabile durante il quiz. [Guida ufficiale Kahoot! all’ingresso in partita](https://support.kahoot.com/hc/it/articles/360039890713)

### 3. Catalogo e tempi di lettura

Il controllo sui 100 quesiti, suddivisi in otto categorie, ha verificato identificativi e tracce univoci, alternative distinte, indice della soluzione valido e presenza della spiegazione. Le 42 domande binarie hanno 21 risposte corrette in ciascuna posizione. Nei 58 quesiti a quattro alternative, le posizioni corrette A, B, C e D ricorrono rispettivamente 15, 15, 14 e 14 volte.

In 18 quesiti, traccia e alternative raggiungono almeno 45 parole. Il più lungo è AUT-010 con 56 parole. La regia segnala questi casi quando la durata scelta è inferiore a 45 secondi e suggerisce 45–60 secondi. Con il bonus velocità, scegliere il tempo a disposizione incide anche sul punteggio. La revisione editoriale precedente e i 17 quesiti rielaborati sono documentati in `REVISIONE_GRAFICA_E_UX.md`. La 2.2 mantiene il catalogo della 2.1. I valori descrivono la struttura dei quesiti. Una misura della difficoltà per gli studenti richiederebbe dati di partite in aula.

### 4. Verifiche effettuate

| Verifica | Esito osservato |
|---|---|
| Avvio e QR | Su Linux, il programma è partito sia in modalità locale sia con **Avvia-Aula**. Un decodificatore indipendente ha letto dai PNG il PIN e l’indirizzo previsti. In modalità aula il QR conteneva l’indirizzo di rete del computer. |
| Gioco dal browser a larghezza mobile | Ingresso da invito e con PIN digitato, nickname, attesa, uscita con conferma, nuovo ingresso, prima domanda automatica e conferma della risposta. Il ricaricamento della pagina ha recuperato la stessa scelta. |
| Regia, giocatore e proiettore | I tre canali hanno ricevuto lo stato previsto. Durante il round il giocatore e il proiettore non hanno ricevuto la soluzione. Alla chiusura sono comparsi soluzione, voti e punteggi. |
| 400 giocatori simulati in locale | Iscrizioni e collegamenti simultanei completati. Primo round ricevuto da tutti e 400, con 400 risposte accettate, punteggi, CSV e classifica finale. Il 401º ingresso è stato rifiutato. |
| Continuità della partita | Verificati rientro a partita iniziata, blocco dei nuovi iscritti, scadenza dopo riavvio del server, conservazione del punteggio e migrazione di una partita creata con una versione precedente. |
| Partite consecutive e regie concorrenti | Verificati il recupero del CSV della classe originaria, il rifiuto del QR scaduto e la conservazione delle prime modifiche in caso di doppio salvataggio. |

La capacità è stata verificata su un processo locale con partecipanti simulati. La verifica del doppio clic nativo su Windows e macOS, della rete Wi-Fi dell’aula, dei telefoni fisici e della specifica istanza Railway resta da effettuare nei rispettivi ambienti. «Collegati» indica le connessioni che il server vede aperte. In caso di spegnimento improvviso del telefono il valore si aggiorna quando il server rileva la disconnessione.

Per avviare il gioco e configurare la rete dell’aula consulta `README.md`. Per Railway usa una replica, un solo worker e un volume persistente montato su `/data`.
