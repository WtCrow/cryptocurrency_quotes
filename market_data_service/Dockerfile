FROM python:3.7.4-alpine
WORKDIR /usr/src/crypto_quotes

RUN apk add build-base
RUN pip install --upgrade pip

COPY requirements.txt /usr/src/crypto_quotes/
RUN pip install --no-cache-dir -r /usr/src/crypto_quotes/requirements.txt

COPY . /usr/src/crypto_quotes/

RUN adduser -D new_user
USER new_user

ENV RABBIT_MQ_STR_CONN=amqp://market_data_service:passwd_service_quotes@rabbit:5672/
ENV EXCHANGER=topic
ENV QUEUE_THIS_SERVICE=crypto_currency_ms
ENV ERROR_QUEUE=crypto_currency_ms_err
ENV ROUTING_KEY_LISTING=crypto_currency_ms_listing

CMD ["python3", "main.py"]

# export RABBIT_MQ_STR_CONN=amqp://guest:guest@172.17.0.2:5672/
# export EXCHANGER=topic
# export QUEUE_THIS_SERVICE=crypto_currency_ms
# export ERROR_QUEUE=crypto_currency_ms_err
# export ROUTING_KEY_LISTING=crypto_currency_ms_listing
