from exchanges import ExchangeFactory
from exchanges.abstract_exchange import BaseExchange
from unittest import TestCase


class FactoryTests(TestCase):

    def test_create_exchange(self):
        factory = ExchangeFactory(None)

        all_exchanges_names = factory.get_all_exchanges_names()

        for name in all_exchanges_names:
            exchange = factory.create_exchange(name)
            self.assertTrue(isinstance(exchange, BaseExchange), 'Object not is exchange')
            self.assertEqual(id(exchange), id(factory.create_exchange(name)), 'Factory create new object, '
                                                                              'no return old')
            self.assertEqual(exchange.name, name, 'Name not eq name request')
