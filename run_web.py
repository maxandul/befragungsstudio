"""Sichtbarer lokaler Start mit Diagnoseprotokoll; keine Paketinstallation."""
from __future__ import annotations

import argparse
import importlib
import sys
import threading
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path


class Tee:
    def __init__(self, terminal, log):
        self.terminal, self.log = terminal, log

    def write(self, text):
        self.terminal.write(text)
        self.log.write(text)
        self.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5051)
    parser.add_argument('--open-browser', action='store_true')
    args = parser.parse_args()
    print('Python wurde gestartet.', flush=True)
    print(f'Python-Version: {sys.version.split()[0]}', flush=True)
    root = Path(__file__).resolve().parent
    log = None
    original_stdout, original_stderr = sys.stdout, sys.stderr
    try:
        instance = root / 'instance'
        instance.mkdir(exist_ok=True)
        log = (instance / 'start.log').open('a', encoding='utf-8')
        sys.stdout, sys.stderr = Tee(original_stdout, log), Tee(original_stderr, log)
        print(f'\n--- Start {datetime.now().isoformat(timespec="seconds")} ---')
        print(f'Diagnoseprotokoll: {instance / "start.log"}')
        print('Der erste Start kann beim Laden der Pakete etwas dauern.')
        for index, name in enumerate(('flask', 'pandas', 'openpyxl', 'waitress'), 1):
            print(f'[{index}/6] Lade {name} ...')
            importlib.import_module(name)
        print('[5/6] Lade Anwendung und oeffne lokale Datenbank ...')
        from app import create_app
        app = create_app()
        print(f'[6/6] Belege lokalen Port {args.port} ...')
        from waitress import create_server
        server = create_server(app, host='127.0.0.1', port=args.port, threads=4)
        url = f'http://127.0.0.1:{server.effective_port}'
        print(f'\nBefragungsstudio ist bereit: {url}')
        print('Dieses Fenster offen lassen. Strg+C beendet die App.')
        if args.open_browser:
            def open_browser():
                try:
                    if not webbrowser.open(url):
                        print(f'Browser bitte manuell oeffnen: {url}')
                except Exception:
                    print(f'Browser bitte manuell oeffnen: {url}')
            threading.Thread(target=open_browser, daemon=True).start()
        try:
            server.run()
        finally:
            server.close()
        return 0
    except KeyboardInterrupt:
        print('\nBefragungsstudio wurde beendet.')
        return 0
    except ModuleNotFoundError as exc:
        print(f'\nFEHLER: Ein benoetigtes Python-Paket fehlt: {exc.name}')
        print('Bitte INSTALL.bat auf Fehler pruefen. Vorhandene Daten nicht loeschen.')
        traceback.print_exc()
        return 1
    except OSError as exc:
        print(f'\nFEHLER beim Zugriff auf Datei oder Port: {exc}')
        print('Pruefen Sie, ob die App bereits laeuft, der Port belegt oder der Ordner schreibgeschuetzt ist.')
        traceback.print_exc()
        return 1
    except Exception:
        print('\nFEHLER beim Start. Details:')
        traceback.print_exc()
        return 1
    finally:
        sys.stdout, sys.stderr = original_stdout, original_stderr
        if log:
            log.close()


if __name__ == '__main__':
    raise SystemExit(main())
