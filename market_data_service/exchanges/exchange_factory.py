from .exchanges_connectors import *


class ExchangeNotExistError(Exception):

    def __init__(self):
        super().__init__()

    def __str__(self):
        return repr('This exchange not found in Factory.')


class ExchangeFactory:
    """Class for create and change exchange."""

    def __init__(self, exchanger):
        self.exchanger = exchanger
        # Classes all exchanges
        self._exchanges = [Binance, HitBTC, HuobiGlobal, Bittrex, OkCoin, OkEx]
        # Хранилище уже созданных бирж
        self._instances_exchanges = dict()

    def get_all_exchanges_names(self):
        """Return list with str names access exchanges"""
        return [item.name for item in self._exchanges]

    def create_exchange(self, name):
        """Get exchange

        If exchange exist, return exist object,
        else get class and create new object

        """
        if name not in self._instances_exchanges.keys():
            exchange = list(filter(lambda item: item.name == name, self._exchanges))
            if exchange:
                self._instances_exchanges[name] = exchange[0](exchanger=self.exchanger)
            else:
                raise ExchangeNotExistError()
        return self._instances_exchanges[name]
