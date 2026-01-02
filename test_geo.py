from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

def test_geo(city):
    print(f"Testing Geolocation for: {city}")
    try:
        geolocator = Nominatim(user_agent="cloudinha_test_script")
        location = geolocator.geocode(city + ", Brasil")
        if location:
            print(f"Success! {city}: {location.latitude}, {location.longitude}")
        else:
            print(f"Failed: Location not found for {city}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_geo("São Paulo")
    test_geo("Manaus")
