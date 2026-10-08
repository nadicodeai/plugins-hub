# Selezione dei bandi

How to decide whether a works notice is one the company can bid for. Read it before judging
the scanner's items; the settings it refers to are `settings.json` in the state directory.

## 1. Is it a works procurement the company can enter?

| The notice is | Verdict |
| --- | --- |
| Avviso di avvio della consultazione (art. 50 c. 2-bis), indagine di mercato, manifestazione di interesse, procedura negoziata, procedura aperta, bando di gara, determina a contrarre that starts a procedure | Can be entered: judge it |
| Esito di gara, aggiudicazione, avviso di appalto aggiudicato, elenco operatori invitati | `aggiudicazione`: market information, never a lead |
| Affidamento diretto or determina a contrarre with direct award to a named firm, impegno di spesa, liquidazione, SAL, subappalto, proroga, collaudo | Drop: already given to someone |
| Incarico or servizi tecnici (progettazione, direzione lavori, collaudo, geologo, RSPP, frazionamento) | Drop: professional service, not works |
| Services, supplies, concessions, staff calls, grants, programma triennale, section headings | Drop |
| Proposta di partenariato pubblico privato (art. 193) for works the company does | `altro`, unless the settings say the company proposes PPPs |

A procedure the comune runs through a central purchasing body (CUC, SUA Provincia di Bergamo,
CUC Area Vasta Brescia, ARIA/Sintel) still counts: the comune's own notice is the lead, and the
platform is where the bid goes.

## 2. Value

Take the value of the works from the notice itself: *importo dei lavori a base di gara* or
*importo complessivo dei lavori*, including the *oneri per la sicurezza*, excluding VAT and the
*somme a disposizione*. A *quadro economico* total is the whole project, not the contract.

The procedure tells the band when the notice gives no figure (D.Lgs. 36/2023, art. 50 c. 1):

| Procedure | Works value |
| --- | --- |
| lett. a, affidamento diretto | under €150,000 |
| lett. c, procedura negoziata, at least 5 operators | €150,000 to under €1,000,000 |
| lett. d, procedura negoziata, at least 10 operators | €1,000,000 to the EU threshold (€5,404,000 in 2026) |
| procedura aperta or ristretta | any value; above the EU threshold always |

A notice is in range when its value is within `min_eur` and `max_eur`. An unknown value is never
a reason to drop a notice that fits the categories: mark it *da verificare*.

## 3. Categories

The notice names the *categoria prevalente* (and any *scorporabili*) with a code such as OG3 or
OS21. When it names none, infer the prevalent category from the subject with the table below and
say that it is inferred.

The company can bid alone when its SOA (`settings.soa`, category → class) holds the prevalent
category with a class whose limit, increased by one fifth, covers the value. A missing
*scorporabile* category can be covered by subcontracting or a temporary grouping (RTI); say so in
the note rather than dropping the lead.

| Class | Limit |
| --- | --- |
| I | €258,000 |
| II | €516,000 |
| III | €1,033,000 |
| III-bis | €1,500,000 |
| IV | €2,582,000 |
| IV-bis | €3,500,000 |
| V | €5,165,000 |
| VI | €10,329,000 |
| VII | €15,494,000 |
| VIII | no limit |

| Code | Work | Words that point to it in a title |
| --- | --- | --- |
| OG1 | Civil and industrial buildings | edificio, scuola, palestra, municipio, ampliamento, nuova sede, spogliatoi, cimitero |
| OG2 | Restoration of protected buildings | restauro, chiesa, bene tutelato |
| OG3 | Roads, bridges, railways, cycle paths | strada, asfaltatura, marciapiede, pista ciclopedonale, rotatoria, parcheggio, piazza, barriere architettoniche |
| OG4 | Underground works | galleria, sottopasso |
| OG6 | Water, gas and sewer networks, irrigation | acquedotto, fognatura, rete idrica, gas, teleriscaldamento, sottoservizi, collettore, tubazioni |
| OG8 | River and hydraulic works, land reclamation | idrogeologico, torrente, alveo, argine, tombotto, esondazione, vasca di laminazione |
| OG10 | Power distribution, public lighting | illuminazione pubblica, cabina, media tensione |
| OG11 | Building technical systems | impianti tecnologici |
| OG12 | Environmental clean-up and protection | bonifica, amianto, siti contaminati, discarica |
| OG13 | Natural engineering | ingegneria naturalistica |
| OS1 | Earthworks | scavi, movimento terra |
| OS3 | Plumbing | impianto idrico-sanitario |
| OS6 / OS7 / OS8 | Finishes, waterproofing | serramenti, finiture, impermeabilizzazione |
| OS9 / OS10 | Traffic lights, road signs | semafori, segnaletica |
| OS12-A / OS12-B | Road barriers, rockfall barriers | guard rail, barriere paramassi |
| OS21 | Special structures | consolidamento, frana, versante, paratie, micropali, muro di sostegno |
| OS22 | Water treatment plants | depuratore, potabilizzazione |
| OS23 | Demolition | demolizione |
| OS24 | Green spaces, street furniture | verde, parco, arredo urbano |
| OS28 | Heating and air conditioning | impianti termici, caldaia, climatizzazione |
| OS29 | Railway track | armamento ferroviario, binari |
| OS30 | Building electrical systems | impianti elettrici |

## 4. Verdict

- `in_linea`: can be entered (step 1), value in range or unknown (step 2), and the prevalent
  category is one the company holds, or the subject matches `attivita` or `parole_chiave` (step 3).
- `altro`: works that can be entered but fail the range or the categories. One line of why.
- `aggiudicazione`: an award, with the winner and value when the notice gives them.
- Drop everything else, and anything matching `escludi`.

Write in `nota`, in Italian and in one or two sentences, why the notice fits or fails: the
category and class that cover it, or the reason it does not.
