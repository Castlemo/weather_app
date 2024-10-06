from flask import Flask, request, jsonify, render_template
import requests
from rapidfuzz import process 

app = Flask(__name__)

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
    # 사용자가 입력한 도시 이름을 공백과 대소문자 구분 없이 처리
    city = request.args.get('city').strip().lower()
    city = " ".join(city.split())  # 중간에 여러 공백이 있을 경우에도 한 칸 공백으로 만듦
    api_key = '008e5844dd6ea339f1fcbc7024bd54c8'
    client_ip = request.remote_addr  # 클라이언트 IP 가져오기

    # API에 도시 이름을 직접 요청
    response = requests.get(f"http://api.openweathermap.org/data/2.5/weather?q={city.title()}&appid={api_key}&units=metric")

    if response.status_code == 200:
        data = response.json()
        temperature = data['main']['temp']
        description = data['weather'][0]['description']

        if city not in search_history:
            search_history.append(city.title())

        return jsonify({
            "city": data['name'],
            "temperature": temperature,
            "description": description,
            'client_ip': client_ip
        })
    elif response.status_code == 404:
        suggestions = get_city_suggestions(city)
        return jsonify({"error": "City not found", "suggestions": suggestions}), 404
    else:
        return jsonify({"error": "Failed to fetch weather data"}), response.status_code

def get_city_suggestions(input_city):
    # 유사한 도시 이름 추천
    best_matches = process.extract(input_city.title(), supported_cities, limit=3)
    suggestions = [match[0] for match in best_matches if match[1] > 50]
    return suggestions

if __name__ == '__main__':
    app.run(debug=True)