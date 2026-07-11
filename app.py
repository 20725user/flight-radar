import requests  # HTTP 통신을 위해 requests 라이브러리를 불러와. (API에 데이터를 요청하기 위함)
import pandas as pd  # 수신한 리스트 데이터를 2차원 표 형태인 데이터프레임 구조로 변환하기 위해 pandas를 불러와.
import streamlit as st  # 웹 화면에 지도와 데이터를 시각화하기 위해 streamlit 라이브러리를 불러와.

# ==========================================
# 1. OpenSky API 데이터 호출 함수 정의
# ==========================================
def get_korea_flights(client_id, client_secret):  
    
    # --- [OAuth2 인증 토큰 발급] ---
    token_url = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
    
    # 💡 [핵심 수정 완료] 키(Key) 이름은 반드시 "client_id"와 "client_secret"이어야 해!
    token_data = {
        "grant_type": "client_credentials",
        "client_id": client_id,        
        "client_secret": client_secret 
    }
    
    try:  
        # 토큰 URL로 POST 요청을 보내고, 응답 지연을 대비해 timeout을 30초로 제한해.
        token_response = requests.post(token_url, data=token_data, timeout=30)
        token_response.raise_for_status()  
        
        # 응답받은 JSON 데이터에서 실제 사용할 'access_token' 값만 추출해.
        access_token = token_response.json().get("access_token")
        
    except requests.exceptions.RequestException as e:  
        print(f"토큰 발급 실패: {e}")
        return None

    # --- [비행기 데이터 실시간 조회] ---
    api_url = "https://opensky-network.org/api/states/all"
    
    # 위에서 발급받은 토큰을 헤더에 넣어서 인증해.
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 한반도 상공의 위도와 경도 범위
    params = {
        "lamin": 33.0, 
        "lamax": 39.0, 
        "lomin": 124.0,
        "lomax": 132.0 
    }
    
    try:  
        # 이번에는 토큰이 담긴 헤더(headers)를 같이 보내서 GET 요청을 해.
        response = requests.get(api_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
    except requests.exceptions.RequestException as e:  
        print(f"데이터 응답 실패: {e}")
        return None

    # --- [Pandas 데이터프레임 변환] ---
    states = data.get("states")
    
    if not states:
        print("현재 한반도 상공에 조회된 비행기 데이터가 없어.")
        return pd.DataFrame()

    columns = [
        "icao24", "callsign", "origin_country", "time_position", "last_contact", 
        "longitude", "latitude", "baro_altitude", "on_ground", "velocity", 
        "true_track", "vertical_rate", "sensors", "geo_altitude", "squawk", 
        "spi", "position_source"
    ]
    
    df = pd.DataFrame(states, columns=columns)
    return df


# ==========================================
# 2. Streamlit 웹 화면 구성 및 실행 파트
# ==========================================

st.title("✈️ 실시간 한반도 비행기 레이더")

# 네가 알려준 Client ID와 Secret 값을 그대로 변수에 담았어.
CLIENT_ID = "20725user-api-client"
CLIENT_SECRET = "GsWs26aDoIMRoAtHmpbX0BDgJrkft5fy"

with st.spinner("한반도 상공의 비행기 데이터를 실시간으로 불러오는 중이야..."):
    # 함수에 ID와 Secret을 전달해서 실행!
    df = get_korea_flights(CLIENT_ID, CLIENT_SECRET)

if df is None:
    st.error("데이터를 불러오는 데 실패했어. 터미널 창(검은 화면)의 에러 메시지를 확인해 봐!")

elif df.empty:
    st.warning("현재 지정된 범위(한반도) 상공에 조회된 비행기가 없어. 잠시 후 다시 시도해 봐.")

else:
    st.success(f"현재 한반도 상공에 {len(df)}대의 비행기가 포착되었어!")
    
    # 지도 오류 방지를 위해 위경도 값이 있는 데이터만 필터링
    map_df = df.dropna(subset=['latitude', 'longitude'])
    st.map(map_df)
    
    with st.expander("📊 수신된 원본 비행기 세부 데이터 표 보기"):
        st.dataframe(df)
