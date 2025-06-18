import os
import googlemaps
from dotenv import load_dotenv


# def get_gmaps_client() -> googlemaps.Client:
#     """
#     Initialize and return a Google Maps client using the API key from environment.

#     Imports needed:
#         import os
#         import googlemaps
#         from dotenv import load_dotenv

#     Returns:
#         googlemaps.Client: An authenticated Google Maps client.

#     Raises:
#         ValueError: If the GOOGLE_MAPS_API_KEY environment variable is not set.
#     """
#     import googlemaps
#     import os
#     from dotenv import load_dotenv
    
#     gmaps  = googlemaps.Client(key=os.environ.get("GOOGLEMAPS_API_KEY"))
#     load_dotenv()
#     api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
#     if not api_key:
#         raise ValueError("Please set the GOOGLE_MAPS_API_KEY environment variable.")
#     return googlemaps.Client(key=api_key)


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
        return loc["lat"], loc["lng"]
    else:
        raise ValueError("Address not found.")


def search_nearby_venues(location: tuple, radius: int = 5000, place_type: str = None, keyword: str = None) -> list:
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
    places_result = gmaps.places_nearby(
        location=location,
        radius=radius,
        type=place_type,
        keyword=keyword,
        min_price=0,
    )
    return places_result.get('results', [])


if __name__ == "__main__":
    # Example usage
    user_loc = "Eindhoven, Netherlands"
    try:
        lat, lng = geocode_address(user_loc)
    except ValueError as e:
        print(f"Error geocoding address: {e}")
        exit(1)

    venues = search_nearby_venues(
        location=(lat, lng),
        radius=2000,
        place_type='restaurant',
        keyword='event venue'
    )

    if len(venues) > 2:
        print("Third venue found:", venues[2]["name"])
    elif venues:
        print("First venue found:", venues[0]["name"])
    else:
        print("No venues found.")