# Escalation Trivial 2.0 · Verifica del gioco e del catalogo

**Rapporto storico della versione 2.0 · 18 novembre 2026.** La revisione riguarda il pacchetto Railway 1.1 allegato. Il prodotto mantiene una partita condivisa, tre interfacce, PIN a sei cifre, WebSocket e SQLite. È stato collaudato su un server locale temporaneo, con dati di prova.

## 1. Cosa cambia per chi gioca

| Situazione | Comportamento nella versione 2.0 |
|---|---|
| Ingresso dal telefono | PIN numerico, nome di gioco e accesso diretto da QR. La pagina spiega il punteggio prima dell’iscrizione. |
| Attesa in lobby | Contatore aggiornato anche sul telefono. Un partecipante può uscire e liberare posto e nickname prima dell’avvio. La regia attende almeno un iscritto. |
| Risposta | Conferma del server distinguibile dall’invio in corso. Il rientro recupera anche la scelta già registrata. Durante il round il proiettore riceve solo contenuti pubblici. |
| Chiusura anticipata | La regia chiede conferma quando alcuni iscritti devono ancora rispondere. I comandi sono associati alla partita e al round visualizzati. |
| Risultati | La soluzione è accompagnata dalla spiegazione. Sul telefono si vedono scelta, punti guadagnati, totale e posizione. La sala vede percentuali e conteggi. |
| Classifica | A punteggio uguale corrisponde la stessa posizione anche nel CSV. Il gioco distingue la normale conclusione, l’annullamento e il caso in cui nessuno abbia totalizzato punti. |
| Proiezione | PIN e QR ad alto contrasto, timer di round, schermo intero e brevi segnali sonori attivabili. L’audio parte spento. |
| Continuità | La singola istanza conserva su SQLite le risposte e le domande assegnate. Un aggiornamento del catalogo lascia alla partita preesistente la soluzione con cui è iniziata. |

L’identità grafica riprende una console da gioco arancione su grafite. Colori, lettere A–D, diciture e icone rendono leggibile l’esito anche senza distinguere le tinte. I controlli sono accessibili da tastiera e le animazioni rispettano la preferenza di movimento ridotto. Nell’ingresso, negli elementi di attesa e nella classifica le animazioni segnalano cambi di stato. Il timer resta basato sulla scadenza del server.

## 2. Analisi delle domande

Nel catalogo iniziale tutti i quesiti avevano livello *Base*. Molti distrattori appartenevano ad ambiti lontani dalla domanda, come batteria o tastiere in un quesito sulle reti. Altre domande si risolvevano cercando un assoluto come «sempre» o «garantisce». Nelle scelte multiple nessuna soluzione occupava la quarta posizione.

Tutti i 100 quesiti sono stati riscritti o rielaborati con i rispettivi distrattori e spiegazioni. Gli ID, le otto categorie e i due formati sono stati conservati. Le alternative binarie contrappongono spesso due decisioni concrete. Le domande avanzate richiedono di interpretare più elementi di uno scenario, per esempio una sessione cloud ancora valida, gli orari di due log o lo scostamento dall’RPO.

| Tema del catalogo | Base | Intermedio | Avanzato | Totale |
|---|---:|---:|---:|---:|
| Phishing e ingegneria sociale | 6 | 7 | 2 | 15 |
| Password e autenticazione | 6 | 6 | 3 | 15 |
| Malware e ransomware | 7 | 6 | 2 | 15 |
| Reti e sicurezza web | 6 | 6 | 3 | 15 |
| Privacy e protezione dati | 3 | 4 | 3 | 10 |
| Comportamenti sicuri | 4 | 5 | 1 | 10 |
| SOC e risposta agli incidenti | 3 | 4 | 3 | 10 |
| Cloud, backup e continuità | 2 | 5 | 3 | 10 |
| **Totale** | **37** | **43** | **20** | **100** |

| Distribuzione delle soluzioni | A | B | C | D |
|---|---:|---:|---:|---:|
| Quattro alternative, versione 1.1 | 40 | 13 | 5 | 0 |
| Quattro alternative, versione 2.0 | 15 | 15 | 14 | 14 |
| Due alternative, versione 1.1 | 20 | 22 | — | — |
| Due alternative, versione 2.0 | 21 | 21 | — | — |

La posizione resta stabile tra regia, telefono, proiezione e riconnessione. L’opzione *Mescola* cambia l’ordine dei quesiti. La pesca da dieci distribuisce la selezione su tutte le categorie e poi estrae due ulteriori domande senza duplicati. Il filtro di difficoltà serve a comporre manualmente un percorso per il pubblico. I livelli sono una valutazione editoriale della complessità richiesta. La difficoltà effettiva dipenderà dal gruppo e potrà essere stimata con le risposte raccolte durante i corsi.

| Esempio | Che cosa verifica |
|---|---|
| PHI-013 e PHI-014 | La distinzione fra un messaggio proveniente da una casella o da un dominio autentico e l’autorizzazione effettiva a cambiare IBAN. |
| AUT-007 e AUT-014 | Perché WebAuthn resiste ai falsi portali e perché, nello scenario specificato, occorre revocare le sessioni oltre a cambiare la password. |
| PRI-002, PRI-009 e PRI-010 | Decorrenza delle 72 ore dalla conoscenza, documentazione della violazione e condizioni della comunicazione agli interessati. |
| SOC-004 e SOC-007 | Correlazione di orari in fusi diversi e interpretazione contestuale di un indicatore condiviso. |
| BCP-003 e BCP-004 | Applicazione numerica degli obiettivi di ripristino e di perdita dei dati. |

### Fonti didattiche principali

| Area | Riferimento consultato |
|---|---|
| Protezione dei dati | Regolamento (UE) 2016/679, in particolare artt. 4–6 e 33–35. [Testo italiano su EUR-Lex](https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32016R0679) |
| Identità digitale | NIST SP 800-63B-4, autenticazione, gestione delle password e resistenza al phishing. [Digital Identity Guidelines](https://pages.nist.gov/800-63-4/sp800-63b.html) |
| Phishing e ransomware | NCSC, riconoscimento delle richieste sospette e recupero da copie separate. [Phishing](https://www.ncsc.gov.uk/collection/phishing-scams/spot-scams) · [Malware e ransomware](https://www.ncsc.gov.uk/guidance/mitigating-malware-and-ransomware-attacks) |
| Risposta agli incidenti | NIST SP 800-61 Rev. 3, integrazione della risposta e del miglioramento nella gestione del rischio. [Pubblicazione NIST](https://csrc.nist.gov/pubs/sp/800/61/r3/final) |
| Sviluppo sicuro | OWASP Cheat Sheet Series, scelta di query parametrizzate e API testuali sicure nei rispettivi contesti. [SQL](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html) · [XSS](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html) |
| Continuità | NIST SP 800-34 Rev. 1, BIA, strategie di ripristino e prove di continuità. [Pubblicazione NIST](https://csrc.nist.gov/pubs/sp/800/34/r1/upd1/final) |

## 3. Collaudo eseguito

| Prova | Esito osservato |
|---|---|
| Integrità catalogo | 100 ID e 100 testi distinti. Tutti i quesiti hanno categoria coerente, spiegazione, livello, alternative distinte e un indice corretto valido. |
| Accesso e isolamento ruoli | API docente con accesso riservato. Verificati su connessioni reali regia, proiettore e partecipante. Il proiettore, anche alla prima apertura HTTP, e il partecipante non ricevono la soluzione durante la domanda. |
| Carico locale | 400 iscrizioni valide, rifiuto del 401º iscritto, 400 connessioni WebSocket di gioco, 400 risposte accettate allo stesso round e 400 classifiche personali finali ricevute. |
| Casi di gioco | Nickname duplicato, rifiuto avvio senza iscritti, uscita e liberazione posto, risposta doppia o riferita al round precedente, comando docente obsoleto, scadenza automatica e risposta tardiva. |
| Punteggi ed esportazione | Risposta esatta nell’intervallo 500–1.000. Domanda saltata a zero. Parità 1ª, 2ª, 2ª coerente fra proiezione e CSV. Il test di carico verifica tutte le 400 righe esportate. |
| Ripristino | Recuperati scelta già inviata e risultati finali. Un riavvio con scadenza trascorsa pubblica il risultato. Una nuova lobby invalida la sessione precedente. |
| Migrazione | Un database con schema 1.1 e risposta originale diversa dal nuovo catalogo mantiene testo e indice corretti per la vecchia partita. Un secondo avvio lascia i dati coerenti. |
| Browser, partecipante | In Chromium è stato percorso l’ingresso, il regolamento, la lobby e un quiz reale di due round, con quattro e due alternative. Entrambe le risposte sono state confermate. Verificati spiegazione, posizione, punteggio finale e ritorno all’ingresso in un riquadro da 390 × 844 pixel. |
| Browser, regia e sala | Verificate la pagina di accesso docente e la resa di configurazione e lobby proiettata con dati di prova. Per i comandi protetti, il ciclo completo è stato collaudato sulle API e sui WebSocket del server. |
| Launcher, risorse e QR | Il launcher Python ha creato credenziali e database da zero usando dipendenze già disponibili. Verificate le tre pagine e tutte le risorse principali. Un decodificatore QR indipendente ha letto dall’immagine restituita dal server l’URL e il PIN corretti. |

Il test di carico usa client virtuali su un singolo computer. Restano da verificare le prestazioni dell’istanza Railway scelta e della rete Wi-Fi con dispositivi fisici. L’immagine Docker non è stata costruita in questa sessione. Il launcher è stato avviato su Linux. I file di avvio Windows e macOS sono inclusi, ma il doppio clic nativo su questi due sistemi non è stato collaudato. I file statici e il backend sono gli stessi nelle tre modalità di avvio.
