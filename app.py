import requests
import pandas as pd
import streamlit as st
import pydeck as pdk  # 💡 강력한 대화형 지도(인터랙티브 맵)를 그리기 위해 새로 추가했어!

# ==========================================
# 1. OpenSky API 데이터 호출 함수 정의
# ==========================================
def get_korea_flights(client_id, client_secret):  
    token_url = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
    token_data = {
        "grant_type": "client_credentials",
        "client_id": client_id,        
        "client_secret": client_secret 
    }
    
    try:  
        token_response = requests.post(token_url, data=token_data, timeout=30)
        token_response.raise_for_status()  
        access_token = token_response.json().get("access_token")
    except requests.exceptions.RequestException as e:  
        print(f"토큰 발급 실패: {e}")
        return None

    api_url = "https://opensky-network.org/api/states/all"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "lamin": 33.0, "lamax": 39.0, 
        "lomin": 124.0, "lomax": 132.0 
    }
    
    try:  
        response = requests.get(api_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:  
        print(f"데이터 응답 실패: {e}")
        return None

    states = data.get("states")
    if not states:
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

st.set_page_config(layout="wide") # 지도를 넓게 보기 위해 전체 화면 모드로 설정!
st.title("✈️ 실시간 한반도 비행기 레이더")

CLIENT_ID = "20725user-api-client"
CLIENT_SECRET = "GsWs26aDoIMRoAtHmpbX0BDgJrkft5fy"

with st.spinner("한반도 상공의 비행기 데이터를 실시간으로 불러오는 중이야..."):
    df = get_korea_flights(CLIENT_ID, CLIENT_SECRET)

if df is None:
    st.error("데이터를 불러오는 데 실패했어. 터미널 창의 에러 메시지를 확인해 봐!")
elif df.empty:
    st.warning("현재 지정된 범위(한반도) 상공에 조회된 비행기가 없어. 잠시 후 다시 시도해 봐.")
else:
    # ---------------------------------------------------------
    # [기능 1] 국적별 비행기 필터링 (국기 이모지 유지)
    # ---------------------------------------------------------
    st.subheader("🌍 국적별 필터링")
    
    flag_dict = {
        "South Korea": "🇰🇷", "United States": "🇺🇸", "China": "🇨🇳", "Japan": "🇯🇵",
        "Taiwan": "🇹🇼", "Russia": "🇷🇺", "Philippines": "🇵🇭", "Vietnam": "🇻🇳",
        "Thailand": "🇹🇭", "Malaysia": "🇲🇾", "Singapore": "🇸🇬", "United Kingdom": "🇬🇧",
        "Germany": "🇩🇪", "France": "🇫🇷", "Netherlands": "🇳🇱", "Qatar": "🇶🇦", "United Arab Emirates": "🇦🇪"
    }

    def format_country_with_flag(country_name):
        if country_name == "전체보기": return "🌐 전체보기"
        return f"{flag_dict.get(country_name, '🏳️')} {country_name}"
    
    country_list = ["전체보기"] + sorted(list(df['origin_country'].dropna().unique()))
    selected_country = st.selectbox("조회하고 싶은 국적을 선택해 봐:", country_list, format_func=format_country_with_flag)
    
    if selected_country != "전체보기":
        filtered_df = df[df['origin_country'] == selected_country]
    else:
        filtered_df = df
        
    st.success(f"선택한 조건에 맞는 비행기가 총 {len(filtered_df)}대 포착되었어!")
    
    # 지도 오류 방지를 위해 위치 데이터가 없는 행은 제거
    map_df = filtered_df.dropna(subset=['latitude', 'longitude']).copy()

    # ---------------------------------------------------------
    # 💡 [기능 3 개선] Pydeck을 활용한 인터랙티브 툴팁 지도!
    # ---------------------------------------------------------
    if not map_df.empty:
        # 데이터프레임의 빈 값(NaN)을 보기 좋게 처리
        map_df['callsign'] = map_df['callsign'].fillna("알 수 없음")
        map_df['baro_altitude'] = map_df['baro_altitude'].fillna(0)
        map_df['velocity'] = map_df['velocity'].fillna(0)
        
        # 1. 지도 초기 화면 설정 (한반도 중심)
        view_state = pdk.ViewState(
            latitude=36.5,
            longitude=127.5,
            zoom=6,
            pitch=40, # 지도를 40도 정도 눕혀서 입체감 있게 보이게 해줘
        )

        # 2. 비행기를 나타낼 레이어(점) 설정
        scatter_layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            get_position='[longitude, latitude]',
            get_radius=8000, # 원의 크기
            get_fill_color='[255, 75, 75, 200]', # 원의 색상 (빨간색 계열)
            pickable=True, # 💡 이걸 True로 해야 마우스를 올렸을 때 인식해!
        )

        # 3. 툴팁(말풍선)에 들어갈 디자인과 데이터 포맷 설정
        tooltip = {
            "html": """
            <b>호출부호(Callsign):</b> {callsign} <br/>
            <b>국적:</b> {origin_country} <br/>
            <b>고도:</b> {baro_altitude} m <br/>
            <b>속도:</b> {velocity} m/s
            """,
            "style": {
                "backgroundColor": "steelblue",
                "color": "white",
                "padding": "10px",
                "borderRadius": "5px"
            }
        }

        # 4. 최종 지도 렌더링
        r = pdk.Deck(
            layers=[scatter_layer],
            initial_view_state=view_state,
            tooltip=tooltip,
            map_style='mapbox://styles/mapbox/dark-v10' # 멋진 다크 모드 지도
        )
        
        st.pydeck_chart(r)
    else:
        st.info("지도에 표시할 수 있는 위치 정보가 없어.")

    st.markdown("---")
    with st.expander("📊 수신된 원본 비행기 세부 데이터 표 보기"):
        st.dataframe(filtered_df)
