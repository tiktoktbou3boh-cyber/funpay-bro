import json
import re
import requests
from bs4 import BeautifulSoup

BASE = "https://funpay.com"


class FunPay:
    def __init__(self, golden_key):
        self.s = requests.Session()
        self.s.cookies.set("golden_key", golden_key, domain="funpay.com")
        self.s.headers["User-Agent"] = (
            "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120 Mobile Safari/537.36"
        )
        self.csrf = None
        self.user_id = None
        self.username = None

    def login(self):
        r = self.s.get(BASE + "/", timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        body = soup.find("body")
        raw = body.get("data-app-data") if body else None
        if not raw:
            raise RuntimeError("Не удалось войти: проверь golden_key.")
        data = json.loads(raw)
        self.csrf = data.get("csrf-token") or data.get("csrf_token")
        self.user_id = data.get("userId")
        if not self.user_id:
            raise RuntimeError("Аккаунт не авторизован: golden_key неверный или устарел.")
        link = soup.select_one(".user-link-name")
        self.username = link.text.strip() if link else str(self.user_id)

    def _get(self, path):
        r = self.s.get(BASE + path, timeout=20)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")

    def _post(self, path, data):
        data = {**data, "csrf_token": self.csrf}
        r = self.s.post(
            BASE + path,
            data=data,
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=20,
        )
        return r

    # ---------- заказы ----------
    def get_orders(self):
        """Возвращает {order_id: (покупатель, описание, статус)}."""
        soup = self._get("/orders/trade")
        result = {}
        for a in soup.select("a.tc-item"):
            oid = a.select_one(".tc-order")
            if not oid:
                continue
            oid = oid.text.strip().lstrip("#")
            desc = a.select_one(".order-desc div")
            buyer = a.select_one(".media-user-name")
            status = a.select_one(".tc-status")
            result[oid] = (
                buyer.text.strip() if buyer else "?",
                desc.text.strip() if desc else "",
                status.text.strip() if status else "",
            )
        return result

    # ---------- сообщения ----------
    def get_unread_chats(self):
        """Возвращает список (node_id, имя, последнее сообщение)."""
        soup = self._get("/chat/")
        chats = []
        for a in soup.select("a.contact-item.unread"):
            chats.append((
                a.get("data-id"),
                (a.select_one(".media-user-name") or a).text.strip(),
                (a.select_one(".contact-item-message") or a).text.strip(),
            ))
        return chats

    def send_message(self, node_id, text):
        objs = [{"type": "chat_node", "id": node_id,
                 "tag": "00000000", "data": {"node": node_id, "last_message": -1, "content": ""}}]
        req = {"action": "chat_message",
               "data": {"node": node_id, "last_message": -1, "content": text}}
        r = self._post("/runner/", {
            "objects": json.dumps(objs),
            "request": json.dumps(req),
        })
        return r.ok

    # ---------- поднятие лотов ----------
    def get_my_categories(self):
        soup = self._get(f"/users/{self.user_id}/")
        nodes = set()
        for a in soup.select(".offer-list-title a"):
            m = re.search(r"/lots/(\d+)/", a.get("href", ""))
            if m:
                nodes.add(m.group(1))
        return sorted(nodes)

    def raise_category(self, node_id):
        soup = self._get(f"/lots/{node_id}/trade")
        btn = soup.select_one(".js-lot-raise")
        game_id = btn.get("data-game") if btn else None
        if not game_id:
            return False, "кнопка поднятия не найдена"
        r = self._post("/lots/raise", {"game_id": game_id, "node_id": node_id})
        try:
            j = r.json()
        except ValueError:
            return False, "неожиданный ответ"
        msg = j.get("msg") or j.get("error") or ""
        ok = not j.get("error")
        return ok, re.sub(r"<[^>]+>", " ", str(msg)).strip()
