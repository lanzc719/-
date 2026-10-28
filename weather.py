# -*- coding: utf-8 -*-
"""
简易天气查询小工具
- 天气数据：Open-Meteo（免费、无需 API Key、无需安装第三方库）
- 地名解析：Photon（OpenStreetMap，能识别到县/区/乡镇，并给出所属省份）
- 只用 Python 标准库，复制到 IDLE 里按 F5 就能直接运行
"""

import json
import urllib.parse
import urllib.request

PHOTON_URL = "https://photon.komoot.io/api/"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# 只保留“行政地名”类结果，过滤掉车站、机场、学校等同名地点
PLACE_TYPES = {"state", "province", "region", "county", "district",
               "city", "municipality", "town", "village", "hamlet", "locality"}
# 结果排序：省 / 市 / 县 / 镇 / 村，越“大”越靠前
TYPE_RANK = {"state": 0, "province": 0, "region": 1, "municipality": 1,
             "city": 1, "county": 2, "district": 2, "town": 3,
             "locality": 4, "village": 5, "hamlet": 6}

# Open-Meteo 的天气代码 -> 中文描述
WEATHER_CODES = {
    0: "晴", 1: "晴间少云", 2: "多云", 3: "阴",
    45: "雾", 48: "霜雾",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    56: "冻毛毛雨", 57: "强冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "强冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "阵雨", 81: "较强阵雨", 82: "强阵雨",
    85: "阵雪", 86: "强阵雪",
    95: "雷阵雨", 96: "雷阵雨伴小冰雹", 99: "雷阵雨伴大冰雹",
}

def pad(text, width):
    """按显示宽度补空格（中文字符算 2 格，让表格对齐）"""
    shown = sum(2 if ord(ch) > 127 else 1 for ch in text)
    return text + " " * max(0, width - shown)

def get_json(url, params):
    """发送 GET 请求并把返回的 JSON 转成 dict"""
    full_url = url + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))

def search_photon(name):
    """用 OpenStreetMap 查地名，能精确到县/区/乡镇"""
    data = get_json(PHOTON_URL, {"q": name, "limit": 10, "lang": "default"})
    places = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        osm_value = props.get("osm_value")
        if props.get("osm_key") != "place" or osm_value not in PLACE_TYPES:
            continue
        lon, lat = feature["geometry"]["coordinates"]
        places.append({
            "name": props.get("name") or name,
            "province": props.get("state") or "",
            "city": props.get("county") or props.get("city") or "",
            "country": props.get("country") or "",
            "lat": lat,
            "lon": lon,
            "rank": TYPE_RANK.get(osm_value, 6),
        })
    return places

def search_open_meteo(name):
    """备用：Open-Meteo 自带地名库，对国外城市和英文名支持更好"""
    data = get_json(GEOCODE_URL, {
        "name": name,
        "count": 8,
        "language": "zh",
        "format": "json",
    })
    places = []
    for item in data.get("results") or []:
        places.append({
            "name": item["name"],
            "province": item.get("admin1") or "",
            "city": item.get("admin2") or "",
            "country": item.get("country") or "",
            "lat": item["latitude"],
            "lon": item["longitude"],
            "rank": 3,
        })
    return places

def find_places(name):
    """两个地名库都查一遍，去重后按“行政级别”排序"""
    places = []
    try:
        places.extend(search_photon(name))
    except Exception:
        pass
    try:
        places.extend(search_open_meteo(name))
    except Exception:
        pass

    unique = []
    for place in places:
        # 经纬度非常接近的视为同一个地方（两个库对同一地点的数据略有差异）
        if all(abs(place["lat"] - old["lat"]) > 0.05
               or abs(place["lon"] - old["lon"]) > 0.05 for old in unique):
            unique.append(place)

    unique.sort(key=lambda p: p["rank"])
    return unique[:6]

def describe(place):
    """拼出“贵州省 黔东南州 中国”这样的位置说明"""
    return " ".join(x for x in (place["province"], place["city"], place["country"]) if x)

def choose_place(name):
    """列出同名地点让用户挑，只有一个就直接用"""
    places = find_places(name)
    if not places:
        print("  没有找到这个地方，换个写法再试试（比如“锦屏县”“北京”“Tokyo”）。")
        return None

    # 省 / 市 / 县级的结果只有一个时，直接用它（避免被同名的村镇带偏）
    big_places = [p for p in places if p["rank"] <= 2]
    if len(big_places) == 1:
        print(f"  定位到：{big_places[0]['name']}（{describe(big_places[0])}）")
        return big_places[0]
    if len(big_places) > 1:
        places = big_places
    elif len(places) == 1:
        print(f"  定位到：{places[0]['name']}（{describe(places[0])}）")
        return places[0]

    print(f"\n  找到 {len(places)} 个叫“{name}”的地方：")
    for index, place in enumerate(places, 1):
        print(f"    {index}. {pad(place['name'], 12)}{describe(place)}")
    while True:
        text = input("  请输入序号（直接回车 = 1）：").strip()
        if text == "":
            return places[0]
        if text.isdigit() and 1 <= int(text) <= len(places):
            return places[int(text) - 1]
        print("  输入无效，请输入上面列表里的序号。")

def query_weather(city_name):
    """查询某个城市的实时天气 + 未来 3 天预报"""
    place = choose_place(city_name)
    if place is None:
        return

    data = get_json(WEATHER_URL, {
        "latitude": place["lat"],
        "longitude": place["lon"],
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                   "wind_speed_10m,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_probability_max,sunrise,sunset",
        "forecast_days": 3,
        "timezone": "auto",
    })

    current = data["current"]
    print()
    print("=" * 46)
    print(f"  {place['name']}（{describe(place)}）")
    print("=" * 46)
    print(f"  当前天气：{WEATHER_CODES.get(current['weather_code'], '未知')}")
    print(f"  温度：{current['temperature_2m']} °C"
          f"（体感 {current['apparent_temperature']} °C）")
    print(f"  湿度：{current['relative_humidity_2m']} %")
    print(f"  风速：{current['wind_speed_10m']} km/h")
    print(f"  更新时间：{current['time'].replace('T', ' ')}")

    print("-" * 46)
    print("  未来三天")
    print("-" * 46)
    daily = data["daily"]
    for i in range(len(daily["time"])):
        desc = WEATHER_CODES.get(daily["weather_code"][i], "未知")
        rain = daily["precipitation_probability_max"][i]
        rain_text = f"{rain}%" if rain is not None else "--"
        print(f"  {daily['time'][i]}  {pad(desc, 12)}"
              f"{daily['temperature_2m_min'][i]:>5} ~ {daily['temperature_2m_max'][i]:>5} °C"
              f"   降水概率 {rain_text}")
    print(f"  日出 {daily['sunrise'][0][-5:]}    日落 {daily['sunset'][0][-5:]}")
    print()

def main():
    print("天气查询小工具（数据来自 Open-Meteo + OpenStreetMap，输入 q 退出）")
    while True:
        city_name = input("请输入城市/县/区名：").strip()
        if city_name.lower() in ("q", "quit", "exit"):
            print("再见！")
            break
        if not city_name:
            continue
        try:
            query_weather(city_name)
        except Exception as error:
            print(f"  查询失败：{error}（检查一下网络连接）")

main()