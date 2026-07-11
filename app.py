import requests
import pandas as pd
import streamlit as st

# ==========================================
# 1. OpenSky API 데이터 호출 함수 정의
# ==========================================
def get_korea_flights(client_id, client_secret):  
    
    # --- [OAuth2 인증 토큰 발급] ---
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

    # --- [비행기 데이터 실시간 조회] ---
    api_url = "https://opensky-network.org/api/states/all"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    params = {
        "lamin": 33.0, 
        "lamax": 39.0, 
        "lomin": 124.0,
        "lomax": 132.0 
    }
    
    try:  
        response = requests.get(api_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:  
        print(f"데이터 응답 실패: {e}")
        return None

    # --- [Pandas 데이터프레임 변환] ---
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
    # [기능 1] 국적별 비행기 필터링 추가
    # ---------------------------------------------------------
    st.subheader("🌍 1. 국적별 필터링")
    
    # 데이터에 존재하는 국가들의 중복 없는 리스트를 만들고, 맨 앞에 '전체보기'를 추가해.
    country_list = ["전체보기"] + sorted(list(df['origin_country'].dropna().unique()))
    
    # 사용자가 국가를 선택할 수 있는 드롭다운 메뉴를 만들어.
    selected_country = st.selectbox("조회하고 싶은 국적을 선택해 봐:", country_list)
    
    # '전체보기'가 아니면, 선택한 국가의 비행기만 남기도록 데이터프레임을 필터링해.
    if selected_country != "전체보기":
        filtered_df = df[df['origin_country'] == selected_country]
    else:
        filtered_df = df
        
    st.success(f"선택한 조건에 맞는 비행기가 총 {len(filtered_df)}대 포착되었어!")
    
    # 필터링된 데이터로 지도를 그려줘.
    map_df = filtered_df.dropna(subset=['latitude', 'longitude'])
    st.map(map_df)
    
    st.markdown("---") # 화면 분리선
    
    # ---------------------------------------------------------
    # [기능 3] 특정 비행기 1대 타겟팅 대시보드 추가
    # ---------------------------------------------------------
    st.subheader("🎯 2. 특정 비행기 타겟팅 대시보드")
    
    # 필터링된 비행기들 중에서 콜사인(호출부호)이 비어있지 않은 정상적인 것만 리스트로 뽑아.
    valid_callsigns = [c.strip() for c in filtered_df['callsign'].dropna().unique() if c.strip() != ""]
    
    if not valid_callsigns:
        st.info("현재 선택한 조건에서는 호출부호(Callsign)가 확인되는 비행기가 없어.")
    else:
        # 비행기를 선택할 수 있는 메뉴를 만들어.
        selected_callsign = st.selectbox("상세 정보를 볼 비행기(Callsign)를 선택해 봐:", valid_callsigns)
        
        # 선택한 콜사인과 일치하는 데이터 딱 한 줄(row)만 추출해.
        target_flight = filtered_df[filtered_df['callsign'].str.strip() == selected_callsign].iloc[0]
        
        # 3개의 열(column)로 나누어서 멋진 계기판을 만들어.
        col1, col2, col3 = st.columns(3)
        
        # API의 velocity는 m/s 단위, baro_altitude는 미터(m) 단위, true_track은 각도(°)야.
        with col1:
            # 고도를 미터(m) 단위로 표시해. 값이 없으면 '데이터 없음' 처리.
            alt = f"{target_flight['baro_altitude']} m" if pd.notna(target_flight['baro_altitude']) else "데이터 없음"
            st.metric(label="현재 고도", value=alt)
            
        with col2:
            # 속도를 m/s 단위로 표시해.
            vel = f"{target_flight['velocity']} m/s" if pd.notna(target_flight['velocity']) else "데이터 없음"
            st.metric(label="현재 속도", value=vel)
            
        with col3:
            # 비행 방향을 각도로 표시해 (0은 북쪽, 90은 동쪽).
            track = f"{target_flight['true_track']}°" if pd.notna(target_flight['true_track']) else "데이터 없음"
            st.metric(label="비행 방향(방위각)", value=track)

    st.markdown("---")
    
    with st.expander("📊 수신된 원본 비행기 세부 데이터 표 보기"):
        # 표 데이터도 전체가 아닌 필터링된 데이터(filtered_df)를 보여주도록 수정했어.
        st.dataframe(filtered_df)
