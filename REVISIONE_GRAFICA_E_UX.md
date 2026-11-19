# Escalation Trivial 2.1
## Revisione grafica, esperienza del giocatore e catalogo

**19 novembre 2026.** Questa revisione parte dalla versione 2.0. Il confronto considera il percorso di un partecipante con lo smartphone in aula e i compiti distinti di chi conduce e di chi guarda il proiettore. Le osservazioni derivano dai sorgenti e dal catalogo. La versione 2.1 non è stata avviata, sottoposta a prove con utenti o collaudata sotto carico.

## 1. Dove intervenire sul disegno del gioco

Il momento più delicato è quello subito dopo il tocco. Nella 2.0 lo studente poteva vedere la scheda dell’intera domanda ricomparire prima all’invio e poi alla conferma. Più la domanda era lunga, più costava ritrovare sul telefono l’opzione scelta. All’esito, inoltre, lo studente doveva attraversare le alternative una seconda volta prima di leggere la spiegazione. Durante il round la 2.1 rende esplicita la ricezione della scelta. Dopo la chiusura porta in primo piano la ragione della soluzione.

| Momento | Osservazione sulla 2.0 | Intervento nella 2.1 |
|---|---|---|
| Ingresso dal telefono | Il manifesto precedeva il modulo. Anche con un invito, il PIN occupava un campo di inserimento. Le regole avevano due richiami sulla stessa pagina. | Il modulo compare per primo. Con un invito a sei cifre viene presentato il PIN e si compila soltanto il nickname. **Cambia PIN** consente di correggere un invito. In sala il QR può essere ingrandito con il PIN accanto alle istruzioni. Su desktop rimane la console illustrata accanto al modulo. |
| Attesa in lobby | Il nome e l’attesa erano riconoscibili, ma le regole diventavano difficili da recuperare una volta entrati. | Il partecipante vede il proprio nickname, il PIN e il numero degli iscritti. Può leggere le regole e l’effetto della velocità sui punti prima che inizi il primo round. |
| Scelta sotto tempo | Piccoli badge e righe simili richiedevano lettura anche solo per individuare un’opzione già vista sul proiettore. Le alternative hanno lunghezze molto diverse. | Ogni tasto usa una lettera, una sagoma e una tinta costanti. Si usano pulsanti accostati quando ciascun testo è breve. Le alternative lunghe occupano tutta la riga sul telefono. Lo stesso codice visivo compare nella proiezione e nell’anteprima docente. |
| Invio e conferma | Il disegno della domanda ripartiva all’invio e alla conferma. La scomparsa di una connessione poteva essere confusa con una risposta perduta. | Il tasto scelto mantiene la posizione. L’indicatore passa dall’invio alla conferma del server. Se il collegamento cade durante l’invio, un messaggio esplicito rinvia la verifica al rientro. Il conto alla rovescia usa secondi numerici e un anello. L’ultima fase cambia tinta senza lampeggiare. |
| Soluzione sul telefono | Per arrivare alla spiegazione occorreva superare di nuovo domanda e opzioni. | Prima compaiono esito, punti del round, risposta corretta e motivazione. In caso di errore è indicata anche la scelta effettuata. Un comando espandibile riapre il quesito completo. |
| Conclusione | La prima posizione dominava la proiezione. Lo studente vedeva il proprio punteggio e aveva come azione finale il ritorno all’ingresso. | La sala ha un podio per le posizioni effettivamente conseguite con punteggio positivo, con gestione delle parità. Sul telefono compaiono i conteggi personali e il ripasso delle domande effettivamente giocate, con un filtro per errori e omissioni. |

Il marchio resta riconoscibile nella console arancione, nello sfondo grafite e nei numeri a spaziatura fissa. Durante il gioco l’arancione segnala le azioni principali, mentre le lettere e le forme identificano le opzioni. Nell’esito corretto, errato o assente la parola e l’icona accompagnano il colore. Le animazioni brevi riguardano il segno di ricezione, l’esito e il podio. La preferenza di sistema per il movimento ridotto è prevista nei fogli di stile.

## 2. Confronto con Kahoot!

| Passaggio | Esperienza descritta da Kahoot! per i giochi live | Scelta per Escalation Trivial |
|---|---|---|
| Entrare | Il giocatore può inserire un PIN oppure aprire un link o un QR che identifica la sessione. Le richieste successive dipendono dalle impostazioni del docente. | L’invito porta direttamente al nickname. Scrivere il PIN resta il percorso per chi entra dalla pagina iniziale. |
| Leggere e rispondere | Una specifica impostazione consente di mostrare domanda e risposte anche sul dispositivo del partecipante. | Il testo integrale è sempre disponibile sul telefono. Nei quesiti tecnici si può riesaminare una parola o una negazione anche lontano dal proiettore. |
| Attendere l’esito | La guida alla conduzione descrive il passaggio ai risultati quando tutti hanno risposto oppure scade il tempo. Il docente può discutere la distribuzione delle scelte. | Le nuove partite create dalla regia hanno preselezionata la chiusura quando tutti gli iscritti hanno risposto. Il docente può disattivarla. La spiegazione rimane aperta finché il docente decide di proseguire. |
| Concludere | Classifica e podio danno rilievo al risultato di gruppo. | Il proiettore celebra il podio. Ciascun telefono propone un resoconto privato e la revisione degli errori. Se nessuno ottiene punti, la sala riporta l’esito collettivo. |

Le fonti sono le guide ufficiali di Kahoot! per [l’accesso via PIN, link e QR](https://support.kahoot.com/hc/en-us/articles/360039890713), per [la visualizzazione delle domande sui dispositivi](https://support.kahoot.com/hc/en-us/articles/115003197928) e per [la conduzione, i risultati e il podio](https://support.kahoot.com/hc/en-us/articles/360039900153).

## 3. Il testo delle domande come parte dell’interfaccia

Il catalogo comprende 100 domande in otto categorie. I 42 quesiti binari e i 58 a quattro scelte richiedono impaginazioni diverse. Sul catalogo aggiornato, in 71 quesiti almeno un’alternativa supera 46 caratteri. La risposta più lunga ha 76 caratteri. Il confronto delle lunghezze serve a comporre la schermata. Il ritmo di lettura individuale resta una variabile della lezione.

| Osservazione editoriale | Valore o esempio | Conseguenza per il gioco |
|---|---|---|
| Lunghezza che suggerisce la soluzione | Nella 2.0 la corretta era *l’unica opzione più lunga* in 30 quesiti a quattro scelte su 58. Nella 2.1 il conteggio scende a 14 su 58. | Sono state rielaborate le alternative di 17 quesiti, esplicitando anche il contesto in due domande. Ogni indice di soluzione, categoria e livello conserva il suo significato. La metrica descrive una caratteristica del testo e non misura la difficoltà effettiva. |
| Distribuzione delle soluzioni | Nel formato a quattro scelte le soluzioni occupano A, B, C e D rispettivamente 15, 15, 14 e 14 volte. Nei binari A e B figurano 21 volte ciascuna. | La posizione di una risposta è stabile per tutti i dispositivi e al rientro nel round. |
| Carico di lettura | In BCP-003 il giocatore confronta quattro orari. In PRI-002 legge due formulazioni lunghe che contengono termini essenziali. | Se tutte le opzioni hanno al massimo 36 caratteri e lo schermo raggiunge 370 pixel CSS, il telefono può accostare i tasti. Altrimenti le alternative sono impilate e il testo va a capo. |
| Tempo assegnato | 18 quesiti raggiungono almeno 45 parole fra traccia e opzioni, contando le sequenze separate da spazi. | Se il docente seleziona uno di questi quesiti e sceglie meno di 45 secondi, la regia segnala il numero di casi lunghi e propone di valutare 45–60 secondi. La decisione resta al docente. |

In **PHI-014** la richiesta di cambio IBAN ora compare nella traccia. Le alternative distinguono quattro verifiche plausibili, tra cui la provenienza del messaggio e l’autorizzazione del fornitore. In **SOC-009** le opzioni richiamano elementi realmente presenti nel lavoro in sala operativa, come la coda degli avvisi e la quantità di log. In **SOC-010** il partecipante distingue tra produrre un resoconto e assegnare un’azione con una scadenza.

Gli altri quesiti rielaborati sono PHI-004, PHI-006, PHI-009, PHI-011, AUT-010, AUT-012, AUT-014, MAL-014, MAL-015, NET-001, OPS-003, OPS-005, OPS-007 e BCP-010. Le partite già create utilizzano le copie dei quesiti salvate all’apertura della lobby.

## 4. Lettura dei risultati

Il punteggio continua a premiare correttezza e rapidità. Ogni risposta esatta vale da 500 a 1.000 punti. Una scelta errata o un’omissione vale zero. Due studenti con lo stesso numero di scelte esatte possono quindi avere posizioni diverse. Il riepilogo individuale mostra anche i conteggi distinti, così il docente può invitare a ripassare un concetto indipendentemente dalla classifica.

Il filtro **Da ripassare** raccoglie gli errori e le domande lasciate senza risposta. **Tutte** permette di rivedere anche le risposte corrette. Il ripasso riguarda i soli round giocati, compreso il caso di conclusione anticipata, ed è accessibile al partecipante finché la sua partita rimane l’ultima sessione disponibile. Il rapporto dedicato alla 2.0 conserva i dettagli del precedente collaudo.
