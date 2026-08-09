from aiogram.fsm.state import State, StatesGroup


class AddCoffee(StatesGroup):
    coffee_name = State()
    coffee_size = State()
    coffee_shop = State()
    rating = State()
