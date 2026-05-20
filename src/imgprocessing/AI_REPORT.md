# AI Report

## Pouzite AI nastroje

- GPT-5 / Codex jako pomoc pri navrhu async workeru a NumPy operaci nad obrazem.

## Co AI pomohla navrhnout

- oddeleni image operaci do `operations.py`
- broker worker loop pro topic `image.jobs`
- upload vysledku zpet pres S3 Gateway jako novy objekt
- osetreni neplatne operace pres `image.done` se stavem `failed`

## Co bylo potreba doladit

- drzet vsechny graficke upravy v NumPy a nepouzit Pillow filtry
- nenechat S3 Gateway cekat na vysledek zpracovani
- posilat worker vysledek jako novy objekt, ne prepisovat puvodni metadata
