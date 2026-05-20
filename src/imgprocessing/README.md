# Image Processing Worker

Samostatny async worker v `src/imgprocessing`, ktery posloucha broker topic `image.jobs`, stahuje puvodni objekt pres S3 Gateway, upravi obraz pres NumPy a vysledek nahraje zpet jako novy objekt.

## Operace

- `negative`
- `mirror`
- `crop` s parametry `x`, `y`, `width`, `height`
- `brightness` s parametrem `amount`
- `grayscale`

## Spusteni

```bash
pip install -r src/imgprocessing/requirements.txt
python -m src.imgprocessing.worker
```

## Konfigurace

- `IMG_BROKER_URL` default `ws://127.0.0.1:8001/broker`
- `IMG_GATEWAY_BASE_URL` default `http://127.0.0.1:8000`
- `IMG_JOBS_TOPIC` default `image.jobs`
- `IMG_DONE_TOPIC` default `image.done`

## Gateway endpoint

```text
POST /buckets/{bucket_id}/objects/{object_id}/process
```

Priklad body:

```json
{
  "operation": "grayscale",
  "params": {}
}
```

Gateway neceka na vysledek. Pouze publikuje job do `image.jobs` a vraci `processing_started`.

## Testy

```bash
pytest src/imgprocessing/tests -q
```

End-to-end smoke test byl overen proti bezicim sluzbam: broker, Haystack, S3 Gateway a image worker.
