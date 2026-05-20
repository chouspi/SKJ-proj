# S3 Storage

FastAPI backend pro jednoduchou object storage službu je teď umístěný celý v `src/S3_Storage/`.

## Co umí

- `POST /files/upload` nahraje soubor přes `multipart/form-data`
- `GET /files` vrátí seznam souborů aktuálního uživatele
- `GET /files/{id}` stáhne soubor, pokud má uživatel přístup
- `DELETE /files/{id}` smaže soubor i metadata

## Identifikace uživatele

Uživatele můžeš předat dvěma způsoby:

- `X-User-Id: alice`
- `?user_id=alice`

Pro otevření v browseru je pohodlnější query parametr, například:

```text
http://127.0.0.1:8000/files?user_id=alice
```

## Uložení na disk

Soubory i metadata se ukládají přímo v rámci tohoto modulu:

```text
src/S3_Storage/
  storage/
    <user_id>/
      <file_id>
  data/
    files_metadata.json
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

Server potom běží standardně na `http://127.0.0.1:8000`.

Poznámka: endpointy `/files*` vyžadují identifikaci uživatele přes `X-User-Id` nebo `user_id`. Pokud nepošleš ani jedno, API vrátí `400`.

## Testování pomocí curl

Upload:

```bash
curl -X POST "http://127.0.0.1:8000/files/upload" ^
  -H "X-User-Id: alice" ^
  -F "file=@test.txt"
```

Seznam souborů:

```bash
curl "http://127.0.0.1:8000/files?user_id=alice"
```

Stažení:

```bash
curl "http://127.0.0.1:8000/files/<file_id>" ^
  -H "X-User-Id: alice" ^
  --output downloaded.txt
```

Smazání:

```bash
curl -X DELETE "http://127.0.0.1:8000/files/<file_id>" -H "X-User-Id: alice"
```
