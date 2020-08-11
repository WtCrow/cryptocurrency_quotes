from .exchanges_connectors import *


class ExchangeNotExistError(Exception):

    def __init__(self, exchange=None):
        self.error_exchange = exchange
        super().__init__()

    def __str__(self):
        return repr(f'{self.error_exchange} not found in Factory.')


class ExchangeFactory:
    """Class for create exchanges."""

    def __init__(self, mq_exchanger):
        self.exchanger = mq_exchanger
        # Classes all exchanges
        self._exchanges = [Binance, Bittrex, HitBTC, HuobiGlobal, OkCoin, OkEx]
        # already created exchanges instance
        self._instances_exchanges = dict()

    def get_all_exchanges_names(self):
        """Return list with str names access exchanges"""
        return [item.name for item in self._exchanges]

    def create_exchange(self, name):
        """Get exchange

        If exchange exist, return exist object,
        else get class and create new object

        """
        if not self._instances_exchanges.get(name):
            exchange = list(filter(lambda item: item.name == name, self._exchanges))
            if exchange:
                self._instances_exchanges[name] = exchange[0](mq_exchanger=self.exchanger)
            else:
                raise ExchangeNotExistError(name)
        return self._instances_exchanges[name]
