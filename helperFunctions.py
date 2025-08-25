import os, googlemaps, parsedatetime, datetime, folium
import streamlit as st
from streamlit_folium import folium_static
from collections import defaultdict

DIETARY_KEYWORDS = {
    "vegetarian": ["vegetarian", "veggie", "plant-based"],
    "vegan": ["vegan", "100% plant-based", "dairy-free"],
    "gluten_free": ["gluten-free", "celiac", "no gluten"],
    "halal": ["halal", "zabiha", "halāl"],
    "steak": ["steak house", "steakhouse", "grill"],
    "pescatarian": ["pescatarian", "seafood only", "fish only"],
}

PRICEABLE_TYPES = {
    "restaurant", "cafe", "bar",
    "meal_takeaway", "meal_delivery",
    "night_club", "bakery"
}

WEEKDAY_TO_NUM = {
    "Sunday": 0,
    "Monday": 1,
    "Tuesday": 2,
    "Wednesday": 3,
    "Thursday": 4,
    "Friday": 5,
    "Saturday": 6,
}

# --- Lazy Google Maps client ---
_GMAPS = None
def get_gmaps():
    global _GMAPS
    if _GMAPS is None:
        key = None

        # Prefer Streamlit session (when inside the Streamlit app)
        try:
            import streamlit as st
            # Only if Streamlit is actually running
            if st.runtime.exists():
                key = st.session_state.get("google_api_key")
        except Exception:
            pass

        # Fallbacks for non-Streamlit child processes
        if not key:
            key = os.environ.get("RUNTIME_GOOGLEMAPS_API_KEY")  # set by parent before exec


        if not key:
            raise ValueError("GOOGLEMAPS_API_KEY is not set. Provide it in the UI.")
        _GMAPS = googlemaps.Client(key=key)
    return _GMAPS


def geocode_address(address: str) -> tuple:
    client = get_gmaps()
    geocode_result = client.geocode(address)
    if geocode_result:
        loc = geocode_result[0]["geometry"]["location"]
        return [loc["lat"], loc["lng"]]
    else:
        raise ValueError("Address not found.")


def search_nearby_venues(lat: float, lng: float, radius: int = 5000, place_type: str = None, keyword: str = None, max_results: int = 5) -> list:
    client = get_gmaps()
    places_result = client.places_nearby(
        location=(lat, lng),
        radius=radius,
        type=place_type,
        keyword=keyword,
        min_price=0,
    )
    results = places_result.get('results', [])
    return results[:max_results]  


def dietary_request(texts: list[str]) -> dict[str, int]:
    tag_hits = defaultdict(int)
    for text in texts:
        lower = text.lower()
        for tag, keywords in DIETARY_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                tag_hits[tag] += 1
    return dict(tag_hits)


def get_venues_by_budget(lat: float,
                         lng: float,
                         radius: int = 10_000,
                         place_type: str = None,
                         keyword: str = None,
                         budget_per_person: float = 0.0,
                         max_results: int = 10,
                         event_day: str = None) -> list[dict]:

    if budget_per_person <= 0:
        level = 0
    elif budget_per_person <= 10:
        level = 1
    elif budget_per_person <= 30:
        level = 2
    elif budget_per_person <= 60:
        level = 3
    else:
        level = 4

    params = {
        "location": (lat, lng),
        "radius": radius,
        "type": place_type,
        "keyword": keyword,
        "max_price": level,
    }
    params = {k: v for k, v in params.items() if v is not None}
    if place_type not in PRICEABLE_TYPES:
        params.pop("max_price", None)  

    client = get_gmaps()
    response = client.places_nearby(**params)
    results = response.get("results", [])
    return results[:max_results]  


def get_venues_by_budget_and_requests(lat: float,
                                     lng: float,
                                     radius: int = 10_000,
                                     place_type: str = None,
                                     keyword: str = None,
                                     budget_per_person: float = 0.0,
                                     special_request: str = None,
                                     event_time: str = None,
                                     max_results: int = 5) -> list[dict]:
    day = None
    time = None
    if event_time:
        try:
            day_name, time = get_event_day_and_time(event_time) 
            day = WEEKDAY_TO_NUM.get(day_name)
        except Exception as e:
            print(f"Error parsing event time: {e}")
            event_time = None

    combined_keyword = " ".join(filter(None, [keyword, special_request]))
    venues = get_venues_by_budget(
        lat=lat, lng=lng,
        radius=radius,
        place_type=place_type,
        keyword=combined_keyword or None,
        budget_per_person=budget_per_person,
        max_results=max_results * 2  
    )

    client = get_gmaps()

    if event_time and day is not None and time is not None:
        still_open = []
        for v in venues:
            try:
                details = client.place(place_id=v["place_id"], fields=["opening_hours"])
                periods = details["result"].get("opening_hours", {}).get("periods", [])
                if periods and is_open(periods, day, time):
                    still_open.append(v)
                elif not periods:
                    still_open.append(v)
            except Exception as e:
                print(f"Error checking opening hours for venue: {e}")
                still_open.append(v)
        venues = still_open

    if special_request and len(special_request.strip()) > 0:
        try:
            req_lower = special_request.lower()
            enhanced_venues = []
            for v in venues:
                venue_score = 1
                try:
                    details = client.place(place_id=v["place_id"], fields=["reviews"])
                    reviews = details["result"].get("reviews", [])
                    if reviews:
                        review_texts = [r.get("text", "").lower() for r in reviews]
                        match_count = sum(review.count(req_lower) for review in review_texts)
                        if match_count > 0:
                            venue_score += match_count
                            v["request_matches"] = match_count
                    v["relevance_score"] = venue_score
                    enhanced_venues.append(v)
                except Exception as e:
                    print(f"Error checking reviews for venue {v.get('name', 'Unknown')}: {e}")
                    v["relevance_score"] = venue_score
                    enhanced_venues.append(v)
            venues = sorted(enhanced_venues, key=lambda x: x.get("relevance_score", 0), reverse=True)
        except Exception as e:
            print(f"Error in special request filtering: {e}")
    return venues[:max_results]


def get_event_day_and_time(event_date: str) -> tuple[str, str]:
    cal = parsedatetime.Calendar()
    time_struct, parse_status = cal.parse(event_date)
    if parse_status:
        dt = datetime.datetime(*time_struct[:6])
    else:
        dt = None
        for fmt in ("%d-%m-%Y %H:%M", "%d-%m-%Y %H%M", "%Y-%m-%d %H:%M",
                    "%Y-%m-%dT%H:%M", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                dt = datetime.datetime.strptime(event_date, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            raise ValueError(f"Could not parse the phrase: {event_date}")
    weekday = dt.strftime("%A")
    time_str = dt.strftime("%H%M")
    return weekday, time_str


def get_venue_opening_hours(results: list[dict]) -> list[tuple[str, dict[str, str]]]:
    client = get_gmaps()
    schedules = []
    for place in results:
        raw_pid = place.get("place_id")
        raw_details = client.place(place_id=raw_pid, fields=["name", "opening_hours"])
        res = raw_details.get("result", {})
        name = res.get("name", raw_pid)
        raw = res.get("opening_hours", {}).get("weekday_text", [])
        schedule = {}
        for entry in raw:
            day, times = entry.split(": ", 1)
            schedule[day] = times
        schedules.append((name, schedule))
    return schedules


def is_open(periods: list[dict], day: int, time: str) -> bool:
    t_user = int(time)
    for p in periods:
        o = p.get("open")
        if not o:
            continue
        o_day, o_time = o["day"], int(o["time"])
        c = p.get("close")
        if c:
            c_day, c_time = c["day"], int(c["time"])
        else:
            c_day, c_time = o_day, 2359
        if o_day == c_day:
            if day == o_day and o_time <= t_user < c_time:
                return True
        else:
            if day == o_day and t_user >= o_time:
                return True
            if day == c_day and t_user < c_time:
                return True
    return False


def create_venue_map(venues):
    if not venues:
        return
    center_lat, center_lng = None, None
    for venue in venues:
        if "geometry" in venue and "location" in venue["geometry"]:
            center_lat = venue["geometry"]["location"]["lat"]
            center_lng = venue["geometry"]["location"]["lng"]
            break
    if center_lat is None or center_lng is None:
        st.error("No valid venue coordinates found")
        return
    m = folium.Map(location=[center_lat, center_lng], zoom_start=13)
    for venue in venues:
        if "geometry" not in venue or "location" not in venue["geometry"]:
            continue
        lat = venue["geometry"]["location"]["lat"]
        lng = venue["geometry"]["location"]["lng"]
        name = venue["name"]
        address = venue.get("vicinity", "Address not available")
        rating = venue.get("rating", "No rating")
        place_id = venue.get("place_id", "")
        if place_id:
            google_maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
        else:
            google_maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
        popup_html = f"""
        <div style="width:200px;border-radius:25px;">
            <h4>{name}</h4>
            <p><b>Address:</b> {address}</p>
            <p><b>Rating:</b> {rating}/5</p>
            <p><a href="{google_maps_url}" target="_blank">View on Google Maps</a></p>
        </div>
        """
        tooltip_html = f"<div style='width:100%;font-size:16px'><strong>{name}</strong>"
        folium.Marker(
            location=[lat, lng],
            tooltip=tooltip_html,
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color='red')
        ).add_to(m)
    if len(venues) > 1:
        coordinates = []
        for venue in venues:
            if "geometry" in venue and "location" in venue["geometry"]:
                lat = venue["geometry"]["location"]["lat"]
                lng = venue["geometry"]["location"]["lng"]
                coordinates.append([lat, lng])
        if coordinates:
            m.fit_bounds(coordinates)
    folium_static(m, width=700, height=500)


if __name__ == "__main__":
    location = "Nicosia, Cyprus"
    loc = geocode_address(location)
    venues = get_venues_by_budget_and_requests(
        lat=loc[0], lng=loc[1],
        radius=5000,
        place_type="cafe",
        keyword="cafe",
        budget_per_person=20,
        event_time="tomorrow evening",
        max_results=5
    )
    create_venue_map(venues)
