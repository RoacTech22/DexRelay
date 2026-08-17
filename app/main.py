from app.core.config import Config


def main():
    config = Config()

    print("================================")
    print("          DEXRELAY")
    print("================================")
    print()
    print("DexRelay iniciado correctamente.")
    print()
    print("Configuración:")
    print(f"  Azahar: {config.get('azahar', 'process_name')}")
    print(f"  HTTP: {config.get('server', 'host')}:{config.get('server', 'port')}")
    print(f"  Refresh: {config.get('realtime', 'refresh_ms')} ms")


if __name__ == "__main__":
    main()