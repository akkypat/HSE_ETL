# Инструкция: ML-прогноз температуры (LightGBM)
## DAG `ml_forecast` + панель Grafana

---

## Содержание

1. [Установка LightGBM в контейнер](#1-установка-lightgbm-в-контейнер)
2. [Копирование DAG](#2-копирование-dag)
3. [Запуск и проверка](#3-запуск-и-проверка)
4. [Проверка данных в БД](#4-проверка-данных-в-бд)
5. [Панель прогноза в Grafana](#5-панель-прогноза-в-grafana)
6. [Как читать результаты](#6-как-читать-результаты)
7. [Частые ошибки](#7-частые-ошибки)

---

## 1. Установка LightGBM в контейнер

### Шаг 1 — Добавить в requirements.txt

Открой `C:\weather_pipeline\requirements.txt` и добавь строку:

```
lightgbm==4.3.0
```

Итоговый файл должен выглядеть так:

```
requests==2.31.0
psycopg2-binary==2.9.9
apache-airflow-providers-postgres==5.10.2
apache-airflow-providers-http==4.10.1
lightgbm==4.3.0
```

### Шаг 2 — Также нужен pandas и numpy (проверь)

Добавь если их нет:

```
pandas==2.2.2
numpy==1.26.4
```

### Шаг 3 — Пересобрать контейнеры Airflow

```powershell
cd C:\weather_pipeline
docker compose up -d --build airflow-worker airflow-scheduler
```

Первый раз займёт **3–5 минут** (скачивание и установка LightGBM).

### Шаг 4 — Проверить установку

```powershell
docker exec weather_airflow_worker python -c "import lightgbm; print(lightgbm.__version__)"
```

Ожидаемый вывод: `4.3.0`

---

## 2. Копирование DAG

Скопируй файл `ml_forecast.py` в папку DAG:

```powershell
copy ml_forecast.py C:\weather_pipeline\dags\
```

Подожди 30 секунд — Airflow подхватит DAG автоматически.

Проверь что DAG появился в Airflow UI: http://localhost:8080

Найди **`ml_forecast`** в списке. DAG будет отключён по умолчанию.

---

## 3. Запуск и проверка

### Шаг 1 — Активировать DAG

В Airflow UI найди `ml_forecast` → нажми переключатель слева (станет синим).

### Шаг 2 — Запустить вручную

Нажми **▶ Trigger DAG** для немедленного запуска.

### Шаг 3 — Следить за выполнением

Нажми на имя DAG → откроется **Graph View**.

Ожидаемый порядок выполнения:

```
ensure_infrastructure
        ↓
[forecast_1] [forecast_2] ... [forecast_8]   ← параллельно
        ↓
log_forecast_summary
```

Время выполнения: **3–8 минут** (зависит от объёма данных).

### Шаг 4 — Посмотреть метрики в логах

Нажми на задачу `log_forecast_summary` → **Log**. Увидишь таблицу:

```
═══════════════════════════════════════════════════
       СВОДКА ML-ПРОГНОЗА ТЕМПЕРАТУРЫ (LightGBM)
═══════════════════════════════════════════════════
Город                RMSE    MAE     R²    Строк
───────────────────────────────────────────────────
Москва               1.84°  1.31°  0.962    8543
Санкт-Петербург      2.01°  1.44°  0.954    8541
Екатеринбург         2.23°  1.58°  0.948    8540
...
```

**Хорошие метрики для прогноза погоды:**
- RMSE < 3°C — отличная точность
- RMSE 3–5°C — приемлемая точность
- R² > 0.90 — модель хорошо объясняет дисперсию

---

## 4. Проверка данных в БД

```powershell
docker exec -it weather_pg_data psql -U weather_user -d weather_db
```

**Проверь что прогнозы записались:**

```sql
SELECT d.city_name,
       COUNT(*) AS forecast_points,
       MIN(target_at) AS from_time,
       MAX(target_at) AS to_time
FROM mart_forecast f
JOIN dim_station d ON f.station_id = d.station_id
GROUP BY d.city_name
ORDER BY d.city_name;
```

Должно вернуть 8 строк с `forecast_points = 24`.

**Посмотри прогноз для Москвы:**

```sql
SELECT
    target_at AT TIME ZONE 'Europe/Moscow' AS время_мск,
    ROUND(temperature_c::NUMERIC, 1)       AS прогноз_с
FROM mart_forecast
WHERE station_id = 1
  AND forecast_at = (SELECT MAX(forecast_at) FROM mart_forecast WHERE station_id = 1)
ORDER BY target_at;
```

**Посмотри метрики моделей:**

```sql
SELECT city_name,
       ROUND(rmse::NUMERIC, 2) AS rmse_c,
       ROUND(mae::NUMERIC, 2)  AS mae_c,
       ROUND(r2::NUMERIC, 3)   AS r2,
       train_rows,
       trained_at::DATE        AS дата_обучения
FROM ml_model_metrics
ORDER BY trained_at DESC, city_name;
```

Выход из psql:
```sql
\q
```

---

## 5. Панель прогноза в Grafana

### Шаг 1 — Открыть дашборд

http://localhost:3000 → **Weather Overview — Russia** → **Edit** (карандаш вверху)

### Шаг 2 — Добавить панель

Нажми **Add** → **Visualization**

Тип панели: **Time series**

Заголовок:
```
🤖 Прогноз температуры на 24 часа (LightGBM)
```

### Шаг 3 — Запрос А: фактические данные (последние 48 часов)

Вставь в поле запроса:

```sql
SELECT
    bucket                                    AS time,
    ROUND(avg_temperature_c::NUMERIC, 1)      AS value,
    d.city_name                               AS metric
FROM mart_hourly_weather h
JOIN dim_station d ON h.station_id = d.station_id
WHERE h.bucket > NOW() - INTERVAL '48 hours'
  AND h.bucket <= NOW()
ORDER BY h.bucket, d.city_name
```

- Format: `Time series`
- Legend: оставь пустым (metric подставится автоматически)

### Шаг 4 — Запрос B: прогнозные данные

Нажми **+ Add query** и вставь:

```sql
SELECT
    target_at                                 AS time,
    ROUND(f.temperature_c::NUMERIC, 1)        AS value,
    d.city_name || ' (прогноз)'               AS metric
FROM mart_forecast f
JOIN dim_station d ON f.station_id = d.station_id
WHERE f.forecast_at = (
    SELECT MAX(forecast_at) FROM mart_forecast
)
ORDER BY f.target_at, d.city_name
```

- Format: `Time series`

### Шаг 5 — Настроить стиль прогнозной линии

В правой панели → **Overrides** → **Add field override**:

- Поле: `Fields with name matching regex` → введи `.*прогноз.*`
- Добавь свойство: **Line style** → `Dashes`
- Добавь свойство: **Line width** → `2`
- Добавь свойство: **Fill opacity** → `0`

Это сделает прогнозные линии пунктирными — визуально отличными от факта.

### Шаг 6 — Настроить временной диапазон панели

В правой панели → **Panel options** → **Relative time**: `now-2d` to `now+1d`

Это фиксирует диапазон панели независимо от глобального фильтра дашборда.

### Шаг 7 — Добавить вертикальную линию «сейчас»

В правой панели → **Annotations** (или через меню дашборда):

Dashboard settings (шестерёнка) → **Annotations** → **Add annotation query**:

| Поле | Значение |
|---|---|
| Name | `Текущий момент` |
| Color | `red` |
| Query | `SELECT NOW() AS time, 'Сейчас' AS text` |

Это добавит красную вертикальную линию разделяющую факт и прогноз.

### Шаг 8 — Добавить панель метрик качества

Добавь ещё одну панель → тип **Table** → заголовок:

```
📊 Точность ML-моделей (последнее обучение)
```

SQL:

```sql
SELECT
    city_name                          AS "Город",
    ROUND(rmse::NUMERIC, 2)            AS "RMSE °C",
    ROUND(mae::NUMERIC, 2)             AS "MAE °C",
    ROUND(r2::NUMERIC, 3)              AS "R²",
    train_rows                         AS "Строк обучения",
    trained_at::DATE                   AS "Дата обучения"
FROM ml_model_metrics
WHERE trained_at = (SELECT MAX(trained_at) FROM ml_model_metrics)
ORDER BY rmse ASC
```

Format: `Table`

В **Overrides** добавь для поля `R²`:
- **Cell display mode** → `Color background`
- **Thresholds**: 0.85 → Yellow, 0.93 → Green

### Шаг 9 — Сохранить дашборд

**Apply** → **Save dashboard** (Ctrl+S)

### Шаг 10 — Экспортировать обновлённый дашборд

Чтобы изменения сохранились после `docker compose down -v`:

Share (↑) → **Export** → **Save to file** → сохрани как:
```
C:\weather_pipeline\grafana\provisioning\dashboards\weather_overview.json
```

---

## 6. Как читать результаты

**На графике** увидишь:
- **Сплошные линии** — фактические данные за последние 48 часов
- **Пунктирные линии** — прогноз на следующие 24 часа
- **Красная вертикальная черта** — текущий момент

**Пример интерпретации метрик:**

| Метрика | Значение | Интерпретация |
|---|---|---|
| RMSE = 1.84°C | Хорошо | Средняя ошибка ~2°C — приемлемо для суточного прогноза |
| MAE = 1.31°C | Хорошо | В среднем прогноз ошибается на ~1.3°C |
| R² = 0.962 | Отлично | Модель объясняет 96% дисперсии температуры |

**Для диплома:** RMSE модели LightGBM на реальных данных обычно составляет 1.5–3°C для горизонта 1–24 часа, что сопоставимо с точностью численных прогнозов погоды (NWP) на коротких горизонтах.

---

## 7. Частые ошибки

### ❌ `ModuleNotFoundError: No module named 'lightgbm'`

LightGBM не установился в контейнер. Выполни:

```powershell
docker compose up -d --build airflow-worker airflow-scheduler
docker exec weather_airflow_worker python -c "import lightgbm; print('OK')"
```

---

### ❌ `skipped — мало данных: N строк`

В `mart_hourly_weather` меньше 720 строк для города. Нужно сначала запустить `historical_backfill` чтобы заполнить архив.

---

### ❌ Прогнозные линии не отображаются в Grafana

Проверь что данные есть в таблице:

```powershell
docker exec -it weather_pg_data psql -U weather_user -d weather_db -c "
SELECT COUNT(*) FROM mart_forecast WHERE target_at > NOW();
"
```

Если 0 — DAG ещё не запускался или завершился с ошибкой. Проверь логи в Airflow UI.

---

### ❌ Прогноз выглядит неправдоподобно (экстремальные значения)

Это может происходить при rolling forecast на дальних шагах (18–24 ч) — ошибки накапливаются. Это нормально для ML-моделей без дополнительных данных. Для повышения точности можно уменьшить горизонт до 12 часов: в файле `ml_forecast.py` измени `FORECAST_HOURS = 12`.

---

## Скриншоты для диплома

| № | Что снимать | Где |
|---|---|---|
| 17 | DAG `ml_forecast` — все TaskGroup зелёные | Airflow UI → Graph |
| 18 | Лог `log_forecast_summary` с таблицей метрик RMSE/MAE/R² | Airflow UI → Task Log |
| 19 | График прогноза (факт + пунктир прогноза) | Grafana → Weather Overview |
| 20 | Таблица точности моделей по городам | Grafana → Weather Overview |
