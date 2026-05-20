# AI report

## Použité AI nástroje

- Codex / GPT-5 jako párový programátor pro návrh a úpravu FastAPI aplikace.

## Příklady promptů

- "Předělej ukládání metadat ze souboru JSON na SQLite přes SQLAlchemy."
- "Doplň Pydantic modely pro vstupy a výstupy endpointů."
- "Zachovej možnost spouštět aplikaci jak z `src/S3_Storage`, tak z kořene projektu."

## Co AI vygenerovala správně

- základní rozdělení do souborů `database.py`, `models.py`, `schemas.py`
- SQLAlchemy model pro metadata souborů
- Pydantic response modely pro upload, list a delete endpointy
- zachování stávající logiky pro ukládání binárních souborů na disk

## Co bylo nutné opravit nebo doladit

- importy mezi moduly tak, aby fungovalo spuštění `uvicorn main:app` i `uvicorn src.S3_Storage.main:app`
- zachování compatibility s dříve uloženými daty pomocí migrace z `files_metadata.json`
- ergonomii používání v browseru přes `user_id` query parametr

## Jaké chyby nebo slabiny AI udělala

- původní verze aplikace ještě nepoužívala SQLAlchemy, takže bylo nutné ji refaktorovat na databázovou vrstvu
- bez doplnění dokumentace by mohlo být nejasné, odkud aplikaci správně spouštět
- u endpointu pro stažení nelze vracet binární obsah přes Pydantic model, takže bylo potřeba ponechat `FileResponse`
