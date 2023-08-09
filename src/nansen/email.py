import asyncio
import email
import email.message
import io
import quopri

import aioimaplib
import regex

UID_PATTERN = regex.compile(r"(^|\s+|\W)UID\s+(?P<uid>\d+)")


class EmailBody:
    def __init__(self, message: email.message.Message):
        self.__message = message

    def __iter__(self) -> iter:
        return self.__message.walk()

    def __str__(self) -> str:
        message_bytes_io = io.BytesIO(self.__message.as_string().encode())
        decoded_bytes_io = io.BytesIO()
        quopri.decode(message_bytes_io, decoded_bytes_io)
        return decoded_bytes_io.getvalue().decode(encoding="utf-8", errors="ignore")

    @property
    def content(self) -> str:
        return self.__str__()

    @property
    def content_type(self) -> str:
        return self.__message.get_content_type()


class EmailMessage(email.message.Message):
    def __init__(self, msg: email.message.Message, uid: int = None):
        super().__init__()
        self.__uid = uid

        for key, value in msg.items():
            self[key] = value

        # If the input message has a payload (body), add it to the current message
        if msg.is_multipart():
            for part in msg.get_payload():
                self.attach(part)
        else:
            self.set_payload(msg.get_payload())

    @property
    def body(self) -> list[EmailBody]:
        return [EmailBody(msg) for msg in self.get_payload()]

    @property
    def subject(self) -> str:
        return self["Subject"]

    @property
    def from_address(self) -> str:
        return self["From"]

    @property
    def to(self) -> str:
        return self["To"]

    @property
    def date(self) -> str:
        return self["Date"]

    @property
    def sender(self) -> str:
        return self["Sender"]

    @property
    def uid(self) -> int | None:
        return self.__uid


class EmailClient:
    def __init__(self, host: str, username: str, password: str, mailbox: str = "INBOX"):
        self.__host = host
        self.__username = username
        self.__password = password

        self.__mailbox = mailbox

    async def __aenter__(self) -> "EmailClient":
        self.__client = aioimaplib.IMAP4_SSL(self.__host)

        await self.__client.wait_hello_from_server()

        await self.__client.login(self.__username, self.__password)
        await self.__client.select(self.__mailbox)

        return self

    async def __aexit__(self, *_):
        await self.__client.logout()

    async def init(self) -> "EmailClient":
        return await self.__aenter__()

    async def close(self):
        await self.__aexit__(None, None, None)

    @property
    def mailbox(self) -> str:
        return self.__mailbox

    @property
    def host(self) -> str:
        return self.__host

    @property
    def username(self) -> str:
        return self.__username

    @property
    def password(self) -> str:
        return self.__password

    @staticmethod
    def __extract_uid(raw_response: str) -> str | None:
        match = UID_PATTERN.search(raw_response)
        return match.group("uid") if match else None

    @staticmethod
    def __check_response(response: aioimaplib.aioimaplib.Response):
        if response.result != "OK":
            raise Exception(f"Error: {response.lines}")

    async def fetch_message_by_uid(self, uid: int = None) -> EmailMessage | None:
        raw_response = await self.__client.uid("fetch", "*", "(UID BODY.PEEK[])")
        self.__check_response(raw_response)

        if raw_response.lines.__len__() < 2:
            return None

        raw_uid, raw_message, *_ = raw_response.lines

        uid = int(self.__extract_uid(raw_uid.decode("utf-8")))
        message = email.message_from_bytes(raw_message)

        return EmailMessage(message, uid)

    async def wait_for_new_message(self, timeout: int = 180, cooldown: int = 5) -> EmailMessage | None:
        current_uid = (await self.fetch_message_by_uid()).uid

        while True:
            response = await self.fetch_message_by_uid()

            if response.uid != current_uid:
                return response

            await asyncio.sleep(cooldown)

            timeout -= cooldown

            if timeout <= 0:
                return None
