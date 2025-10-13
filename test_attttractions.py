from modules.attractions_api import fetch_attractions

city = input("Enter city: ").strip()
attractions = fetch_attractions(city)

print("\n🎯 Top Attractions:\n")
for i, a in enumerate(attractions, start=1):
    name = a.get("name", "Unknown")
    category = a.get("category", "N/A")
    rating = a.get("rating", "N/A")
    reviews = a.get("reviews", "N/A")
    print(f"{i}. {name} — {category} | ⭐ {rating} ({reviews} reviews)")
