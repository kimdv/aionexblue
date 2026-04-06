# aionexblue

Async Python client for the NexBlue EV charger cloud API.

## Installation

```bash
pip install aionexblue
```

## Quick start

```python
import asyncio
import aiohttp
from aionexblue import NexBlueClient, login

async def main() -> None:
    async with aiohttp.ClientSession() as session:
        tokens = await login(session, "user@example.com", "password")
        client = NexBlueClient(session, tokens)

        chargers = await client.get_chargers()
        for charger in chargers:
            status = await client.get_charger_status(charger.serial_number)
            print(f"{charger.serial_number}: {status.charging_state.name} @ {status.power} kW")

asyncio.run(main())
```

## API reference

Interactive documentation is available at the
[NexBlue Swagger UI](https://prod-management.nexblue.com/swagger/dist/index.html).

## License

[MIT](LICENSE)
