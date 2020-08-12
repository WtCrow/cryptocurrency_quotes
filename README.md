Web app for streaming cryptocurrency quotes (candlestick, bid and ask prices, market depth).
A program, that collects information, runs separately. Communicates via message queues (RabbitMQ).

You can see result on this url: https://cryptocurrency-quotes.herokuapp.com

If you want start server local, exist two way for this:

With docker and docker-compose:
1) Enter in terminal: `cd <path/to/project>`
2) Enter in terminal: `(sudo) docker-compose up`
3) Go to url: http://0.0.0.0:8080
4) Profit!

Without docker and docker-compose:
1) Install and start rabbiMQ
2) In terminal enter: `rabbitmqctl add_user main_web passwd_web`
3) In terminal enter: `rabbitmqctl set_permissions -p / main_web ".*" ".*" ".*"`
4) In terminal enter: `rabbitmqctl add_user market_data_service passwd_service_quotes`
5) In terminal enter: `rabbitmqctl set_permissions -p / market_data_service ".*" ".*" ".*"`
6) Open new terminal and enter: `cd <path/to/project>/main_app`
7) Enter in terminal: `pip install -r requirements.txt`
8) In new terminal define next env variables:
- RABBIT_MQ_STR_CONN=amqp://main_web:passwd_web@localhost:5672/
- EXCHANGER=topic_logs
- ROUTING_KEY_LISTING=crypto_currency_ms_listing
- ERROR_QUEUE=crypto_currency_ms_err
- QUEUE_SERVICE_CRYPTO_QUOTES=crypto_currency_ms
9) In new terminal enter: `python3 main.py`
10) Open new terminal and enter: `cd <path/to/project>/market_data_service`
11) Enter in terminal: `pip install -r requirements.txt`
12) In new terminal define next env variables:
- RABBIT_MQ_STR_CONN=amqp://market_data_service:passwd_service_quotes@localhost:5672/
- EXCHANGER=topic_logs
- QUEUE_THIS_SERVICE=crypto_currency_ms
- ERROR_QUEUE=crypto_currency_ms_err
- ROUTING_KEY_LISTING=crypto_currency_ms_listing
13) In new terminal enter: `python3 main.py`
14) Go to url: http://0.0.0.0:8080
15) Profit!

P. S. For this server access PyQt client from this repository: https://github.com/WtCrow/client_cryptocurrency_quotes
