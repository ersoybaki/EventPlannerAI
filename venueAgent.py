from dotenv import load_dotenv
import os
import googlemaps

gmaps = googlemaps.Client(key="AIzaSyAoENP6GT2FNZVo61yLam6FfznnCLnI-Ak")

class VenueAgent:
    def __init__(self, client=googlemaps.Client):
        self.client = client
    
    def geocode_address(self, address: str) -> tuple:
        """
        Convert a free-form address into geographic coordinates (latitude and longitude).

        Parameters:
        ---------------
        address (str):
            The address or place name to geocode (e.g., "1600 Amphitheatre Parkway, Mountain View, CA").

        Returns:
        ---------------
        tuple:
            A (latitude, longitude) pair as floats representing the geocoded location.

        Raises:
        ---------------
        ValueError:
            If the provided address cannot be found or geocoded.
        """
        geocode_result = self.client.geocode(address)
        if geocode_result:
            loc = geocode_result[0]['geometry']['location']
            return loc['lat'], loc['lng']
        else:
            raise ValueError("Address not found.")
        

    def search_nearby_venues(self, location: tuple, radius: str = 5000, place_type: str = None, keyword: str = None) -> list:
        """
        Retrieve a list of nearby venues matching the specified criteria.

        Parameters:
        ---------------
        location (tuple):
            A (latitude, longitude) tuple indicating the search center.
        radius (int, optional):
            Search radius in meters. Defaults to 5000 (5 kilometers).
        place_type (str, optional):
            A Google Places API type filter (e.g., "cafe", "restaurant").
        keyword (str, optional):
            A term to match against venue names or attributes (e.g., "pet-friendly").

        Returns:
        ---------------
        list:
            A list of place result dictionaries, each containing details
            such as name, location, rating, and place_id.
        """
        places_result = self.client.places_nearby(
            location=location,
            radius=radius,
            type=place_type,
            keyword=keyword,
            min_price=0,
        )
        return places_result.get('results', [])
    

venue_agent = VenueAgent(gmaps)    

user_loc = "Eindhoven, Netherlands"
lat, lng = venue_agent.geocode_address(user_loc)

venues = venue_agent.search_nearby_venues(
    location=(lat, lng),
    radius=2000,  # 2 km radius
    place_type='restaurant',  # Example place type
    keyword='event venue'  # Example keyword
)

print(venues[2]["name"])  # Print the name of the first venue found