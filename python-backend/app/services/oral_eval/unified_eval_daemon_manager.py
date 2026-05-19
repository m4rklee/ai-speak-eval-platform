"""启动 / 停止 MultiPA、APG-MOS 常驻评测子进程。"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import time
from typing import Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_multipa_proc: Optional[subprocess.Popen] = None
_apg_proc: Optional[subprocess.Popen] = None
_started_by_us: bool = False

MULTIPA_LOG = "/tmp/ai-eval-multipa.log"
APG_LOG = "/tmp/ai-eval-apg.log"


def _daemon_env() -> dict[str, str]:
    settings = get_settings()
    env = os.environ.copy()
    env["MULTIPA_DIR"] = settings.MULTIPA_DIR
    env["APG_MOS_DIR"] = settings.APG_MOS_DIR
    env["MULTIPA_DAEMON_PORT"] = str(settings.MULTIPA_DAEMON_PORT)
    env["APG_DAEMON_PORT"] = str(settings.APG_DAEMON_PORT)
    return env


def _multipa_daemon_script() -> str:
    return os.path.join(get_settings().UNIFIED_EVAL_DIR, "multipa_daemon.py")


def _apg_daemon_script() -> str:
    return os.path.join(get_settings().UNIFIED_EVAL_DIR, "apg_daemon.py")


async def _wait_health(url: str, timeout_sec: float) -> bool:
    deadline = time.monotonic() + timeout_sec
    async with httpx.AsyncClient() as client:
        while time.monotonic() < deadline:
            try:
                resp = await client.get(url, timeout=5.0)
                if resp.status_code == 200 and resp.json().get("ready"):
                    return True
            except Exception:
                pass
            await asyncio.sleep(2.0)
    return False


async def _probe_daemons_ready() -> bool:
    """通过 HTTP 探测端口上的 daemon 是否就绪（不依赖本进程 Popen 句柄）。"""
    settings = get_settings()
    try:
        async with httpx.AsyncClient() as client:
            m = await client.get(
                f"http://127.0.0.1:{settings.MULTIPA_DAEMON_PORT}/health",
                timeout=3.0,
            )
            a = await client.get(
                f"http://127.0.0.1:{settings.APG_DAEMON_PORT}/health",
                timeout=3.0,
            )
            return (
                m.status_code == 200
                and m.json().get("ready")
                and a.status_code == 200
                and a.json().get("ready")
            )
    except Exception:
        return False


async def start_daemons() -> tuple[bool, str]:
    """启动两个常驻子进程并等待模型加载完成。"""
    global _multipa_proc, _apg_proc, _started_by_us
    settings = get_settings()

    if await _probe_daemons_ready():
        logger.info("Unified eval daemons already reachable on configured ports")
        return True, "already reachable"

    multipa_script = _multipa_daemon_script()
    apg_script = _apg_daemon_script()
    if not os.path.isfile(multipa_script) or not os.path.isfile(apg_script):
        return False, "daemon 脚本不存在"

    if daemons_running():
        return True, "already running"

    env = _daemon_env()
    try:
        multipa_log = open(MULTIPA_LOG, "a", encoding="utf-8")
        apg_log = open(APG_LOG, "a", encoding="utf-8")
        _multipa_proc = subprocess.Popen(
            [settings.multipa_python_path, multipa_script],
            env=env,
            stdout=multipa_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        _apg_proc = subprocess.Popen(
            [sys.executable, apg_script],
            env=env,
            stdout=apg_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        _started_by_us = True
    except Exception as e:
        await stop_daemons()
        return False, str(e)

    warmup = float(settings.UNIFIED_EVAL_DAEMON_WARMUP_SEC)
    multipa_ok, apg_ok = await asyncio.gather(
        _wait_health(
            f"http://127.0.0.1:{settings.MULTIPA_DAEMON_PORT}/health",
            warmup,
        ),
        _wait_health(
            f"http://127.0.0.1:{settings.APG_DAEMON_PORT}/health",
            warmup,
        ),
    )

    if not multipa_ok or not apg_ok:
        await stop_daemons()
        return False, f"daemon 预热超时 (multipa={multipa_ok}, apg={apg_ok})"

    logger.info("Unified eval daemons ready (multipa + apg_mos)")
    return True, "ok"


async def stop_daemons() -> None:
    global _multipa_proc, _apg_proc, _started_by_us
    if not _started_by_us:
        logger.info("Skip stopping eval daemons (not started by this process)")
        return
    for proc, name in ((_multipa_proc, "multipa"), (_apg_proc, "apg")):
        if proc is None:
            continue
        try:
            proc.terminate()
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        except Exception as e:
            logger.warning("Stop %s daemon: %s", name, e)
    _multipa_proc = None
    _apg_proc = None
    _started_by_us = False


def daemons_running() -> bool:
    return (
        _multipa_proc is not None
        and _multipa_proc.poll() is None
        and _apg_proc is not None
        and _apg_proc.poll() is None
    )


async def daemons_healthy() -> bool:
    return await _probe_daemons_ready()
