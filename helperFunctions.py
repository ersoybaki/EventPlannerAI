import os, googlemaps, parsedatetime, datetime
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

WEEKDAY_TO_NUM = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
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
                         radius: int = 5_000,
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
            Search radius in meters. Defaults to 5_000.
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

    response = gmaps.places_nearby(**params)
    results = response.get("results", [])

    return results[:max_results]  


def get_venues_by_budget_and_requests(lat: float,
                                     lng: float,
                                     radius: int = 5_000,
                                     place_type: str = None,
                                     keyword: str = None,
                                     budget_per_person: float = 0.0,
                                     special_request: str = None,
                                     event_time: str = None,
                                     max_results: int = 5) -> list[dict]:
    """
    Return nearby venues that satisfy **all** of the following, in order:

    1. **Budget** – the place’s Google `price_level` (0–4) must match the
       `budget_per_person` bracket (see mapping below).
    2. **Opening hours** – if `event_time` is supplied, the venue must be
       open at that exact day & time (fuzzy phrases like “tomorrow 18:30”
       are accepted via `get_event_day_and_time`).
    3. **Dietary tag** – if `dietary_keyword` is supplied, at least one user
       review must contain that keyword (case-insensitive).  A per-venue
       ``dietary_tags`` dict is added with hit counts for all tags.

    The search is performed in three passes:
    * *Nearby Search* → budget filter  
      (delegates to `get_venues_by_budget`, cap =`max_results`).
    * *Place Details* → opening-hours filter (`is_open` helper).  
      Skipped if `event_time` is ``None``.
    * *Place Details* → review / dietary filter (`dietary_request`).  
      Skipped if `dietary_keyword` is ``None``.

    ----------
    Parameters
    ----------
    lat, lng : float  
        Latitude / longitude of the search center.
    radius : int, default **5000**  
        Search radius in metres.
    place_type : str | None  
        Google Places “type” filter (e.g. ``"restaurant"``).
    keyword : str | None  
        Additional free-text keyword to refine the Nearby Search.
    budget_per_person : float  
        Maximum spend **per person in euros**.  Mapped to
        ``price_level`` as:  
        ``≤ 0 € → 0``, ``1–10 € → 1``, ``11–30 € → 2``,
        ``31–60 € → 3``, ``≥ 61 € → 4``.
    dietary_keyword : str | None  
        Dietary tag to look for in reviews (e.g. ``"vegan"``, ``"halal"``).
    event_time : str | None  
        Desired date/time the event will take place  
        (e.g. ``"tomorrow evening"``, ``"09-07-2025 18:00"``).  
        If omitted, no opening-hours check is applied.
    max_results : int, default **5**  
        Maximum number of venues returned *after* all filters.

    ----------
    Returns
    ----------
    list[dict]  
        Google place dictionaries that meet every active constraint.
        If a diet filter is applied, each dict also contains:

        ``"dietary_tags" : dict[str, int]`` – keyword hit counts across reviews.

    ----------
    Raises
    ----------
    • `ValueError`   – if `event_time` cannot be parsed.  
    • `googlemaps.exceptions.ApiError`   – propagated from any Places API call.
    """
    day_name, time = get_event_day_and_time(event_time) 
    day = WEEKDAY_TO_NUM[day_name]

    combined_keyword = " ".join(filter(None, [keyword, special_request]))
    
    # filter venues by budget
    venues = get_venues_by_budget(
        lat=lat, lng=lng,
        radius=radius,
        place_type=place_type,
        keyword=combined_keyword or None,
        budget_per_person=budget_per_person,
        max_results=max_results
    )

    # filter venues by opening hours
    if event_time:
        still_open = []
        for v in venues:
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
        venues = still_open
    
    # # filter venues by dietary keyword if provided
    #     if special_request:
    #         req_lower = special_request.lower()
    #         filtered = []
    #         for v in venues:
    #             # fetch up to the first 5 reviews
    #             details = gmaps.place(
    #                 place_id=v["place_id"],
    #                 fields=["reviews"]
    #             )
    #             reviews = [r["text"].lower() for r in details["result"].get("reviews", [])]
    #             # count occurrences of the exact request phrase
    #             match_count = sum(review.count(req_lower) for review in reviews)
    #             if match_count > 0:
    #                 # annotate how often we saw it
    #                 v["request_matches"] = match_count
    #                 filtered.append(v)
    #         return filtered

    # if no special_request, just return the budget (and hours) filtered list
    return venues
    

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
        o_day, o_time = p["open"]["day"],  int(p["open"]["time"])
        c_day, c_time = p["close"]["day"], int(p["close"]["time"])

        if o_day == c_day:                       # normal same-day period
            if day == o_day and o_time <= t_user < c_time:
                return True
        else:                                    # crosses midnight
            # part A: open-day slice (e.g. Fri 11:30-24:00)
            if day == o_day and t_user >= o_time:
                return True
            # part B: after-midnight slice (e.g. Sat 00:00-01:00)
            if day == c_day and t_user < c_time:
                return True

    return False


if __name__ == "__main__":
    location = "Amsterdam, Netherlands"
    loc = geocode_address(location)

    venues = get_venues_by_budget_and_requests(
        lat=loc[0],
        lng=loc[1],
        radius=10000,
        place_type="restaurant",
        keyword="good wifi",
        budget_per_person=80,
        event_time="tomorrow evening",
        max_results=5
    )
    print(venues)


