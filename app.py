import requests  # HTTP 통신을 위해 requests 라이브러리를 불러와. (API에 데이터를 요청하기 위함)
import pandas as pd  # 수신한 리스트 데이터를 2차원 표 형태인 데이터프레임 구조로 변환하기 위해 pandas를 불러와.
import streamlit as st  # 웹 화면에 지도와 데이터를 시각화하기 위해 streamlit 라이브러리를 불러와.

# ==========================================
# 1. OpenSky API 데이터 호출 함수 정의
# ==========================================
def get_korea_flights(client_id, client_secret):  # API 인증에 필요한 ID와 시크릿 키를 인자로 받는 함수야.
    
    # --- [OAuth2 인증 토큰 발급] ---
    # OpenSky OAuth2 인증 토큰을 발급받기 위한 엔드포인트 URL이야.
    token_url = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
    
    # 토큰 발급에 필요한 요청 데이터(payload)를 딕셔너리로 묶어줘.
    token_data = {
        "grant_type": "client_credentials",  # 서버-대-서버 통신에 적합한 '클라이언트 자격 증명' 방식을 사용한다고 명시해.
        "20725user-api-client": client_id,  # 사용자의 OpenSky 클라이언트 ID 값을 넣어.
        "GsWs26aDoIMRoAtHmpbX0BDgJrkft5fy": client_secret  # 사용자의 OpenSky 클라이언트 시크릿 값을 넣어.
    }
    
    try:  # 네트워크 오류나 토큰 발급 실패(예: 잘못된 키)를 대비해 try-except 블록을 시작해.
        # 토큰 URL로 POST 요청을 보내고, 응답 지연을 대비해 timeout을 30초로 제한해.
        token_response = requests.post(token_url, data=token_data, timeout=30)
        # HTTP 응답 코드가 200번대(성공)가 아니면 강제로 에러를 발생시켜 catch(except)로 넘겨.
        token_response.raise_for_status()  
        # 응답받은 JSON 포맷의 데이터에서 실제 사용할 'access_token' 값만 추출해 변수에 저장해.
        access_token = token_response.json().get("access_token")
    except requests.exceptions.RequestException as e:  # 요청 중 발생한 모든 통신/HTTP 예외를 여기서 잡아내.
        # 토큰 발급에 실패했다는 메시지와 에러 내용을 콘솔(또는 터미널)에 출력해.
        print(f"토큰 발급 실패: {e}")
        # 인증 토큰이 없으면 다음 데이터 조회를 할 수 없으니 None을 반환하고 함수를 바로 종료해.
        return None

    # --- [비행기 데이터 실시간 조회] ---
    # 전체 비행기 상태(State Vectors) 데이터를 가져올 OpenSky API 주소야.
    api_url = "https://opensky-network.org/api/states/all"
    
    # API 서버에 인증된 사용자임을 증명하기 위해 헤더에 Authorization을 Bearer 토큰 방식으로 설정해.
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 한반도 상공의 위도와 경도 범위(Bounding Box)를 쿼리 파라미터로 설정해. (서버에서 이 영역만 필터링해서 줌)
    params = {
        "lamin": 33.0,  # 최소 위도 (한반도 남단)
        "lamax": 39.0,  # 최대 위도 (한반도 북단)
        "lomin": 124.0, # 최소 경도 (서해)
        "lomax": 132.0  # 최대 경도 (동해)
    }
    
    try:  # 실제 비행기 데이터 조회 중 발생할 수 있는 네트워크 오류를 대비해 다시 try 블록을 열어.
        # 설정한 URL, 파라미터, 헤더를 담아 GET 방식으로 요청하고, 여기서도 timeout을 30초로 제한해.
        response = requests.get(api_url, params=params, headers=headers, timeout=30)
        # 데이터 응답이 성공(200)이 아니라면 에러를 발생시켜. (예: rate limit 초과 등)
        response.raise_for_status()
        # 성공적으로 수신한 JSON 문자열 데이터를 파이썬 딕셔너리로 변환해.
        data = response.json()
    except requests.exceptions.RequestException as e:  # 데이터를 가져오다가 문제가 생기면 잡아내.
        # 데이터 조회에 실패했다는 메시지와 원인을 출력해.
        print(f"데이터 응답 실패: {e}")
        # 에러가 발생했으므로 None을 반환하고 함수를 끝내.
        return None

    # --- [Pandas 데이터프레임 변환] ---
    # 전체 응답 데이터 구조 중 'states'라는 키에 들어있는 실제 비행기 리스트만 뽑아내.
    states = data.get("states")
    
    # 만약 조회된 시간대에 한반도 상공에 비행기가 한 대도 없다면 (states가 None이거나 빈 리스트일 때),
    if not states:
        # 데이터가 없다는 안내 메시지를 출력해.
        print("현재 한반도 상공에 조회된 비행기 데이터가 없어.")
        # Streamlit 앱에서 에러가 나지 않고 빈 화면을 그릴 수 있도록 빈 데이터프레임을 반환해.
        return pd.DataFrame()

    # OpenSky API 명세서에 지정된 17개 컬럼(열) 이름들을 순서대로 리스트로 정의해. (원래 API는 값만 리스트로 반환함)
    columns = [
        "icao24", "callsign", "origin_country", "time_position", "last_contact", 
        "longitude", "latitude", "baro_altitude", "on_ground", "velocity", 
        "true_track", "vertical_rate", "sensors", "geo_altitude", "squawk", 
        "spi", "position_source"
    ]
    
    # 리스트 형태로 받은 비행기 상태 데이터(states)에 위에서 만든 컬럼 이름을 매핑해서 pandas 데이터프레임을 생성해.
    df = pd.DataFrame(states, columns=columns)
    
    # 최종적으로 정형화된 데이터프레임을 반환해서 외부(Streamlit)에서 쓸 수 있게 해.
    return df


# ==========================================
# 2. Streamlit 웹 화면 구성 및 실행 파트
# ==========================================

# 웹 앱의 메인 제목을 브라우저 화면에 띄워줘.
st.title("✈️ 실시간 한반도 비행기 레이더")

# ⚠️ 여기에 본인의 OpenSky API ID와 시크릿 키를 문자열로 정확하게 입력해야 해!
CLIENT_ID = "20725user-api-client"
CLIENT_SECRET = "GsWs26aDoIMRoAtHmpbX0BDgJrkft5fy"

# 데이터를 불러오는 동안 사용자가 지루하지 않게 화면에 로딩 애니메이션(스피너)을 보여줘.
with st.spinner("한반도 상공의 비행기 데이터를 실시간으로 불러오는 중이야..."):
    # 위에서 정의한 API 호출 함수를 사용해 비행기 데이터를 데이터프레임 형태로 가져와.
    df = get_korea_flights(CLIENT_ID, CLIENT_SECRET)

# [화면 예외 처리 1] API 통신이나 인증 자체에 실패해서 함수가 None을 반환했을 때
if df is None:
    st.error("데이터를 불러오는 데 실패했어. 터미널 창(검은 화면)의 에러 메시지를 확인해 봐!")

# [화면 예외 처리 2] 통신은 성공했지만 현재 한반도 상공에 비행기가 0대일 때
elif df.empty:
    st.warning("현재 지정된 범위(한반도) 상공에 조회된 비행기가 없어. 잠시 후 다시 시도해 봐.")

# [성공 화면 출력] 데이터를 성공적으로 잘 가져왔을 때 화면을 그려주는 로직이야.
else:
    # 현재 상공을 날아다니는 총 비행기 대수를 초록색 성공 박스로 예쁘게 띄워줘.
    st.success(f"현재 한반도 상공에 {len(df)}대의 비행기가 포착되었어!")
    
    # Streamlit의 st.map() 시각화 기능은 'latitude(위도)'와 'longitude(경도)' 데이터가 필수야.
    # 가끔 위치 정보값이 누락(NaN)된 비행기 데이터가 섞여 있으면 지도가 깨질 수 있으므로 위/경도가 확실히 있는 데이터만 걸러내.
    map_df = df.dropna(subset=['latitude', 'longitude'])
    
    # 위치 정보가 필터링된 데이터프레임을 지도 위에 점(Dot)으로 매핑해서 화면에 출력해줘!
    st.map(map_df)
    
    # 지도 밑에 너무 긴 표가 바로 나오면 지저분하니까, 접었다 펼칠 수 있는 토글 메뉴(expander)를 만들어.
    with st.expander("📊 수신된 원본 비행기 세부 데이터 표 보기"):
        # 토글을 열면 17개 컬럼을 가진 가독성 좋은 pandas 데이터프레임 표가 웹 화면에 그대로 표출돼.
        st.dataframe(df)
