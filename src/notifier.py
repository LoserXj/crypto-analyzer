"""通知系统 — macOS / Server酱 / PushPlus"""
import json
import subprocess
from urllib.request import urlopen, Request
from urllib.parse import urlencode


def notify_macos(msg: str):
    """macOS 系统通知"""
    try:
        subprocess.run([
            "osascript", "-e",
            f'display notification "{msg}" with title "Crypto Alert"'
        ], timeout=5, capture_output=True)
    except Exception:
        pass


def notify_serverchan(title: str, content: str, token: str) -> bool:
    """Server酱推送到微信"""
    url = f"https://sctapi.ftqq.com/{token}.send"
    data = urlencode({"title": title, "desp": content}).encode()
    req = Request(url, data=data)
    try:
        with urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            return result.get("code") == 0
    except Exception as e:
        print(f"   [微信推送失败] {e}")
        return False


def notify_pushplus(title: str, content: str, token: str) -> bool:
    """PushPlus 推送到微信"""
    url = "https://www.pushplus.plus/send"
    payload = json.dumps({
        "token": token,
        "title": title,
        "content": content,
        "template": "markdown",
    }).encode()
    req = Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            return result.get("code") == 200
    except Exception as e:
        print(f"   [PushPlus推送失败] {e}")
        return False


def send_notification(title: str, content: str, config: dict):
    """根据配置发送通知"""
    notify_cfg = config.get("notify", {})

    # macOS
    if notify_cfg.get("macos", False):
        notify_macos(title)

    # 微信
    wechat_cfg = notify_cfg.get("wechat", {})
    if wechat_cfg.get("enabled", False):
        token = wechat_cfg.get("token", "")
        if not token:
            print("   [警告] 微信推送已启用但未配置 token")
            return
        method = wechat_cfg.get("method", "serverchan")
        if method == "serverchan":
            ok = notify_serverchan(title, content, token)
        elif method == "pushplus":
            ok = notify_pushplus(title, content, token)
        else:
            print(f"   [警告] 未知微信推送方式: {method}")
            return
        if ok:
            print("   [微信推送成功]")
