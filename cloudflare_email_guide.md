# Cloudflare Email DNS Settings

## Текущее состояние
- **SPF**: ✅ `v=spf1 include:_spf.timeweb.ru ~all`
- **DMARC**: ✅ `v=DMARC1; p=quarantine; rua=mailto:info@tokenpay.space`
- **DKIM**: ❌ **Отсутствует** — нужно добавить в Timeweb, затем добавить в Cloudflare

## Что выставить в Cloudflare

### 1. **DNS Records → Proxy Status**

Для email-записей **ОБЯЗАТЕЛЬНО** выставить **DNS only** (серый облак ☁️), НЕ proxied:

| Запись | Тип | Proxy | Примечание |
|--------|-----|-------|-----------|
| `tokenpay.space` | MX | ☁️ DNS only | Почтовый сервер |
| `_spf.tokenpay.space` | TXT | ☁️ DNS only | SPF запись |
| `_dmarc.tokenpay.space` | TXT | ☁️ DNS only | DMARC политика |
| `default._domainkey.tokenpay.space` | TXT | ☁️ DNS only | DKIM ключ (когда добавите) |

**⚠️ ВАЖНО**: Если выставить Proxied (оранжевый облак 🟠), Cloudflare будет отвечать вместо Timeweb → email не будет доставляться!

### 2. **Email Routing (если используется)**

Если в Cloudflare включено Email Routing:
- Зайти в **Email Routing** → **Routing rules**
- Убедиться, что правила не блокируют письма от `info@tokenpay.space`
- Или отключить Email Routing, если не нужно

### 3. **Firewall Rules**

Проверить, что нет правил, блокирующих SMTP:
- **Security** → **WAF** → убедиться, что нет блокировок для портов 25, 465, 587
- Обычно Cloudflare не блокирует исходящий SMTP, но проверить стоит

### 4. **SSL/TLS**

- **SSL/TLS** → **Overview** → выставить **Full** или **Full (strict)**
- Это не влияет на email напрямую, но важно для HTTPS

## Пошаговая инструкция

### Шаг 1: Проверить текущие DNS записи в Cloudflare

1. Зайти в **DNS** → **Records**
2. Найти записи:
   - `MX` для `tokenpay.space` → должна указывать на Timeweb
   - `TXT` для `_spf.tokenpay.space`
   - `TXT` для `_dmarc.tokenpay.space`

### Шаг 2: Убедиться, что они **DNS only** (☁️)

Если видите 🟠 (Proxied) — **ИЗМЕНИТЬ на ☁️ (DNS only)**:
1. Нажать на запись
2. Нажать на облако (🟠 Proxied)
3. Выбрать ☁️ DNS only
4. Сохранить

### Шаг 3: Добавить DKIM в Timeweb

1. Зайти в **Timeweb** → **Почта** → **DKIM**
2. Скопировать TXT-запись (обычно вида `v=DKIM1; k=rsa; p=MIGfMA0...`)
3. Вернуться в **Cloudflare** → **DNS** → **Add record**
   - **Type**: TXT
   - **Name**: `default._domainkey`
   - **Content**: значение из Timeweb
   - **TTL**: Auto
   - **Proxy**: ☁️ DNS only
4. Сохранить

### Шаг 4: Проверить распространение

```bash
# Проверить SPF
dig TXT _spf.tokenpay.space

# Проверить DMARC
dig TXT _dmarc.tokenpay.space

# Проверить DKIM (после добавления)
dig TXT default._domainkey.tokenpay.space

# Проверить MX
dig MX tokenpay.space
```

## Результат

После этого:
- ✅ SPF пройдёт проверку (письма от `info@tokenpay.space` авторизованы)
- ✅ DKIM пройдёт проверку (письма подписаны)
- ✅ DMARC пройдёт проверку (письма не будут в спаме)
- ✅ Письма будут доставляться во входящие

## Если письма всё ещё в спаме

1. Проверить **Timeweb** → **Почта** → **Отправленные письма** → логи
2. Проверить **MX запись** — должна указывать на Timeweb, не на Cloudflare
3. Проверить **Reverse DNS (PTR)** для IP сервера Timeweb
4. Проверить **DKIM подпись** в исходном коде письма (Headers)
