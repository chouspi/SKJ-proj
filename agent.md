# Agent Notes

Tento soubor shrnuje důležité informace pro další implementaci projektu. Je určený jako pracovní kontext pro další agenty a vývojáře. Nejde o finální dokumentaci API, ale o implementační orientaci.

## Aktuální stav repozitáře

- V repozitáři jsou teď čtyři aplikace:
  - `src/S3_Storage` - backendová FastAPI služba
  - `src/web` - React + Vite + TypeScript frontend pro lokální práci nad aktuálním backendem
  - `src/messagebroker` - samostatný FastAPI WebSocket broker pro interní Pub/Sub komunikaci
  - `src/haystack` - samostatný FastAPI storage node pro append-only volume soubory
- `src/S3_Storage` je aktuálně S3 Gateway, která:
  - přijímá upload přes `POST /files/upload`
  - nové uploady fyzicky neukládá do vlastního filesystemu
  - publikuje binární data přes broker do `storage.write`
  - na pozadí poslouchá ACK zprávy ze `storage.ack`
  - po ACK nastavuje objekt na `status = "ready"` a ukládá `volume_id`, `offset`, `size`
  - download čte interně z Haystack Node přes `/volume/{volume_id}/{offset}/{size}`
  - metadata ukládá do SQLite databáze `src/S3_Storage/data/object_storage.db`
  - používá Alembic migrace pro správu schématu databáze
  - nabízí bucket endpointy `POST /buckets/`, `GET /buckets/`, `GET /buckets/{bucket_id}/objects/`, `GET /buckets/{bucket_id}/billing/`
  - nabízí objektové endpointy `GET /files`, `GET /files/{file_id}`, `DELETE /files/{file_id}` a aliasy pod `/objects/{file_id}`
- Identita uživatele se řeší přes `X-User-Id` header nebo `?user_id=` query parametr.
- V backendu teď existují modely `Bucket` a `StoredFile`.
- `Bucket` aktuálně obsahuje minimálně:
  - `id`
  - `user_id`
  - `name`
  - `created_at`
  - `bandwidth_bytes`
  - `current_storage_bytes`
  - `ingress_bytes`
  - `egress_bytes`
  - `internal_transfer_bytes`
- `StoredFile` aktuálně obsahuje minimálně:
  - `id`
  - `user_id`
  - `bucket_id`
  - `filename`
  - `path`
  - `size`
  - `status`
  - `volume_id`
  - `offset`
  - `is_deleted`
  - `created_at`
- `path` je už jen legacy/dočasné pole pro starší lokální data. Nové Haystack uploady používají `volume_id + offset + size`.
- `src/haystack` už umí:
  - background subscribe na `storage.write`
  - append-only zapisovat payload do `volume_<n>.dat`
  - rotovat volume po překročení limitu velikosti
  - publikovat ACK do `storage.ack`
  - vracet raw data přes `GET /volume/{volume_id}/{offset}/{size}`

## Cílová architektura

Projekt má být rozdělený na 4 nezávislé aplikace/služby:

1. `S3 Gateway`
2. `Message Broker`
3. `Image Processing Node`
4. `Haystack Node`

Aktuální `src/S3_Storage` už plní roli `S3 Gateway` pro upload/download/delete flow přes broker a Haystack. Stále ale chybí image worker a compaction.

Budoucí samostatné aplikace mají mít vlastní adresáře pod `src/`.

- `Message Broker` implementovat do `src/messagebroker`
- `S3 Gateway` bude evoluce dnešního `src/S3_Storage`
- další služby držet odděleně jako samostatné aplikace, ne přimíchávat je do `src/S3_Storage`

Jde o 4 backendové služby, ne o 4 veřejné frontendové aplikace.

- `S3 Gateway` je hlavní veřejné API pro klienty.
- `Message Broker` je interní pub/sub vrstva mezi službami.
- `Image Processing Node` je interní worker pro úpravy obrázků.
- `Haystack Node` je interní storage služba pro fyzický zápis/čtení dat z `volume_<n>.dat`.

Uživatel nebo API klient komunikuje pouze se `S3 Gateway`.

- `Haystack Node` nemá být navrhovaný jako veřejný frontend.
- `Haystack Node` slouží jen jako interní storage backend.
- `Message Broker` také není veřejné API pro klienty.

Praktický tok komunikace:

```text
Client / Postman / curl
        |
        v
   S3 Gateway API
        |
        +--> Message Broker --> Haystack Node
        |
        +--> Message Broker --> Image Processing Node
```

## Hlavní architektonická změna

S3 Gateway už nesmí fyzicky ukládat uploadnuté soubory na disk.

Místo toho má:

- přijmout upload od klienta
- vytvořit metadata záznam v SQLite
- odeslat binární payload přes broker do tématu `storage.write`
- vrátit `202 Accepted`
- počkat na asynchronní ACK zprávu z `storage.ack`
- teprve po ACK označit objekt jako připravený

Fyzické uložení dat na disk bude zodpovědnost `Haystack Node`.

## Co zachovat z aktuální aplikace

- FastAPI základ pro gateway lze zachovat.
- SQLite + SQLAlchemy + Alembic lze zachovat pro metadata/index.
- Identifikace uživatele přes `X-User-Id` nebo `user_id` je užitečná a může zůstat, pokud zadání výslovně nevyžádá jiný auth model.
- UUID identifikátor objektu je vhodné zachovat jako `object_id`.
- Bucket vrstvu a billing model lze zachovat a rozšířit i po přechodu na haystack architekturu.

## Co se musí změnit v S3 Gateway

- `path` už nesmí být hlavní údaj pro čtení nových objektů.
- Metadata model už obsahuje `status`, `volume_id`, `offset`, `size`.
- Současný backend už má `is_deleted` a soft delete na úrovni DB. To je v souladu s cílovým zadáním a má se zachovat.
- `GET` download už interně čte přes HTTP z Haystack Node.
- Další změny v gateway mají být jen kolem compaction/admin API a případného image worker flow, ne návrat k lokálnímu ukládání souborů.

## Doporučený cílový význam polí metadat

- `id` / `object_id`: UUID objektu přidělené gateway
- `user_id`: vlastník objektu
- `filename`: původní název souboru
- `size`: velikost objektu v bajtech
- `status`: očekávané hodnoty minimálně `uploading` a `ready`
- `volume_id`: číslo haystack volume souboru
- `offset`: byte offset uvnitř volume
- `is_deleted`: soft delete příznak
- `created_at`: timestamp vytvoření záznamu

Poznámka: pokud bude potřeba zachovat kompatibilitu se stávajícím kódem, je lepší `path` odstranit až ve chvíli, kdy bude nahrazeno `volume_id + offset + size` v celé read/delete flow.

## Message Broker kontrakty

Zadání předpokládá pub/sub komunikaci a MessagePack serializaci.

Implementační umístění:

- broker má být samostatná FastAPI aplikace v `src/messagebroker`
- veřejné rozhraní brokeru má být interní WebSocket endpoint `/broker`
- broker neimplementovat jako součást `src/S3_Storage`
- aktuální implementace brokeru je záměrně jednoduchá in-memory Pub/Sub vrstva bez vlastní DB persistence
- pokud nebude explicitně vyžadované starší cvičení s durable queues, nevrstvit do brokeru vlastní SQLite/Alembic řešení

Minimální témata:

- `storage.write`
- `storage.ack`

Minimální payload pro `storage.write`:

```python
{
    "object_id": "<uuid>",
    "data": b"<binary payload>"
}
```

Minimální payload pro `storage.ack`:

```python
{
    "object_id": "<uuid>",
    "volume_id": 1,
    "offset": 10560,
    "size": 1024
}
```

Pro další rozšíření může být užitečné přidat i `content_type`, `filename` nebo korelační metadata, ale zatím nevyžadovat bez konkrétní potřeby.

## Haystack Node očekávané chování

Haystack Node je nová FastAPI aplikace, která:

- drží aktivní volume soubor otevřený v append režimu
- zapisuje data append-only na konec souboru
- rotuje na nový volume po překročení nakonfigurovaného limitu
- po zápisu publikuje ACK na `storage.ack`
- poskytuje čtecí endpoint `GET /volume/{volume_id}/{offset}/{size}`

Implementační umístění:

- haystack node je samostatná FastAPI aplikace v `src/haystack`
- volume soubory se ukládají do `src/haystack/data/volumes/`
- broker URL a limit velikosti volume se nastavují přes environment variables

Praktické invarianty:

- Volume je obyčejný binární soubor typu `volume_<n>.dat`
- Offset musí vždy ukazovat na přesný začátek payloadu
- `size` je přesná délka uložených dat v bajtech
- Čtení objektu má fungovat pouze přes `seek(offset)` + `read(size)`
- Haystack Node neřeší ownership, auth ani soft delete; to zůstává v gateway

## S3 Gateway read flow

Budoucí read flow má být:

1. Gateway přijme požadavek uživatele na download.
2. Ověří, že objekt existuje, patří uživateli, není smazaný a má `status == "ready"`.
3. Z DB načte `volume_id`, `offset`, `size`.
4. Gateway interně zavolá Haystack Node endpoint `/volume/{volume_id}/{offset}/{size}`.
5. Data obratem přepošle klientovi.

Uživatel nemá komunikovat přímo s Haystack Node.

To platí i v případě, že Haystack Node poskytuje vlastní HTTP endpoint pro interní čtení. Tento endpoint je určený pro volání ze `S3 Gateway`, ne jako veřejné API pro klienta.

## Mazání

Cílové mazání má být striktní soft delete:

- v gateway DB ponechat řádek
- nastavit `is_deleted = True`
- fyzická data ve volume nesahat
- Haystack Node o smazání nemusí vědět

To je důležité i pro pozdější compaction.

## Compaction

Compaction se má dělat odděleně od běžného write/read provozu.

Očekávaný postup:

1. Pro konkrétní volume získat ze S3 Gateway seznam živých objektů.
2. Vytvořit nový soubor typu `volume_<n>_compacted.dat`.
3. Přeskládat živé objekty těsně za sebe.
4. Průběžně posílat gateway nové `offset` a případně `volume_id`.
5. Po úspěšném dokončení nahradit původní volume.

Compaction logika nemá měnit obsah payloadů, jen jejich fyzické umístění.

## Důležité implementační poznámky

- Broker listener v gateway i v Haystack Node musí běžet na pozadí, aby neblokoval FastAPI server.
- Pro background listenery použít task spuštěný při startu aplikace.
- ACK update v gateway musí být idempotentní; opakované doručení zprávy nesmí rozbít data.
- Billing se má spouštět až po úspěšném ACK, ne při přijetí upload HTTP requestu.
- `uploading` stav znamená eventual consistency; download v této fázi nemá být prezentovaný jako hotový soubor.
- Pokud objekt není `ready`, gateway má vracet vhodnou odpověď místo pokusu o čtení z Haystack Node.

## Co zatím v repozitáři není

- samostatná implementace image workeru
- compaction skript nebo chráněný Haystack endpoint

## Doporučený další postup implementace

1. Přidat Image Processing Node, pokud je potřeba pro projektovou část 1.
2. Přidat compaction skript nebo chráněný endpoint v Haystack Node.
3. Volitelně doladit frontend polling pro `uploading -> ready` stavy.
4. Dopsat integrační dokumentaci pro spuštění všech služeb.

## Důležité omezení pro další agenty

- Nevracet se k ukládání uploadů přímo do filesystemu gateway, pokud to není jen dočasný migrační krok.
- Neposílat klienta přímo na Haystack Node; gateway zůstává jediným veřejným vstupem.
- Nemazat řádky objektů z DB při běžném delete endpointu.
- Nepředpokládat, že aktuální `path` model je dlouhodobě správný; je to jen pozůstatek první verze.
