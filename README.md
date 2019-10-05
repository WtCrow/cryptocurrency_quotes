Server and site with cryptocurrency quotes.
A program, that collects information, runs separately. Communicates via message queues.

You can see result to this url: https://cryptocurrency-quotes.herokuapp.com

If you want start server local, exist two way for this:

With docker and docker-compose:
1) Enter in cmd `cd <path/to/project>`
2) Enter in cmd `docker-compose up`
3) Go to url: http://localhost:8080
4) Profit!

Without docker and docker-compose:
RabbitMQ
1) Install and start rabbimq
2) In cmd enter: `rabbitmqctl main_web web passwd_web`
3) In cmd enter: `rabbitmqctl set_permissions -p / main_web ".*" ".*" ".*"`
4) In cmd enter: `rabbitmqctl add_user market_data_service passwd_service_quotes`
5) In cmd enter: `rabbitmqctl set_permissions -p / market_data_service ".*" ".*" ".*"`

Web aggregator
6) Open new cmd and enter: `cd <path/to/project>/main_app`
7) Enter in cmd: `pip install -r requirements.txt`
8) In new cmd enter next strings:
- set RABBIT_MQ_STR_CONN=amqp://main_web:passwd_web@rabbit:5672/
- set EXCHANGER=topic_logs
- set ROUTING_KEY_LISTING=crypto_currency_ms_listing
- set ERROR_QUEUE=crypto_currency_ms_err
- set QUEUE_SERVICE_CRYPTO_QUOTES=crypto_currency_ms
9) In new cmd enter: `python(3) main.py`

Service for collects cryptocurrency quotes
10) Open new cmd and enter: `cd <path/to/project>/market_data_service`
11) Enter in cmd: `pip install -r requirements.txt`
12) In new cmd enter next strings:
- set RABBIT_MQ_STR_CONN=amqp://market_data_service:passwd_service_quotes@rabbit:5672/
- set EXCHANGER=topic_logs
- set QUEUE_THIS_SERVICE=crypto_currency_ms
- set ERROR_QUEUE=crypto_currency_ms_err
- set ROUTING_KEY_LISTING=crypto_currency_ms_listing
13) In new cmd enter: `python(3) main.py`

14) Go to url: http://localhost:8080
15) Profit!

P. S. For this server access PyQt client from this repository: https://github.com/WtCrow/client_cryptocurrency_quotes
