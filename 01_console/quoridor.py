#!/usr/bin/env python3
"""
Quoridor (クオリドール) - 2プレイヤー コンソール版

ルール:
  - P1(1): 上辺 (row=0) からスタート → 下辺 (row=8) がゴール
  - P2(2): 下辺 (row=8) からスタート → 上辺 (row=0) がゴール
  - 各ターン: ポーンの移動 か 壁の設置 のどちらか1つ
  - 壁でどちらかのプレイヤーの経路を完全には塞げない
  - 相手に隣接したらジャンプ可能
"""

from collections import deque
import os


class Quoridor:
    SIZE = 9

    def __init__(self):
        # ポーン位置: (col, row), 0-indexed
        self.pos = {1: (4, 0), 2: (4, 8)}
        self.walls = {1: 10, 2: 10}  # 残り壁枚数

        # 水平壁 (c, r): row r と row r+1 の間に横向きに2マス分設置
        #   → (c,r)↔(c,r+1) と (c+1,r)↔(c+1,r+1) をブロック
        self.h_walls: set = set()

        # 垂直壁 (c, r): col c と col c+1 の間に縦向きに2マス分設置
        #   → (c,r)↔(c+1,r) と (c,r+1)↔(c+1,r+1) をブロック
        self.v_walls: set = set()

        self.turn = 1

    # ─────────────────────────────────────────────────────
    # コアロジック
    # ─────────────────────────────────────────────────────

    def goal_row(self, p: int) -> int:
        return 8 if p == 1 else 0

    def is_blocked(self, a: tuple, b: tuple) -> bool:
        """隣接セル a と b の間に壁があるか判定"""
        (c1, r1), (c2, r2) = a, b
        if c1 == c2 and abs(r1 - r2) == 1:
            # 上下移動 → 水平壁をチェック
            lo = min(r1, r2)
            return (c1, lo) in self.h_walls or (c1 - 1, lo) in self.h_walls
        if r1 == r2 and abs(c1 - c2) == 1:
            # 左右移動 → 垂直壁をチェック
            lo = min(c1, c2)
            return (lo, r1) in self.v_walls or (lo, r1 - 1) in self.v_walls
        return False

    def open_neighbors(self, pos: tuple) -> list:
        """壁を考慮した隣接セル（ポーン位置は無視）"""
        c, r = pos
        result = []
        for dc, dr in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nb = (c + dc, r + dr)
            if 0 <= nb[0] < self.SIZE and 0 <= nb[1] < self.SIZE:
                if not self.is_blocked(pos, nb):
                    result.append(nb)
        return result

    def valid_moves(self, p: int) -> set:
        """プレイヤー p の有効な移動先セット"""
        me = self.pos[p]
        opp = self.pos[3 - p]
        moves = set()

        for dc, dr in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            c, r = me
            nb = (c + dc, r + dr)
            if not (0 <= nb[0] < self.SIZE and 0 <= nb[1] < self.SIZE):
                continue
            if self.is_blocked(me, nb):
                continue

            if nb == opp:
                # 相手の真向こうへ直進ジャンプ
                jump = (nb[0] + dc, nb[1] + dr)
                if (0 <= jump[0] < self.SIZE and 0 <= jump[1] < self.SIZE
                        and not self.is_blocked(opp, jump)):
                    moves.add(jump)
                else:
                    # 直進不可なら横ジャンプ
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

    def path_exists(self, p: int) -> bool:
        """BFS: プレイヤー p がゴールに到達できるか確認"""
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

    # ─────────────────────────────────────────────────────
    # アクション
    # ─────────────────────────────────────────────────────

    def move_pawn(self, p: int, nc: int, nr: int):
        """ポーンを移動。(ok: bool, message: str) を返す"""
        vm = self.valid_moves(p)
        if (nc, nr) not in vm:
            candidates = sorted(vm)
            return False, f"無効な移動です。有効な移動先: {candidates}"
        self.pos[p] = (nc, nr)
        return True, ""

    def place_wall(self, p: int, wtype: str, c: int, r: int):
        """壁を設置。(ok: bool, message: str) を返す"""
        if self.walls[p] <= 0:
            return False, "壁の残りがありません"
        if not (0 <= c <= 7 and 0 <= r <= 7):
            return False, "座標は 0〜7 の範囲で指定してください"

        if wtype == 'h':
            if (c, r) in self.h_walls:
                return False, "その位置に既に水平壁があります"
            if (c - 1, r) in self.h_walls or (c + 1, r) in self.h_walls:
                return False, "水平壁と重なります"
            if (c, r) in self.v_walls:
                return False, "垂直壁と交差します"
            self.h_walls.add((c, r))
            if not (self.path_exists(1) and self.path_exists(2)):
                self.h_walls.remove((c, r))
                return False, "この壁はプレイヤーの経路を完全に塞ぎます"

        elif wtype == 'v':
            if (c, r) in self.v_walls:
                return False, "その位置に既に垂直壁があります"
            if (c, r - 1) in self.v_walls or (c, r + 1) in self.v_walls:
                return False, "垂直壁と重なります"
            if (c, r) in self.h_walls:
                return False, "水平壁と交差します"
            self.v_walls.add((c, r))
            if not (self.path_exists(1) and self.path_exists(2)):
                self.v_walls.remove((c, r))
                return False, "この壁はプレイヤーの経路を完全に塞ぎます"

        else:
            return False, "'h'(水平) か 'v'(垂直) を指定してください"

        self.walls[p] -= 1
        return True, ""

    def check_winner(self):
        for p in [1, 2]:
            if self.pos[p][1] == self.goal_row(p):
                return p
        return None

    # ─────────────────────────────────────────────────────
    # 表示
    # ─────────────────────────────────────────────────────

    def display(self):
        N = self.SIZE
        lines = []

        # 列番号ヘッダー
        lines.append("      " + "   ".join(str(c) for c in range(N)))

        for r in range(N):
            # 最上段の上境界
            if r == 0:
                lines.append("    +" + "---+" * N)

            # セル行
            row_str = f" {r:2} |"
            for c in range(N):
                if self.pos[1] == (c, r):
                    cell = " 1 "
                elif self.pos[2] == (c, r):
                    cell = " 2 "
                else:
                    cell = "   "
                row_str += cell

                # 右区切り: 垂直壁なら #、なければ |
                if c < N - 1:
                    row_str += "#" if self.is_blocked((c, r), (c + 1, r)) else "|"
                else:
                    row_str += "|"
            lines.append(row_str)

            # 下境界: 水平壁なら ===、なければ ---
            bot = "    +"
            for c in range(N):
                if r < N - 1 and self.is_blocked((c, r), (c, r + 1)):
                    bot += "==="
                else:
                    bot += "---"
                bot += "+"
            lines.append(bot)

        # ステータス表示
        lines.append("")
        lines.append(f"  P1 [1]: {self.pos[1]}  残り壁: {self.walls[1]}枚  ゴール → 行8 (下)")
        lines.append(f"  P2 [2]: {self.pos[2]}  残り壁: {self.walls[2]}枚  ゴール → 行0 (上)")
        lines.append("  凡例: # = 垂直壁  === = 水平壁")

        print("\n".join(lines))


# ─────────────────────────────────────────────────────
# ヘルプ・ユーティリティ
# ─────────────────────────────────────────────────────

HELP = """
┌─────────────────────────────────────────┐
│          コマンド一覧                   │
├─────────────────────────────────────────┤
│  move <col> <row>      ポーンを移動     │
│  wall h <col> <row>    水平壁を設置     │
│  wall v <col> <row>    垂直壁を設置     │
│  help                  ヘルプ表示       │
│  quit                  ゲーム終了       │
└─────────────────────────────────────────┘

壁の設置について:
  水平壁 h: row と row+1 の間に横向きに置く
            col と col+1 の2マスをまたぐ
            例) wall h 3 4 → 行4と行5の間、列3〜4をブロック

  垂直壁 v: col と col+1 の間に縦向きに置く
            row と row+1 の2マスをまたぐ
            例) wall v 4 3 → 列4と列5の間、行3〜4をブロック

  ※ col, row は 0〜7 の範囲で指定

移動について:
  相手のポーンに隣接したら飛び越えが可能
  壁や盤端で飛び越せない場合は斜め移動が可能
"""


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


# ─────────────────────────────────────────────────────
# メインループ
# ─────────────────────────────────────────────────────

def main():
    game = Quoridor()
    print("=" * 45)
    print("       Quoridor (クオリドール)")
    print("=" * 45)
    print(HELP)
    try:
        input("Enter キーでゲーム開始...")
    except (EOFError, KeyboardInterrupt):
        return

    while True:
        clear_screen()
        game.display()

        winner = game.check_winner()
        if winner:
            print(f"\n  ★ プレイヤー {winner} の勝利！ おめでとうございます！\n")
            break

        print(f"\n  プレイヤー {game.turn} のターン")
        try:
            raw = input("  コマンド> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nゲームを終了します")
            break

        parts = raw.split()
        if not parts:
            continue

        cmd = parts[0].lower()

        if cmd == "quit":
            print("ゲームを終了します")
            break

        elif cmd == "help":
            print(HELP)
            try:
                input("  Enter で続行...")
            except (EOFError, KeyboardInterrupt):
                break

        elif cmd == "move":
            if len(parts) != 3:
                print("  使い方: move <col> <row>")
                input("  Enter で続行...")
                continue
            try:
                nc, nr = int(parts[1]), int(parts[2])
            except ValueError:
                print("  数値を入力してください")
                input("  Enter で続行...")
                continue
            ok, msg = game.move_pawn(game.turn, nc, nr)
            if ok:
                game.turn = 3 - game.turn
            else:
                print(f"  エラー: {msg}")
                input("  Enter で続行...")

        elif cmd == "wall":
            if len(parts) != 4:
                print("  使い方: wall <h/v> <col> <row>")
                input("  Enter で続行...")
                continue
            wtype = parts[1].lower()
            try:
                c, r = int(parts[2]), int(parts[3])
            except ValueError:
                print("  数値を入力してください")
                input("  Enter で続行...")
                continue
            ok, msg = game.place_wall(game.turn, wtype, c, r)
            if ok:
                game.turn = 3 - game.turn
            else:
                print(f"  エラー: {msg}")
                input("  Enter で続行...")

        else:
            print(f"  不明なコマンド '{cmd}' — 'help' でヘルプを表示します")
            input("  Enter で続行...")


if __name__ == "__main__":
    main()
