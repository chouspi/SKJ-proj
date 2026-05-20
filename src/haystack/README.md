# Haystack Node

Samostatna FastAPI aplikace v `src/haystack` implementujici zjednoduseny Haystack storage node.

## Co umi

- pri startu otevre nebo vytvori aktivni volume soubor `volume_<n>.dat`
- append-only zapis payloadu na konec aktivniho volume
- rotaci na dalsi volume pri prekroceni limitu velikosti
- background subscriber na broker topicu `storage.write`
- publikaci ACK zprav do `storage.ack`
- HTTP cteni pres `GET /volume/{volume_id}/{offset}/{size}`

## Konfigurace

Konfigurace se bere z environment variables:

- `HAYSTACK_BROKER_URL` - default `ws://127.0.0.1:8001/broker`
- `HAYSTACK_WRITE_TOPIC` - default `storage.write`
- `HAYSTACK_ACK_TOPIC` - default `storage.ack`
- `HAYSTACK_MAX_VOLUME_SIZE_BYTES` - default `104857600` (100 MB)

Volume soubory se ukladaji do `src/haystack/data/volumes/`.

## Spusteni

```bash
pip install -r src/haystack/requirements.txt
uvicorn src.haystack.main:app --reload --host 127.0.0.1 --port 8002
```

## Broker flow

Haystack node pouziva broker jako MessagePack subscriber/publisher.

Prichozi zprava na `storage.write`:

```python
{
    "object_id": "<uuid>",
    "data": b"<binary payload>"
}
```

ACK publikovana na `storage.ack`:

```python
{
    "object_id": "<uuid>",
    "volume_id": 1,
    "offset": 0,
    "size": 1024,
}
```

## HTTP cteni

```text
GET /volume/{volume_id}/{offset}/{size}
```

Endpoint vraci presne `size` bajtu od daneho `offset` z vybraneho `volume_<id>.dat`.

## Compaction

Admin skript pro defragmentaci konkretniho volume:

```bash
python -m src.haystack.compact 1 --gateway-url http://127.0.0.1:8000
```

Postup:

1. skript se ze S3 Gateway zepta na zive objekty ve volume pres `/internal/volumes/{volume_id}/objects`
2. vytvori `volume_<id>_compacted.dat`
3. prepise zive objekty tesne za sebe
4. posle Gateway nove offsety pres `/internal/objects/{object_id}/location`
5. nahradi stary `volume_<id>.dat` kompaktnim souborem
