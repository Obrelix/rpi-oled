import pytest

import config
from state import AppState, Mode, PAGE_COUNT


# ---------- Initial state ----------

def test_initial_state_is_page_mode_idx_0():
    s = AppState()
    assert s.mode == Mode.PAGE
    assert s.page_idx == 0
    assert s.needs_redraw is True


# ---------- PAGE mode navigation ----------

def test_rotate_cw_in_page_advances_with_wrap():
    s = AppState()
    for expected in [1, 2, 3, 4, 5, 0, 1]:
        s.on_rotate_cw()
        assert s.page_idx == expected
        assert s.mode == Mode.PAGE


def test_rotate_ccw_in_page_decrements_with_wrap():
    s = AppState()
    s.on_rotate_ccw()
    assert s.page_idx == PAGE_COUNT - 1


def test_short_press_in_page_jumps_to_home():
    s = AppState()
    s.page_idx = 3
    s.on_short_press()
    assert s.page_idx == 0
    assert s.mode == Mode.PAGE


def test_long_press_in_page_enters_menu():
    s = AppState()
    s.on_long_press()
    assert s.mode == Mode.MENU
    assert s.menu_idx == 0


# ---------- MENU mode ----------

def test_rotate_cw_in_menu_advances_menu_idx_with_wrap():
    s = AppState()
    s.on_long_press()  # → MENU
    for expected in [1, 2, 3, 0]:
        s.on_rotate_cw()
        assert s.menu_idx == expected
        assert s.mode == Mode.MENU


def test_rotate_ccw_in_menu_decrements():
    s = AppState()
    s.on_long_press()
    s.on_rotate_ccw()
    assert s.menu_idx == len(config.MENU_ITEMS) - 1


def test_short_press_on_cancel_returns_to_page():
    s = AppState()
    s.on_long_press()
    s.menu_idx = config.MENU_CANCEL_INDEX
    s.on_short_press()
    assert s.mode == Mode.PAGE


def test_short_press_on_action_item_enters_confirm():
    s = AppState()
    s.on_long_press()
    s.menu_idx = 0  # restart active LED
    s.on_short_press()
    assert s.mode == Mode.CONFIRM
    assert s.confirm_idx == 0


def test_long_press_in_menu_returns_to_page():
    s = AppState()
    s.on_long_press()  # → MENU
    s.on_long_press()  # → PAGE
    assert s.mode == Mode.PAGE


# ---------- CONFIRM mode ----------

def test_rotate_in_confirm_returns_to_menu():
    s = AppState()
    s.on_long_press()
    s.on_short_press()  # enter confirm on item 0
    s.on_rotate_cw()
    assert s.mode == Mode.MENU


def test_short_press_in_confirm_returns_execute_signal():
    s = AppState()
    s.on_long_press()
    s.on_short_press()
    result = s.on_short_press()
    assert result == "execute"
    # after execute, state resets to PAGE
    assert s.mode == Mode.PAGE


def test_long_press_in_confirm_returns_to_menu():
    s = AppState()
    s.on_long_press()   # PAGE → MENU
    s.on_short_press()  # MENU → CONFIRM (item 0)
    s.on_long_press()   # CONFIRM → MENU
    assert s.mode == Mode.MENU


# ---------- Idle / dim / blank ----------

def test_idle_under_threshold_is_full_contrast():
    s = AppState()
    s.tick(config.DIM_THRESHOLD_SEC - 1)
    assert s.display_state == "full"


def test_idle_over_dim_threshold_is_dimmed():
    s = AppState()
    s.tick(config.DIM_THRESHOLD_SEC + 1)
    assert s.display_state == "dim"


def test_idle_over_blank_threshold_is_blank():
    s = AppState()
    s.tick(config.BLANK_THRESHOLD_SEC + 1)
    assert s.display_state == "blank"


def test_any_event_resets_idle():
    s = AppState()
    s.tick(config.BLANK_THRESHOLD_SEC + 1)
    assert s.display_state == "blank"
    s.on_rotate_cw()
    assert s.display_state == "full"


def test_event_while_blanked_only_wakes_not_acts():
    s = AppState()
    s.tick(config.BLANK_THRESHOLD_SEC + 1)  # blanked
    assert s.page_idx == 0
    s.on_rotate_cw()  # wake event; should NOT advance page
    assert s.page_idx == 0
    assert s.display_state == "full"
    # next rotate now advances normally
    s.on_rotate_cw()
    assert s.page_idx == 1


def test_needs_redraw_flag_sets_on_event_and_clears_on_mark_drawn():
    s = AppState()
    s.mark_drawn()
    assert s.needs_redraw is False
    s.on_rotate_cw()
    assert s.needs_redraw is True


# ---------- Pixel shift ----------

def test_pixel_shift_offset_cycles_every_interval():
    s = AppState()
    assert s.pixel_shift_offset == (0, 0)
    s.tick(config.PIXEL_SHIFT_INTERVAL_SEC + 0.1)
    assert s.pixel_shift_offset == (1, 0)
    s.tick(config.PIXEL_SHIFT_INTERVAL_SEC + 0.1)
    assert s.pixel_shift_offset == (1, 1)
    s.tick(config.PIXEL_SHIFT_INTERVAL_SEC + 0.1)
    assert s.pixel_shift_offset == (0, 1)
    s.tick(config.PIXEL_SHIFT_INTERVAL_SEC + 0.1)
    assert s.pixel_shift_offset == (0, 0)  # wraps
