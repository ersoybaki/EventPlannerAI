import os, googlemaps, parsedatetime, datetime, folium
import pandas as pd
import streamlit as st
import pydeck as pdk
from streamlit_folium import folium_static
from dotenv import load_dotenv
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

gmaps  = googlemaps.Client(key=os.environ.get("GOOGLEMAPS_API_KEY"))


def geocode_address(address: str) -> tuple:
    """
    Convert a free-form address into geographic coordinates (latitude and longitude).

    Imports needed:
        import googlemaps   # uses the global gmaps client

    Parameters:
        address (str): The address or place name to geocode.

    Returns:
        tuple: A (latitude, longitude) pair as floats.

    Raises:
        ValueError: If the address cannot be geocoded.
    """
    import googlemaps
    import os
    from dotenv import load_dotenv

    gmaps  = googlemaps.Client(key=os.environ.get("GOOGLEMAPS_API_KEY"))
    geocode_result = gmaps.geocode(address)
    if geocode_result:
        loc = geocode_result[0]["geometry"]["location"]
        return [loc["lat"], loc["lng"]]
    else:
        raise ValueError("Address not found.")


def search_nearby_venues(lat: float, lng: float, radius: int = 5000, place_type: str = None, keyword: str = None, max_results: int = 5) -> list:
    """
    Retrieve a list of nearby venues matching specified criteria.

    Imports needed:
        import googlemaps   # uses the global gmaps client

    Parameters:
        location (tuple): A (latitude, longitude) pair.
        radius (int, optional): Search radius in meters. Defaults to 5000.
        place_type (str, optional): A Google Places API type filter.
        keyword (str, optional): A term to match against venue names or attributes.

    Returns:
        list: A list of place result dictionaries.
    """
    import googlemaps
    import os
    from dotenv import load_dotenv
    
    gmaps  = googlemaps.Client(key=os.environ.get("GOOGLEMAPS_API_KEY"))

    location = (lat, lng) 
    places_result = gmaps.places_nearby(
        location=location,
        radius=radius,
        type=place_type,
        keyword=keyword,
        min_price=0,
    )
    results = places_result.get('results', [])
    return results[:max_results]  

def dietary_request(texts: list[str]) -> dict[str, int]:
    """
    Query the Google Places API for nearby venues around a geographic point.

    Uses `gmaps.places_nearby` under the hood to retrieve up to `max_results` places
    matching the given filters, sorted by prominence.

    Parameters:
        lat (float):
            Latitude of the search center in decimal degrees.
        lng (float):
            Longitude of the search center in decimal degrees.
        radius (int, optional):
            Search radius in meters. Defaults to 5000.
        place_type (str, optional):
            Restrict results to places of this type (e.g., "restaurant", "cafe").
            If None, no type filter is applied.
        keyword (str, optional):
            A free-text search term to match against place names and attributes.
            If None, no keyword filtering is applied.
        max_results (int, optional):
            Maximum number of place dicts to return. Defaults to 5.

    Returns:
        list[dict]:
            A list of place result dictionaries, each containing at least the
            fields returned by the Places API `places_nearby` endpoint.
            If fewer than `max_results` places are found, returns all available.
    """
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
                         budget_per_person: float = 0.0,  # in euros
                         max_results: int = 10,
                         event_day: str = None) -> list[dict]:

    """
    Search for nearby venues whose price level matches a user’s per-person budget.

    This function:
        1. Maps the user’s euro budget to a Google Maps price_level (0–4).
        2. Uses the Places API Nearby Search with both min_price and max_price set to that level.
        3. Returns up to `max_results` venue dicts matching the filter.

    Parameters:
        lat (float):
            Latitude of the search center.
        lng (float):
            Longitude of the search center.
        radius (int, optional):
            Search radius in meters. Defaults to 10_000.
        place_type (str, optional):
            One of Google Places’ supported `type` filters (e.g. "restaurant", "cafe").
            Defaults to None (no type filter).
        keyword (str, optional):
            Free-text term to further filter nearby results. Defaults to None.
        budget_per_person (float, optional):
            Maximum euros you’re willing to spend per person. This is
            internally converted to a `price_level` bucket:
              0 ⇒ €0 or less (free)
              1 ⇒ €1–€10 (inexpensive)
              2 ⇒ €11–€30 (moderate)
              3 ⇒ €31–€60 (expensive)
              4 ⇒ €61+ (very expensive)
            Defaults to 0.0.
        max_results (int, optional):
            Maximum number of venues to return. Defaults to 5.

    Returns:
        List[dict]:
            A list of venue result dictionaries as returned by
            `gmaps.places_nearby()`, filtered by the computed price level
            and truncated to at most `max_results` entries.

    Raises:
        googlemaps.exceptions.ApiError:
            If the Places API request fails.
    """

    # 1) budget → price_level mapping
    if budget_per_person <= 0:
        level = 0      # free
    elif budget_per_person <= 10:
        level = 1      # €1–€10 
    elif budget_per_person <= 30:
        level = 2      # €11–€30 
    elif budget_per_person <= 60:
        level = 3      # €31–€60 
    else:
        level = 4      # €61+ 

    # build nearby search params, using min_price=max_price=level
    params = {
        "location": (lat, lng),
        "radius": radius,
        "type": place_type,
        "keyword": keyword,
        "max_price": level,
    }

    # drop  None values
    params = {k: v for k, v in params.items() if v is not None}

    if place_type not in PRICEABLE_TYPES:
        params.pop("max_price", None)  

    response = gmaps.places_nearby(**params)
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
    """
    Search for nearby venues that satisfy budget, opening-hours, and special-request constraints.

    This function performs a three-stage filter on Google Places results:

    1. **Budget Filter**  
       Uses a Nearby Search to retrieve up to `max_results * 2` places whose
       Google `price_level` maps to your `budget_per_person` bracket:
           - ≤ €0 ⇒ 0
           - €1–10 ⇒ 1
           - €11–30 ⇒ 2
           - €31–60 ⇒ 3
           - ≥ €61 ⇒ 4

    2. **Opening-Hours Filter** (optional)  
       If `event_time` is provided, parses it into a weekday and 24-hour time,
       then retains only venues open at that specific slot. Venues without any
       hours data are assumed “always open.”

    3. **Special-Request Filter** (optional)  
       If `special_request` is provided, fetches up to 5 recent reviews per venue,
       counts mentions of the request keyword (case-insensitive), and assigns each
       venue a `relevance_score = 1 + match_count`. Venues are then sorted by score.

    Parameters
    ----------
    lat : float
        Latitude of search center.
    lng : float
        Longitude of search center.
    radius : int, default 10000
        Search radius in meters.
    place_type : str | None
        Google Places “type” (e.g. "restaurant") or None for no type filter.
    keyword : str | None
        Free-text keyword to refine the Nearby Search.
    budget_per_person : float, default 0.0
        Maximum spend per person in euros; mapped to Google `price_level`.
    special_request : str | None
        Extra requirement (e.g. “vegan menu”); triggers review-based scoring.
    event_time : str | None
        Desired date/time (e.g. "tomorrow evening" or "09-07-2025 18:00").
        If provided, only venues open at that slot are returned.
    max_results : int, default 5
        Maximum number of venues returned after all filters.

    Returns
    -------
    list of dict
        Up to `max_results` Google Place dicts matching all active filters.
        If `special_request` is used, each dict includes:
          - "request_matches": int, count of review hits
          - "relevance_score": int, base score (+ hits)
    
    Raises
    ------
    ValueError
        If `event_time` cannot be parsed by `get_event_day_and_time`.
    googlemaps.exceptions.ApiError
        If any Places API call fails.
    """
    day = None
    time = None
    if event_time:
        try:
            day_name, time = get_event_day_and_time(event_time) 
            day = WEEKDAY_TO_NUM.get(day_name)
        except Exception as e:
            print(f"Error parsing event time: {e}")
            event_time = None

    # Combine keyword and special_request for the initial search
    combined_keyword = " ".join(filter(None, [keyword, special_request]))
    
    # Filter venues by budget first
    venues = get_venues_by_budget(
        lat=lat, lng=lng,
        radius=radius,
        place_type=place_type,
        keyword=combined_keyword or None,
        budget_per_person=budget_per_person,
        max_results=max_results * 2  
    )

    # Filter venues by opening hours if event_time is provided
    if event_time and day is not None and time is not None:
        still_open = []
        for v in venues:
            try:
                details = gmaps.place(
                    place_id=v["place_id"],
                    fields=["opening_hours"],
                )
                periods = (
                    details["result"]
                    .get("opening_hours", {})
                    .get("periods", [])
                )
                if periods and is_open(periods, day, time):
                    still_open.append(v)
                elif not periods:
                    # If no opening hours info,assume always open
                    still_open.append(v)
            except Exception as e:
                print(f"Error checking opening hours for venue: {e}")
                # Include venue if we can't check hours
                still_open.append(v)
        venues = still_open

    # This is more thorough but uses more API calls
    if special_request and len(special_request.strip()) > 0:
        try:
            req_lower = special_request.lower()
            enhanced_venues = []
            
            for v in venues:
                # Start with a base score for venues that matched the keyword search
                venue_score = 1
                
                try:
                    # Fetch reviews to check for special request mentions
                    details = gmaps.place(
                        place_id=v["place_id"],
                        fields=["reviews"]
                    )
                    reviews = details["result"].get("reviews", [])
                    
                    if reviews:
                        review_texts = [r.get("text", "").lower() for r in reviews]
                        match_count = sum(review.count(req_lower) for review in review_texts)
                        
                        if match_count > 0:
                            # Boost score for venues mentioned in reviews
                            venue_score += match_count
                            v["request_matches"] = match_count
                    
                    # Include venue with its score
                    v["relevance_score"] = venue_score
                    enhanced_venues.append(v)
                    
                except Exception as e:
                    print(f"Error checking reviews for venue {v.get('name', 'Unknown')}: {e}")
                    # Include venue even if review check fails
                    v["relevance_score"] = venue_score
                    enhanced_venues.append(v)
            
            # Sort by relevance score (higher is better)
            venues = sorted(enhanced_venues, key=lambda x: x.get("relevance_score", 0), reverse=True)
            
        except Exception as e:
            print(f"Error in special request filtering: {e}")
            # If special request filtering fails, continue with existing venues

    # Return the top results
    return venues[:max_results]
    

def get_event_day_and_time(event_date: str) -> tuple[str, str]:
    """
    Get the weekday name and time for a given date expression,
    including fuzzy dates or explicit dates.

    Args:
        event_date (str): A date string or fuzzy date expression
            (e.g., "tomorrow evening", "09-07-2025 14:30", "2025-07-09T09:15").

    Returns:
        tuple[str, str]:
            - Weekday name (e.g., "Wednesday")
            - Time string in HHMM format (e.g., "1830")

    Raises:
        ValueError: If the phrase could not be parsed into a date.
    """
    cal = parsedatetime.Calendar()
    time_struct, parse_status = cal.parse(event_date)

    if parse_status:
        # parsedatetime succeeded
        dt = datetime.datetime(*time_struct[:6])
    else:
        # fallback to explicit formats (with optional time)
        dt = None
        for fmt in (
            "%d-%m-%Y %H:%M",
            "%d-%m-%Y %H%M",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M",
            "%d-%m-%Y",
            "%Y-%m-%d",
        ):
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
    # Matching the opening hours with the prefered event time   
    schedules: list[tuple[str, dict[str,str]]] = [] 
    for place in results:
        raw_pid = place.get("place_id")
        raw_details = gmaps.place(place_id=raw_pid, fields=["name", "opening_hours"])

        res = raw_details.get("result", {})
        name = res.get("name", raw_pid)
        raw = res.get("opening_hours", {}).get("weekday_text", [])

        schedule: dict[str, str] = {}
        for entry in raw:
            day, times = entry.split(": ", 1)
            schedule[day] = times

        schedules.append((name, schedule))

    return schedules

def is_open(periods: list[dict], day: int, time: str) -> bool:
    """
    Return True if the venue is open on `user_day` at `user_hhmm`.

    Args:
        periods     Google `opening_hours.periods`
        user_day    int 0-6 where 0 = Sunday
        user_hhmm   "HHMM" (24-h)      e.g. "1845"

    Handles periods that close after midnight, e.g.
        open day=5 time=1130  →  close day=6 time=0100
    """
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
            # no explicit close → assume closes same day at 23:59
            c_day, c_time = o_day, 2359

        # same‐day period
        if o_day == c_day:
            if day == o_day and o_time <= t_user < c_time:
                return True
        else:
            # overnight period
            # part A: before midnight slice
            if day == o_day and t_user >= o_time:
                return True
            # part B: after‐midnight slice
            if day == c_day and t_user < c_time:
                return True

    return False



def create_venue_map(venues):
    # Skip if no venues
    if not venues:
        return
    
    # Get coordinates of first venue to center the map
    # If no venue with geometry exists, use a default location
    center_lat, center_lng = None, None
    for venue in venues:
        if "geometry" in venue and "location" in venue["geometry"]:
            center_lat = venue["geometry"]["location"]["lat"]
            center_lng = venue["geometry"]["location"]["lng"]
            break
    
    # If no valid venue was found, return
    if center_lat is None or center_lng is None:
        st.error("No valid venue coordinates found")
        return
        
    # Create a single map centered at the first venue
    m = folium.Map(location=[center_lat, center_lng], zoom_start=13)
    
    # Add all venues as markers to this map
    for venue in venues:
        if "geometry" not in venue or "location" not in venue["geometry"]:
            continue
        
        lat = venue["geometry"]["location"]["lat"]
        lng = venue["geometry"]["location"]["lng"]
        name = venue["name"]
        
        # Get additional venue details for the popup if available
        address = venue.get("vicinity", "Address not available")
        rating = venue.get("rating", "No rating")
        
         # Create Google Maps link
        place_id = venue.get("place_id", "")
        if place_id:
            google_maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
        else:
            # Fallback to coordinates if place_id not available
            google_maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
        

        # Create a more informative popup
        popup_html = f"""
        <div style="width:200px;border-radius:25px;">
            <h4>{name}</h4>
            <p><b>Address:</b> {address}</p>
            <p><b>Rating:</b> {rating}/5</p>
            <p><a href="{google_maps_url}" target="_blank">View on Google Maps</a></p>
        </div>
        """

        tooltip_html = f"""
        <div style="width:100%;font-size:16px">
            <strong>{name}</strong>
        """
        
        # Add marker with popup/tooltip
        folium.Marker(
            location=[lat, lng],
            tooltip=tooltip_html,
            popup=folium.Popup(popup_html, max_width=300),
            
            icon=folium.Icon(color='red')
        ).add_to(m)
    
    # If we have multiple venues, fit the bounds of the map to show all markers
    if len(venues) > 1:
        # Get all coordinates
        coordinates = []
        for venue in venues:
            if "geometry" in venue and "location" in venue["geometry"]:
                lat = venue["geometry"]["location"]["lat"]
                lng = venue["geometry"]["location"]["lng"]
                coordinates.append([lat, lng])
        
        if coordinates:
            m.fit_bounds(coordinates)
    
    # Display the map in Streamlit
    folium_static(m, width=700, height=500)


if __name__ == "__main__":
    location = "Nicosia, Cyprus"
    loc = geocode_address(location)

    venues = get_venues_by_budget_and_requests(
        lat=loc[0],
        lng=loc[1],
        radius=5000,
        place_type="cafe",
        keyword="cafe",
        budget_per_person=20,
        event_time="tomorrow evening",
        max_results=5
    )

    create_venue_map(venues)
    # x = geocode_address("Eindhoven, Netherlands")
    # df = pd.DataFrame([x], columns=["lat", "lon"])

    # st.map(df, color="#ff0000", zoom=12, use_container_width=True)

