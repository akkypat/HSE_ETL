# Инструкция по настройке Grafana
## Пункты 2 (аномалии), 3 (алерты), 8 (геокарта)

Все SQL-объекты создаются автоматически DAG-ами.
Вручную выполнять SQL не нужно.

---

## Пункт 2 — Панель аномалий температуры

### Шаг 1 — Открыть дашборд

Открой http://localhost:3000 → **Dashboards** → **Weather Overview — Russia**

### Шаг 2 — Добавить панель

Нажми значок **+** в правом верхнем углу дашборда → **Add visualization**

### Шаг 3 — Настроить панель

**Тип панели** (правый верхний угол): выбери **Table**

**Заголовок**: вставь в поле Title справа:
```
🔴 Аномалии температуры (> 3σ от среднего за 30 дней)
```

**SQL-запрос** — вставь в поле запроса внизу:

```sql
WITH stats AS (
    SELECT station_id,
           AVG(avg_temperature_c)    AS mean_t,
           STDDEV(avg_temperature_c) AS std_t
    FROM mart_hourly_weather
    WHERE bucket > NOW() - INTERVAL '30 days'
    GROUP BY station_id
    HAVING STDDEV(avg_temperature_c) > 0
)
SELECT
    d.city_name                                              AS "Город",
    h.bucket                                                 AS "Время",
    ROUND(h.avg_temperature_c::NUMERIC, 1)                  AS "Температура °C",
    ROUND(s.mean_t::NUMERIC, 1)                             AS "Среднее °C",
    ROUND(ABS(h.avg_temperature_c - s.mean_t) / s.std_t, 1) AS "Отклонение σ"
FROM mart_hourly_weather h
JOIN stats s ON h.station_id = s.station_id
JOIN dim_station d ON h.station_id = d.station_id
WHERE $__timeFilter(h.bucket)
  AND ABS(h.avg_temperature_c - s.mean_t) / s.std_t > 3
ORDER BY "Отклонение σ" DESC
LIMIT 50
```

Убедись что в поле **Format** выбрано `Table`

### Шаг 4 — Настроить цветовую шкалу

В правой панели найди раздел **Overrides** → **Add field override** →
выбери поле **Отклонение σ** → добавь свойство **Cell display mode** → `Color background`

Добавь **Thresholds**:
- `3.0` → 🟡 Yellow
- `4.0` → 🔴 Red

### Шаг 5 — Сохранить

Нажми **Apply** (правый верхний угол) → **Save dashboard** (Ctrl+S)

---

## Пункт 3 — Алерты в Grafana

### Алерт 1: «Нет свежих данных»

**Шаг 1** — Меню слева → **Alerting** → **Alert rules** → **New alert rule**

**Шаг 2** — Заполни поля:

| Поле | Значение |
|---|---|
| Rule name | `Нет свежих данных по городу` |
| Folder | нажми New folder → введи `Weather` → Create |
| Group | введи `pipeline-health` |

**Шаг 3** — В разделе **Define query and alert condition**:

- Источник данных: **WeatherDB**
- Нажми **Code** (переключатель над полем запроса)
- Вставь SQL:

```sql
SELECT
    d.city_name AS metric,
    ROUND(
        EXTRACT(EPOCH FROM (NOW() - MAX(o.observed_at))) / 3600.0,
        1
    ) AS value
FROM staging_observations o
JOIN dim_station d ON o.station_id = d.station_id
GROUP BY d.city_name
HAVING MAX(o.observed_at) < NOW() - INTERVAL '2 hours'
```

- Format: `Time series`

**Шаг 4** — В разделе **Alert condition**:

- Condition: `IS ABOVE` → значение `0`
- Evaluate every: `5m`
- For: `5m`

**Шаг 5** — В разделе **Configure labels and notifications**:

- Severity: `critical`
- Contact point: `grafana-default-email` (или настрой Telegram — см. ниже)

**Шаг 6** — Нажми **Save rule and exit**

---

### Алерт 2: «Экстремальный мороз (< −35°C)»

**Alerting → Alert rules → New alert rule**

| Поле | Значение |
|---|---|
| Rule name | `Экстремальный мороз` |
| Folder | `Weather` |
| Group | `weather-extremes` |

SQL:

```sql
SELECT
    d.city_name AS metric,
    MIN(o.temperature_c) AS value
FROM staging_observations o
JOIN dim_station d ON o.station_id = d.station_id
WHERE o.observed_at > NOW() - INTERVAL '1 hour'
  AND o.temperature_c < -35
  AND o.qc_flag = 0
GROUP BY d.city_name
```

- Condition: `IS BELOW` → `-35`
- Evaluate every: `10m`, For: `20m`

Нажми **Save rule and exit**

---

### Алерт 3: «Штормовой ветер (> 20 м/с)»

| Поле | Значение |
|---|---|
| Rule name | `Штормовой ветер` |
| Folder | `Weather` |
| Group | `weather-extremes` |

SQL:

```sql
SELECT
    d.city_name AS metric,
    MAX(o.wind_speed_ms) AS value
FROM staging_observations o
JOIN dim_station d ON o.station_id = d.station_id
WHERE o.observed_at > NOW() - INTERVAL '1 hour'
  AND o.wind_speed_ms > 20
  AND o.qc_flag = 0
GROUP BY d.city_name
```

- Condition: `IS ABOVE` → `20`
- Evaluate every: `10m`, For: `10m`

Нажми **Save rule and exit**

---

### Настройка уведомлений в Telegram

**Шаг 1** — Создай бота:

1. Напиши `@BotFather` в Telegram
2. Отправь `/newbot`
3. Введи имя бота (например `WeatherAlertBot`)
4. Скопируй **токен** вида `7123456789:AAF...`

**Шаг 2** — Узнай свой Chat ID:

1. Напиши боту `@userinfobot` → `/start`
2. Скопируй число из поля **Id** (например `123456789`)

**Шаг 3** — Добавь Contact Point в Grafana:

Меню → **Alerting** → **Contact points** → **Add contact point**

| Поле | Значение |
|---|---|
| Name | `Telegram Weather` |
| Integration | `Telegram` |
| BOT API Token | вставь токен из шага 1 |
| Chat ID | вставь число из шага 2 |

Нажми **Test** → в Telegram придёт тестовое сообщение.

Нажми **Save contact point**

**Шаг 4** — Привяжи к алертам:

Открой каждый из трёх созданных алертов → поле **Contact point** → выбери `Telegram Weather` → Save

---

## Пункт 8 — Геокарта с маркерами городов

### Шаг 1 — Добавить панель

Дашборд → **+** → **Add visualization**

Тип панели: **Geomap**

Заголовок:
```
🗺 Текущая погода по городам России
```

### Шаг 2 — SQL-запрос

Вставь в поле запроса:

```sql
SELECT
    d.latitude,
    d.longitude,
    d.city_name                         AS name,
    ROUND(o.temperature_c::NUMERIC, 1)  AS temperature_c,
    ROUND(o.wind_speed_ms::NUMERIC, 1)  AS wind_speed_ms,
    ROUND(o.humidity_pct::NUMERIC, 0)   AS humidity_pct,
    ROUND(o.pressure_hpa::NUMERIC, 0)   AS pressure_hpa
FROM staging_observations o
JOIN dim_station d ON o.station_id = d.station_id
WHERE o.observed_at = (
    SELECT MAX(o2.observed_at)
    FROM staging_observations o2
    WHERE o2.station_id = o.station_id
      AND o2.qc_flag = 0
)
ORDER BY d.city_name
```

Format: **Table**

### Шаг 3 — Настройка Geomap

В правой панели найди раздел **Map layers**:

**Layer 1** (уже существует):
- Layer type: `Markers`
- нажми на иконку карандаша слева от Layer 1

В настройках слоя:

| Параметр | Значение |
|---|---|
| Data | выбери запрос A |
| Location Mode | `Coords` |
| Latitude field | `latitude` |
| Longitude field | `longitude` |
| Size | `Fixed value` → `10` |
| Color | выбери поле `temperature_c` |
| Color scheme | `Blue-Yellow-Red (by value)` |
| Min | `-30` |
| Max | `35` |

В разделе **Tooltip** включи все поля.

### Шаг 4 — Начальный вид карты

В правой панели → раздел **Map view**:

| Параметр | Значение |
|---|---|
| View | `Fit to data` |

Или задай вручную:
| Параметр | Значение |
|---|---|
| Latitude | `62` |
| Longitude | `95` |
| Zoom | `3` |

### Шаг 5 — Сохранить

Нажми **Apply** → **Save dashboard** (Ctrl+S)

---

## Итоговый чеклист

| Пункт | Что проверить | Статус |
|---|---|---|
| 2 | Панель «Аномалии» появилась на дашборде | ☐ |
| 3 | Три правила алертов в Alerting → Alert rules | ☐ |
| 3 | Telegram получает тестовое сообщение | ☐ |
| 8 | Геокарта показывает 8 маркеров на карте России | ☐ |

После добавления всех панелей нажми **Save dashboard** и сделай скриншоты для диплома.
