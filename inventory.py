"""Player inventory: a hotbar of 5 slots (shown at the bottom of the screen, the mouse wheel picks
the block to build with) and a backpack of 20 slots (opened with I).

Pure Python, no pygame / OpenGL. A slot is ``None`` (empty) or a ``Stack`` (item id, count).
Slots 0..4 are the hotbar, 5..24 the backpack. Items are block ids (settings.SAND...).
"""
import json
from dataclasses import dataclass

HOTBAR_SIZE = 5
BACKPACK_SIZE = 20
SLOT_COUNT = HOTBAR_SIZE + BACKPACK_SIZE
STACK_MAX = 64


@dataclass
class Stack:
    item: int
    count: int


class Inventory:
    def __init__(self):
        self.slots = [None] * SLOT_COUNT
        self.selected = 0      # hotbar slot used to build
        self.held = None       # stack carried by the mouse in the backpack screen
        self.held_from = None  # slot it was taken from
        self.version = 0       # bumped on every change (the HUD redraws then)

    def changed(self):
        self.version += 1

    # ------------------------------------------------------------------ queries
    @staticmethod
    def is_hotbar(index):
        return 0 <= index < HOTBAR_SIZE

    def count(self, item):
        return sum(s.count for s in self.slots if s is not None and s.item == item)

    def selected_stack(self):
        return self.slots[self.selected]

    def selected_item(self):
        stack = self.slots[self.selected]
        return stack.item if stack is not None else None

    def can_add(self, item):
        return any(s is None or (s.item == item and s.count < STACK_MAX) for s in self.slots)

    # ------------------------------------------------------------------ changes
    def add(self, item, count=1):
        """Store ``count`` items: on the stacks of the same item first, then in empty slots
        (hotbar before backpack). Returns how many did not fit."""
        left = count
        for stack in self.slots:
            if left == 0:
                break
            if stack is not None and stack.item == item and stack.count < STACK_MAX:
                n = min(left, STACK_MAX - stack.count)
                stack.count += n
                left -= n
        for i, stack in enumerate(self.slots):
            if left == 0:
                break
            if stack is None:
                n = min(left, STACK_MAX)
                self.slots[i] = Stack(item, n)
                left -= n
        if left != count:
            self.changed()
        return left

    def take_selected(self):
        """Use one item of the selected hotbar slot (to build). Returns its id, or None if empty."""
        stack = self.slots[self.selected]
        if stack is None:
            return None
        stack.count -= 1
        if stack.count <= 0:
            self.slots[self.selected] = None
        self.changed()
        return stack.item

    def scroll(self, steps):
        """Move the hotbar selection (mouse wheel), wrapping around."""
        self.select((self.selected + steps) % HOTBAR_SIZE)

    def select(self, index):
        if 0 <= index < HOTBAR_SIZE and index != self.selected:
            self.selected = index
            self.changed()

    # ------------------------------------------------------------------ moving stacks
    def move(self, src, dst):
        """Put the stack of slot ``src`` in slot ``dst``: merged with the same item, else swapped."""
        if src == dst or self.slots[src] is None:
            return
        a, b = self.slots[src], self.slots[dst]
        if b is not None and b.item == a.item:
            n = min(a.count, STACK_MAX - b.count)
            b.count += n
            a.count -= n
            if a.count == 0:
                self.slots[src] = None
        else:
            self.slots[src], self.slots[dst] = b, a
        self.changed()

    def quick_move(self, index):
        """Send a stack to the other part (hotbar <-> backpack): merged, then in the first free slot."""
        stack = self.slots[index]
        if stack is None:
            return
        targets = range(HOTBAR_SIZE, SLOT_COUNT) if self.is_hotbar(index) else range(HOTBAR_SIZE)
        for i in targets:
            other = self.slots[i]
            if other is not None and other.item == stack.item and other.count < STACK_MAX:
                n = min(stack.count, STACK_MAX - other.count)
                other.count += n
                stack.count -= n
                if stack.count == 0:
                    break
        if stack.count > 0:
            for i in targets:
                if self.slots[i] is None:
                    self.slots[i] = stack
                    self.slots[index] = None
                    break
        if stack.count == 0:
            self.slots[index] = None
        self.changed()

    def click(self, index):
        """Backpack screen click on a slot: pick its stack up, or put the carried one down
        (merged with the same item, else swapped with what is there)."""
        if self.held is None:
            if self.slots[index] is not None:
                self.held, self.slots[index] = self.slots[index], None
                self.held_from = index
                self.changed()
            return
        here = self.slots[index]
        if here is None:
            self.slots[index], self.held = self.held, None
        elif here.item == self.held.item:
            n = min(self.held.count, STACK_MAX - here.count)
            here.count += n
            self.held.count -= n
            if self.held.count == 0:
                self.held = None
        else:
            self.slots[index], self.held = self.held, here
            self.held_from = index
        self.changed()

    def drop_held(self):
        """Closing the backpack screen: the carried stack goes back (its slot, else anywhere).
        Returns the items that did not fit (Stack) or None."""
        if self.held is None:
            return None
        held, self.held = self.held, None
        if self.held_from is not None and self.slots[self.held_from] is None:
            self.slots[self.held_from] = held
            self.changed()
            return None
        left = self.add(held.item, held.count)
        self.changed()
        return Stack(held.item, left) if left else None

    # ------------------------------------------------------------------ save
    def to_json(self):
        slots = [None if s is None else [s.item, s.count] for s in self.slots]
        return json.dumps({'slots': slots, 'selected': self.selected})

    @classmethod
    def from_json(cls, text):
        inv = cls()
        if not text:
            return inv
        try:
            data = json.loads(text)
            for i, s in enumerate(data.get('slots', [])[:SLOT_COUNT]):
                if s is not None and int(s[1]) > 0:
                    inv.slots[i] = Stack(int(s[0]), min(int(s[1]), STACK_MAX))
            inv.selected = int(data.get('selected', 0)) % HOTBAR_SIZE
        except (ValueError, TypeError, KeyError, IndexError):
            return cls()  # unreadable: start empty rather than crash
        return inv
