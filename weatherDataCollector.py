import requests
import json
from pathlib import Path
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# api docs: https://open-meteo.com/en/docs

CAPITALS = [
    {"country": "Polska", "city": "Warsaw", "lat": 52.2297, "lon": 21.0122, "tz": "Europe/Warsaw"},
    {"country": "Portugal", "city": "Lisbon", "lat": 38.7223, "lon": -9.1393, "tz": "Europe/Lisbon"},
    {"country": "Spain", "city": "Madrid", "lat": 40.4168, "lon": -3.7038, "tz": "Europe/Madrid"},
    {"country": "France", "city": "Paris", "lat": 48.8566, "lon": 2.3522, "tz": "Europe/Paris"},
    {"country": "Italy", "city": "Rome", "lat": 41.9028, "lon": 12.4964, "tz": "Europe/Rome"},
    {"country": "Germany", "city": "Berlin", "lat": 52.5200, "lon": 13.4050, "tz": "Europe/Berlin"},
    {"country": "UK", "city": "London", "lat": 51.5074, "lon": -0.1278, "tz": "Europe/London"},
    {"country": "Ireland", "city": "Dublin", "lat": 53.3498, "lon": -6.2603, "tz": "Europe/Dublin"},
    {"country": "Norway", "city": "Oslo", "lat": 59.9139, "lon": 10.7522, "tz": "Europe/Oslo"},
    {"country": "Sweden", "city": "Stockholm", "lat": 59.3293, "lon": 18.0686, "tz": "Europe/Stockholm"},
    {"country": "Finland", "city": "Helsinki", "lat": 60.1699, "lon": 24.9384, "tz": "Europe/Helsinki"},
    {"country": "Greece", "city": "Athens", "lat": 37.9838, "lon": 23.7275, "tz": "Europe/Athens"},
    {"country": "Japan", "city": "Tokyo", "lat": 35.6762, "lon": 139.6503, "tz": "Asia/Tokyo"},
    {"country": "USA", "city": "Washington", "lat": 38.9072, "lon": -77.0369, "tz": "America/New_York"},
    {"country": "Australia", "city": "Canberra", "lat": -35.2809, "lon": 149.1300, "tz": "Australia/Sydney"},
]


def fetch_weather_open_meteo(
    latitude: float,                    # szerokość geograficzna
    longitude: float,                   # długość geograficzna
    timezone: str = "Europe/Warsaw",
    days: int = 3                       # jako default 3 ostatnie dni, max to 16 dni
) -> dict:
    """
    pobiera dane pogodowe (zwracane co godzine z każdego dnia) z Open-Meteo API
    zwraca JSON jako słownik (dict) w Pythonie
    """
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": [
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "wind_speed_10m",
            "cloud_cover",
        ],
        "forecast_days": days,
        "timezone": timezone,
    }

    # Setup retry strategy
    session = requests.Session()
    retry = Retry(
        total=3,  # liczba prób
        backoff_factor=1,  # czekaj 1s, 2s, 4s między próbami
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    try:
        response = session.get(url, params=params, timeout=60)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        time.sleep(3)
        response = session.get(url, params=params, timeout=60)
        response.raise_for_status()
        return response.json()


def save_json(data: dict, filepath: str) -> None:
    """
    uwtorzenie pliku z json'em
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json_from_file(filepath: str) -> dict:
    """
    wczytanie danych z pliku (typ danych w pliku json) i zwraca dict.
    """
    path = Path(filepath)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def pretty_print_json(data: dict, max_chars: int = 3000) -> None:
    """
    wyswietlenie JSON w konsoli (razem z formatowaniem)
    max_chars - ograniczenie dlugosci outputu (aby nie wyswietlic calego dlugiego pliku w konsoli)
    """
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if len(text) > max_chars:
        print(text[:max_chars] + "\n... (ucięte)")
    else:
        print(text)


# DATA CLEANING
def clean_hourly_data(data: dict) -> list[dict]:
    """
    Oczyszczanie danych godzinowych:
    - spłaszczenie hourly JSON do listy wierszy
    - usunięcie rekordyów, gdzie brakuje temperatury lub wilgotności (None)
    """
    hourly = data.get("hourly", {})

    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    hums = hourly.get("relative_humidity_2m", [])
    precip = hourly.get("precipitation", [])
    wind = hourly.get("wind_speed_10m", [])
    cloud = hourly.get("cloud_cover", [])

    rows = []

    min_len = min(
        len(times),
        len(temps),
        len(hums),
        len(precip),
        len(wind),
        len(cloud)
    )

    for i in range(min_len):
        t = times[i]
        temp = temps[i]
        hum = hums[i]
        pr = precip[i]
        ws = wind[i]
        cc = cloud[i]

        # cleaning: pominięcie rekordów z brakami kluczowych danych
        if temp is None or hum is None:
            continue

        rows.append({
            "time": t,
            "temperature_2m": float(temp),
            "relative_humidity_2m": float(hum),
            "precipitation": None if pr is None else float(pr),
            "wind_speed_10m": None if ws is None else float(ws),
            "cloud_cover": None if cc is None else float(cc),
        })

    return rows


def main():
    days = 16
    output_folder = Path("weather_data")


    # --- Równoległe pobieranie danych dla miast ---
    import concurrent.futures


    def fetch_clean_and_save(capital):
        country = capital["country"]
        city = capital["city"]
        lat = capital["lat"]
        lon = capital["lon"]
        tz = capital["tz"]
        weather_json = fetch_weather_open_meteo(
            latitude=lat,
            longitude=lon,
            timezone=tz,
            days=days
        )
        weather_json["metadata"] = {
            "country": country,
            "city": city,
            "lat": lat,
            "lon": lon,
            "timezone": tz
        }
        safe_city = city.lower().replace(" ", "_")
        file_path = output_folder / f"open_meteo_{safe_city}.json"
        save_json(weather_json, str(file_path))
        cleaned_rows = clean_hourly_data(weather_json)
        return {
            "metadata": weather_json["metadata"],
            "cleaned_hourly_rows": cleaned_rows
        }, weather_json

    cleaned_data = []
    all_data = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(fetch_clean_and_save, capital) for capital in CAPITALS]
        for future in concurrent.futures.as_completed(futures):
            try:
                cleaned, raw = future.result()
                cleaned_data.append(cleaned)
                all_data.append(raw)
            except Exception as e:
                print(f"Błąd pobierania miasta: {e}")

    # zapis zbiorczy (wszystkie stolice w jednym JSON)
    all_capitals_file = output_folder / "open_meteo_all_capitals.json"
    save_json({"capitals_weather": all_data}, str(all_capitals_file))

    # zapis CLEANED
    cleaned_file = output_folder / "open_meteo_all_capitals_CLEANED.json"
    save_json({"capitals_weather_cleaned": cleaned_data}, str(cleaned_file))

    print(f"Zapisano oczyszczone dane do pliku: {cleaned_file.resolve()}")


if __name__ == "__main__":
    main()
