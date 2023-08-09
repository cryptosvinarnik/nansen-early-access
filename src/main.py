import asyncio
import random

from loguru import logger

from nansen.const import Account
from nansen.nansen import Nansen
from nansen.config import SLEEP_RANGE


async def worker(
    q: asyncio.Queue,
) -> None:
    while not q.empty():
        account: Account = await q.get()

        try:
            client = await Nansen(logger=logger, account=account).init()

            await client.register()

            await client.close()
        except Exception as e:
            logger.error(f"[{account.email_username}] {e}")
        finally:
            sleep_time = random.randint(*SLEEP_RANGE)
            logger.info(f"[{account.email_username}] Sleeping for {sleep_time} seconds")
            await asyncio.sleep(sleep_time)


async def main() -> None:
    q = asyncio.Queue()

    with open("accounts.txt", "r") as file:
        accounts = file.read().splitlines()

    form_accounts = []
    for account in accounts:
        account = account.split(":", maxsplit=4)

        form_accounts.append(
            Account(account[0], account[1], account[2], account[3], account[4])
        )

    for account in form_accounts:
        await q.put(account)

    await asyncio.gather(
        *[asyncio.create_task(worker(q)) for _ in range(3)]
    )


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        logger.error(e)
