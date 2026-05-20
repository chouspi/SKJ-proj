# AI Report

## Pouzite AI nastroje

- GPT-5 / Codex jako asistence pri navrhu WebSocket brokeru, ConnectionManageru a integracnich testu.

## Příklady promptu

- "Navrhni jednoduchy FastAPI WebSocket pub/sub broker se spravou topicu."
- "Jak udelat ConnectionManager pro vice topicu a vice klientu bez padu pri disconnectu?"
- "Jak otestovat WebSocket tok ve FastAPI pres pytest a TestClient?"

## Co AI pomohla navrhnout spravne

- oddeleni serializace zprav od ConnectionManageru
- in-memory mapovani `topic -> subscribers`
- podporu soucasnych JSON a MessagePack klientu
- jednotny protokol `subscribe/publish/deliver`

## Co bylo potreba doladit rucne

- zjednodusit scope podle finalniho Kelvin zadani a neimplementovat durable queues s DB
- osetrit odpojovani klientu tak, aby spadly jen jejich subscription state a ne cely broker
- navrhnout test scenar pro overeni, ze zprava pro jiny topic subscriberovi nedorazi

## Jake chyby nebo slepe ulicky AI navrhovala

- puvodne navrhovala i perzistentni DB vrstvu pro broker, coz patri do starsiho zadani s durable queues, ne do finalni jednodussi architektury
- bylo nutne rucne udrzet broker jako samostatnou aplikaci v `src/messagebroker`, ne soucast `src/S3_Storage`
- u WebSocket testu AI snadno sklouzava k blokujicim scenarum bez timeout strategie, takze bylo potreba zvolit deterministictejsi poradi publish eventu v testech
