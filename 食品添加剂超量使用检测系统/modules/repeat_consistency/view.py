from runtime import BasePage
from .logic import Engine

class Page(BasePage):
    def __init__(self, store, spec):
        super().__init__(store, spec, Engine())
