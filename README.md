# Escalation Trivial 2.3 per Railway

Quiz live in italiano sulla cybersicurezza. Un servizio Railway ospita una partita condivisa, con regia docente, proiezione e fino a 400 giocatori. Il catalogo comprende 100 domande in otto categorie. Docente e studenti usano il browser. I partecipanti possono collegarsi dalla rete mobile o dal Wi-Fi.

## 1. Pubblicazione su Railway

Estrai lo ZIP in una cartella vuota e carica il contenuto nella radice del repository GitHub che collegherai a Railway. Nella stessa directory devono comparire `Dockerfile`, `app.py`, `catalogue.py`, `questions.json`, `requirements.txt` e `static/`. Railway rileva il Dockerfile in quella posizione. [Rilevamento del Dockerfile](https://docs.railway.com/builds/dockerfiles)

Nel progetto Railway crea un servizio per il gioco. Configura le voci seguenti nel pannello del servizio, collega il repository e avvia il deploy. Per un servizio già collegato, applica le impostazioni e distribuisci la nuova versione.

| Impostazione | Configurazione del servizio |
|---|---|
| `ADMIN_PASSWORD` | In **Variables** inserisci una password lunga, riservata al docente. |
| `SESSION_SECRET` | In **Variables** inserisci un segreto casuale, diverso dalla password. Puoi generarlo con un gestore di password o con `python -c "import secrets; print(secrets.token_hex(32))"`. Mantieni lo stesso valore fra i deploy per conservare la validità delle sessioni docente. |
| Volume persistente | Collega un volume al servizio con percorso **`/data`**. Il Dockerfile imposta `DATA_DIR=/data`. Qui SQLite conserva partite, partecipanti e punteggi. Per aggiornare un’installazione esistente, riutilizza il suo volume. |
| Repliche | Imposta **1 replica**. Il Dockerfile avvia **1 worker** Uvicorn. Le connessioni in tempo reale della classe condividono quel processo. |
| Avvio e porta | Lascia a Docker il comando di avvio. Il server ascolta su `0.0.0.0` e legge `PORT` assegnata da Railway. |
| Controllo del deploy | Nelle impostazioni di deploy scegli **Healthcheck Path** `/health`. Per riprendere i valori della versione precedente, usa 60 secondi di timeout e la politica di riavvio **On Failure** con 5 tentativi. |
| Dominio | In **Settings → Networking → Public Networking** seleziona **Generate Domain**. Per gli inviti l’app usa HTTPS e il dominio fornito da Railway in `RAILWAY_PUBLIC_DOMAIN`. Per preferire un dominio personalizzato, collegalo al servizio e imposta `PUBLIC_URL` al suo indirizzo completo, con `https://`. |

Le impostazioni sopra sono gestite dal pannello Railway. Chi aggiorna un vecchio servizio che punta esplicitamente a `railway.json` deve prima trasferire in Railway le impostazioni desiderate e completare la migrazione di quel riferimento secondo la procedura ufficiale. [Volumi](https://docs.railway.com/volumes) · [Healthcheck](https://docs.railway.com/deployments/healthchecks) · [Domini pubblici](https://docs.railway.com/networking/public-networking) · [Migrazione della configurazione precedente](https://docs.railway.com/infrastructure-as-code#migrating-from-config-as-code)

## 2. Prima partita dal dominio pubblico

Apri il dominio HTTPS mostrato da Railway. Tutti i percorsi seguenti appartengono allo stesso servizio.

| Percorso | Chi lo usa | Funzione |
|---|---|---|
| `/docente` | Docente | Accede con la password configurata in Railway, seleziona le domande, apre la lobby e dà il via. |
| `/schermo` | Proiettore | Mostra PIN, QR, domande e classifica. Apri **Proiettore** dalla regia per usare la stessa sessione. Su un secondo browser serve la password docente, che abilita anche la regia. |
| `/` | Giocatore | Inserisce PIN e nickname. L’invito via QR o link precompila il PIN. |
| `/health` | Verifica del servizio | Su un’installazione nuova risponde con codice HTTP 200, stato `ok` e `question_count` pari a 100. |

Per la prima partita accedi a `/docente`, scegli **Pesca 10 miste** e poi **Apri la lobby**. Sul proiettore appariranno il QR e il PIN. Il telefono mostra **In attesa del via** dopo l’ingresso e passa alla prima domanda quando premi **Avvia partita**. Per confermare l’accessibilità da Internet dopo la pubblicazione, puoi inquadrare il QR con un telefono sulla rete mobile.

## 3. Conduzione della partita

In regia puoi selezionare categorie intere o singole domande, cercare per parola o codice, filtrare per difficoltà e consultare soluzione e spiegazione in **Dettagli**. **Pesca 10 miste** sostituisce la selezione e copre tutte le otto categorie del catalogo. Il tempo predefinito è **30 secondi**. Puoi portarlo fino a 120 secondi per gli scenari lunghi. Se la selezione contiene domande con almeno 45 parole fra traccia e opzioni, la regia suggerisce di valutarne il tempo di lettura. La selezione, la durata e le impostazioni restano modificabili fino all’avvio.

Una volta aperta la lobby, ogni studente sceglie un nickname da 2 a 24 caratteri. Sul telefono appare **In attesa del via** quando il collegamento è attivo. La prima domanda sostituisce automaticamente la lobby al comando **Avvia partita**. I contatori **Iscritti** e **Collegati** distinguono i posti riservati dai giocatori con almeno una scheda collegata. Una seconda scheda con la stessa identità conta una sola volta. Il docente può copiare il link diretto. Gli iscritti possono lasciare la lobby liberando il posto. Dopo l’avvio sono ammessi i rientri dei partecipanti già iscritti, utilizzando lo stesso browser e profilo. Una disconnessione conserva il posto. Il server decide la scadenza e accetta una sola risposta per persona e round.

Una risposta esatta dà **500 punti più un bonus fino a 500**, proporzionale alla frazione di tempo rimasta quando il server riceve la scelta. Il totale viene arrotondato all’intero più vicino. A metà tempo una risposta corretta vale 750 punti. Risposta errata o assente vale zero. I nuovi punti diventano visibili alla chiusura del round. La risposta giusta, la spiegazione e la distribuzione dei voti restano sul proiettore fino al comando successivo. Le percentuali usano come denominatore le risposte ricevute. I numeri accanto alle barre riportano i voti effettivi.

Nelle nuove partite create dalla regia, **Mostra la soluzione quando tutti hanno risposto** è preselezionata. Il conteggio considera tutti gli iscritti, inclusi quelli momentaneamente disconnessi. Quando un iscritto manca all’appello, il round termina comunque alla scadenza oppure al comando del docente. Disattiva l’opzione in regia se desideri conservare tutto il tempo assegnato dopo l’ultima risposta.

**Chiudi le risposte** anticipa la scadenza. Se qualcuno deve ancora rispondere, compare una conferma. Dopo ogni soluzione puoi proseguire o concludere in anticipo. Dopo l’ultimo round, **Mostra la classifica** apre il risultato finale. A parità di punti si condivide la posizione, per esempio 1ª, 1ª, 3ª. In classifica i pari merito sono elencati in ordine di iscrizione. Il CSV contiene tutti gli iscritti, inclusi i giocatori con zero punti. La regia visualizza fino a 20 nominativi, la proiezione fino a 10. Il collegamento **Esporta CSV** identifica la partita visualizzata. Puoi salvare il file prima di aprire una nuova lobby o conservare quel collegamento nel browser del docente.

Lo schermo del giocatore conferma l’invio appena il server registra la risposta. Alla chiusura mostra l’esito, la soluzione, la spiegazione e la posizione. **Rivedi domanda e opzioni** riapre tutte le alternative. A fine partita la sala vede il podio e lo studente può scegliere **Ripassa le domande**, quindi **Da ripassare** o **Tutte**. Prima di aprire un’altra lobby lascia all’aula il tempo per il ripasso e per l’esportazione del docente.

## 4. Aggiornamento dalle versioni precedenti

Collega il servizio allo stesso volume SQLite. Il campo dedicato alla chiusura quando tutti hanno risposto viene aggiunto al primo avvio con una versione dalla 2.1 in poi. Per le partite preesistenti il valore iniziale mantiene il comportamento basato sulla scadenza o sul comando del docente. Prima di aggiornare, conserva una copia del volume o un backup coerente del database. Al primo avvio la migrazione salva i testi, le alternative e le soluzioni delle partite già presenti. Il nuovo catalogo diventa disponibile per le nuove partite. Per una lobby precedente, le domande già associate mantengono il contenuto originale. Le sessioni e i punteggi già registrati restano nel database. Il progetto può anche partire da una cartella dati vuota.

`questions.json` è la fonte modificabile del catalogo. Dopo una modifica, esegui `python tools/check_questions.py` e riavvia il servizio. Mantieni identificativi stabili. Le partite conservano una copia dei quesiti selezionati. Le personalizzazioni con gli stessi ID dei quesiti distribuiti vanno riportate nel JSON prima di aggiornare. Per il ripristino copia il database a servizio fermo includendo gli eventuali file SQLite `-wal` e `-shm`, oppure usa un backup SQLite coerente. I dati rimangono sul volume finché il gestore ne cura la conservazione.

## 5. Revisione, catalogo e materiale tecnico

La versione 2.3 riprende il prompt verde, la chiave gialla e la scritta ambra e vermiglio del marchio Escalation. Nel quiz il lettering segue una linea di base regolare. Le carte avorio identificano gli spazi personali e il blu inchiostro fa da fondo alla proiezione. Il marchio vettoriale completo e il simbolo si trovano in `static/assets/escalation-trivial.svg` e `static/assets/escalation-segno.svg`. [Marchio di riferimento in CyberCard](https://github.com/CollectorsElite/CyberCard/blob/97bedfdfd9eea713472a66be0f51439f376c03ff/art/board/logo.jpg)

Il file vettoriale autonomo `Marchio/Logo-Escalation-Trivial.svg` include il fondo blu e può essere inserito in una slide o su una pagina chiara.

La cartella `Schermate/` contiene otto immagini della versione 2.3 acquisite dal browser. Documentano ingresso, regia, attesa del giocatore, lobby in proiezione, primo round su telefono e proiettore, soluzione e classifica. Il PIN e il dominio nelle immagini appartengono alla sessione locale dimostrativa.

`Verifica-Escalation-Trivial-2.2.md` documenta i difetti riprodotti, le modifiche alla lobby e le verifiche della 2.2. `node tests/ui_lobby.cjs` ripete i casi del controller del browser con Node.js. Questo comando è facoltativo per chi desidera verificare il software.

`REVISIONE_GRAFICA_E_UX.md` illustra le scelte della 2.1, il confronto con Kahoot!, le metriche sul testo e gli interventi su 17 quesiti. La 2.1 è stata revisionata sui sorgenti, senza eseguire il gioco o prove di carico.

`VERIFICA_E_CORREZIONI.md` riporta l’analisi didattica, le fonti e gli esiti del collaudo storico della versione 2.0. Per ripetere la suite locale installa `requirements-test.txt` e avvia `python tests/run.py --players 400`. Le prove usano directory temporanee e due porte locali libere, 8129 e 8131. La suite include il recupero della scadenza dopo il riavvio e la migrazione di una partita precedente.

Il backend è in `app.py`, la validazione in `catalogue.py`, le tre interfacce in `static/`. Il carattere Archivo è distribuito con la licenza SIL Open Font License inclusa in `static/assets/Archivo-OFL.txt`. Anche la fotografia illustrativa del mazzo viene servita dal pacchetto. L’applicazione non richiede un database esterno né una compilazione del frontend.

## Appendice. Avvio locale facoltativo

Estrai tutto lo ZIP in una cartella scrivibile. Occorre **Python 3.12 o successivo**. La prima installazione delle dipendenze richiede una connessione Internet. Durante il gioco, font, grafica e QR vengono serviti dall’applicazione.

| Sistema | Come avviare |
|---|---|
| Windows | Apri `Avvia-Windows.cmd` con un doppio clic. In alternativa esegui `py -3 avvia.py` dalla cartella estratta. |
| macOS o Linux | Apri il terminale nella cartella estratta ed esegui `python3 avvia.py`. È incluso anche `Avvia-macOS-Linux.command`. |

**Per giocare con i telefoni della classe** apri `Avvia-Aula-Windows.cmd` su Windows oppure `Avvia-Aula-macOS-Linux.command` su macOS o Linux. Collega i telefoni alla rete che raggiunge il computer del docente. La regia mostrerà il QR e il link con l’indirizzo di rete. Se l’indirizzo invita al solo computer locale, la lobby indica come attivare la modalità aula.

Il launcher prepara le dipendenze, apre la regia nel browser e indica il percorso della password. Al primo avvio locale genera credenziali casuali in **`data/accesso-locale.env`**. Per accedere copia il valore accanto ad `ADMIN_PASSWORD`. Conserva il file sul computer del docente. Agli studenti serve soltanto il PIN della lobby. Per fermare il servizio premi `Ctrl+C` nella finestra di avvio.

Nella regia scegli **Pesca 10 miste**, poi **Apri la lobby**. Apri **Proiettore** e sposta la nuova scheda sullo schermo dell’aula. Seleziona il QR sul proiettore per ingrandirlo nelle aule profonde. Gli studenti possono inquadrarlo e inserire il nickname, oppure aprire l’indirizzo giocatori e digitare il PIN. Premi **Avvia partita** in regia quando l’aula è pronta. Il comando si abilita con il primo iscritto.

| Vista | Indirizzo locale | Accesso |
|---|---|---|
| Partecipante | `http://127.0.0.1:8000/` | PIN e nickname, oppure QR e nickname |
| Regia | `http://127.0.0.1:8000/docente` | Password docente |
| Proiezione | `http://127.0.0.1:8000/schermo` | Stessa sessione del docente sullo stesso browser. Su un altro computer occorre la password docente. |

**Con gli smartphone nella stessa rete.** Avvia `python3 avvia.py --rete` oppure `py -3 avvia.py --rete`. Apri la regia sul computer e condividi l’indirizzo *Giocatori* stampato dal launcher. Il QR conterrà l’indirizzo LAN del computer. I dispositivi devono raggiungere la porta scelta e la rete Wi-Fi deve consentire la comunicazione tra loro. Se sono presenti più schede di rete, imposta `PUBLIC_URL` con l’indirizzo LAN corretto. L’avvio normale serve la sola macchina locale. Per cambiare porta aggiungi `--porta 8080`.
