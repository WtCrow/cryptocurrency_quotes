FROM python:3.7.4-alpine
WORKDIR /usr/src/web_app

RUN pip install --upgrade pip

COPY requirements.txt /usr/src/web_app/
RUN pip3 install --no-cache-dir -r /usr/src/web_app/requirements.txt

COPY . /usr/src/web_app/

EXPOSE 8080

CMD ["python3", "main.py"]
