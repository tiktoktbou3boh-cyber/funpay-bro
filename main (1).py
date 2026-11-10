import json
import os
import random
import threading
import time

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder

from api import FunPay

KV = """
BoxLayout:
    orientation: 'vertical'
    padding: dp(12)
    spacing: dp(8)
    Label:
        text: 'FunPay BRO'
        font_size: '22sp'
        size_hint_y: None
        height: dp(40)
    TextInput:
        id: key
        hint_text: 'golden_key'
        multiline: False
        password: True
        size_hint_y: None
        height: dp(44)
    BoxLayout:
        size_hint_y: None
        height: dp(40)
        Label:
            text: 'Автоподнятие лотов'
        Switch:
            id: sw_raise
            active: True
    BoxLayout:
        size_hint_y: None
        height: dp(40)
        Label:
            text: 'Автоответ'
        Switch:
            id: sw_reply
            active: False
    TextInput:
        id: reply_text
        text: 'Здравствуйте! Сейчас не на месте, отвечу как только смогу.'
        multiline: True
        size_hint_y: None
        height: dp(70)
    Button:
        id: btn
        text: 'Запустить'
        size_hint_y: None
        height: dp(52)
        on_release: app.toggle()
    ScrollView:
        Label:
            id: log
            text: ''
            size_hint_y: None
            height: self.texture_size[1]
            text_size: self.width, None
            valign: 'top'
"""

RAISE_EVERY = 245 * 60
POLL = 15


class FunPayApp(App):
    title = "FunPay BRO"

    def build(self):
        self.root_w = Builder.load_string(KV)
        self.stop_evt = threading.Event()
        self.thread = None
        self.lines = []
        self.load_cfg()
        return self.root_w

    def on_start(self):
        try:
            from android.permissions import request_permissions
            request_permissions(["android.permission.POST_NOTIFICATIONS"])
        except Exception:
            pass

    # ---------- настройки ----------
    @property
    def cfg_path(self):
        return os.path.join(self.user_data_dir, "config.json")

    def load_cfg(self):
        try:
            with open(self.cfg_path, encoding="utf-8") as f:
                c = json.load(f)
        except Exception:
            return
        ids = self.root_w.ids
        ids.key.text = c.get("golden_key", "")
        ids.sw_raise.active = c.get("raise", True)
        ids.sw_reply.active = c.get("reply", False)
        ids.reply_text.text = c.get("reply_text", ids.reply_text.text)

    def save_cfg(self):
        ids = self.root_w.ids
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            json.dump({
                "golden_key": ids.key.text.strip(),
                "raise": ids.sw_raise.active,
                "reply": ids.sw_reply.active,
                "reply_text": ids.reply_text.text,
            }, f, ensure_ascii=False)

    # ---------- лог и уведомления ----------
    def log(self, text, notify=False):
        stamp = time.strftime("%H:%M:%S")
        Clock.schedule_once(lambda dt: self._add_line(f"[{stamp}] {text}"))
        if notify:
            try:
                from plyer import notification
                notification.notify(title="FunPay", message=text[:200], timeout=10)
            except Exception:
                pass

    def _add_line(self, line):
        self.lines = (self.lines + [line])[-100:]
        self.root_w.ids.log.text = "\n".join(reversed(self.lines))

    # ---------- запуск и остановка ----------
    def toggle(self):
        ids = self.root_w.ids
        if self.thread and self.thread.is_alive():
            self.stop_evt.set()
            ids.btn.text = "Запустить"
            self.log("Остановлено")
            return
        if not ids.key.text.strip():
            self.log("Введи golden_key")
            return
        self.save_cfg()
        self.stop_evt = threading.Event()
        self.thread = threading.Thread(target=self.worker, daemon=True)
        self.thread.start()
        ids.btn.text = "Остановить"

    def worker(self):
        ids = self.root_w.ids
        key = ids.key.text.strip()
        do_raise = ids.sw_raise.active
        do_reply = ids.sw_reply.active
        reply_text = ids.reply_text.text
        try:
            fp = FunPay(key)
            fp.login()
            self.log(f"Вход выполнен: {fp.username}")
            known = set(fp.get_orders().keys())
        except Exception as e:
            self.log(f"Ошибка входа: {e}")
            Clock.schedule_once(lambda dt: setattr(ids.btn, "text", "Запустить"))
            return

        seen = set()
        last_raise = 0.0
        while not self.stop_evt.is_set():
            try:
                for oid, (buyer, desc, status) in fp.get_orders().items():
                    if oid not in known:
                        known.add(oid)
                        self.log(f"Новый заказ #{oid} от {buyer}: {desc}", notify=True)

                current = set()
                for node, name, text in fp.get_unread_chats():
                    k = f"{node}:{text}"
                    current.add(k)
                    if k not in seen:
                        self.log(f"{name}: {text}", notify=True)
                        if do_reply:
                            fp.send_message(node, reply_text)
                seen = current

                if do_raise and time.time() - last_raise > RAISE_EVERY:
                    last_raise = time.time()
                    for node in fp.get_my_categories():
                        ok, msg = fp.raise_category(node)
                        self.log(f"Поднятие {node}: {'успех' if ok else 'не вышло'}. {msg}")
                        time.sleep(random.uniform(3, 6))
            except Exception as e:
                self.log(f"Ошибка: {e}")
                self.stop_evt.wait(30)
                try:
                    fp.login()
                except Exception:
                    pass
            self.stop_evt.wait(POLL + random.uniform(0, 4))


if __name__ == "__main__":
    FunPayApp().run()
