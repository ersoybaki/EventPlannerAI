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

def get_venues_with_dietary_tags(lat: float, lng: float,
                                 radius: int = 5000,
                                 place_type: str = None,
                                 keyword: str = None,
                                 max_results: int = 5) -> list[dict]:
    """
        Combine nearby place search with dietary-tag analysis on each venue’s reviews.

        For each venue found within the specified radius:
        1. Fetch its Place Details (requesting `name` and `reviews`).
        2. Extract the review texts and count dietary keyword occurrences via `dietary_request`.
        3. Filter tags by a minimum hit threshold (>=1 by default).
        4. Append a `dietary_tags` dict to each venue’s data.

        Parameters:
            lat (float):
                Latitude of the search center.
            lng (float):
                Longitude of the search center.
            radius (int, optional):
                Search radius in meters for `search_nearby_venues`. Defaults to 5000.
            place_type (str, optional):
                Place type filter passed to `search_nearby_venues`.
            keyword (str, optional):
                Free-text keyword filter passed to `search_nearby_venues`.
            max_results (int, optional):
                Maximum venues to process.

        Returns:
            list[dict]:
                A list of enriched venue dicts. Each dict includes all original
                fields from `places_nearby` plus:
                - `dietary_tags` (dict[str, int]): tags meeting the threshold.
        """
    
    venues = search_nearby_venues(lat, lng, radius, place_type, keyword, max_results)
    enriched = []
    for v in venues:
        pid = v["place_id"]
        details = gmaps.place(place_id=pid, fields=["name", "reviews"])
        reviews = details["result"].get("reviews", [])
        texts = [r["text"] for r in reviews]
        tags = dietary_request(texts)
        # You can apply a threshold, e.g. only keep tags with count >= 2
        filtered = {t: c for t, c in tags.items() if c >= 1}
        v["dietary_tags"] = filtered
        enriched.append(v)
    return enriched             

if __name__ == "__main__":
    location = "Eindhoven, Netherlands"
    lat, lng = geocode_address(location)
    venues = get_venues_with_dietary_tags(lat, lng,
                                          radius=2000,
                                          place_type="restaurant",
                                          keyword="dinner",
                                          max_results=5)
    for place in venues:
        if (len(place["dietary_tags"]) == 0):
            continue
        print(place["name"])
        print("Dietary tags:", place["dietary_tags"])
        print("---")
    # print(venues)