import requests
import pandas as pd
import streamlit as st
import pydeck as pdk 

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

st.set_page_config(layout="wide") 
st.title("✈️ 실시간 한반도 비행기 레이더")

CLIENT_ID = "20725user-api-client"
CLIENT_SECRET = "GsWs26aDoIMRoAtHmpbX0BDgJrkft5fy"

# 💡 자주 보이는 국가들의 국기 매핑 딕셔너리
flag_dict = {
    "South Korea": "🇰🇷", "United States": "🇺🇸", "China": "🇨🇳", "Japan": "🇯🇵",
    "Taiwan": "🇹🇼", "Russia": "🇷🇺", "Philippines": "🇵🇭", "Vietnam": "🇻🇳",
    "Thailand": "🇹🇭", "Malaysia": "🇲🇾", "Singapore": "🇸🇬", "United Kingdom": "🇬🇧",
    "Germany": "🇩🇪", "France": "🇫🇷", "Netherlands": "🇳🇱", "Qatar": "🇶🇦", "United Arab Emirates": "🇦🇪"
}

with st.spinner("한반도 상공의 비행기 데이터를 실시간으로 불러오는 중이야..."):
    df = get_korea_flights(CLIENT_ID, CLIENT_SECRET)

if df is None:
    st.error("데이터를 불러오는 데 실패했어. 터미널 창의 에러 메시지를 확인해 봐!")
elif df.empty:
    st.warning("현재 지정된 범위(한반도) 상공에 조회된 비행기가 없어. 잠시 후 다시 시도해 봐.")
else:
    # 💡 데이터프레임에 아예 '국기(flag)'와 '국기+이름' 컬럼을 새로 만들어버려!
    df['flag'] = df['origin_country'].apply(lambda x: flag_dict.get(x, "🏳️"))
    df['country_with_flag'] = df['flag'] + " " + df['origin_country']

    st.subheader("🌍 국적별 필터링")
    
    country_list = ["전체보기"] + sorted(list(df['origin_country'].dropna().unique()))
    
    def format_country_with_flag(country_name):
        if country_name == "전체보기": return "🌐 전체보기"
        return f"{flag_dict.get(country_name, '🏳️')} {country_name}"
    
    selected_country = st.selectbox("조회하고 싶은 국적을 선택해 봐:", country_list, format_func=format_country_with_flag)
    
    if selected_country != "전체보기":
        filtered_df = df[df['origin_country'] == selected_country]
    else:
        filtered_df = df
        
    st.success(f"선택한 조건에 맞는 비행기가 총 {len(filtered_df)}대 포착되었어!")
    
    map_df = filtered_df.dropna(subset=['latitude', 'longitude']).copy()

    # ---------------------------------------------------------
    # [지도 시각화] 국기 이모지를 지도 위에 직접 그리기!
    # ---------------------------------------------------------
    if not map_df.empty:
        map_df['callsign'] = map_df['callsign'].fillna("알 수 없음")
        map_df['baro_altitude'] = map_df['baro_altitude'].fillna(0)
        map_df['velocity'] = map_df['velocity'].fillna(0)
        
        view_state = pdk.ViewState(
            latitude=36.5,
            longitude=127.5,
            zoom=6.5,
            pitch=45, 
        )

        # 1. 비행기 위치를 나타내는 빨간 점(Scatterplot)
        scatter_layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            get_position='[longitude, latitude]',
            get_radius=5000, 
            get_fill_color='[255, 75, 75, 200]', 
            pickable=True, 
        )

        # 2. 💡 비행기 점 바로 옆에 국기를 텍스트로 그려주는 레이어 추가!
        text_layer = pdk.Layer(
            "TextLayer",
            data=map_df,
            get_position='[longitude, latitude]',
            get_text='flag', # 새로 만든 flag 컬럼의 이모지를 가져옴
            get_size=25, # 국기 이모지 크기
            get_alignment_baseline="'bottom'", # 점 위쪽에 띄우기 위해 정렬
            pickable=False, # 툴팁 중복 방지
        )

        # 3. 툴팁에도 새로 만든 'country_with_flag' 열을 사용해서 국기가 나오게 수정
        tooltip = {
            "html": """
            <b>호출부호(Callsign):</b> {callsign} <br/>
            <b>국적:</b> {country_with_flag} <br/>
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

        # 4. 점(scatter_layer)과 국기(text_layer)를 둘 다 layers 리스트에 넣어서 렌더링
        r = pdk.Deck(
            layers=[scatter_layer, text_layer],
            initial_view_state=view_state,
            tooltip=tooltip,
            map_style='mapbox://styles/mapbox/dark-v10' 
        )
        
        st.pydeck_chart(r)
    else:
        st.info("지도에 표시할 수 있는 위치 정보가 없어.")

    st.markdown("---")
    with st.expander("📊 수신된 원본 비행기 세부 데이터 표 보기"):
        st.dataframe(filtered_df)
