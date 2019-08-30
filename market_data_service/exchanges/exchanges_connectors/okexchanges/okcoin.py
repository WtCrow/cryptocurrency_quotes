from exchanges.exchanges_connectors.okexchanges.base_ok_exchange import BaseOkExchange


class OkCoin(BaseOkExchange):
    """Коннектор OkCoin"""

    name = 'OkСoin'

    def __init__(self, exchanger):
        super(OkCoin, self).__init__('wss://real.okcoin.com:10442/ws/v3/', 'https://www.okcoin.com/api/spot/v3',
                                     exchanger)
