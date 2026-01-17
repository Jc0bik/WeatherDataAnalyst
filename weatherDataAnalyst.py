import json
import pandas as pd
import numpy as np

"""
Przypisanie wartości danym pogodowym

Metodologia: ranking temperatury jest zależny od pory roku na danej półkuli 
- w zimę optimum temperatury wynosi 10 stopni, a tolerancja 8, w lato - 22 i 10,
w inne pory roku 15 i 10. Jeśli wartość temperatury różni się od optimum o więcej 
niż wynosi tolerancja, to wynik wynosi 0, w innych przypadkach dostaje punkty od 0 do 1.

Pozostałe czynniki są niezależne od pór roku:
- dla wilgotności optimum to 50, a tolerancja wynosi 30,
- dla prędkości wiatru optimum to 0, a tolerancja wynosi 70,
- dla opadów optimum to 0, a tolerancja wynosi 5,
- dla zachmurzenia optimum to 0, a tolerancja wynosi 90
"""


def temperature_score_seasonal(t, month, lat):
    north = lat >= 0

    if north:
        winter = [12, 1, 2]
        summer = [6, 7, 8]
    else:
        winter = [6, 7, 8]
        summer = [12, 1, 2]

    if month in winter:
        optimum = 10
        tolerance = 8
    elif month in summer:
        optimum = 22
        tolerance = 10
    else:
        optimum = 15
        tolerance = 10

    score = 1 - abs(t - optimum) / tolerance
    return np.clip(score, 0, 1)


def humidity_score(h):
    return np.clip(1 - abs(h - 50) / 30, 0, 1)


def wind_score(w):
    return np.clip(1 - w / 70, 0, 1)


def precipitation_score(p):
    return 1 if p == 0 else np.clip(1 - p / 5, 0, 1)


def cloud_score(c):
    return np.clip(1 - c / 90, 0, 1)


def calculate_all_rankings(data_json_path):
    """
    Wczytaj dane z JSON i oblicz wszystkie rankingi
    
    Zwraca słownik z następującymi kluczami:
    - ranking: główny ranking miast
    - city_stats: statystyki pogodowe po miastach
    - daily_ranking: ranking na każdy dzień
    - top3_per_day: top 3 miasta na każdy dzień
    - best_city_per_day: najlepsze miasto na każdy dzień
    """
    # Wczytanie danych
    with open(data_json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    rows = []
    for city_block in raw["capitals_weather_cleaned"]:
        city = city_block["metadata"]["city"]
        country = city_block["metadata"]["country"]

        for i in city_block["cleaned_hourly_rows"]:
            rows.append({
                "city": city,
                "country": country,
                "latitude": city_block["metadata"]["lat"],
                "time": i["time"],
                "temperature": i["temperature_2m"],
                "humidity": i["relative_humidity_2m"],
                "precipitation": i["precipitation"],
                "wind": i["wind_speed_10m"],
                "clouds": i["cloud_cover"],
            })

    # main_table
    main_table = pd.DataFrame(rows)
    main_table["time"] = pd.to_datetime(main_table["time"])
    main_table["date"] = main_table["time"].dt.date

    # Statystyki po miastach
    city_stats = (
        main_table.groupby(["country", "city"])
        .agg(
            avg_temperature=("temperature", "mean"),
            max_temperature=("temperature", "max"),
            min_temperature=("temperature", "min"),
            avg_humidity=("humidity", "mean"),
            max_humidity=("humidity", "max"),
            min_humidity=("humidity", "min"),
            avg_wind=("wind", "mean"),
            max_wind=("wind", "max"),
            avg_precipitation=("precipitation", "mean"),
            total_precipitation=("precipitation", "sum"),
            avg_clouds=("clouds", "mean"),
        )
        .reset_index()
    )
    city_stats = city_stats.round(2)

    # main_table_day - tylko godziny dzienne (7-22)
    main_table_day = main_table[
        (main_table["time"].dt.hour >= 7) &
        (main_table["time"].dt.hour <= 22)
    ].copy()

    # Obliczenie score'ów
    main_table_day["temperature_score"] = main_table_day.apply(
        lambda r: temperature_score_seasonal(
            r["temperature"],
            r["time"].month,
            r["latitude"]
        ),
        axis=1
    )

    # Indeks komfortu
    main_table_day["comfort_index"] = (
        0.35 * main_table_day["temperature_score"] +
        0.20 * main_table_day["humidity"].apply(humidity_score) +
        0.20 * main_table_day["precipitation"].apply(precipitation_score) +
        0.15 * main_table_day["wind"].apply(wind_score) +
        0.10 * main_table_day["clouds"].apply(cloud_score)
    )

    # Główny ranking
    ranking = (
        main_table_day.groupby("city")["comfort_index"]
        .mean()
        .sort_values(ascending=False)
        .reset_index()
    )
    ranking["Pozycja"] = range(1, len(ranking) + 1)
    ranking = ranking.rename(columns={"city": "Miasto", "comfort_index": "Indeks komfortu"})
    ranking = ranking[["Pozycja", "Miasto", "Indeks komfortu"]]
    ranking["Indeks komfortu"] = ranking["Indeks komfortu"].round(3)

    # Daily ranking
    daily_ranking = (
        main_table_day.groupby(["date", "city"])["comfort_index"]
        .mean()
        .reset_index()
        .sort_values(["date", "comfort_index"], ascending=[True, False])
    )
    daily_ranking.columns = ["Data", "Miasto", "Indeks komfortu"]
    daily_ranking["Indeks komfortu"] = daily_ranking["Indeks komfortu"].round(3)
    daily_ranking["Data"] = daily_ranking["Data"].astype(str)

    # Top 3 na dzień
    top3_per_day = (
        daily_ranking
        .groupby("Data")
        .head(3)
        .reset_index(drop=True)
    )

    # Najlepsze miasto na dzień
    best_city_per_day = (
        daily_ranking
        .groupby("Data")
        .first()
        .reset_index()
    )

    return {
        "ranking": ranking,
        "city_stats": city_stats,
        "daily_ranking": daily_ranking,
        "top3_per_day": top3_per_day,
        "best_city_per_day": best_city_per_day,
    }


def main():
    # Wczytanie danych
    with open("weather_data/open_meteo_all_capitals_CLEANED.json", "r", encoding="utf-8") as f:
        raw = json.load(f)

    rows = []
    for city_block in raw["capitals_weather_cleaned"]:
        city = city_block["metadata"]["city"]
        country = city_block["metadata"]["country"]

        for i in city_block["cleaned_hourly_rows"]:
            rows.append({
                "city": city,
                "country": country,
                "latitude": city_block["metadata"]["lat"],
                "time": i["time"],
                "temperature": i["temperature_2m"],
                "humidity": i["relative_humidity_2m"],
                "precipitation": i["precipitation"],
                "wind": i["wind_speed_10m"],
                "clouds": i["cloud_cover"],
                "comfort_index": None,
            })

    # main_table - tabela zawierająca dane pogodowe z podziałem na miasta i godziny
    main_table = pd.DataFrame(rows)
    main_table["time"] = pd.to_datetime(main_table["time"])
    main_table["date"] = main_table["time"].dt.date

    # tabela zawierające średnie, maksymalne, minimalne lub sumaryczne wartości
    # spośród 16 prognozowanych dni z podziałem na miasta
    city_stats = (
        main_table.groupby(["country", "city"])
        .agg(
            avg_temperature=("temperature", "mean"),
            max_temperature=("temperature", "max"),
            min_temperature=("temperature", "min"),

            avg_humidity=("humidity", "mean"),
            max_humidity=("humidity", "max"),
            min_humidity=("humidity", "min"),

            avg_wind=("wind", "mean"),
            max_wind=("wind", "max"),

            avg_precipitation=("precipitation", "mean"),
            total_precipitation=("precipitation", "sum"),

            avg_clouds=("clouds", "mean"),
        )
        .reset_index()
    )
    city_stats = city_stats.round(2)

    # main_table_day - kopia main_table uwzględniają tylko warunki w dzień (między 7 a 22)
    # dalsze rankingi opierają się na tej tabeli
    main_table_day = main_table[
        (main_table["time"].dt.hour >= 7) &
        (main_table["time"].dt.hour <= 22)
        ].copy()

    # Obliczenie rankingu temperatury
    main_table_day["temperature_score"] = main_table_day.apply(
        lambda r: temperature_score_seasonal(
            r["temperature"],
            r["time"].month,
            r["latitude"]
        ),
        axis=1
    )

    # Indeks komfortu (wagi)
    main_table_day["comfort_index"] = (
            0.35 * main_table_day["temperature_score"] +
            0.20 * main_table_day["humidity"].apply(humidity_score) +
            0.20 * main_table_day["precipitation"].apply(precipitation_score) +
            0.15 * main_table_day["wind"].apply(wind_score) +
            0.10 * main_table_day["clouds"].apply(cloud_score)
    )

    # Agregacja do miast
    # ranking - tabela z podziałem na miasta i średnią wartością comfort_index
    ranking = (
        main_table_day.groupby("city")["comfort_index"]
        .mean()
        .sort_values(ascending=False)
        .reset_index()
    )

    # daily_ranking - tabela z podziałem na miasta, dni i średnią wartością comfort_index
    daily_ranking = (
        main_table_day.groupby(["date", "city"])["comfort_index"]
        .mean()
        .reset_index()
        .sort_values(["date", "comfort_index"], ascending=[True, False])
    )

    # top3_per_day - po 3 najlepsze miasta dla każdego dnia (uwaga - ostatni dzień z zakresu
    # może być niemiarodajny ze względu na różne strefy czasowe)
    top3_per_day = (
        daily_ranking
        .groupby("date")
        .head(3)
    )

    # best_city_per_day - miasta z najwyższą punktacją w danym dniu
    best_city_per_day = (
        daily_ranking
        .groupby("date")
        .first()
        .reset_index()
    )

    print()


if __name__ == "__main__":
    main()
