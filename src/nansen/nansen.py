import asyncio
from typing import Optional

import httpx
import loguru
import regex
from bs4 import BeautifulSoup
from capmonster_python import RecaptchaV2Task

from nansen.config import CAPMONSTER_API_KEY
from nansen.const import HEADERS, Account
from nansen.email import EmailClient
from nansen.logger import Logger

URL_REGEX = regex.compile(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+")
REF_URL_REGEX = regex.compile(r"https://nansen\.ai/early-access/\?ref=[a-zA-Z0-9]+")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
}


class AsyncContextManager:
    """
    An async context manager that allows for easy management of asynchronous resources.
    """

    async def __aenter__(self) -> "AsyncContextManager":
        for _, value in self.__dict__.items():
            if hasattr(value, "__aenter__"):
                await value.__aenter__()
        return self

    async def __aexit__(self, *args) -> None:
        for _, value in self.__dict__.items():
            if hasattr(value, "__aexit__"):
                await value.__aexit__(*args)

    async def init(self) -> "AsyncContextManager":
        return await self.__aenter__()

    async def close(self) -> None:
        await self.__aexit__(None, None, None)


class Nansen(AsyncContextManager):
    def __init__(
            self,
            logger: loguru.logger,
            account: Account,
    ) -> None:
        super().__init__()
        self.__account = account
        self.__captcha_api_key = CAPMONSTER_API_KEY
        self.__ref_code = self.__account.ref_code

        self.__csrf_token: Optional[str] = None
        self.__own_ref_url: Optional[str] = None

        self._logger = Logger(logger, self.__account.email_username)
        self.__client = httpx.AsyncClient(
            timeout=30,
            headers=HEADERS,
            follow_redirects=True,
            proxies={"all://": self.__account.proxy} if self.__account.proxy else None,
        )
        self.__email_client = EmailClient(
            self.__account.email_host,
            self.__account.email_username,
            self.__account.email_password
        )

    @property
    def own_ref_code(self) -> str:
        return httpx.URL(self.__own_ref_url).params["ref"] if self.__own_ref_url else ""

    @property
    def logger(self) -> Logger:
        return self._logger

    async def _solve_captcha(self) -> str:
        capmonster = RecaptchaV2Task(self.__captcha_api_key)

        task_id = capmonster.create_task(
            "https://www.nansen.ai/early-access",
            "6LcnRGwnAAAAAH-fdJFy0hD3e4GeYxWkMcbkCwi2"
        )
        self._logger.info(f"Task ID: {task_id}")

        result = await capmonster.join_task_result_async(task_id)

        return result.get("gRecaptchaResponse")

    async def _send_confirmation(self) -> None:
        self._logger.info("Sending confirmation email...")

        response = await self.__client.get(
            "https://www.nansen.ai/early-access",
            params={"ref": self.__ref_code} if self.__ref_code else None
        )
        response.raise_for_status()

        self._logger.log_response(response)

        soup = BeautifulSoup(response.text, "html.parser")
        captcha_settings = soup.select("input[name='captcha_settings']")[0].get("value")

        response = await self.__client.post(
            "https://getlaunchlist.com/s/yeywGr",
            params={
                "ref": self.__ref_code,
            } if self.__ref_code else None,
            headers={
                "Origin": "https://www.nansen.ai",
                "Referer": "https://www.nansen.ai/",
            },
            data={
                "_gotcha": "",
                "email": self.__email_client.username,
                "captcha_settings": captcha_settings,
                "g-recaptcha-response": await self._solve_captcha(),
                "submit": "Join Waitlist",
            },
        )
        response.raise_for_status()
        self._logger.log_response(response)

        soup = BeautifulSoup(response.text, "html.parser")
        self.__csrf_token = soup.select("meta[name='csrf-token']")[0].get("content")

        self._logger.debug(f"Set CSRF token to {self.__csrf_token}")

    async def _resend_confirmation_email(self) -> None:
        self._logger.info("Resending confirmation email...")

        if not self.__csrf_token:
            raise Exception("CSRF token not found")

        response = await self.__client.post(
            url=f"https://getlaunchlist.com/s/verify/send/{self.__email_client.username}",
            headers={
                "Origin": "https://getlaunchlist.com",
                "Referer": f"https://getlaunchlist.com/s/yeywGr/{self.__email_client.username}",
            },
            json={
                "email": self.__email_client.username,
                "csrf_token": self.__csrf_token,
            },
        )
        response.raise_for_status()
        self._logger.log_response(response)

        if not response.json().get("ok"):
            raise Exception("Failed to resend confirmation email")

    async def _confirm(self) -> None:
        self._logger.info("Confirming email...")

        timeout = 60
        while timeout > 0:
            message = await self.__email_client.fetch_message_by_uid()

            if not message:
                self._logger.debug("Waiting for confirmation email...")
                await asyncio.sleep(5)
                timeout -= 5
                continue

            if not message.subject == "Verify Email Address - Nansen 2 Early Access Waitlist Program":
                self._logger.debug("Waiting for confirmation email...")
                await asyncio.sleep(5)
                timeout -= 5
                continue

            url = URL_REGEX.search(message.body[0].content).group(0)
            response = await self.__client.get(url)
            response.raise_for_status()
            self._logger.log_response(response)

            match = REF_URL_REGEX.search(response.text)
            self.__own_ref_url = match.group(0) if match else None
            self._logger.debug(f"Set own ref URL to {self.__own_ref_url}")

            return

        await self._resend_confirmation_email()
        await self._confirm()

    async def register(self) -> None:
        await self._send_confirmation()

        await self._confirm()

        self._logger.info("Registered!")
