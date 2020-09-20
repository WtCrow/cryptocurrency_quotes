#Web app for streaming cryptocurrency quotes (candlestick, bid and ask prices, market depth).
A program, that collects information, runs separately. Communicates via message queues (RabbitMQ).

You can see result on this url: https://cryptocurrency-quotes.herokuapp.com

If you want start server local, exist two way for this:

With docker and docker-compose:
1) Enter in terminal: `cd <path/to/project>`
2) Enter in terminal: `sudo docker-compose up`
3) Go to url: http://0.0.0.0:8080
4) Profit!

Without docker and docker-compose:
1) Install and start rabbiMQ
1.1) In terminal enter: `rabbitmqctl add_user main_web passwd_web`
1.2) In terminal enter: `rabbitmqctl set_permissions -p / main_web ".*" ".*" ".*"`
1.3) In terminal enter: `rabbitmqctl add_user market_data_service passwd_service_quotes`
1.4) In terminal enter: `rabbitmqctl set_permissions -p / market_data_service ".*" ".*" ".*"`

2) Enter in terminal: `cd <path/to/project>`

3) Install nginx for static files or uncomment 13-14 lines in main_app/cryptoview/urls.py and skip substeps
3.1) Enter in terminal `sudo cp main_app/default.conf /etc/nginx/conf.d`
3.2) Enter in terminal `sudo systemctl reload nginx`

4) Start market_data_service
4.1) Enter in terminal: `cd market_data_service`
4.2) Enter in terminal: `pip3 install -r requirements.txt`
4.3) Define next environment variables (`export=`):
- RABBIT_MQ_STR_CONN=amqp://market_data_service:passwd_service_quotes@localhost:5672/
- EXCHANGER=topic_logs
- QUEUE_THIS_SERVICE=crypto_currency_ms
- ERROR_QUEUE=crypto_currency_ms_err
- ROUTING_KEY_LISTING=crypto_currency_ms_listing
4.4) Enter in terminal: `python3 main.py`

5) Start main_app
5.1) In new terminal enter: `cd <path/to/project>/main_app`
5.2) Enter in terminal: `pip3 install -r requirements.txt`
5.3) Define next environment variables (`export=`):
- RABBIT_MQ_STR_CONN=amqp://main_web:passwd_web@localhost:5672/
- EXCHANGER=topic_logs
- ROUTING_KEY_LISTING=crypto_currency_ms_listing
- ERROR_QUEUE=crypto_currency_ms_err
- QUEUE_SERVICE_CRYPTO_QUOTES=crypto_currency_ms
- PORT=8080
5.4) Enter in terminal: `python3 main.py`

6) Go to url: http://0.0.0.0:8080
7) Profit!

P. S. For this server access PyQt client from this repository: https://github.com/WtCrow/client_cryptocurrency_quotes
