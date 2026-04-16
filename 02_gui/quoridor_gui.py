#!/usr/bin/env python3
"""Quoridor GUI - tkinter版"""

import tkinter as tk
from tkinter import messagebox
from collections import deque


# ═══════════════════════════════════════════════
# ゲームロジック
# ═══════════════════════════════════════════════

class Quoridor:
    SIZE = 9

    def __init__(self):
        self.pos = {1: (4, 0), 2: (4, 8)}
        self.walls = {1: 10, 2: 10}
        self.h_walls = set()
        self.v_walls = set()
        self.turn = 1

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
        for dc, dr in [(0,1),(0,-1),(1,0),(-1,0)]:
            nb = (c+dc, r+dr)
            if 0 <= nb[0] < self.SIZE and 0 <= nb[1] < self.SIZE:
                if not self.is_blocked(pos, nb):
                    result.append(nb)
        return result

    def valid_moves(self, p):
        me = self.pos[p]
        opp = self.pos[3-p]
        moves = set()
        for dc, dr in [(0,1),(0,-1),(1,0),(-1,0)]:
            c, r = me
            nb = (c+dc, r+dr)
            if not (0 <= nb[0] < self.SIZE and 0 <= nb[1] < self.SIZE):
                continue
            if self.is_blocked(me, nb):
                continue
            if nb == opp:
                jump = (nb[0]+dc, nb[1]+dr)
                if (0 <= jump[0] < self.SIZE and 0 <= jump[1] < self.SIZE
                        and not self.is_blocked(opp, jump)):
                    moves.add(jump)
                else:
                    for ddc, ddr in [(0,1),(0,-1),(1,0),(-1,0)]:
                        if (ddc, ddr) in [(dc,dr),(-dc,-dr)]:
                            continue
                        side = (nb[0]+ddc, nb[1]+ddr)
                        if (0 <= side[0] < self.SIZE and 0 <= side[1] < self.SIZE
                                and not self.is_blocked(opp, side)):
                            moves.add(side)
            else:
                moves.add(nb)
        return moves

    def path_exists(self, p):
        goal = self.goal_row(p)
        start = self.pos[p]
        visited = {start}
        q = deque([start])
        while q:
            c, r = q.popleft()
            if r == goal:
                return True
            for nb in self.open_neighbors((c, r)):
                if nb not in visited:
                    visited.add(nb)
                    q.append(nb)
        return False

    def move_pawn(self, p, nc, nr):
        if (nc, nr) not in self.valid_moves(p):
            return False, "そこには移動できません"
        self.pos[p] = (nc, nr)
        return True, ""

    def place_wall(self, p, wtype, c, r):
        if self.walls[p] <= 0:
            return False, "壁の残りがありません"
        if not (0 <= c <= 7 and 0 <= r <= 7):
            return False, "無効な位置です"
        if wtype == 'h':
            if (c, r) in self.h_walls:
                return False, "既に壁があります"
            if (c-1, r) in self.h_walls or (c+1, r) in self.h_walls:
                return False, "壁が重なります"
            if (c, r) in self.v_walls:
                return False, "壁が交差します"
            self.h_walls.add((c, r))
            if not (self.path_exists(1) and self.path_exists(2)):
                self.h_walls.remove((c, r))
                return False, "経路が塞がれます"
        else:
            if (c, r) in self.v_walls:
                return False, "既に壁があります"
            if (c, r-1) in self.v_walls or (c, r+1) in self.v_walls:
                return False, "壁が重なります"
            if (c, r) in self.h_walls:
                return False, "壁が交差します"
            self.v_walls.add((c, r))
            if not (self.path_exists(1) and self.path_exists(2)):
                self.v_walls.remove((c, r))
                return False, "経路が塞がれます"
        self.walls[p] -= 1
        return True, ""

    def check_winner(self):
        for p in [1, 2]:
            if self.pos[p][1] == self.goal_row(p):
                return p
        return None


# ═══════════════════════════════════════════════
# 描画定数
# ═══════════════════════════════════════════════

CELL   = 60
WALL_W = 10
MARGIN = 36

P1_COL    = "#D62828"
P2_COL    = "#1A78C2"
WALL_COL  = "#FF7700"
WALL_STR  = "#994400"
MOVE_COL  = "#44EE44"
HOVER_COL = "#FFD700"


# ═══════════════════════════════════════════════
# GUI
# ═══════════════════════════════════════════════

class QuoridorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Quoridor")
        self.root.resizable(False, False)
        self.root.configure(bg="#222")
        self.game = Quoridor()
        self.mode = "move"
        self.hover = None
        self.game_over = False
        self._build()
        self.refresh()

    # ─────────────────────────────────────────
    # レイアウト
    # ─────────────────────────────────────────

    def _build(self):
        board_px = MARGIN * 2 + 9 * CELL + 8 * WALL_W

        mf = tk.Frame(self.root, bg="#222")
        mf.pack(padx=12, pady=12)

        # キャンバス
        self.cv = tk.Canvas(mf, width=board_px, height=board_px,
                            bg="#8B6000", highlightthickness=0)
        self.cv.grid(row=0, column=0, rowspan=20, padx=(0, 12))
        self.cv.bind("<Button-1>", self._click)
        self.cv.bind("<Motion>",   self._hover_ev)
        self.cv.bind("<Leave>",    self._leave)

        # Player boxes
        self.p1_box = tk.LabelFrame(mf, text=" Player 1 ", font=("Arial", 10, "bold"),
                                     fg=P1_COL, bg="#333", bd=2, relief=tk.RIDGE)
        self.p1_box.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        self.p1_lbl = tk.Label(self.p1_box, text="", fg="white", bg="#333",
                                font=("Arial", 10), justify=tk.LEFT)
        self.p1_lbl.pack(padx=8, pady=4, anchor=tk.W)

        self.p2_box = tk.LabelFrame(mf, text=" Player 2 ", font=("Arial", 10, "bold"),
                                     fg=P2_COL, bg="#333", bd=2, relief=tk.RIDGE)
        self.p2_box.grid(row=1, column=1, sticky="ew", pady=(0, 12))
        self.p2_lbl = tk.Label(self.p2_box, text="", fg="white", bg="#333",
                                font=("Arial", 10), justify=tk.LEFT)
        self.p2_lbl.pack(padx=8, pady=4, anchor=tk.W)

        # ターン
        self.turn_lbl = tk.Label(mf, text="", font=("Arial", 14, "bold"),
                                  fg="white", bg="#222")
        self.turn_lbl.grid(row=2, column=1, pady=(0, 8))

        # モード選択
        mdf = tk.LabelFrame(mf, text=" アクション ", font=("Arial", 9),
                             fg="#aaa", bg="#333", bd=1)
        mdf.grid(row=3, column=1, sticky="ew", pady=(0, 8))
        self.mode_var = tk.StringVar(value="move")
        for txt, val in [("ポーン移動", "move"),
                          ("水平壁を置く", "h_wall"),
                          ("垂直壁を置く", "v_wall")]:
            tk.Radiobutton(mdf, text=txt, variable=self.mode_var, value=val,
                           command=self._mode_change,
                           fg="white", bg="#333", selectcolor="#555",
                           activebackground="#333", activeforeground="white",
                           font=("Arial", 10)).pack(anchor=tk.W, padx=10, pady=2)

        # メッセージ
        self.msg_lbl = tk.Label(mf, text="", font=("Arial", 9),
                                 fg="#FF9999", bg="#222", wraplength=190)
        self.msg_lbl.grid(row=4, column=1, pady=(0, 8), padx=4)

        # リセット
        tk.Button(mf, text="ゲームをリセット", command=self._reset,
                  bg="#444", fg="white", font=("Arial", 10), relief=tk.FLAT,
                  padx=8, pady=4, activebackground="#666"
                  ).grid(row=5, column=1, sticky="ew", pady=(0, 14))

        # ヘルプ
        help_txt = (
            "【操作方法】\n\n"
            "ポーン移動:\n  緑のマスをクリック\n\n"
            "水平壁:\n  行間の隙間をクリック\n  (黄色プレビュー表示)\n\n"
            "垂直壁:\n  列間の隙間をクリック\n  (黄色プレビュー表示)\n\n"
            "壁は2マス分をまたぎます。\n"
            "相手の経路を完全には\n塞げません。"
        )
        tk.Label(mf, text=help_txt, font=("Arial", 8), fg="#666",
                 bg="#222", justify=tk.LEFT).grid(row=6, column=1, padx=4, sticky="nw")

    # ─────────────────────────────────────────
    # 座標変換
    # ─────────────────────────────────────────

    def _xy(self, c, r):
        """セル左上座標"""
        return MARGIN + c*(CELL+WALL_W), MARGIN + r*(CELL+WALL_W)

    def _center(self, c, r):
        x, y = self._xy(c, r)
        return x + CELL//2, y + CELL//2

    def _hit(self, px, py):
        """ピクセル→ボード位置  ('cell'|'h_gap'|'v_gap', c, r) or None"""
        px -= MARGIN
        py -= MARGIN
        if px < 0 or py < 0:
            return None
        slot = CELL + WALL_W
        c = int(px // slot)
        r = int(py // slot)
        if c >= 9 or r >= 9:
            return None
        xi = px - c * slot
        yi = py - r * slot
        in_cx = 0 <= xi < CELL
        in_cy = 0 <= yi < CELL
        in_gx = CELL <= xi < CELL + WALL_W
        in_gy = CELL <= yi < CELL + WALL_W
        if in_cx and in_cy:
            return ('cell', c, r)
        if in_gx and in_cy and c < 8:
            return ('v_gap', c, r)
        if in_cx and in_gy and r < 8:
            return ('h_gap', c, r)
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

    def _click(self, ev):
        if self.game_over:
            return
        pos = self._hit(ev.x, ev.y)
        if pos is None:
            return
        ptype, c, r = pos

        if self.mode == "move":
            if ptype == "cell":
                ok, msg = self.game.move_pawn(self.game.turn, c, r)
                self._after(ok, msg)
            else:
                self.msg_lbl.config(text="セルをクリックしてください")

        elif self.mode == "h_wall":
            if ptype == "h_gap":
                wc = min(c, 7)
                ok, msg = self.game.place_wall(self.game.turn, 'h', wc, r)
                self._after(ok, msg)
            else:
                self.msg_lbl.config(text="行と行の隙間をクリックしてください")

        elif self.mode == "v_wall":
            if ptype == "v_gap":
                wr = min(r, 7)
                ok, msg = self.game.place_wall(self.game.turn, 'v', c, wr)
                self._after(ok, msg)
            else:
                self.msg_lbl.config(text="列と列の隙間をクリックしてください")

        self.refresh()

    def _after(self, ok, msg):
        if ok:
            self.msg_lbl.config(text="")
            self.game.turn = 3 - self.game.turn
            winner = self.game.check_winner()
            if winner:
                self.game_over = True
                self.refresh()
                messagebox.showinfo("ゲーム終了",
                                    f"Player {winner} の勝利！\nおめでとうございます！")
        else:
            self.msg_lbl.config(text=msg)

    def _reset(self):
        self.game = Quoridor()
        self.mode = "move"
        self.mode_var.set("move")
        self.hover = None
        self.game_over = False
        self.msg_lbl.config(text="")
        self.refresh()

    # ─────────────────────────────────────────
    # 描画
    # ─────────────────────────────────────────

    def refresh(self):
        self.cv.delete("all")
        self._draw_cells()
        self._draw_move_hints()
        self._draw_hover()
        self._draw_walls()
        self._draw_pawns()
        self._update_side()

    def _draw_cells(self):
        for r in range(9):
            for c in range(9):
                x, y = self._xy(c, r)
                # ゴール行は色を変える
                if r == 8:
                    fill = "#E8A0A0" if (c+r)%2==0 else "#C88080"
                elif r == 0:
                    fill = "#A0C0E8" if (c+r)%2==0 else "#8090C8"
                else:
                    fill = "#F0D880" if (c+r)%2==0 else "#C8B050"
                self.cv.create_rectangle(x, y, x+CELL, y+CELL,
                                         fill=fill, outline="#8B6000", width=1)
        # 座標ラベル
        for i in range(9):
            cx, _ = self._xy(i, 0)
            self.cv.create_text(cx+CELL//2, MARGIN//2,
                                text=str(i), fill="#bbb", font=("Arial", 9))
            _, ry = self._xy(0, i)
            self.cv.create_text(MARGIN//2, ry+CELL//2,
                                text=str(i), fill="#bbb", font=("Arial", 9))
        # ゴールラベル
        x0, y0 = self._xy(0, 0)
        x8, y8 = self._xy(8, 0)
        self.cv.create_text((x0+x8+CELL)//2, y0+CELL//2,
                             text="P2 GOAL", fill=P2_COL, font=("Arial", 8, "bold"))
        x0, y8b = self._xy(0, 8)
        x8, _ = self._xy(8, 8)
        self.cv.create_text((x0+x8+CELL)//2, y8b+CELL//2,
                             text="P1 GOAL", fill=P1_COL, font=("Arial", 8, "bold"))

    def _draw_move_hints(self):
        if self.mode != "move" or self.game_over:
            return
        for (c, r) in self.game.valid_moves(self.game.turn):
            x, y = self._xy(c, r)
            self.cv.create_rectangle(x+5, y+5, x+CELL-5, y+CELL-5,
                                     fill=MOVE_COL, outline="#00AA00", width=2)

    def _draw_hover(self):
        if self.hover is None or self.game_over:
            return
        ptype, c, r = self.hover

        if self.mode == "h_wall" and ptype == "h_gap":
            wc = min(c, 7)
            x1, y1 = self._xy(wc, r)
            x2, _  = self._xy(wc+1, r)
            wy = y1 + CELL
            self.cv.create_rectangle(x1, wy, x2+CELL, wy+WALL_W,
                                     fill=HOVER_COL, outline="#AA8800")

        elif self.mode == "v_wall" and ptype == "v_gap":
            wr = min(r, 7)
            x1, y1 = self._xy(c, wr)
            _,  y2 = self._xy(c, wr+1)
            wx = x1 + CELL
            self.cv.create_rectangle(wx, y1, wx+WALL_W, y2+CELL,
                                     fill=HOVER_COL, outline="#AA8800")

        elif self.mode == "move" and ptype == "cell":
            if (c, r) in self.game.valid_moves(self.game.turn):
                x, y = self._xy(c, r)
                self.cv.create_rectangle(x+5, y+5, x+CELL-5, y+CELL-5,
                                         fill="#00EE00", outline="#007700", width=3)

    def _draw_walls(self):
        for (c, r) in self.game.h_walls:
            x1, y1 = self._xy(c, r)
            x2, _  = self._xy(c+1, r)
            wy = y1 + CELL
            self.cv.create_rectangle(x1, wy, x2+CELL, wy+WALL_W,
                                     fill=WALL_COL, outline=WALL_STR, width=1)

        for (c, r) in self.game.v_walls:
            x1, y1 = self._xy(c, r)
            _,  y2 = self._xy(c, r+1)
            wx = x1 + CELL
            self.cv.create_rectangle(wx, y1, wx+WALL_W, y2+CELL,
                                     fill=WALL_COL, outline=WALL_STR, width=1)

    def _draw_pawns(self):
        for p in [2, 1]:
            c, r = self.game.pos[p]
            cx, cy = self._center(c, r)
            rad = CELL//2 - 7
            col = P1_COL if p == 1 else P2_COL
            # 影
            self.cv.create_oval(cx-rad+3, cy-rad+4, cx+rad+3, cy+rad+4,
                                fill="#111", outline="")
            # 本体
            self.cv.create_oval(cx-rad, cy-rad, cx+rad, cy+rad,
                                fill=col, outline="white", width=2)
            # 番号
            self.cv.create_text(cx, cy, text=str(p),
                                fill="white", font=("Arial", 14, "bold"))
            # 現ターンは点線リング
            if self.game.turn == p and not self.game_over:
                self.cv.create_oval(cx-rad-4, cy-rad-4, cx+rad+4, cy+rad+4,
                                    fill="", outline="white", width=2, dash=(4, 3))

    def _update_side(self):
        g = self.game
        self.p1_lbl.config(
            text=f"位置: {g.pos[1]}\n残り壁: {g.walls[1]} 枚\nゴール: 行8 (下)")
        self.p2_lbl.config(
            text=f"位置: {g.pos[2]}\n残り壁: {g.walls[2]} 枚\nゴール: 行0 (上)")

        if self.game_over:
            w = g.check_winner()
            col = P1_COL if w == 1 else P2_COL
            self.turn_lbl.config(text=f"Player {w} の勝利！", fg=col)
        else:
            col = P1_COL if g.turn == 1 else P2_COL
            self.turn_lbl.config(text=f"Player {g.turn} のターン", fg=col)

        p1_bg = "#3d1a1a" if g.turn == 1 else "#333"
        p2_bg = "#1a2d3d" if g.turn == 2 else "#333"
        self.p1_box.config(bg=p1_bg)
        self.p1_lbl.config(bg=p1_bg)
        self.p2_box.config(bg=p2_bg)
        self.p2_lbl.config(bg=p2_bg)


# ═══════════════════════════════════════════════
# エントリーポイント
# ═══════════════════════════════════════════════

def main():
    root = tk.Tk()
    QuoridorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
