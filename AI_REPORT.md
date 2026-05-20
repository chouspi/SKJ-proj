# AI Report

## Pouzite AI nastroje

- OpenAI Codex / ChatGPT jako asistence pri navrhu API a implementaci FastAPI backendu

## Priklady promptu

- "Navrhni minimalni REST API pro object storage sluzbu inspirovanou S3."
- "Vytvor FastAPI endpoint pro upload souboru pres multipart/form-data a uloz metadata do JSON."
- "Jak navrhnout oddeleni souboru ruznych uzivatelu na disku bez kolize nazvu?"

## Co AI vygenerovala spravne

- zakladni strukturu REST API
- navrh upload endpointu s `multipart/form-data`
- generovani unikatniho `file_id`
- rozdeleni ulozeni souboru podle uzivatele

## Co bylo nutne opravit

- doplnit kontrolu pristupu k souborum podle uzivatele
- upravit ukladani metadat tak, aby obsahovala i cestu a cas vytvoreni
- doladit dokumentaci a priklady volani endpointu

## Jake chyby AI udelala

- AI mela tendenci navrhovat slozitejsi reseni s databazi, i kdyz minimalni zadani staci splnit pres JSON metadata
- bylo potreba zkontrolovat, aby se puvodni nazvy souboru nepouzivaly jako jmena ulozenych souboru na disku
- bylo potreba rucne projit autorizacni logiku, aby jiny uzivatel nemohl cist nebo mazat cizi soubory
