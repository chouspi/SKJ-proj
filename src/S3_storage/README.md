# S3 Storage

## Cíl

Cílem této části je navrhnout a implementovat základní verzi object storage služby inspirované cloudovými úložišti, například Amazon S3.

Výsledkem má být backendová služba, která umožní:

- nahrávání souborů
- ukládání souborů na disk
- správu metadat
- stažení souborů
- smazání souborů

## Kontext projektu

Tato služba bude součástí větší mini cloud platformy a bude sloužit jako:

- obecné cloudové úložiště pro uživatele
- úložiště vstupů pro výpočetní úlohy (jobs)
- úložiště výstupů

## Poznámka k realizaci

Při implementaci budeme s tímto zadáním pracovat jako se základním rozsahem funkcionality pro modul `S3_storage`.

## Použité technologie

Použijeme zejména následující technologie:

- FastAPI
- SQLAlchemy
- python-multipart
- aiofiles

Je možné použít i další podpůrné knihovny podle potřeb implementace.
