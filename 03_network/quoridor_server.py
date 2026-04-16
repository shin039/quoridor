#!/usr/bin/env python3
"""
Quoridor ネットワーク対戦サーバー
使い方: python quoridor_server.py [ポート番号]
デフォルト: 5555
"""

import socket
import threading
import json
import sys
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

    def path_exists(self, p):
        goal, start = self.goal_row(p), self.pos[p]
        visited, q = {start}, deque([start])
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
            return False, "無効な移動です"
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
            if (c - 1, r) in self.h_walls or (c + 1, r) in self.h_walls:
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
            if (c, r - 1) in self.v_walls or (c, r + 1) in self.v_walls:
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
# サーバー
# ═══════════════════════════════════════════════

class GameServer:
    def __init__(self, host="0.0.0.0", port=5555):
        self.host = host
        self.port = port
        self.game = Quoridor()
        self.clients = {}       # player_num(1|2) -> socket
        self.lock = threading.Lock()

    def start(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(2)
        print(f"[SERVER] 起動: {self.host}:{self.port}")
        print("[SERVER] 2人のプレイヤーを待機中...")

        for pnum in [1, 2]:
            conn, addr = srv.accept()
            self.clients[pnum] = conn
            print(f"[SERVER] Player {pnum} 接続: {addr}")
            self._send(conn, {"type": "assign", "player": pnum})
            if pnum == 1:
                self._send(conn, {"type": "info",
                                  "msg": "Player 2 の接続を待っています..."})

        print("[SERVER] 両プレイヤー接続完了 — ゲーム開始！")
        self._broadcast_state()

        threads = []
        for pnum in [1, 2]:
            t = threading.Thread(target=self._client_loop, args=(pnum,), daemon=True)
            t.start()
            threads.append(t)

        try:
            while any(t.is_alive() for t in threads):
                for t in threads:
                    t.join(timeout=0.5)
        except KeyboardInterrupt:
            pass

        print("[SERVER] 終了")

    # ─────────────────────────────────────────
    # クライアント受信ループ
    # ─────────────────────────────────────────

    def _client_loop(self, pnum):
        conn = self.clients[pnum]
        buf = ""
        while True:
            try:
                data = conn.recv(4096).decode("utf-8")
                if not data:
                    print(f"[SERVER] Player {pnum} 切断")
                    self._broadcast({"type": "info",
                                     "msg": f"Player {pnum} が切断しました"})
                    break
                buf += data
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._process(pnum, json.loads(line))
            except ConnectionResetError:
                print(f"[SERVER] Player {pnum} 接続リセット")
                break
            except Exception as e:
                print(f"[SERVER] Player {pnum} エラー: {e}")
                break

    # ─────────────────────────────────────────
    # アクション処理
    # ─────────────────────────────────────────

    def _process(self, pnum, msg):
        with self.lock:
            g = self.game
            if g.check_winner():
                return
            if g.turn != pnum:
                self._send(self.clients[pnum],
                           {"type": "error", "msg": "あなたのターンではありません"})
                return

            mtype = msg.get("type")
            if mtype == "move":
                ok, err = g.move_pawn(pnum, msg["col"], msg["row"])
                if ok:
                    print(f"[SERVER] P{pnum} 移動 → ({msg['col']}, {msg['row']})")
            elif mtype == "wall":
                ok, err = g.place_wall(pnum, msg["wtype"], msg["col"], msg["row"])
                if ok:
                    print(f"[SERVER] P{pnum} 壁({msg['wtype']}) ({msg['col']}, {msg['row']})")
            else:
                return

            if not ok:
                self._send(self.clients[pnum], {"type": "error", "msg": err})
                return

            g.turn = 3 - g.turn
            winner = g.check_winner()
            if winner:
                print(f"[SERVER] Player {winner} の勝利！")
            self._broadcast_state()

    # ─────────────────────────────────────────
    # 送受信ユーティリティ
    # ─────────────────────────────────────────

    def _broadcast_state(self):
        g = self.game
        state = {
            "type": "state",
            "pos":     {str(k): list(v) for k, v in g.pos.items()},
            "walls":   {str(k): v for k, v in g.walls.items()},
            "h_walls": [list(w) for w in g.h_walls],
            "v_walls": [list(w) for w in g.v_walls],
            "turn":    g.turn,
            "winner":  g.check_winner(),
        }
        self._broadcast(state)

    def _broadcast(self, msg):
        for conn in self.clients.values():
            self._send(conn, msg)

    def _send(self, conn, msg):
        try:
            conn.sendall((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
        except Exception:
            pass


# ═══════════════════════════════════════════════
# エントリーポイント
# ═══════════════════════════════════════════════

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5555
    GameServer(port=port).start()


if __name__ == "__main__":
    main()
