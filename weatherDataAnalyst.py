import requests
import json
from pathlib import Path
import matplotlib.pyplot as plt

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

    response = requests.get(url, params=params, timeout=60)
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
def calculate_comfort_index(temperature: float, humidity: float, wind_speed: float, 
                            precipitation: float, cloud_cover: float) -> float:
    """
    Oblicza indeks komfortu pogodowego (0-100).
    
    Parametry:
    - temperatura: ideał 18-24°C
    - wilgotność: ideał 40-60%
    - wiatr: lekki (< 10 km/h) = ok
    - opady: bez opadów = lepiej
    - zachmurzenie: poniżej 30% = ok
    """
    score = 0
    
    # Temperatura: 18-24°C = 25 pkt
    if 18 <= temperature <= 24:
        temp_score = 25
    elif 15 <= temperature < 18 or 24 < temperature <= 27:
        temp_score = 15  # trochę chłodne/ciepłe
    elif 10 <= temperature < 15 or 27 < temperature <= 30:
        temp_score = 5   # zimne/gorące
    else:
        temp_score = 0   # bardzo zimno/gorąco
    
    # Wilgotność: 40-60% = 25 pkt
    if 40 <= humidity <= 60:
        humidity_score = 25
    elif 30 <= humidity < 40 or 60 < humidity <= 70:
        humidity_score = 15  # trochę za niska/wysoka
    elif 20 <= humidity < 30 or 70 < humidity <= 80:
        humidity_score = 5   # bardzo za niska/wysoka
    else:
        humidity_score = 0   # ekstremalna
    
    # Wiatr: do 10 km/h = 20 pkt
    if wind_speed <= 10:
        wind_score = 20
    elif wind_speed <= 15:
        wind_score = 10  # umiarkowany
    else:
        wind_score = 0   # silny wiatr
    
    # Opady: brak = 15 pkt
    if precipitation == 0 or precipitation is None:
        precip_score = 15
    elif precipitation < 1:
        precip_score = 8   # lekkie opady
    else:
        precip_score = 0   # silne opady
    
    # Zachmurzenie: do 30% = 15 pkt
    if cloud_cover <= 30:
        cloud_score = 15
    elif cloud_cover <= 60:
        cloud_score = 8    # częściowo pochmurno
    else:
        cloud_score = 0    # bardzo pochmurne
    
    score = temp_score + humidity_score + wind_score + precip_score + cloud_score
    return score

def calculate_city_comfort_index(cleaned_rows: list[dict]) -> float:
    """
    Oblicza średni indeks komfortu dla miasta (średnia z wszystkich godzin).
    """
    if not cleaned_rows:
        return 0
    
    scores = []
    for row in cleaned_rows:
        score = calculate_comfort_index(
            temperature=row["temperature_2m"],
            humidity=row["relative_humidity_2m"],
            wind_speed=row["wind_speed_10m"] or 0,
            precipitation=row["precipitation"] or 0,
            cloud_cover=row["cloud_cover"] or 0
        )
        scores.append(score)
    
    return sum(scores) / len(scores)

def plot_comfort_ranking(comfort_scores: dict) -> None:
    """
    Rysuje ranking miast ze względu na komfort pogodowy.
    
    comfort_scores: słownik {nazwa_miasta: indeks_komfortu}
    """
    # Sortowanie miast malejąco
    cities = list(comfort_scores.keys())
    scores = list(comfort_scores.values())
    
    sorted_data = sorted(zip(cities, scores), key=lambda x: x[1], reverse=True)
    cities_sorted = [x[0] for x in sorted_data]
    scores_sorted = [x[1] for x in sorted_data]
    
    # Utworzenie wykresu
    fig, ax = plt.subplots(figsize=(12, 8))
    
    bars = ax.barh(cities_sorted, scores_sorted, color='skyblue', edgecolor='navy')
    
    # Kolorowanie paski w zależności od wyniku
    for i, (bar, score) in enumerate(zip(bars, scores_sorted)):
        if score > 50:
            bar.set_color('green')
        elif score >= 38:
            bar.set_color('yellow')
        else:
            bar.set_color('red')
    
    ax.set_xlabel('Indeks Komfortu Pogodowego (0-100)', fontsize=12)
    ax.set_ylabel('Miasto', fontsize=12)
    ax.set_title('Ranking Miast - Komfort Pogodowy', fontsize=14, fontweight='bold')
    ax.set_xlim(0, 100)
    
    # Dodanie wartości na słupkach
    for i, (city, score) in enumerate(zip(cities_sorted, scores_sorted)):
        ax.text(score + 1, i, f'{score:.1f}', va='center', fontsize=10)
    
    plt.tight_layout()
    plt.savefig('weather_data/comfort_ranking.png', dpi=150, bbox_inches='tight')
    print("✓ Zapisano wykres rankingu do: weather_data/comfort_ranking.png")
    plt.close()

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

    all_data = []

    for capital in CAPITALS:
        country = capital["country"]
        city = capital["city"]
        lat = capital["lat"]
        lon = capital["lon"]
        tz = capital["tz"]

        print(f"Pobieram: {city} ({country})...")

        weather_json = fetch_weather_open_meteo(
            latitude=lat,
            longitude=lon,
            timezone=tz,
            days=days
        )

        # dodanie metadata (aby łatwiej połączyć ze sobą dane)
        weather_json["metadata"] = {
            "country": country,
            "city": city,
            "lat": lat,
            "lon": lon,
            "timezone": tz
        }

        # zapisnie osobnego pliku dla każdego miasta
        safe_city = city.lower().replace(" ", "_")
        file_path = output_folder / f"open_meteo_{safe_city}.json"
        save_json(weather_json, str(file_path))

        all_data.append(weather_json)

    # zapis zbiorczy (wszystkie stolice w jednym JSON)
    all_capitals_file = output_folder / "open_meteo_all_capitals.json"
    save_json({"capitals_weather": all_data}, str(all_capitals_file))

    print("\nGotowe!")
    print(f"Pliki zapisane w folderze: {output_folder.resolve()}")

    # odczyt danych z pliku
    print("\nWczytuję plik zbiorczy...")

    loaded_all = load_json_from_file(str(all_capitals_file))

    # Podstawowe info
    capitals_list = loaded_all.get("capitals_weather", [])
    print(f"Liczba znalezionych miast w pliku zbiorczym: {len(capitals_list)}")

    # Podgląd fragmentu JSON
    # print("\nPodgląd JSON (fragment z pliku zbiorczego):")
    # pretty_print_json(loaded_all, max_chars=3000)

    # CLEANING DLA WSZYSTKICH MIAST + ZAPIS DO ODDZIELNEGO PLIKU
    cleaned_data = []

    for city_data in capitals_list:
        meta = city_data.get("metadata", {})
        cleaned_rows = clean_hourly_data(city_data)

        cleaned_data.append({
            "metadata": meta,
            "cleaned_hourly_rows": cleaned_rows
        })

    cleaned_file = output_folder / "open_meteo_all_capitals_CLEANED.json"
    save_json({"capitals_weather_cleaned": cleaned_data}, str(cleaned_file))

    print(f"Zapisano oczyszczone dane do pliku: {cleaned_file.resolve()}")
    
    # OBLICZENIE INDEKSU KOMFORTU DLA KAŻDEGO MIASTA
    print("\n" + "="*60)
    print("RANKING KOMFORTU POGODOWEGO")
    print("="*60)
    
    comfort_scores = {}
    
    for city_record in cleaned_data:
        meta = city_record.get("metadata", {})
        city_name = meta.get("city", "Unknown")
        cleaned_rows = city_record.get("cleaned_hourly_rows", [])
        
        comfort_index = calculate_city_comfort_index(cleaned_rows)
        comfort_scores[city_name] = comfort_index
        
        print(f"{city_name:15} -> Indeks komfortu: {comfort_index:6.2f}/100")
    
    # Sortowanie i wyświetlenie Top 5
    top_5 = sorted(comfort_scores.items(), key=lambda x: x[1], reverse=True)[:5]
    print("\n🏆 TOP 5 najwygodniejszych miast:")
    for rank, (city, score) in enumerate(top_5, 1):
        print(f"  {rank}. {city:15} ({score:.2f}/100)")
    
    # Rysowanie wykresu
    plot_comfort_ranking(comfort_scores)

if __name__ == "__main__":
    main()
