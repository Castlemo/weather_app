from flask import Flask, request, jsonify, render_template
import requests
from rapidfuzz import process
from dotenv import load_dotenv
import os
import openai
from scapy.all import sniff  # scapy 임포트
import threading
from collections import deque
import time
import json

app = Flask(__name__)

load_dotenv()
# OpenAI API 키 설정
openai.api_key = os.getenv('OPENAI_API_KEY')

# 지원하는 도시 목록 (추가할 도시가 많다면 이곳에 직접 추가)
supported_cities = [
    "New York", "Seoul", "Los Angeles", "London",
    "Tokyo", "Paris", "Beijing", "Mumbai"
]

# 검색 기록을 저장할 리스트
search_history = []

# 패킷 수 데이터를 저장할 데크 초기화 (시간당 패킷 수를 저장)
packet_counts = deque()

def packet_sniffer():
    # 최근 60초 동안의 패킷 수를 저장하기 위한 변수
    start_time = time.time()
    count = 0
    while True:
        # 1초 동안 패킷 수를 측정
        packets = sniff(timeout=1)
        count = len(packets)
        current_time = time.time()
        packet_counts.append((current_time, count))

        # 60초를 넘은 오래된 데이터는 제거
        while packet_counts and packet_counts[0][0] < current_time - 60:
            packet_counts.popleft()

sniffer_thread = threading.Thread(target=packet_sniffer)
sniffer_thread.daemon = True
sniffer_thread.start()

@app.route('/packet_data')
def packet_data():
    # 그래프를 그리기 위한 데이터 생성
    times = [(time_point - time.time()) for time_point, _ in packet_counts]
    counts = [count for _, count in packet_counts]

    data = {
        'times': times,
        'counts': counts
    }
    return jsonify(data)

@app.route('/')
def index():
    return render_template('index.html', search_history=search_history)  # 검색 기록 전달

@app.route('/weather', methods=['GET'])
def weather():
    city = request.args.get('city').strip().lower()
    city = " ".join(city.split())  # 중간에 여러 공백이 있을 경우에도 한 칸 공백으로 만듦
    api_key = '008e5844dd6ea339f1fcbc7024bd54c8'
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)  # 클라이언트 IP 가져오기

    # API에 도시 이름을 직접 요청
    response = requests.get(f"http://api.openweathermap.org/data/2.5/weather?q={city.title()}&appid={api_key}&units=metric")

    if response.status_code == 200:
        data = response.json()
        temperature = data['main']['temp']
        temp_max = data['main']['temp_max']    # 최고 기온 추가
        temp_min = data['main']['temp_min']    # 최저 기온 추가
        description = data['weather'][0]['description']
        humidity = data['main']['humidity']
        wind_speed = data['wind']['speed']
        rain = data.get('rain', {}).get('1h', 0)
        coordinates = {
            'lat': data['coord']['lat'],
            'lon': data['coord']['lon']
        }

        if city.title() not in search_history:
            search_history.append(city.title())

        # 날씨에 따른 알림 메시지 추가
        advice = get_weather_advice(description, temperature)

        return jsonify({
            "city": data['name'],
            "temperature": temperature,
            "temp_max": temp_max,           # 최고 기온 추가
            "temp_min": temp_min,           # 최저 기온 추가
            "description": description,
            "humidity": humidity,
            "wind_speed": wind_speed,
            "rain": rain,
            "advice": advice,
            'client_ip': client_ip,
            'coordinates': coordinates  # 좌표 정보 추가
        })
    elif response.status_code == 404:
        suggestions = get_city_suggestions(city)
        return jsonify({"error": "City not found", "suggestions": suggestions}), 404
    else:
        return jsonify({"error": "Failed to fetch weather data"}), response.status_code


def get_weather_advice(description, temperature):
    # 기본 조언 메시지 초기화
    basic_advice = ""
    
    # 날씨에 따른 기본 조언
    if temperature > 35:
        basic_advice = "기온이 섭씨 35도를 넘었네요. 오늘은 야외 활동을 피하는 것이 좋겠습니다."
    elif "rain" in description.lower():
        basic_advice = "비가 오고 있어요. 우산을 챙기고, 야외 활동은 피하는 것이 좋겠습니다."
    elif "snow" in description.lower():
        basic_advice = "눈이 오고 있습니다. 도로가 미끄러울 수 있으니 주의하세요."
    else:
        basic_advice = "날씨가 괜찮네요!"

    # GPT 프롬프트로 상세 조언 받기
    prompt = f"""현재 날씨: {description}, 기온: {temperature}°C

    다음 내용을 핵심적으로 전달해주세요:
    - 현재 날씨 상황에 대한 실용적인 조언
    - 이런 날씨에 추천하는 구체적인 활동
    - 현재 날씨에 적합한 옷차림
    
    * 인사말이나 안부 인사는 제외하고 날씨 정보에만 집중해서 답변해주세요.
    * 9~10문장 정도로 작성해주세요. "-"나 "*" 같은 기호는 사용하지 않습니다.
    * 친근하고 자연스러운 말투로 작성해주세요."""
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "당신은 날씨 전문가입니다. 인사말 없이 날씨 정보와 실용적인 조언만을 제공합니다."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=400
    )
    
    # 기본 조언과 상세 조언 합치기
    detailed_advice = response['choices'][0]['message']['content'].strip()
    return f"{basic_advice}\n\n{detailed_advice}"


def get_city_suggestions(input_city):
    # 유사한 도시 이름 추천
    best_matches = process.extract(input_city.title(), supported_cities, limit=3)
    suggestions = [match[0] for match in best_matches if match[1] > 50]
    return suggestions

if __name__ == '__main__':
    app.run(debug=True)