# S3 Storage

FastAPI backend pro jednoduchou object storage službu. Binární soubory se ukládají na disk, metadata jsou v SQLite přes SQLAlchemy ORM a schéma databáze se spravuje přes Alembic migrace.

## Co umí

- `POST /buckets/` vytvoří bucket pro aktuálního uživatele
- `GET /buckets/` vrátí buckety aktuálního uživatele
- `GET /buckets/{bucket_id}/objects/` vrátí objekty v bucketu
- `GET /buckets/{bucket_id}/billing/` vrátí billing counters bucketu
- `POST /files/upload` nahraje soubor přes `multipart/form-data`
- `GET /files` vrátí seznam objektů aktuálního uživatele napříč buckety
- `GET /files/{file_id}` nebo `GET /objects/{file_id}` stáhne objekt, pokud má uživatel přístup
- `DELETE /files/{file_id}` nebo `DELETE /objects/{file_id}` provede soft delete

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

## Uložení na disk

```text
src/S3_Storage/
  storage/
    <user_id>/
      <file_id>
  data/
    object_storage.db
    files_metadata.json   # volitelný legacy zdroj pro jednorázovou migraci
```

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

# z kořene repozitáře
uvicorn src.S3_Storage.main:app --reload

# nebo přímo z adresáře src/S3_Storage
uvicorn main:app --reload
```

Server běží standardně na `http://127.0.0.1:8000`.

## Billing logika

- `bandwidth_bytes`: celkový součet přenesených bajtů pro bucket
- `current_storage_bytes`: součet velikostí všech uložených objektů v bucketu
- `ingress_bytes`: externí uploady
- `egress_bytes`: externí downloady
- `internal_transfer_bytes`: interní přenosy označené `X-Internal-Source: true`

Soft delete nemaže fyzická data na disku a nesnižuje `current_storage_bytes`.

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
