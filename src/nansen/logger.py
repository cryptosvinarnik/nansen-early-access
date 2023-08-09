from typing import Any

import httpx
import loguru

class Logger:
    def __init__(self, logger: loguru.logger, email: str):
        self.__logger = logger
        self.__email = email

    def log_response(self, response: httpx.Response):
        self.debug(f"Method: {response.request.method}, Url: {response.request.url}, Response: {response}")

    def info(self, __message: str, *args: Any, **kwargs: Any) -> None:
        self.__logger.info(f"[{self.__email}] {__message}", *args, **kwargs)

    def debug(self, __message: str, *args: Any, **kwargs: Any) -> None:
        self.__logger.debug(f"[{self.__email}] {__message}", *args, **kwargs)

    def error(self, __message: str, *args: Any, **kwargs: Any) -> None:
        self.__logger.error(f"[{self.__email}] {__message}", *args, **kwargs)

    def warning(self, __message: str, *args: Any, **kwargs: Any) -> None:
        self.__logger.warning(f"[{self.__email}] {__message}", *args, **kwargs)
