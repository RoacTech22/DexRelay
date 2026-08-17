import ctypes
from ctypes import wintypes

from app.core.config import Config


# Permisos necesarios para consultar y leer el proceso.
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

PROCESS_ACCESS = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ


# Kernel32 de Windows.
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class ProcessEntry32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]


def find_process(process_name):
    """
    Busca un proceso por nombre y devuelve su PID.

    Devuelve:
        int: PID del proceso encontrado.
        None: si no se encuentra.
    """

    snapshot = kernel32.CreateToolhelp32Snapshot(
        0x00000002,
        0
    )

    if snapshot == -1:
        raise ctypes.WinError(ctypes.get_last_error())

    entry = ProcessEntry32()
    entry.dwSize = ctypes.sizeof(ProcessEntry32)

    try:
        success = kernel32.Process32First(
            snapshot,
            ctypes.byref(entry)
        )

        while success:
            name = entry.szExeFile.decode(
                "utf-8",
                errors="ignore"
            )

            if name.lower() == process_name.lower():
                return entry.th32ProcessID

            success = kernel32.Process32Next(
                snapshot,
                ctypes.byref(entry)
            )

    finally:
        kernel32.CloseHandle(snapshot)

    return None


def open_process(pid):
    """
    Abre un proceso con permisos para consultar
    información y leer memoria.

    Devuelve:
        HANDLE del proceso.

    Lanza:
        OSError si Windows no permite abrir el proceso.
    """

    handle = kernel32.OpenProcess(
        PROCESS_ACCESS,
        False,
        pid
    )

    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())

    return handle


def main():
    config = Config()

    process_name = config.get(
        "azahar",
        "process_name"
    )

    print("================================")
    print("     DEXRELAY PROCESS PROBE")
    print("================================")
    print()

    print(f"Buscando proceso: {process_name}")

    pid = find_process(process_name)

    if pid is None:
        print("Azahar no encontrado.")
        return

    print("Azahar encontrado.")
    print(f"PID: {pid}")

    try:
        handle = open_process(pid)

        print(f"Handle obtenido: {handle}")

    except OSError as error:
        print("No se pudo abrir el proceso.")
        print(f"Error de Windows: {error}")
        return

    finally:
        if "handle" in locals() and handle:
            kernel32.CloseHandle(handle)
            print("Handle cerrado correctamente.")


if __name__ == "__main__":
    main()
