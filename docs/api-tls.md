# HTTPS/TLS для REST API (#175)

## Вариант 1 — reverse-proxy (рекомендуется)

Waitress (прод-сервер MIA-ScreenCapture) слушает HTTP; TLS терминируется
прокси. Это прод-паттерн: приложение остаётся на waitress, а прокси берёт
на себя шифрование, keep-alive и ограничение доступа.

### nginx

```nginx
server {
    listen 8443 ssl;
    server_name mia.example.local;

    ssl_certificate     /etc/ssl/certs/mia.pem;
    ssl_certificate_key /etc/ssl/private/mia.key;
    ssl_protocols       TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        # WebSocket (/ws) требует Upgrade-заголовков
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

При прокси включите в `config/config.json` доверие заголовкам
(иначе rate limiter будет лимитировать IP прокси, а не клиентов):

```json
{ "api": { "trust_proxy_headers": true } }
```

### Caddy (авто-сертификаты, включая self-signed для LAN)

```
mia.example.local {
    tls internal
    reverse_proxy 127.0.0.1:5000
}
```

`tls internal` сам создаёт и продлевает локальный CA — самый простой путь
получить доверенный HTTPS внутри домашней сети.

## Вариант 2 — встроенный HTTPS одним флагом

Waitress принципиально не поддерживает TLS, поэтому при
`api.tls_enabled = true` MIA-ScreenCapture запускает API на werkzeug
(threaded) с указанным сертификатом:

```json
{
    "api": {
        "enabled": true,
        "host": "0.0.0.0",
        "port": 5000,
        "tls_enabled": true,
        "tls_cert_path": "C:/certs/mia.pem",
        "tls_key_path": "C:/certs/mia.key"
    }
}
```

- Компромисс: сервер меняется с waitress на werkzeug — документированное
  и осознанное решение для сценария «TLS без прокси».
- Без указанных файлов сервер не запустится (понятная ошибка в логах).
- Генерация самоподписанного сертификата (openssl):

```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
    -keyout mia.key -out mia.pem \
    -subj "/CN=mia.local" -addext "subjectAltName=DNS:mia.local,IP:127.0.0.1"
```

- Для WebSocket-клиентов используйте `wss://`.

## Что выбрать

- Доступ из LAN, есть сервер/роутер с Linux → **reverse-proxy** (Вариант 1).
- Нужно «включил и работает» без прокси → **Вариант 2**.
- Только localhost → TLS не нужен: изолированный loopback + API-ключ
  уже защищают сценарий по умолчанию.
