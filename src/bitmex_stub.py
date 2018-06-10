# coding: UTF-8
from src import logger
from src.bitmex import BitMex

# スタブ取引用クラス
class BitMexStub(BitMex):
    # デフォルトの残高 (0.1BTC)
    balance = 0.1 * 100000000
    # デフォルトのレベレッジ
    leverage = 1
    # 現在のポジションサイズ
    position_size = 0
    # 現在のポジション平均価格
    position_avg_price = 0
    # 注文数
    order_count = 0
    # 勝ち数
    win_count = 0
    # 負け数
    lose_count = 0
    # 勝ちの総利益
    win_profit = 0
    # 負けの総損失
    lose_loss = 0
    # 最大損失率
    max_draw_down = 0
    # 注文
    open_orders = []

    def __init__(self, threading=True):
        """
        コンストラクタ
        :param threading:
        """
        BitMex.__init__(self, threading=threading)

    def get_balance(self):
        """
        残高の取得を行う。
        :return:
        """
        return self.balance

    def get_leverage(self):
        """
        レバレッジの取得する。
        :return:
        """
        return self.leverage

    def get_position_size(self):
        """
         現在のポジションサイズを取得する。
         :return:
         """
        return self.position_size

    def get_position_avg_price(self):
        """
        現在のポジションの平均価格を取得する。
        :return:
        """
        return self.position_avg_price

    def cancel_all(self):
        """
        すべての注文をキャンセルする。
        """
        self.open_orders = []

    def close_all(self):
        """
        すべてのポジションを解消する。
        """
        pos_size = self.position_size
        if pos_size > 0:
            self.entry("CLOSE", False, abs(pos_size))
        elif pos_size < 0:
            self.entry("CLOSE", True, abs(pos_size))

    def cancel(self, id):
        """
        注文をキャンセルする。
        :param long: ロング or ショート
        :return:
        """
        self.open_orders = [o for o in self.open_orders if o["id"] != id]

    def entry(self, id, long, qty, limit=0, stop=0, when=True):
        """
        注文をする。pineの関数と同等の機能。
        https://jp.tradingview.com/study-script-reference/#fun_strategy{dot}entry
        :param id: 注文の番号
        :param long: ロング or ショート
        :param qty: 注文量
        :param limit: 指値
        :param stop: ストップ指値
        :param when: 注文するか
        :return:
        """
        if not when:
            return

        pos_size = self.get_position_size()

        if long and pos_size > 0:
            return

        if not long and pos_size < 0:
            return

        self.cancel(id)
        ord_qty = qty + abs(pos_size)

        if limit > 0 or stop > 0:
            self.open_orders.append({"id": id, "long": long, "qty": ord_qty, "limit": limit, "stop": stop})
        else:
            self.commit(id, long, ord_qty, self.get_market_price())
            return

    def commit(self, id, long, qty, price):
        """
        約定する。
        :param id: 注文番号
        :param long: ロング or ショート
        :param qty: 注文量
        :param price: 価格
        """
        self.order_count += 1

        order_qty = qty if long else -qty
        next_qty = self.position_size + order_qty

        if (self.position_size > 0 >= order_qty) or (self.position_size < 0 < order_qty):
            if self.position_avg_price > price:
                close_rate = ((
                              self.position_avg_price - price) / price - self.get_commission()) * self.get_leverage()
                profit = -1 * self.position_size * close_rate
            else:
                close_rate = ((
                              price - self.position_avg_price) / self.position_avg_price - self.get_commission()) * self.get_leverage()
                profit = self.position_size * close_rate

            if profit > 0:
                self.win_profit += profit/self.get_market_price()*100000000
                self.win_count += 1
            else:
                self.lose_loss += -1 * profit/self.get_market_price()*100000000
                self.lose_count += 1
                if close_rate > self.max_draw_down:
                    self.max_draw_down = close_rate

            self.balance += profit/self.get_market_price()*100000000

            if self.enable_trade_log:
                logger.info(f"========= Close Position =============")
                logger.info(f"TRADE COUNT   : {self.order_count}")
                logger.info(f"POSITION SIZE : {self.position_size}")
                logger.info(f"ENTRY PRICE   : {self.position_avg_price}")
                logger.info(f"EXIT PRICE    : {price}")
                logger.info(f"PROFIT        : {profit}")
                logger.info(f"BALANCE       : {self.get_balance()}")
                logger.info(f"WIN RATE      : {0 if self.order_count == 0 else self.win_count/self.order_count*100} %")
                logger.info(f"PROFIT FACTOR : {self.win_profit if self.lose_loss == 0 else self.win_profit/self.lose_loss}")
                logger.info(f"MAX DRAW DOWN : {self.max_draw_down * 100}")
                logger.info(f"======================================")

        if next_qty != 0:
            if self.enable_trade_log:
                logger.info(f"********* Create Position ************")
                logger.info(f"TIME          : {self.now_time()}")
                logger.info(f"PRICE         : {price}")
                logger.info(f"TRADE COUNT   : {self.order_count}")
                logger.info(f"ID            : {id}")
                logger.info(f"POSITION SIZE : {qty}")
                logger.info(f"**************************************")

            self.position_size = next_qty
            self.position_avg_price = price
        else:
            self.position_size = 0
            self.position_avg_price = 0

    def on_update(self, bin_size, listener):
        """
        戦略の関数を登録する。
        :param listener:
        """
        def __override_listener(open, close, high, low):
            new_open_orders = []

            for _, order in enumerate(self.open_orders):
                id = order["id"]
                long = order["long"]
                qty = order["qty"]
                limit = order["limit"]
                stop = order["stop"]

                if limit > 0 and stop > 0:
                    if (long and high[-1] > stop and close[-1] < limit) or (not long and low[-1] < stop and close[-1] > limit):
                        self.commit(id, long, qty, limit)
                        continue
                    elif (long and high[-1] > stop) or (not long and low[-1] < stop):
                        new_open_orders.append({"id": id, "long": long, "qty": qty, "limit": limit, "stop": 0})
                        continue
                elif limit > 0:
                    if (long and low[-1] < limit) or (not long and high[-1] > limit):
                        self.commit(id, long, qty, limit)
                        continue
                elif stop > 0:
                    if (long and high[-1] > stop) or (not long and low[-1] < stop):
                        self.commit(id, long, qty, stop)
                        continue

                new_open_orders.append(order)

            self.open_orders = new_open_orders
            listener(open, close, high, low)

        BitMex.on_update(self, bin_size, __override_listener)