# Message Broker

Samostatna FastAPI aplikace v `src/messagebroker` implementujici asynchronni Pub/Sub broker nad WebSocket endpointem `/broker`.

## Co umi

- vice soucasnych klientu
- subscribe na konkretni topic
- publish zpravy do topicu
- okamzite routovani vsem subscriberum daneho topicu
- podporu `JSON` a `MessagePack`
- bezpecne odebrani klienta pri odpojeni

Tato verze je zamerne jednodussi a drzi se finalni architektury projektu: broker je komunikacni vrstva mezi sluzbami a nema vlastni perzistentni DB.

## Instalace

```bash
pip install -r src/messagebroker/requirements.txt
```

## Spusteni brokeru

```bash
uvicorn src.messagebroker.main:app --reload --host 127.0.0.1 --port 8001
```

Broker pak posloucha na:

```text
ws://127.0.0.1:8001/broker
```

## Protokol zprav

Subscribe:

```json
{
  "action": "subscribe",
  "topic": "storage.write"
}
```

Publish:

```json
{
  "action": "publish",
  "topic": "storage.ack",
  "payload": {
    "object_id": "123",
    "volume_id": 1,
    "offset": 4096,
    "size": 512
  }
}
```

Deliver event od brokeru:

```json
{
  "action": "deliver",
  "topic": "storage.ack",
  "message_id": 7,
  "payload": {
    "object_id": "123",
    "volume_id": 1,
    "offset": 4096,
    "size": 512
  }
}
```

## Klientsky skript

Subscriber v JSON modu:

```bash
python -m src.messagebroker.mb_client subscriber --topic storage.write --format json
```

Publisher v MessagePack modu:

```bash
python -m src.messagebroker.mb_client publisher \
  --topic storage.ack \
  --format msgpack \
  --payload '{"object_id":"abc","volume_id":1,"offset":10,"size":20}'
```

Publisher s binarnim souborem v payloadu:

```bash
python -m src.messagebroker.mb_client publisher \
  --topic storage.write \
  --format msgpack \
  --payload '{"object_id":"abc"}' \
  --payload-file ./image.jpg \
  --payload-key data
```

## Benchmark

```bash
python -m src.messagebroker.benchmark --format both --publishers 5 --subscribers 5 --messages 10000
```

## Testy

```bash
pytest src/messagebroker/tests -q
```
