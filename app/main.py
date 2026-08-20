from app.core.app import Application


def main():
    app = Application()

    try:
        app.start()
        app.run()
    except KeyboardInterrupt:
        print("\nInterrupción recibida.")
    finally:
        app.stop()


if __name__ == "__main__":
    main()
