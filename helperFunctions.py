import os
import googlemaps
from dotenv import load_dotenv
from collections import defaultdict

DIETARY_KEYWORDS = {
    "vegetarian": ["vegetarian", "veggie", "plant-based"],
    "vegan": ["vegan", "100% plant-based", "dairy-free"],
    "gluten_free": ["gluten-free", "celiac", "no gluten"],
    "halal": ["halal", "zabiha", "halāl"],
    "steak_house": ["steak house", "steakhouse", "grill"],
    "pescatarian": ["pescatarian", "seafood only", "fish only"],
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
                         max_results: int = 5) -> list[dict]:

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

def get_venues_by_budget_and_dietary(lat: float,
                                     lng: float,
                                     radius: int = 5_000,
                                     place_type: str = None,
                                     keyword: str = None,
                                     budget_per_person: float = 0.0,
                                     dietary_keyword: str = None,
                                     max_results: int = 5) -> list[dict]:
    """
    Find venues that match BOTH a per-person budget and an optional dietary tag.

    1) Uses get_venues_by_budget(...) to fetch up to max_results places
       at the appropriate Google price_level.
    2) If dietary_keyword is provided, for each budget-filtered venue:
         a) pull its reviews via gmaps.place()
         b) run dietary_request(...) over the texts
         c) keep only those venues where the requested dietary_keyword hit count ≥1
         d) attach a `dietary_tags` dict for full tag breakdown
    3) Return the filtered (and possibly annotated) list.

    Parameters:
        lat, lng (float): center of search
        radius (int): meters
        place_type (str): e.g. "restaurant", "cafe"
        keyword (str): free-text search term
        budget_per_person (float): € per head → price_level 0–4
        dietary_keyword (str, optional): one of your DIETARY_KEYWORDS keys, e.g. "vegan"
        max_results (int): cap on number of places to fetch

    Returns:
        List[dict]: the budget-and-diet-filtered place dicts
    """

    # filter venues by budget
    venues = get_venues_by_budget(
        lat, lng, radius,
        place_type, keyword,
        budget_per_person,
        max_results
    )

    # filter venues by dietary keyword if provided
    if dietary_keyword:
        filtered = []
        for v in venues:
            # look into reviews
            details = gmaps.place(
                place_id=v["place_id"],
                fields=["reviews"]
            )
            texts = [r["text"] for r in details["result"].get("reviews", [])]
            tags = dietary_request(texts)

            if tags.get(dietary_keyword, 0) >= 1:
                v["dietary_tags"] = tags
                filtered.append(v)

        return filtered

    # if no dietary filter, just return the budget‐filtered list
    return venues


if __name__ == "__main__":
    location = "Eindhoven, Netherlands"
    loc = geocode_address(location)
    # venues = get_venues_with_dietary_tags(lat, lng,
    #                                       radius=2000,
    #                                       place_type="restaurant",
    #                                       keyword="dinner",
    #                                       max_results=5)

    venues = get_venues_by_budget_and_dietary(loc[0], loc[1],
                                  radius=5000,
                                  place_type="restaurant",
                                  keyword="restaurant",
                                  budget_per_person=20,
                                  dietary_keyword="vegetarian",
                                  max_results=5)
    # for place in venues:
    #     if (len(place["dietary_tags"]) == 0):
    #         continue
    #     print(place["name"])
    #     print("Dietary tags:", place["dietary_tags"])
    #     print("---")
    print(venues)