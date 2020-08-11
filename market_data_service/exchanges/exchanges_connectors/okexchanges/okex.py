from exchanges.exchanges_connectors.okexchanges.base_ok_exchange import BaseOkExchange


class OkEx(BaseOkExchange):
    """Коннектор OKEx"""

    name = 'OKEx'

    def __init__(self, mq_exchanger):
        super(OkEx, self).__init__('wss://real.okex.com:8443/ws/v3/', 'https://www.okex.com/api/spot/v3', mq_exchanger)
