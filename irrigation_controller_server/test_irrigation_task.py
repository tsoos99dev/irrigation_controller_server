from tasks import irrigate


def main():
    result = irrigate.delay(zones=[{"name": "front", "duration": "PT10S"}])
    result.get()


if __name__ == "__main__":
    main()
