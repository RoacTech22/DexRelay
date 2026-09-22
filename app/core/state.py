class ApplicationState:
    """
    Estado compartido en vivo, leido por el hilo de fondo de
    Runtime (que lo escribe) y por los hilos de
    ThreadingHTTPServer/pywebview (que solo lo leen) sin ningun
    lock.

    Bloque 1.3 (22/09/2026, guia siguiente version -- documenta la
    invariante implicita que ya sostenia esto, no cambia
    comportamiento): esto es seguro SOLO si cada atributo se
    REASIGNA por completo (self.state.team = nueva_lista,
    self.state.nuzlocke = nuevo_dict) y nunca se MUTA in-place
    (nada de self.state.team.append(...) o
    self.state.nuzlocke["roster"].append(...)). Una reasignacion es
    atomica a nivel de bytecode de Python (un solo STORE_ATTR): un
    lector de otro hilo siempre ve el objeto viejo completo o el
    nuevo completo, nunca un estado a medio construir. Una mutacion
    in-place no tiene esa garantia -- un lector podria ver una lista
    o un dict a medio modificar. Si se agrega un atributo nuevo,
    mantener el mismo patron: quien lo actualiza arma el valor
    completo aparte y recien al final lo asigna entero.
    """

    def __init__(self):
        self.azahar_connected = False
        self.reader_active = False
        self.team = []
        self.badges = []
        self.combat_active = False
        self.combat_hp = None
        self.nuzlocke = {
            "roster": [],
            "graveyard": [],
        }
