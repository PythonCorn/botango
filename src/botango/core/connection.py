import asyncio
import hmac
import logging
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import List

from aiogram import Bot, Dispatcher, Router, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.loggers import event
from aiogram.types import Update
from aiohttp import web, ClientSession, ClientTimeout
from aiohttp.web_response import Response

logger = logging.getLogger(__name__)

class _BaseConnect:
    def __init__(
            self,
            token: str,
            parse_mode: str = "html",
            allowed_updates: List[str] = None,
            is_logger: bool = True
    ):
        self._bot = Bot(token=token, default=DefaultBotProperties(parse_mode=parse_mode.upper()))
        self._dispatcher = Dispatcher()
        self._allowed_updates = allowed_updates
        if is_logger:
            event.setLevel(logging.INFO)
            handler = logging.StreamHandler(sys.stdout)
            event.addHandler(handler)


class LongPolling(_BaseConnect):

    @property
    def dispatcher(self) -> Dispatcher:
        return self._dispatcher

    @property
    def bot(self) -> Bot:
        return self._bot

    def include_router(self, router: Router):
        self.dispatcher.include_router(router)

    def include_routers(self, *routers: Router):
        self.dispatcher.include_routers(*routers)

    def add_middleware(self, middleware: BaseMiddleware, *events: str):
        if events:
            for e in events:
                type_event = getattr(self.dispatcher, e)
                if type_event:
                    type_event.middleware(middleware)

    async def _run(self, drop_pending_updates: bool = True):
        if drop_pending_updates:
            await self._bot.delete_webhook(drop_pending_updates=True)
        await self.dispatcher.start_polling(self.bot, allowed_updates=self._allowed_updates)

    def run_polling(self, drop_pending_updates: bool = True):
        asyncio.run(self._run(drop_pending_updates))



class WebhookBot(_BaseConnect):
    def __init__(
        self,
        token: str,
        base_url: str | None,
        webhook_secret: str,
        webhook_path: str = "/telegram/webhook",
        *,
        allowed_updates: list[str] | None = None
    ):
        super().__init__(token=token, allowed_updates=allowed_updates)

        self.app = web.Application(client_max_size=1024*1024)

        self._webhook_secret = webhook_secret
        self._webhook_path = webhook_path if webhook_path.startswith("/") else f"/{webhook_path}"
        self._base_url = base_url  # может быть None — тогда возьмём из ngrok
        self._webhook_url = None  # вычислим на старте
        self._drop_pending_updates: bool = True


    async def _resolve_public_base_url(self) -> str:
        if not self._base_url:
            raise AttributeError("Base url can't be empty!")
        return self._base_url.rstrip("/")

    async def _handle(self, request: web.Request) -> Response:
        header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if not header_secret or not hmac.compare_digest(header_secret, self._webhook_secret):
            return web.Response(status=403)
        try:
            data = await request.json()
        except Exception as e:
            event.exception("Invalid JSON on webhook: %s", e)
            return web.json_response({"ok": False, "error": "invalid json"}, status=200)

        try:
            update = Update.model_validate(data, context={"bot": self._bot})
            await self._dispatcher.feed_update(self._bot, update)
        except Exception:
            event.exception("Update handling failed")
            return web.json_response({"ok": True})
        return web.json_response({"ok": True})

    async def _on_startup(self, app: web.Application):
        self.app["http_session"] = ClientSession(timeout=ClientTimeout(total=10))
        base = await self._resolve_public_base_url()
        self._webhook_url = f"{base}{self._webhook_path}"

        if self._allowed_updates is None or not isinstance(self._allowed_updates, list):
            self._allowed_updates = ["message", "callback_query"]

        await self._bot.set_webhook(
            url=self._webhook_url,
            secret_token=self._webhook_secret,
            allowed_updates=self._allowed_updates,
            drop_pending_updates=self._drop_pending_updates,
        )
        # хук жизненного цикла aiogram v3
        try:
            await self._dispatcher.emit_startup(self._bot)
        except AttributeError:
            pass

    async def _on_cleanup(self, app: web.Application):
        try:
            await self._dispatcher.emit_shutdown()
        except AttributeError:
            pass
        await self._bot.delete_webhook()
        await self.app["http_session"].close()

    def run_polling(self, host: str = "0.0.0.0", port: int = 8000, drop_pending_updates: bool = True):
        self._drop_pending_updates = drop_pending_updates
        self.app.router.add_post(self._webhook_path, self._handle)

        async def _health(_):
            return web.json_response({
                "status": "ok",
                "webhook_url": self._webhook_url,
            })

        self.app.router.add_get("/healthz", _health)
        self.app.on_startup.append(self._on_startup) # type: ignore
        self.app.on_cleanup.append(self._on_cleanup) # type: ignore
        web.run_app(self.app, host=host, port=port)


class NgrokManager:
    """
    Менеджер ngrok с установкой через APT:
    - install() — добавляет key+repo и ставит пакет ngrok
    - start(port) — запуск в фоне
    - wait_for_https_tunnel() — ждёт https URL из :4040
    - stop() — корректное завершение процесса
    """
    APT_KEY_URL = "https://ngrok-agent.s3.amazonaws.com/ngrok.asc"
    APT_LIST_PATH = "/etc/apt/sources.list.d/ngrok.list"
    APT_KEY_DST = "/etc/apt/trusted.gpg.d/ngrok.asc"

    def __init__(self, api_url: str = "http://127.0.0.1:4040/api/tunnels"):
        self.api_url = api_url
        self.proc: subprocess.Popen | None = None

    @staticmethod
    def _exists_in_path() -> bool:
        return shutil.which("ngrok") is not None

    @staticmethod
    def _detect_codename(default: str = "bookworm") -> str:
        """
        Пробуем вытащить VERSION_CODENAME из /etc/os-release.
        Возвращаем default, если не нашли.
        """
        try:
            with open("/etc/os-release", "r", encoding="utf-8") as f:
                data = f.read()
            for line in data.splitlines():
                if line.startswith("VERSION_CODENAME="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'") or default
        except Exception:
            pass
        return default

    @staticmethod
    def _run_shell(cmd: str, *, sudo_password: str | None = None):
        """
        Запуск shell-команды (для пайпов/redirect'ов). Если передан sudo_password,
        команда может содержать 'sudo -S ...' и пароль будет подан в stdin.
        """
        kwargs = dict(shell=True, check=True, text=True)
        if sudo_password is not None:
            return subprocess.run(cmd, input=sudo_password + "\n", **kwargs)
        return subprocess.run(cmd, **kwargs)

    def install(
        self,
        *,
        codename: str | None = None,
        assume_yes: bool = True,
        use_sudo: bool = True,
        sudo_password: str | None = None,
    ):
        """
        Установка через APT по новой инструкции.
        - codename: override для дистрибутива (например, 'bookworm', 'jammy').
        - assume_yes: добавляет -y к apt install.
        - use_sudo: если False — команды выполнятся без sudo (скрипт должен быть root).
        - sudo_password: опционально — будет подан в stdin для 'sudo -S ...'.
        """
        if self._exists_in_path():
            return

        cd = codename or self._detect_codename()

        # 1) импорт ключа
        # curl -sSL <key_url> | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
        cmd_key = (
            f"curl -sSL {self.APT_KEY_URL} | "
            f"{'sudo -S ' if use_sudo else ''}tee {self.APT_KEY_DST} >/dev/null"
        )
        self._run_shell(cmd_key, sudo_password=sudo_password if use_sudo else None)

        # 2) репозиторий
        # echo 'deb https://ngrok-agent.s3.amazonaws.com <codename> main' |
        #   sudo tee /etc/apt/sources.list.d/ngrok.list
        repo_line = f"deb https://ngrok-agent.s3.amazonaws.com {cd} main"
        cmd_repo = (
            f"echo '{repo_line}' | "
            f"{'sudo -S ' if use_sudo else ''}tee {self.APT_LIST_PATH}"
        )
        self._run_shell(cmd_repo, sudo_password=sudo_password if use_sudo else None)

        # 3) apt update && apt install ngrok
        # важно делать update перед install
        install_flag = "-y" if assume_yes else ""
        cmd_install = (
            f"{'sudo -S ' if use_sudo else ''}apt update && "
            f"{'sudo -S ' if use_sudo else ''}apt install {install_flag} ngrok"
        ).strip()
        self._run_shell(cmd_install, sudo_password=sudo_password if use_sudo else None)

        # после установки бинарь должен оказаться в PATH (/usr/bin/ngrok)
        if not self._exists_in_path():
            # на всякий: попробуем /usr/bin/ngrok
            if not Path("/usr/bin/ngrok").exists():
                raise RuntimeError("ngrok установлен, но не найден в PATH")

    @staticmethod
    def ensure_token(token: str):
        """Проставляет authtoken, если его ещё нет в конфиге."""
        cfg = Path.home() / ".config" / "ngrok" / "ngrok.yml"
        if not cfg.exists():
            subprocess.run(["ngrok", "config", "add-authtoken", token], check=True)

    def start(self, port: int = 8000, region: str | None = None, extra_args: list[str] | None = None):
        """Запускает ngrok http <port> в фоне (не блокирует)."""
        cmd = ["ngrok", "http", str(port)]
        if region:
            cmd += ["--region", region]
        if extra_args:
            cmd += extra_args
        self.proc = subprocess.Popen(cmd)

    async def wait_for_https_tunnel(self, timeout: float = 30.0) -> str:
        """Ожидает появления https-туннеля в API ngrok и возвращает public_url."""
        deadline = asyncio.get_event_loop().time() + timeout
        async with ClientSession() as s:
            while True:
                try:
                    async with s.get(self.api_url, timeout=3) as resp:
                        data = await resp.json()
                    for t in data.get("tunnels", []):
                        pub = t.get("public_url", "")
                        if pub.startswith("https://"):
                            return pub.rstrip("/")
                except Exception:
                    pass
                if asyncio.get_event_loop().time() > deadline:
                    raise TimeoutError("Не дождался https-туннеля от ngrok")
                await asyncio.sleep(0.5)

    def stop(self):
        """Корректно останавливает ngrok, если запущен нами."""
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.send_signal(signal.SIGINT)
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()
        self.proc = None

class NgrokWebhook(WebhookBot):
    """
    Обёртка над твоим WebhookBot: если base_url не задан,
    менеджер ngrok сам установит/запустит туннель и передаст URL.
    """

    def __init__(
            self,
            token: str,
            webhook_secret: str,
            ngrok_api: str = "http://127.0.0.1:4040/api/tunnels",
            ngrok_manager: NgrokManager | None = None,
            ngrok_token: str | None = None,
            ngrok_port: int = 8000,
            **kwargs
    ):
        kwargs.pop("base_url", None)
        super().__init__(token=token, base_url=None, webhook_secret=webhook_secret)
        self._ngrok_api = ngrok_api
        self._ngrok_mgr = ngrok_manager
        self._ngrok_token = ngrok_token
        self._ngrok_port = ngrok_port

    async def _resolve_public_base_url(self) -> str:
        # Если base_url передали — используем его (как у тебя)
        if self._base_url:
            return self._base_url.rstrip("/")

        # Если base_url нет — поднимаем ngrok и ждём https-URL
        if self._ngrok_mgr is None:
            self._ngrok_mgr = NgrokManager(api_url=self._ngrok_api)

        # Установка при необходимости
        self._ngrok_mgr.install()
        if self._ngrok_token:
            self._ngrok_mgr.ensure_token(self._ngrok_token)

        # Стартуем ngrok только если он ещё не отдаёт туннель (например, поднят руками)
        # Попробуем сначала быстро дернуть API; если пусто — стартуем
        try:
            return await self._ngrok_mgr.wait_for_https_tunnel(timeout=1.0)
        except Exception:
            pass

        self._ngrok_mgr.start(port=self._ngrok_port)
        return await self._ngrok_mgr.wait_for_https_tunnel(timeout=30.0)

    async def _on_cleanup(self, app: web.Application):
        # Сначала — твоя логика
        await super()._on_cleanup(app)
        # Затем выключаем ngrok, если поднимали здесь
        if self._ngrok_mgr:
            self._ngrok_mgr.stop()

