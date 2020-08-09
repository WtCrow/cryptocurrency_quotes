FROM python:3.7.4-alpine
WORKDIR /usr/src/crypto_quotes

RUN apk add build-base
RUN pip install --upgrade pip

COPY requirements.txt /usr/src/crypto_quotes/
RUN pip install --no-cache-dir -r /usr/src/crypto_quotes/requirements.txt

COPY . /usr/src/crypto_quotes/

RUN adduser -D new_user
USER new_user

CMD ["python3", "main.py"]

