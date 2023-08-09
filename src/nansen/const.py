import typing
from dataclasses import dataclass


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://www.nansen.ai",
    "Connection": "keep-alive",
    "Referer": "https://www.nansen.ai/",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-User": "?1",
}


@dataclass
class Account:
    email_username: str
    email_password: str
    email_host: str
    ref_code: typing.Optional[str] = None
    proxy: typing.Optional[str] = None
    own_ref_code: typing.Optional[str] = None
