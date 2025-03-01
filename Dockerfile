FROM python:3.11

WORKDIR /opt/app

COPY requirements.txt .
RUN pip install --requirement requirements.txt

COPY . .

ARG VERSION_STRING
ENV VERSION_STRING=$VERSION_STRING

ENV FLASK_APP=isacc_messaging.app:create_app() \
    PORT=8000

EXPOSE "${PORT}"

CMD flask upgrade && gunicorn --bind "0.0.0.0:${PORT:-8000}" ${FLASK_APP}
