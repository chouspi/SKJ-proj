# S3 Storage

FastAPI S3 Gateway pro object storage službu. Metadata jsou v SQLite přes SQLAlchemy ORM, schéma databáze se spravuje přes Alembic migrace a nové uploady se fyzicky ukládají přes Message Broker do Haystack Node.

## Co umí

- `POST /buckets/` vytvoří bucket pro aktuálního uživatele
- `GET /buckets/` vrátí buckety aktuálního uživatele
- `GET /buckets/{bucket_id}/objects/` vrátí objekty v bucketu
- `GET /buckets/{bucket_id}/billing/` vrátí billing counters bucketu
- `POST /files/upload` přijme soubor, uloží metadata se stavem `uploading`, pošle payload do `storage.write` a vrátí `202 Accepted`
- `GET /files` vrátí seznam objektů aktuálního uživatele napříč buckety
- `GET /files/{file_id}` nebo `GET /objects/{file_id}` stáhne objekt přes Haystack, pokud má status `ready`
- `DELETE /files/{file_id}` nebo `DELETE /objects/{file_id}` provede soft delete
- `POST /buckets/{bucket_id}/objects/{object_id}/process` spustí async image processing job přes broker topic `image.jobs`

Pokud upload nepředá `bucket_id`, backend automaticky použije nebo vytvoří výchozí bucket `default-<user_id>`.

## Identifikace uživatele

Uživatele můžeš předat dvěma způsoby:

- `X-User-Id: alice`
- `?user_id=alice`

Pro otevření v browseru je pohodlnější query parametr:

```text
http://127.0.0.1:8000/files?user_id=alice
```

## Databázové migrace

Inicializace DB probíhá přes Alembic, ne přes `Base.metadata.create_all()`.

```bash
# z kořene repozitáře
alembic upgrade head
```

V repozitáři jsou 3 revize:

- `0001_buckets` - bucket tabulka a vazba objektu na bucket
- `0002_bucket_billing` - billing a storage counters
- `0003_soft_delete` - příznak `is_deleted`
- `0004_haystack_metadata` - `status`, `volume_id`, `offset` a nullable legacy `path`

## Uložení dat

S3 Gateway už nové soubory fyzicky neukládá do svého `storage/` adresáře.

Upload flow:

1. Gateway přijme soubor a vytvoří DB záznam se `status = "uploading"`.
2. Gateway pošle MessagePack zprávu do broker topicu `storage.write`.
3. Haystack Node zapíše data do `volume_<n>.dat`.
4. Haystack publikuje ACK do `storage.ack`.
5. Gateway ACK listener doplní `volume_id`, `offset`, `size` a nastaví `status = "ready"`.

Legacy adresář může pořád existovat kvůli starším datům:

```text
src/S3_Storage/
  storage/
    <user_id>/
      <file_id>
  data/
    object_storage.db
    files_metadata.json   # volitelný legacy zdroj pro jednorázovou migraci
```

Haystack volume soubory jsou v `src/haystack/data/volumes/`.

## Instalace

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r src/S3_Storage/requirements.txt
```

## Spuštění

```bash
# nejdřív aplikuj migrace
alembic upgrade head

# spust broker
uvicorn src.messagebroker.main:app --reload --host 127.0.0.1 --port 8001

# spust Haystack Node
uvicorn src.haystack.main:app --reload --host 127.0.0.1 --port 8002

# z kořene repozitáře
uvicorn src.S3_Storage.main:app --reload

# nebo přímo z adresáře src/S3_Storage
uvicorn main:app --reload
```

Server běží standardně na `http://127.0.0.1:8000`.

Pro lokální spuštění celého řetězce lze použít root skript:

```bash
./start.sh
```

## Billing logika

- `bandwidth_bytes`: celkový součet přenesených bajtů pro bucket
- `current_storage_bytes`: součet velikostí všech uložených objektů v bucketu
- `ingress_bytes`: úspěšně ACKnuté uploady
- `egress_bytes`: externí downloady
- `internal_transfer_bytes`: interní přenosy označené `X-Internal-Source: true`

Soft delete nemaže fyzická data na disku a nesnižuje `current_storage_bytes`.

## Image Processing

Gateway neprovádí CPU-bound operace nad obrázky. Pouze zvaliduje request, ověří práva a stav objektu a pošle job do brokeru.

```bash
curl -X POST "http://127.0.0.1:8000/buckets/1/objects/<file_id>/process?user_id=alice" ^
  -H "Content-Type: application/json" ^
  -d "{\"operation\":\"grayscale\",\"params\":{}}"
```

Podporované operace workeru:

- `negative`
- `mirror`
- `crop`
- `brightness`
- `grayscale`

Výsledek se nahraje zpět přes Gateway jako nový objekt a worker publikuje stav do `image.done`.

## Compaction API pro Haystack

Interni endpointy pro administrační skript `src.haystack.compact`:

- `GET /internal/volumes/{volume_id}/objects`
- `PATCH /internal/objects/{object_id}/location`

Tyto endpointy nejsou určeny pro běžného klienta. Slouží jen pro přepsání živých objektů při kompakci volume souborů.

## Testování přes Swagger UI

Otevři:

```text
http://127.0.0.1:8000/docs
```

Pro vytvoření bucketu:

1. otevři `POST /buckets/`
2. klikni na `Try it out`
3. vyplň `user_id`, například `alice`
4. do body zadej `{"name": "alice-photos"}`
5. klikni na `Execute`

Pro upload:

1. otevři `POST /files/upload`
2. klikni na `Try it out`
3. vyplň `user_id`, například `alice`
4. volitelně vyplň `bucket_id`
5. vyber soubor přes `Choose File`
6. klikni na `Execute`

Pro výpis bucket objektů:

1. otevři `GET /buckets/{bucket_id}/objects/`
2. klikni na `Try it out`
3. vyplň `user_id`, například `alice`
4. zadej `bucket_id`
5. klikni na `Execute`

## Testování pomocí curl

Upload:

```bash
curl -X POST "http://127.0.0.1:8000/files/upload?user_id=alice&bucket_id=1" ^
  -F "file=@test.txt"
```

Vytvoření bucketu:

```bash
curl -X POST "http://127.0.0.1:8000/buckets/?user_id=alice" ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"alice-photos\"}"
```

Seznam bucket objektů:

```bash
curl "http://127.0.0.1:8000/buckets/1/objects/?user_id=alice"
```

Seznam všech souborů uživatele:

```bash
curl "http://127.0.0.1:8000/files?user_id=alice"
```

Stažení:

```bash
curl "http://127.0.0.1:8000/files/<file_id>?user_id=alice" ^
  --output downloaded.txt
```

Smazání:

```bash
curl -X DELETE "http://127.0.0.1:8000/files/<file_id>?user_id=alice"
```

Billing:

```bash
curl "http://127.0.0.1:8000/buckets/1/billing/?user_id=alice"
```
