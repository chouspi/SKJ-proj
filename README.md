# Mini Object Storage Service

Jednoducha backendova sluzba ve FastAPI pro upload, ulozeni, stazeni, vypsani a smazani souboru.

## Co umi

- `POST /files/upload` nahraje soubor pres `multipart/form-data`
- `GET /files` vrati seznam souboru aktualniho uzivatele
- `GET /files/{id}` stahne soubor, pokud uzivatel ma pristup
- `DELETE /files/{id}` smaze soubor i metadata

## Identifikace uzivatele

Pro jednoduchost se uzivatel predava v HTTP hlavicce:

- `X-User-Id: alice`

Tento pristup je vhodny pro cviceni. Ve vetsim projektu by na tom miste byla autentizace a autorizace pres token/session.

## Ulozeni na disk

Soubory se ukladaji takto:

```text
storage/
  <user_id>/
    <file_id>
```

Metadata jsou ulozena v JSON souboru:

```text
data/files_metadata.json
```

## Instalace

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Spusteni

```bash
uvicorn app.main:app --reload
```

Server pote bezi standardne na [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Testovani pomoci curl

Upload:

```bash
curl -X POST "http://127.0.0.1:8000/files/upload" ^
  -H "X-User-Id: alice" ^
  -F "file=@test.txt"
```

Seznam souboru:

```bash
curl "http://127.0.0.1:8000/files" -H "X-User-Id: alice"
```

Stazeni:

```bash
curl "http://127.0.0.1:8000/files/<file_id>" ^
  -H "X-User-Id: alice" ^
  --output downloaded.txt
```

Smazani:

```bash
curl -X DELETE "http://127.0.0.1:8000/files/<file_id>" -H "X-User-Id: alice"
```

## API navrh

### `POST /files/upload`

- Vstup: `multipart/form-data` s polem `file`
- Vystup:

```json
{
  "id": "string",
  "filename": "string",
  "size": 1234
}
```

### `GET /files`

- Vrati seznam metadat souboru daneho uzivatele

### `GET /files/{id}`

- Vrati binarni obsah souboru
- Kontroluje vlastnictvi souboru podle `X-User-Id`

### `DELETE /files/{id}`

- Smaze soubor ze storage
- Odstrani odpovidajici metadata

