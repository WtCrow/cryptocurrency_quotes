FROM python:3.7.4-alpine
WORKDIR /usr/src/crypto_quotes

RUN apk add build-base
RUN pip install --upgrade pip

COPY requirements.txt /usr/src/crypto_quotes/
RUN pip install --no-cache-dir -r /usr/src/crypto_quotes/requirements.txt

COPY . /usr/src/crypto_quotes/

ENV RABBIT_MQ_STR_CONN=amqp://market_data_service:passwd_service_quotes@rabbit:5672/
ENV EXCHANGER=topic
ENV QUEUE_THIS_SERVICE=crypto_currency_ms
ENV ERROR_QUEUE=crypto_currency_ms_err
ENV ROUTING_KEY_LISTING=crypto_currency_ms_listing

CMD ["python3", "main.py"]
