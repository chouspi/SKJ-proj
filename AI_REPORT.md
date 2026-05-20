# AI Report

## Pouzite AI nastroje

- OpenAI Codex / ChatGPT jako asistence pri navrhu API, Alembic migraci a implementaci FastAPI backendu

## Priklady promptu

- "Navrhni minimalni REST API pro object storage sluzbu inspirovanou S3."
- "Zaved Alembic do existujici SQLAlchemy aplikace a navrhni postupne migrace."
- "Jak navrhnout bucket relaci, billing counters a soft delete bez ztraty stavajicich dat?"

## Co AI vygenerovala spravne

- zakladni strukturu REST API
- navrh upload endpointu s `multipart/form-data`
- generovani unikatniho `file_id`
- zakladni napojeni Alembicu na SQLAlchemy metadata
- navrh bucket a soft delete rozsireni

## Co bylo nutne opravit

- doplnit kontrolu pristupu k souborum a bucketum podle uzivatele
- dopsat migracni backfill pro existujici data pri pridani `bucket_id`
- doladit dokumentaci, Alembic konfiguraci a priklady volani endpointu

## Jake chyby AI udelala

- AI mela tendenci navrhovat finalni schema najednou misto tri po sobe jdoucich migraci
- bylo potreba zkontrolovat, aby se puvodni nazvy souboru nepouzivaly jako jmena ulozenych souboru na disku
- bylo potreba rucne projit autorizacni logiku a SQLite batch migrace, aby jiny uzivatel nemohl cist nebo mazat cizi soubory a migrace fungovaly spolehlive
