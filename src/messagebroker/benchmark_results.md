# Benchmark Results

## Konfigurace prostredi

Benchmark byl spusten nad bezicim brokerem pres:

```bash
python -m src.messagebroker.benchmark --format both --publishers 5 --subscribers 5 --messages 10000
```

- OS: `Linux 7.0.5-arch1-1 x86_64 GNU/Linux`
- CPU: `AMD Ryzen 7 7840HS with Radeon 780M Graphics`
- CPU cores / threads: `8 / 16`
- RAM: `27 GiB`
- Broker runtime: `FastAPI + Uvicorn`
- Parametry benchmarku:
  - `publishers = 5`
  - `subscribers = 5`
  - `messages_per_publisher = 10000`
  - `total_published_messages = 50000`
  - `expected_total_deliveries = 250000`

## Namerene vysledky

| Format | Total deliveries | Elapsed | Throughput |
| --- | ---: | ---: | ---: |
| JSON | 250000 | 6.148 s | 40660.83 msg/s |
| MessagePack | 250000 | 6.285 s | 39778.23 msg/s |

## Zhodnoceni

- V tomto konkretnim Python/FastAPI/WebSocket setupu vysel `JSON` mirne rychleji nez `MessagePack`.
- Rozdil je maly a pravdepodobne souvisi s Python overheadem a s tim, ze benchmark pouziva relativne maly payload.
- `MessagePack` se i tak porad vyplati drzet pro interni cloud komunikaci tam, kde je potreba:
  - binarni payload
  - mensi velikost zprav
  - lepsi kompatibilita pro budouci `storage.write` zpravy s raw bytes
- Pro finalni Haystack architekturu je `MessagePack` stale vhodnejsi volba pro `S3 Gateway <-> Broker <-> Haystack Node`, i kdyz cisty throughput v tomto lokalnim benchmarku nevysel vyssi.

## Poznamka k interpretaci

Broker meri propustnost v `msg/s` nad poctem dorucenych zprav subscriberum, ne jen nad poctem odeslanych publish eventu.
