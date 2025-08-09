from aos.runner import main


if __name__ == "__main__":
    config = ""
    with open("config.txt", "r+") as f:
        config = f.read()

    main(config)