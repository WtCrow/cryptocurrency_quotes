from exchanges.exchanges_connectors.okexchanges.base_ok_exchange import BaseOkExchange


class OkEx(BaseOkExchange):
    """Коннектор OKEx"""

    name = 'OKEx'

    def __init__(self, exchanger):
        super(OkEx, self).__init__('wss://real.okex.com:10442/ws/v3/', 'https://www.okex.com/api/spot/v3',
                                   exchanger)
