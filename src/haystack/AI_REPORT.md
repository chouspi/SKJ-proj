# AI Report

## Pouzite AI nastroje

- GPT-5 / Codex jako asistence pri navrhu append-only volume manageru a broker subscriber loopu.

## Priklady promptu

- "Navrhni jednoduchy append-only Haystack node s rotaci volume souboru."
- "Jak napojit FastAPI aplikaci na existujici WebSocket message broker na background task?"
- "Jak bezpecne serializovat bytes payload pres MessagePack mezi brokerem a storage nodem?"

## Co AI pomohla navrhnout spravne

- oddeleni `VolumeManager` a broker klienta do samostatnych modulu
- pouziti background tasku vytvoreneho pri startu aplikace
- append-only zapis s offset/size metadaty pro ACK
- jednoduchy read endpoint pres `seek(offset)` a `read(size)`

## Co bylo potreba doladit rucne

- drzet scope podle finalniho zadani a nepridavat zbytecnou DB vrstvu do Haystack nodu
- ujasnit, ze Haystack ma byt subscriber na `storage.write` a publisher na `storage.ack` pres stejne WebSocket spojeni
- navrhnout rotaci tak, aby se neoteviral novy volume zbytecne pri prazdnem souboru

## Jake chyby nebo slepe ulicky AI navrhovala

- AI mela tendenci navrhovat slozitejsi metadata a perzistenci mimo zadani
- bylo potreba rucne pohlidat, aby se HTTP endpoint nepropojoval primo s gateway logikou a zustal ciste storage-oriented
- bez explicitniho usmerneni AI snadno sklouzava k tomu, ze broker a haystack sdili vice logiky, nez je nutne pro finalni mikrosluzbovou architekturu
