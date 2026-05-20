# AI report

## Použité AI nástroje

- Codex / GPT-5 jako párový programátor pro návrh Alembicu, relací a úprav FastAPI aplikace.

## Příklady promptů

- "Zaveď Alembic do existující FastAPI + SQLAlchemy aplikace se SQLite databází."
- "Navrhni tři samostatné migrace: buckets, billing, soft delete."
- "Jak bezpečně backfillnout existující objekty do nového bucket schématu bez ztráty dat?"

## Co AI vygenerovala správně

- základní Alembic scaffolding a napojení `target_metadata = Base.metadata`
- návrh modelu `Bucket` a vazby `StoredFile.bucket_id`
- rozšíření Pydantic modelů pro buckety, billing a soft delete
- zachování legacy `/files` endpointů vedle nových bucket/object endpointů

## Co bylo nutné opravit nebo doladit

- u SQLite bylo potřeba zapnout `render_as_batch=True`, jinak by alter operace na existujících tabulkách nebyly spolehlivé
- první návrh migrace musel být doplněn o backfill existujících objektů do výchozích bucketů podle `user_id`
- bylo potřeba vyřešit, že aplikace už nesmí spoléhat na `Base.metadata.create_all()` a schema musí vznikat přes `alembic upgrade head`
- bylo potřeba ujasnit billing semantiku: `bandwidth_bytes` je kumulativní přenos, zatímco `current_storage_bytes` reprezentuje data at rest

## Jaké chyby nebo slabiny AI udělala

- AI měla tendenci navrhovat jen finální schéma bez rozdělení do tří po sobě jdoucích migrací, což neodpovídalo zadání
- bez explicitního upozornění AI snadno navrhuje hard delete i při zavedení `is_deleted`, takže bylo nutné ručně pohlídat soft delete flow
- AI sama neřešila, jak naložit s existujícími daty při přidání non-null `bucket_id`; to bylo nutné doplnit backfill logikou
- u Alembic konfigurace bylo potřeba ručně ověřit importy a cestu k databázi, aby autogenerace a upgrade fungovaly z kořene repozitáře
