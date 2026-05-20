# S3 Storage

FastAPI backend pro jednoduchou object storage službu. Binární soubory se ukládají na disk a metadata se perzistují v SQLite databázi přes SQLAlchemy ORM.

## Co umí

- `POST /files/upload` nahraje soubor přes `multipart/form-data`
- `GET /files` vrátí seznam souborů aktuálního uživatele
- `GET /files/{file_id}` stáhne soubor, pokud má uživatel přístup
- `DELETE /files/{file_id}` smaže soubor i metadata

## Identifikace uživatele

Uživatele můžeš předat dvěma způsoby:

- `X-User-Id: alice`
- `?user_id=alice`

Pro otevření v browseru je pohodlnější query parametr:

```text
http://127.0.0.1:8000/files?user_id=alice
```

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
# z kořene repozitáře
uvicorn src.S3_Storage.main:app --reload

# nebo přímo z adresáře src/S3_Storage
uvicorn main:app --reload
```

Server běží standardně na `http://127.0.0.1:8000`.

## Testování přes Swagger UI

Otevři:

```text
http://127.0.0.1:8000/docs
```

Pro upload:

1. otevři `POST /files/upload`
2. klikni na `Try it out`
3. vyplň `user_id`, například `alice`
4. vyber soubor přes `Choose File`
5. klikni na `Execute`

Pro výpis souborů:

1. otevři `GET /files`
2. klikni na `Try it out`
3. vyplň `user_id`, například `alice`
4. klikni na `Execute`

## Testování pomocí curl

Upload:

```bash
curl -X POST "http://127.0.0.1:8000/files/upload?user_id=alice" ^
  -F "file=@test.txt"
```

Seznam souborů:

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
