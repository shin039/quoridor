#!/usr/bin/env python3
"""
Quoridor ネットワーク対戦クライアント
使い方: python quoridor_client.py
"""

import tkinter as tk
from tkinter import messagebox
import socket
import threading
import json
from collections import deque


# ═══════════════════════════════════════════════
# ゲーム状態 (サーバーから受け取り・表示用)
# ═══════════════════════════════════════════════

class GameState:
    SIZE = 9

    def __init__(self):
        self.pos = {1: (4, 0), 2: (4, 8)}
        self.walls = {1: 10, 2: 10}
        self.h_walls: set = set()
        self.v_walls: set = set()
        self.turn = 1
        self.winner = None

    def apply(self, msg):
        self.pos     = {int(k): tuple(v) for k, v in msg["pos"].items()}
        self.walls   = {int(k): v        for k, v in msg["walls"].items()}
        self.h_walls = {tuple(w) for w in msg["h_walls"]}
        self.v_walls = {tuple(w) for w in msg["v_walls"]}
        self.turn    = msg["turn"]
        self.winner  = msg.get("winner")

    def goal_row(self, p):
        return 8 if p == 1 else 0

    def is_blocked(self, a, b):
        (c1, r1), (c2, r2) = a, b
        if c1 == c2 and abs(r1 - r2) == 1:
            lo = min(r1, r2)
            return (c1, lo) in self.h_walls or (c1 - 1, lo) in self.h_walls
        if r1 == r2 and abs(c1 - c2) == 1:
            lo = min(c1, c2)
            return (lo, r1) in self.v_walls or (lo, r1 - 1) in self.v_walls
        return False

    def open_neighbors(self, pos):
        c, r = pos
        result = []
        for dc, dr in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nb = (c + dc, r + dr)
            if 0 <= nb[0] < self.SIZE and 0 <= nb[1] < self.SIZE:
                if not self.is_blocked(pos, nb):
                    result.append(nb)
        return result

    def valid_moves(self, p):
        me, opp = self.pos[p], self.pos[3 - p]
        moves = set()
        for dc, dr in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            c, r = me
            nb = (c + dc, r + dr)
            if not (0 <= nb[0] < self.SIZE and 0 <= nb[1] < self.SIZE):
                continue
            if self.is_blocked(me, nb):
                continue
            if nb == opp:
                jump = (nb[0] + dc, nb[1] + dr)
                if (0 <= jump[0] < self.SIZE and 0 <= jump[1] < self.SIZE
                        and not self.is_blocked(opp, jump)):
                    moves.add(jump)
                else:
                    for ddc, ddr in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                        if (ddc, ddr) in [(dc, dr), (-dc, -dr)]:
                            continue
                        side = (nb[0] + ddc, nb[1] + ddr)
                        if (0 <= side[0] < self.SIZE and 0 <= side[1] < self.SIZE
                                and not self.is_blocked(opp, side)):
                            moves.add(side)
            else:
                moves.add(nb)
        return moves


# ═══════════════════════════════════════════════
# 描画定数
# ═══════════════════════════════════════════════

CELL   = 60
WALL_W = 10
MARGIN = 36
BOARD_PX = MARGIN * 2 + 9 * CELL + 8 * WALL_W

P1_COL    = "#D62828"
P2_COL    = "#1A78C2"
WALL_COL  = "#FF7700"
WALL_STR  = "#994400"
MOVE_COL  = "#44EE44"
HOVER_COL = "#FFD700"


# ═══════════════════════════════════════════════
# 接続ダイアログ
# ═══════════════════════════════════════════════

class ConnectDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Quoridor — サーバーに接続")
        self.resizable(False, False)
        self.configure(bg="#222")
        self.result = None

        tk.Label(self, text="Quoridor\nネットワーク対戦",
                 font=("Arial", 18, "bold"), fg="white", bg="#222"
                 ).pack(pady=(24, 12))

        frm = tk.Frame(self, bg="#333", bd=1, relief=tk.GROOVE)
        frm.pack(padx=24, pady=4, fill=tk.X)

        for row, (label, var_val) in enumerate([
            ("サーバーアドレス:", "localhost"),
            ("ポート番号:",       "5555"),
        ]):
            tk.Label(frm, text=label, fg="#aaa", bg="#333",
                     font=("Arial", 10)).grid(row=row, column=0,
                                              sticky=tk.W, padx=12, pady=8)

        self.host_var = tk.StringVar(value="localhost")
        self.port_var = tk.StringVar(value="5555")

        tk.Entry(frm, textvariable=self.host_var, width=22,
                 bg="#444", fg="white", insertbackground="white",
                 font=("Arial", 10)).grid(row=0, column=1, padx=12, pady=8)
        tk.Entry(frm, textvariable=self.port_var, width=10,
                 bg="#444", fg="white", insertbackground="white",
                 font=("Arial", 10)).grid(row=1, column=1, sticky=tk.W,
                                          padx=12, pady=8)

        self.err_lbl = tk.Label(self, text="", fg="#FF6666", bg="#222",
                                 font=("Arial", 9))
        self.err_lbl.pack(pady=(4, 0))

        tk.Button(self, text="接続する", command=self._ok,
                  bg=P1_COL, fg="white", font=("Arial", 12, "bold"),
                  relief=tk.FLAT, padx=24, pady=8,
                  activebackground="#aa1010"
                  ).pack(pady=(8, 24))

        self.grab_set()
        self.focus_force()
        self.bind("<Return>", lambda _: self._ok())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _ok(self):
        host = self.host_var.get().strip()
        if not host:
            self.err_lbl.config(text="アドレスを入力してください")
            return
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            self.err_lbl.config(text="ポートは数値で入力してください")
            return
        self.result = (host, port)
        self.destroy()

    def _cancel(self):
        self.destroy()


# ═══════════════════════════════════════════════
# GUI クライアント
# ═══════════════════════════════════════════════

class QuoridorClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Quoridor")
        self.root.resizable(False, False)
        self.root.configure(bg="#222")

        self.state = GameState()
        self.my_player = None
        self.sock = None
        self.mode = "move"
        self.hover = None
        self.game_started = False
        self.overlay_text = "サーバーに接続してください"

        self._build()
        self.root.after(100, self._show_connect_dialog)

    # ─────────────────────────────────────────
    # レイアウト構築
    # ─────────────────────────────────────────

    def _build(self):
        mf = tk.Frame(self.root, bg="#222")
        mf.pack(padx=12, pady=12)

        # キャンバス
        self.cv = tk.Canvas(mf, width=BOARD_PX, height=BOARD_PX,
                            bg="#8B6000", highlightthickness=0)
        self.cv.grid(row=0, column=0, rowspan=20, padx=(0, 12))
        self.cv.bind("<Button-1>", self._click)
        self.cv.bind("<Motion>",   self._hover_ev)
        self.cv.bind("<Leave>",    self._leave)

        # Player boxes
        self.p1_box = tk.LabelFrame(mf, text=" Player 1 ",
                                     font=("Arial", 10, "bold"),
                                     fg=P1_COL, bg="#333", bd=2, relief=tk.RIDGE)
        self.p1_box.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        self.p1_lbl = tk.Label(self.p1_box, text="", fg="white", bg="#333",
                                font=("Arial", 10), justify=tk.LEFT)
        self.p1_lbl.pack(padx=8, pady=4, anchor=tk.W)

        self.p2_box = tk.LabelFrame(mf, text=" Player 2 ",
                                     font=("Arial", 10, "bold"),
                                     fg=P2_COL, bg="#333", bd=2, relief=tk.RIDGE)
        self.p2_box.grid(row=1, column=1, sticky="ew", pady=(0, 12))
        self.p2_lbl = tk.Label(self.p2_box, text="", fg="white", bg="#333",
                                font=("Arial", 10), justify=tk.LEFT)
        self.p2_lbl.pack(padx=8, pady=4, anchor=tk.W)

        self.turn_lbl = tk.Label(mf, text="接続待ち",
                                  font=("Arial", 13, "bold"),
                                  fg="#888", bg="#222")
        self.turn_lbl.grid(row=2, column=1, pady=(0, 8))

        # モード選択
        mdf = tk.LabelFrame(mf, text=" アクション ", font=("Arial", 9),
                             fg="#aaa", bg="#333", bd=1)
        mdf.grid(row=3, column=1, sticky="ew", pady=(0, 8))
        self.mode_var = tk.StringVar(value="move")
        for txt, val in [("ポーン移動",    "move"),
                          ("水平壁を置く", "h_wall"),
                          ("垂直壁を置く", "v_wall")]:
            tk.Radiobutton(mdf, text=txt, variable=self.mode_var,
                           value=val, command=self._mode_change,
                           fg="white", bg="#333", selectcolor="#555",
                           activebackground="#333", activeforeground="white",
                           font=("Arial", 10)).pack(anchor=tk.W, padx=10, pady=2)

        self.msg_lbl = tk.Label(mf, text="", font=("Arial", 9),
                                 fg="#FF9999", bg="#222", wraplength=190)
        self.msg_lbl.grid(row=4, column=1, pady=(0, 8), padx=4)

        self.my_lbl = tk.Label(mf, text="", font=("Arial", 10, "bold"),
                                fg="#aaa", bg="#222")
        self.my_lbl.grid(row=5, column=1, pady=(0, 8))

        tk.Button(mf, text="再接続", command=self._reconnect,
                  bg="#444", fg="white", font=("Arial", 9), relief=tk.FLAT,
                  padx=8, pady=4, activebackground="#666"
                  ).grid(row=6, column=1, sticky="ew", pady=(0, 12))

        help_txt = (
            "【操作方法】\n\n"
            "ポーン移動:\n  緑のマスをクリック\n\n"
            "水平壁:\n  行間の隙間をクリック\n  (黄プレビュー)\n\n"
            "垂直壁:\n  列間の隙間をクリック\n  (黄プレビュー)\n\n"
            "壁は2マス分をまたぎます。\n"
            "相手の経路を完全には\n塞げません。"
        )
        tk.Label(mf, text=help_txt, font=("Arial", 8),
                 fg="#555", bg="#222", justify=tk.LEFT
                 ).grid(row=7, column=1, padx=4, sticky="nw")

        # 初期オーバーレイ描画
        self._draw_overlay_canvas(self.overlay_text)

    # ─────────────────────────────────────────
    # 接続
    # ─────────────────────────────────────────

    def _show_connect_dialog(self):
        dlg = ConnectDialog(self.root)
        self.root.wait_window(dlg)
        if dlg.result is None:
            self.root.quit()
            return
        host, port = dlg.result
        self._connect(host, port)

    def _reconnect(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        self.game_started = False
        self.my_player = None
        self.state = GameState()
        self._show_connect_dialog()

    def _connect(self, host, port):
        self._set_overlay(f"{host}:{port} に接続中...")

        def do_connect():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(6)
                s.connect((host, port))
                s.settimeout(None)
                self.sock = s
                threading.Thread(target=self._recv_loop, daemon=True).start()
            except Exception as e:
                self._schedule(self._connect_error, str(e))

        threading.Thread(target=do_connect, daemon=True).start()

    def _connect_error(self, err):
        messagebox.showerror("接続エラー",
                             f"サーバーに接続できませんでした\n\n{err}")
        self._show_connect_dialog()

    # ─────────────────────────────────────────
    # 受信ループ (バックグラウンドスレッド)
    # ─────────────────────────────────────────

    def _recv_loop(self):
        buf = ""
        while True:
            try:
                data = self.sock.recv(4096).decode("utf-8")
                if not data:
                    self._schedule(self._on_disconnect)
                    break
                buf += data
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._schedule(self._handle_msg, json.loads(line))
            except Exception:
                self._schedule(self._on_disconnect)
                break

    def _schedule(self, fn, *args):
        try:
            if self.root.winfo_exists():
                self.root.after(0, fn, *args)
        except Exception:
            pass

    # ─────────────────────────────────────────
    # メッセージ処理 (メインスレッド)
    # ─────────────────────────────────────────

    def _handle_msg(self, msg):
        mtype = msg.get("type")

        if mtype == "assign":
            self.my_player = msg["player"]
            col = P1_COL if self.my_player == 1 else P2_COL
            self.root.title(f"Quoridor — Player {self.my_player}")
            self.my_lbl.config(
                text=f"あなた: Player {self.my_player}", fg=col)
            self._set_overlay(
                f"あなたは Player {self.my_player} です\n\n相手の接続を待っています...")

        elif mtype == "info":
            self._set_overlay(msg["msg"])

        elif mtype == "state":
            self.state.apply(msg)
            if not self.game_started:
                self.game_started = True
            self.refresh()
            if self.state.winner:
                w = self.state.winner
                if w == self.my_player:
                    messagebox.showinfo("ゲーム終了",
                                        "あなたの勝利！\nおめでとうございます！")
                else:
                    messagebox.showinfo("ゲーム終了", "相手の勝利...")

        elif mtype == "error":
            self.msg_lbl.config(text=msg["msg"])

    def _on_disconnect(self):
        if not self.root.winfo_exists():
            return
        messagebox.showwarning("切断", "サーバーから切断されました")
        self.game_started = False
        self._set_overlay("切断されました\n「再接続」ボタンで再試行できます")
        self.refresh()

    # ─────────────────────────────────────────
    # 座標変換
    # ─────────────────────────────────────────

    def _xy(self, c, r):
        return MARGIN + c * (CELL + WALL_W), MARGIN + r * (CELL + WALL_W)

    def _center(self, c, r):
        x, y = self._xy(c, r)
        return x + CELL // 2, y + CELL // 2

    def _hit(self, px, py):
        px -= MARGIN
        py -= MARGIN
        if px < 0 or py < 0:
            return None
        slot = CELL + WALL_W
        c, r = int(px // slot), int(py // slot)
        if c >= 9 or r >= 9:
            return None
        xi, yi = px - c * slot, py - r * slot
        in_cx = 0 <= xi < CELL
        in_cy = 0 <= yi < CELL
        in_gx = CELL <= xi < CELL + WALL_W
        in_gy = CELL <= yi < CELL + WALL_W
        if in_cx and in_cy:               return ("cell",  c, r)
        if in_gx and in_cy and c < 8:    return ("v_gap", c, r)
        if in_cx and in_gy and r < 8:    return ("h_gap", c, r)
        return None

    # ─────────────────────────────────────────
    # イベント
    # ─────────────────────────────────────────

    def _mode_change(self):
        self.mode = self.mode_var.get()
        self.hover = None
        self.msg_lbl.config(text="")
        self.refresh()

    def _hover_ev(self, ev):
        h = self._hit(ev.x, ev.y)
        if h != self.hover:
            self.hover = h
            self.refresh()

    def _leave(self, ev):
        self.hover = None
        self.refresh()

    def _is_my_turn(self):
        return (self.game_started
                and self.my_player is not None
                and self.state.turn == self.my_player
                and not self.state.winner)

    def _click(self, ev):
        if not self.game_started:
            return
        if not self._is_my_turn():
            if not self.state.winner:
                self.msg_lbl.config(text="相手のターンです")
            return

        pos = self._hit(ev.x, ev.y)
        if pos is None:
            return
        ptype, c, r = pos

        if self.mode == "move":
            if ptype == "cell":
                self._send({"type": "move", "col": c, "row": r})
                self.msg_lbl.config(text="")
            else:
                self.msg_lbl.config(text="セルをクリックしてください")

        elif self.mode == "h_wall":
            if ptype == "h_gap":
                self._send({"type": "wall", "wtype": "h",
                            "col": min(c, 7), "row": r})
                self.msg_lbl.config(text="")
            else:
                self.msg_lbl.config(text="行と行の隙間をクリックしてください")

        elif self.mode == "v_wall":
            if ptype == "v_gap":
                self._send({"type": "wall", "wtype": "v",
                            "col": c, "row": min(r, 7)})
                self.msg_lbl.config(text="")
            else:
                self.msg_lbl.config(text="列と列の隙間をクリックしてください")

    def _send(self, msg):
        if self.sock:
            try:
                self.sock.sendall(
                    (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
            except Exception:
                pass

    # ─────────────────────────────────────────
    # 描画
    # ─────────────────────────────────────────

    def refresh(self):
        self.cv.delete("all")
        if not self.game_started:
            self._draw_overlay_canvas(self.overlay_text)
            return
        self._draw_cells()
        self._draw_move_hints()
        self._draw_hover()
        self._draw_walls()
        self._draw_pawns()
        self._update_side()

    def _set_overlay(self, text):
        self.overlay_text = text
        if not self.game_started:
            self.cv.delete("all")
            self._draw_overlay_canvas(text)

    def _draw_overlay_canvas(self, text):
        self.cv.create_rectangle(0, 0, BOARD_PX, BOARD_PX,
                                  fill="#111", outline="")
        self.cv.create_text(BOARD_PX // 2, BOARD_PX // 2,
                             text=text, fill="white",
                             font=("Arial", 15), justify=tk.CENTER)

    def _draw_cells(self):
        for r in range(9):
            for c in range(9):
                x, y = self._xy(c, r)
                if r == 8:
                    fill = "#E8A0A0" if (c + r) % 2 == 0 else "#C88080"
                elif r == 0:
                    fill = "#A0C0E8" if (c + r) % 2 == 0 else "#8090C8"
                else:
                    fill = "#F0D880" if (c + r) % 2 == 0 else "#C8B050"
                self.cv.create_rectangle(x, y, x + CELL, y + CELL,
                                          fill=fill, outline="#8B6000", width=1)
        for i in range(9):
            cx, _ = self._xy(i, 0)
            self.cv.create_text(cx + CELL // 2, MARGIN // 2,
                                text=str(i), fill="#bbb", font=("Arial", 9))
            _, ry = self._xy(0, i)
            self.cv.create_text(MARGIN // 2, ry + CELL // 2,
                                text=str(i), fill="#bbb", font=("Arial", 9))
        x0, y0 = self._xy(0, 0)
        x8, _  = self._xy(8, 0)
        mid = (x0 + x8 + CELL) // 2
        self.cv.create_text(mid, y0 + CELL // 2,
                             text="P2 GOAL", fill=P2_COL,
                             font=("Arial", 8, "bold"))
        _, y8 = self._xy(0, 8)
        self.cv.create_text(mid, y8 + CELL // 2,
                             text="P1 GOAL", fill=P1_COL,
                             font=("Arial", 8, "bold"))

    def _draw_move_hints(self):
        if self.mode != "move" or not self._is_my_turn():
            return
        for c, r in self.state.valid_moves(self.my_player):
            x, y = self._xy(c, r)
            self.cv.create_rectangle(x + 5, y + 5, x + CELL - 5, y + CELL - 5,
                                     fill=MOVE_COL, outline="#00AA00", width=2)

    def _draw_hover(self):
        if self.hover is None or not self._is_my_turn():
            return
        ptype, c, r = self.hover

        if self.mode == "h_wall" and ptype == "h_gap":
            wc = min(c, 7)
            x1, y1 = self._xy(wc, r)
            x2, _  = self._xy(wc + 1, r)
            wy = y1 + CELL
            self.cv.create_rectangle(x1, wy, x2 + CELL, wy + WALL_W,
                                     fill=HOVER_COL, outline="#AA8800")

        elif self.mode == "v_wall" and ptype == "v_gap":
            wr = min(r, 7)
            x1, y1 = self._xy(c, wr)
            _,  y2 = self._xy(c, wr + 1)
            wx = x1 + CELL
            self.cv.create_rectangle(wx, y1, wx + WALL_W, y2 + CELL,
                                     fill=HOVER_COL, outline="#AA8800")

        elif self.mode == "move" and ptype == "cell":
            if (c, r) in self.state.valid_moves(self.my_player):
                x, y = self._xy(c, r)
                self.cv.create_rectangle(x + 5, y + 5,
                                         x + CELL - 5, y + CELL - 5,
                                         fill="#00EE00", outline="#007700",
                                         width=3)

    def _draw_walls(self):
        for c, r in self.state.h_walls:
            x1, y1 = self._xy(c, r)
            x2, _  = self._xy(c + 1, r)
            wy = y1 + CELL
            self.cv.create_rectangle(x1, wy, x2 + CELL, wy + WALL_W,
                                     fill=WALL_COL, outline=WALL_STR, width=1)
        for c, r in self.state.v_walls:
            x1, y1 = self._xy(c, r)
            _,  y2 = self._xy(c, r + 1)
            wx = x1 + CELL
            self.cv.create_rectangle(wx, y1, wx + WALL_W, y2 + CELL,
                                     fill=WALL_COL, outline=WALL_STR, width=1)

    def _draw_pawns(self):
        for p in [2, 1]:
            c, r = self.state.pos[p]
            cx, cy = self._center(c, r)
            rad = CELL // 2 - 7
            col = P1_COL if p == 1 else P2_COL
            self.cv.create_oval(cx - rad + 3, cy - rad + 4,
                                cx + rad + 3, cy + rad + 4,
                                fill="#111", outline="")
            self.cv.create_oval(cx - rad, cy - rad, cx + rad, cy + rad,
                                fill=col, outline="white", width=2)
            self.cv.create_text(cx, cy, text=str(p),
                                fill="white", font=("Arial", 14, "bold"))
            # 現在のターンは点線リング
            if self.state.turn == p and not self.state.winner:
                self.cv.create_oval(cx - rad - 4, cy - rad - 4,
                                    cx + rad + 4, cy + rad + 4,
                                    fill="", outline="white",
                                    width=2, dash=(4, 3))

    def _update_side(self):
        s = self.state
        self.p1_lbl.config(
            text=f"位置: {s.pos[1]}\n残り壁: {s.walls[1]} 枚\nゴール: 行8 (下)")
        self.p2_lbl.config(
            text=f"位置: {s.pos[2]}\n残り壁: {s.walls[2]} 枚\nゴール: 行0 (上)")

        if s.winner:
            col = P1_COL if s.winner == 1 else P2_COL
            self.turn_lbl.config(text=f"Player {s.winner} の勝利！", fg=col)
        elif self._is_my_turn():
            col = P1_COL if s.turn == 1 else P2_COL
            self.turn_lbl.config(text="あなたのターン", fg=col)
        else:
            self.turn_lbl.config(text="相手のターン...", fg="#888")

        p1_bg = "#3d1a1a" if s.turn == 1 else "#333"
        p2_bg = "#1a2d3d" if s.turn == 2 else "#333"
        self.p1_box.config(bg=p1_bg)
        self.p1_lbl.config(bg=p1_bg)
        self.p2_box.config(bg=p2_bg)
        self.p2_lbl.config(bg=p2_bg)


# ═══════════════════════════════════════════════
# エントリーポイント
# ═══════════════════════════════════════════════

def main():
    root = tk.Tk()
    QuoridorClient(root)
    root.mainloop()


if __name__ == "__main__":
    main()
