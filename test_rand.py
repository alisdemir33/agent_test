from random import randint

def get_temperature(city: str) -> int:
    """
    Get the current temperature for a given city.
    """
    print("Fetching temperature for:", city)
    rastgele_tam_sayi = randint(-10, 35)
    print("Generated temperature:", rastgele_tam_sayi)
    return rastgele_tam_sayi

def main():
    print("Hello from agents!")
    get_temperature("Ankara")

if __name__ == "__main__":
    main()
