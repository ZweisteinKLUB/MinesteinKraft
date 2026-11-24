from pathlib import Path
from storage import WorldInfo
from menu import MenuModel, default_world_name, parse_seed


def worlds():
    return [WorldInfo(Path('a.db'), 'Monde 1', 1, 0, 200, 50),
            WorldInfo(Path('b.db'), 'Plage', 2, 0, 100, 60),
            WorldInfo(Path('c.db'), 'c', error='not a world database')]


def test_items_and_navigation():
    m = MenuModel(worlds())
    assert [i.kind for i in m.items] == ['world', 'world', 'broken', 'new', 'quit']
    assert m.activate() == ('open', m.items[0].info)
    m.move(-1)
    assert m.items[m.selected].kind == 'quit' and m.activate() == ('quit',)


def test_broken_world_shows_message_only():
    m = MenuModel(worlds())
    assert m.activate(2) is None and 'ne peut pas' in m.message


def test_new_world_form():
    m = MenuModel(worlds())
    assert m.activate(3) is None and m.mode == 'new'
    assert m.name == 'Monde 2'  # 'Monde 1' already exists
    for _ in range(len(m.name)):
        m.backspace()
    m.type_text('Île ')
    m.type_text('été')
    m.switch_field()
    m.type_text('42')
    assert m.submit() == ('create', 'Île été', 42)
    m.cancel()
    assert m.mode == 'list' and m.cancel() == ('quit',)


def test_empty_name_is_refused():
    m = MenuModel([])
    m.open_new_form()
    m.name = '   '
    assert m.submit() is None and m.message


def test_seed_parsing():
    assert parse_seed('123') == 123
    assert parse_seed('banane') == parse_seed('banane') != parse_seed('pomme')
    assert parse_seed('') != parse_seed('')  # random
    assert default_world_name(set()) == 'Monde 1'
