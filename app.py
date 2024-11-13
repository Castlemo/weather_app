from flask import Flask, request, jsonify, render_template
import requests
from rapidfuzz import process
from dotenv import load_dotenv
import os
import openai

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
            'client_ip': client_ip
        })
    elif response.status_code == 404:
        suggestions = get_city_suggestions(city)
        return jsonify({"error": "City not found", "suggestions": suggestions}), 404
    else:
        return jsonify({"error": "Failed to fetch weather data"}), response.status_code


def get_weather_advice(description, temperature):
    # 날씨에 따른 맞춤형 일정 추천
    if temperature > 35:
        return "기온이 섭씨 35도를 넘었네요. 오늘은 야외 활동을 피하는 것이 좋겠습니다."
    elif "rain" in description.lower():
        return "비가 오고 있어요. 우산을 챙기고, 야외 활동은 피하는 것이 좋겠습니다."
    elif "snow" in description.lower():
        return "눈이 오고 있습니다. 도로가 미끄러울 수 있으니 주의하세요."
    else:
        # GPT-3.5를 이용해 추가적인 날씨 조언 제공 (한국어로 응답하도록 요청)
        prompt = f"현재 날씨는 {description}이고 기온은 {temperature}도 입니다. 이 날씨에 할 수 있는 활동에 대한 조언을 2가지 정도 제시해. 예를들어 캠핑을 가기 좋다던지 러닝을 하면 좋다던지 등, 구체적인 활동을 조언해. 또한 외출할 때 필요한 옷 품목을 한두가지 정도만 추천해. {description}을 나타내야 할 경우 한국어로 번역한 상태여야 합니다. 네/아니오 같은 대답은 하지 마세요."
        
        # 새로운 API 형식에 맞게 수정된 부분
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "당신은 한국어로 자세하고 깔끔한 날씨 관련 조언을 제공하는 인공지능 비서입니다. 답변은 완전해야 하며 중간에 끊기지 않아야 합니다."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000  # 필요에 따라 토큰 수 조정
        )
        return response['choices'][0]['message']['content'].strip()


def get_city_suggestions(input_city):
    # 유사한 도시 이름 추천
    best_matches = process.extract(input_city.title(), supported_cities, limit=3)
    suggestions = [match[0] for match in best_matches if match[1] > 50]
    return suggestions

if __name__ == '__main__':
    app.run(debug=True)